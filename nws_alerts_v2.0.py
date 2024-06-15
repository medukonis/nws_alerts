#==================================================================
#NWS_Alerts
#Testing Updated V1.3.1 12/26/22 added test. If not weather alerts, then exit.
#Updated V1.3 4/6/2022  added mysql connectioon and storage
#Updated v1.2 3/31/2022 added json file output on each run.
#Updated v1.1 8/23/2020 added state codes to listings on html.
#Fixed an occassional array out of bounds error for polygon coordinates.
#
#Version: 1.0
#Author: Mike Edukonis
#Date: 8/25/19
#Description: Reads in NWS xml data, grabbing alerts with "Urgent"
#designation.  Isolates certain fields such as text, polygon
#coordinates and link to NWS page for that alert to get more info
#writes out an html file for human use and a kml file for google
#earth visualization.
#USE: run manually or as a cron job.  If automating, keep updates
#at 15 minutes or more.  Don't abuse NWS bandwidth.

#2/11/2024
#moved the add to database block to take place before file writing
#error in file write crashed script and lost the data.
#Change in NWS XML format/schema caused script to stop working correctly
#NWS decommisioned v1.1 CAP/ATOM and changed to v1.2

#5/26/2024
#V2.0 of script
#revamp entire script to utilize xml.etree.ElementTree for proper
#xml parsing. Added logging, mysql storage supports POLYGON and
#JSON data types updated data types in script to utilize.

#TODO - add event to database DONE 5/27/24
'''
mysql table, alerts2 compatible with this script
+-------------+----------+------+-----+---------+----------------+
| Field       | Type     | Null | Key | Default | Extra          |
+-------------+----------+------+-----+---------+----------------+
| id          | int      | NO   | PRI | NULL    | auto_increment |
| date        | datetime | YES  |     | NULL    |                |
| event       | text     | YES  |     | NULL    |                |
| title       | text     | YES  |     | NULL    |                |
| link        | text     | YES  |     | NULL    |                |
| summary     | text     | YES  |     | NULL    |                |
| areas       | JSON     | YES  |     | NULL    |                |
| coordinates | POLYGON  | YES  |     | NULL    |                |
+-------------+----------+------+-----+---------+----------------+
'''
#==================================================================

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import logging
import pymysql
import json

# Add a global variable to hold the update time
update_time = ""

#===================================================================
#file names - change to suit your needs
#===================================================================
logfilename = "nws_alerts.log"
kmlfilename = "nws_alerts.kml"
jsonfilename = "nws_alerts.json"
htmlfilename = "nws_alerts.html"
# URL of the file on the server
#url = 'https://edukonis.com/~medukonis/active.atom' #for testing
url = 'https://alerts.weather.gov/cap/us.php?x=0'


logging.basicConfig(filename=logfilename, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("/////////////////////////////////////////////////////////////////////////////////////")

#===================================================================
#Database connection
#===================================================================
db_config = {
    'user':     '',
    'password': '',
    'host':     'localhost',
    'database': 'weather_alerts_2024'
}

#===================================================================
#lists
#===================================================================
immediate_entries = []
events = []
titles = []
links = []
summaries = []
published_dates = []
affected_areas_list = []
polygons = []

# List of all lists to be checked for same size
lists = {
    "immediate_entries": immediate_entries,
    "events": events,
    "titles": titles,
    "links": links,
    "summaries": summaries,
    "published_dates": published_dates,
    "affected_areas_list": affected_areas_list,
    "polygons": polygons,
}

#dictionary to hold the data for JSON output
json_data = {
    "alerts": []
}


#===================================================================
#functions
#===================================================================
def find_immediate_urgency_entries(url):
    global update_time  # Ensure update_time is the global variable
    response = requests.get(url)
    if response.status_code != 200:
        #print("Failed to fetch the file from the server.")
        logging.info("Failed to fetch the file from the server.")
        return []

    xml_data = response.content
    #print("XML data fetched successfully.")
    logging.info("XML data fetched successfully.")

    namespaces = {'default': 'http://www.w3.org/2005/Atom', 'cap': 'urn:oasis:names:tc:emergency:cap:1.2'}
    ET.register_namespace('', namespaces['default'])
    ET.register_namespace('cap', namespaces['cap'])

    try:
        root = ET.fromstring(xml_data)
        #print("XML data parsed successfully.")
        logging.info("XML data parsed successfully.")
    except ET.ParseError as e:
        #print(f"ParseError: {e}")
        logging.info(f"ParseError: {e}")
        return []

    # Capture the <updated> tag's value
    updated_element = root.find('default:updated', namespaces)
    if updated_element is not None:
        update_time = updated_element.text
        #print(update_time) #debug

    for entry in root.findall('default:entry', namespaces):
        urgency_element = entry.find('cap:urgency', namespaces)
        if urgency_element is not None and urgency_element.text == 'Immediate':
            immediate_entries.append(entry)
            title_element = entry.find('default:title', namespaces)
            if title_element is not None:
                title_text = ' '.join(title_element.text.split())
                titles.append(title_text)
            link_element = entry.find('default:id', namespaces)
            if link_element is not None:
                link_text = ' '.join(link_element.text.split())
                links.append(link_text)
            summary_element = entry.find('default:summary', namespaces)
            if summary_element is not None:
                summary = ' '.join(summary_element.text.split())
                summaries.append(summary)
            published_element = entry.find('default:published', namespaces)
            if published_element is not None:
                published_date = datetime.strptime(published_element.text, "%Y-%m-%dT%H:%M:%S%z")
                published_date_sql = published_date.strftime("%Y-%m-%d %H:%M:%S")
                published_dates.append(published_date_sql)
            area_desc_element = entry.find('cap:areaDesc', namespaces)
            if area_desc_element is not None:
                affected_areas = area_desc_element.text.split('; ')
                for i in range(len(affected_areas)):
                    affected_areas[i] = affected_areas[i].replace(', ', ':') #change csv to key:value pair for county:state
                affected_areas_list.append(affected_areas)
            event_element = entry.find('cap:event', namespaces)
            if event_element is not None:
                txtevent = event_element.text.split('; ')
                events.append(txtevent)
            polygon = entry.find('cap:polygon', namespaces)
            if polygon is not None:
                points = polygon.text.strip().split(' ')
                points = [tuple(map(float, point.split(','))) for point in points]
                mysql_polygon = 'POLYGON((' + ','.join([f'{lat} {lon}' for lon, lat in points]) + '))'
                polygons.append(mysql_polygon)


# Function to check if all lists have the same length
def check_equal_lengths(lists):
    lengths = {name: len(lst) for name, lst in lists.items()}
    for name, length in lengths.items():
        #print(f"{name}: {length}")
        logging.info(f"{name}: {length}")
    return len(set(lengths.values())) == 1

# Function to convert a polygon string to KML format with additional info
def polygon_to_kml(polygon, event, title, link, summary, published_date, affected_area):
    # Remove the 'POLYGON((' prefix and '))' suffix
    coordinates = polygon[len("POLYGON(("):-2]
    
    # Replace spaces with commas and convert to KML coordinate format
    kml_coords = " ".join([f"{lon},{lat},0" for lon, lat in [coord.split() for coord in coordinates.split(',')]])
    
    return f"""
    <Placemark>
        <name>{title}</name>
        <description><![CDATA[
            <a href="{link}">{title}</a><br/>
            <b>Event:</b> {event}<br/>
            <b>Summary:</b> {summary}<br/>
            <b>Published Date:</b> {published_date}<br/>
            <b>Affected Area:</b> {affected_area}<br/>
        ]]></description>
        <Style>
            <PolyStyle>
                <color>#a00000ff</color> <!-- Semi-transparent red -->
                <outline>1</outline>
            </PolyStyle>
        </Style>
        <Polygon>
            <outerBoundaryIs>
                <LinearRing>
                    <coordinates>
                        {kml_coords}
                    </coordinates>
                </LinearRing>
            </outerBoundaryIs>
        </Polygon>
    </Placemark>
    """

# Function to generate KML file with polygons and pertinent info
def generate_kml(polygons, events, titles, links, summaries, published_dates, affected_areas_list):
    placemarks = ''.join(
        polygon_to_kml(polygons[i], events[i], titles[i], links[i], summaries[i], published_dates[i], affected_areas_list[i])
        for i in range(len(polygons))
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>Polygons</name>
    {placemarks}
</Document>
</kml>
"""

# Function to insert data into the alerts2 table
def insert_data(date, event, title, link, summary, areas, coordinates):
    insert_query = """
    INSERT INTO alerts2 (date, event, title, link, summary, areas, coordinates)
    VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText(%s))
    """
    areas_json = json.dumps(areas)  # Convert areas list to JSON string
    try:
        cursor.execute(insert_query, (date, event, title, link, summary, areas_json, coordinates))
        conn.commit()
    except pymysql.MySQLError as e:
        logging.error(f"Error inserting data: {e}")

# Function to generate HTML file
def generate_html(titles, links, affected_areas_list, published_dates, update_time):
    #print(update_time)
    # Combine all the data into a list of tuples
    combined_data = list(zip(published_dates, titles, links, affected_areas_list))
    # Sort the combined data by the published date
    combined_data.sort()

    # Parse the ISO 8601 formatted update_time string
    update_time_obj = datetime.strptime(update_time[:-6], "%Y-%m-%dT%H:%M:%S")  # Remove the timezone offset for parsing
    # Convert the update_time to a more readable format
    formatted_update_time = update_time_obj.strftime("%B %d, %Y %I:%M %p")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Alerts</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        <style>
            body {{
                background-color: black;
                color: white;
            }}
            .table-container {{
                max-height: 80vh;
                overflow-y: scroll;
            }}
            .table {{
                background-color: #333;
                color: white;
            }}
            .table th, .table td {{
                border-color: #444;
            }}
            .table a {{
                color: #1e90ff;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Current Weather Alerts</h1>
            <p>Information last updated: {formatted_update_time} UTC</p>
            <div class="table-container">
                <table class="table table-bordered">
                    <thead>
                        <tr>
                            <th>Published Date</th>
                            <th>Title</th>
                            <th>County:State</th>
                            <th>Link</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    for date, title, link, areas in combined_data:
        areas_text = ', '.join(areas)
        html_content += f"""
            <tr>
                <td>{date}</td>
                <td>{title}</td>
                <td>{areas_text}</td>
                <td><a href="{link}" target="_blank">Link</a></td>
            </tr>
        """

    html_content += """
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content




#===================================================================
#main program
#===================================================================
 
find_immediate_urgency_entries(url)

#print(f"Number of immediate entries found: {len(immediate_entries)}")
logging.info(f"Number of immediate entries found: {len(immediate_entries)}")

#DEBUG
#for poly in polygons:
#    print(poly)
#    #print('\n')

# Check length of lists after finding entries.  They should all be the same length.  
if check_equal_lengths(lists):
    #print("All lists have the same length.")
    logging.info("All lists have the same length.")
else:
    #print("Lists have different lengths.")
    logging.error("Lists have different lengths.")

# Generate the KML file for google earth
kml_content = generate_kml(polygons, events, titles, links, summaries, published_dates, affected_areas_list)

# Write the KML content to a file
with open(kmlfilename, "w") as file:
    file.write(kml_content)
#print("KML file created successfully.")
logging.info("KML file created successfully.")

# Connect to the database
conn = pymysql.connect(
    user=db_config['user'],
    password=db_config['password'],
    host=db_config['host'],
    database=db_config['database']
)
cursor = conn.cursor()

# Loop through the data and insert into the database
for i in range(len(polygons)):
    insert_data(published_dates[i], events[i], titles[i], links[i], summaries[i], affected_areas_list[i], polygons[i])

# Close the database connection and log
cursor.close()
conn.close()
logging.info("Data inserted successfully into the alerts2 table.")

#Generate JSON file
for i in range(len(polygons)):
    alert_data = {
        "date": published_dates[i],
        "event": events[i],
        "title": titles[i],
        "link": links[i],
        "summary": summaries[i],
        "areas": affected_areas_list[i],
        "coordinates": polygons[i]
    }
    json_data["alerts"].append(alert_data)

# Write the JSON data to a file
json_filename = "nws_alerts.json"
with open(json_filename, "w") as json_file:
    json.dump(json_data, json_file, indent=4)

logging.info(f"JSON data written to {json_filename} successfully.")

# Generate and write the HTML file
html_content = generate_html(titles, links, affected_areas_list, published_dates, update_time)
with open(htmlfilename, 'w') as f:
    f.write(html_content)
logging.info(f"HTML file '{htmlfilename}' generated successfully.")

logging.info("/////////////////////////////////////////////////////////////////////////////////////\n")
