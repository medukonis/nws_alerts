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

#5/27/24
#add event to database DONE 5/27/24
'''
mysql table, alerts2 compatible with this script
| Field       | Type     | Null | Key | Default | Extra          |
|-------------|----------|------|-----|---------|----------------|
| id          | int      | NO   | PRI | NULL    | auto_increment |
| date        | datetime | YES  |     | NULL    |                |
| event       | text     | YES  |     | NULL    |                |
| title       | text     | YES  |     | NULL    |                |
| link        | text     | YES  |     | NULL    |                |
| summary     | text     | YES  |     | NULL    |                |
| areas       | json     | YES  |     | NULL    |                |
| coordinates | polygon  | YES  |     | NULL    |                |

CREATE TABLE weather_alerts (
    id INT NOT NULL AUTO_INCREMENT,
    date DATETIME,
    event TEXT,
    title TEXT,
    link TEXT,
    summary TEXT,
    areas JSON,
    coordinates POLYGON,
    PRIMARY KEY (id)
);
'''
#6/15/2024
#added search, sort, and paging options from DataTables and jquery to generate_html
#function
#TODO install these localy
#TODO add links for kml, json files.
#DONE - clarify updated date/time to show date/time script was run and date/time nws
#updated their info. DONE 6/17 added map to main page
#TODO look at changing published dates to UTC or EASTERN?  Right now they are local
#6/17/2024
#Added map to main page - still have option for kml but google no longer required.
#6/19/2024
#DONE - updated different polygon colors based on event (generate_html function)
#BUG - tropical storm warnings for TX appearing up in MN.  Log indicates:
# 2024-06-19 12:45:02,354 - ERROR - Lists have different lengths.
#7/7/2024
#Fixed misaligned data when a polygon is not provided for a weather event
#7/8/2024
#TODO Hurricane Beryl hit TX and many counties were under multiple types of watches/warnings
#You can only click on and view the top layer.  Need a way to turn off layers so you can
#click on the ones underneath.
#==================================================================

#12/21/2025
#!/usr/bin/env python3
#==================================================================
# NWS Update to data feed
#
# V3.0 (JSON API)
# - Migrated from CAP/ATOM XML feed to the NWS JSON/JSON-LD Alerts API:
#     https://api.weather.gov/alerts/active?urgency=Immediate
# - Keeps the same outputs/behavior as your v2.0 script:
#     * logs to nws_alerts.log
#     * writes nws_alerts.kml, nws_alerts.json, nws_alerts.html
#     * inserts rows into MySQL table (alerts2 / weather_alerts schema-compatible)
#
# Notes:
# - NWS requires a User-Agent header that identifies your application.
# - Geometry in the API is GeoJSON:
#     * Polygon / MultiPolygon (coordinates are [lon, lat])
# - Your MySQL column is POLYGON, so for MultiPolygon we store the FIRST polygon's outer ring.
#   (If we want true MultiPolygon storage, we'd need a schema change to MULTIPOLYGON.)
#==================================================================

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
import pymysql

#===================================================================
# file names - change to suit your needs
#===================================================================
logfilename = "nws_alerts.log"
kmlfilename = "nws_alerts.kml"
jsonfilename = "nws_alerts.json"
htmlfilename = "nws_alerts.html"

# NWS JSON API endpoint (Immediate urgency alerts)
API_URL = "https://api.weather.gov/alerts/active?urgency=Immediate"

# IMPORTANT: NWS requires a User-Agent header.
# Use something stable and unique; include an email or website if you can.
USER_AGENT = os.getenv("NWS_USER_AGENT", "edukonis.com (medukonis@yahoo.com)")

# If you run as a cron job, NWS recommends <= 1 request per 30 seconds.
# (Your old script advice was 15 minutes; that's still fine.)
MIN_SECONDS_BETWEEN_CALLS = 30

# Add a global variable to hold the update time (for the HTML page)
update_time = ""  # ISO string

logging.basicConfig(
    filename=logfilename,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logging.info("/////////////////////////////////////////////////////////////////////////////////////")

#TODO make get database credentials out of here
#===================================================================
# Database connection
#
# Recommended: set these via environment variables so your password
# isn't stored in the script:
#   export NWS_DB_USER=...
#   export NWS_DB_PASSWORD=...
#   export NWS_DB_HOST=...
#   export NWS_DB_NAME=...
#
# Falls back to your prior defaults if env vars are not set.
#===================================================================


#DB_TABLE = os.getenv("NWS_DB_TABLE", "alerts2")
#db_config = {
#    "user": os.getenv("NWS_DB_USER", "medukonis"),
#    "password": os.getenv("NWS_DB_PASSWORD", "CHANGE_ME"),
#    "host": os.getenv("NWS_DB_HOST", "localhost"),
#    "database": os.getenv("NWS_DB_NAME", "weather_alerts_2025"),
#}

#===================================================================
#Database connection
#===================================================================
db_config = {
    'user':     'YOUR_USERNAME',
    'password': 'YOUR_PASSWORD',
    'host':     'localhost',
    'database': 'weather_alerts_2025'
}

DB_TABLE = 'alerts2'

#===================================================================
# in-memory lists
#===================================================================
immediate_features: List[Dict[str, Any]] = []
events: List[str] = []
titles: List[str] = []
links: List[str] = []
summaries: List[str] = []
published_dates: List[str] = []
affected_areas_list: List[List[str]] = []
polygons: List[Optional[str]] = []  # MySQL WKT: 'POLYGON((lon lat, ...))'

lists = {
    "immediate_features": immediate_features,
    "events": events,
    "titles": titles,
    "links": links,
    "summaries": summaries,
    "published_dates": published_dates,
    "affected_areas_list": affected_areas_list,
    "polygons": polygons,
}

json_data: Dict[str, Any] = {"alerts": []}


#===================================================================
# helpers
#===================================================================
def _iso_to_sql_dt(iso_str: Optional[str]) -> Optional[str]:
    """Convert ISO 8601 time to 'YYYY-mm-dd HH:MM:SS' in local timezone offset preserved as naive string.
    Returns None if iso_str missing.
    """
    if not iso_str:
        return None
    try:
        # Handles Z or offset, and fractional seconds
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logging.warning(f"Could not parse datetime '{iso_str}': {e}")
        return None


def _clean_whitespace(s: Optional[str]) -> str:
    return " ".join(s.split()) if s else ""


def _areas_from_areaDesc(area_desc: str) -> List[str]:
    """Match your old output: list of 'County:State' items."""
    if not area_desc:
        return []
    parts = [p.strip() for p in area_desc.split(";") if p.strip()]
    # Convert "County, ST" -> "County:ST"
    out = []
    for p in parts:
        out.append(p.replace(", ", ":"))
    return out


def geojson_geometry_to_mysql_polygon(geom: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Convert GeoJSON geometry to a MySQL POLYGON WKT string.

    - If geometry is Polygon: use outer ring (coordinates[0])
    - If geometry is MultiPolygon: use first polygon's outer ring (coordinates[0][0])
    - Coordinates are [lon, lat]
    - Ensure ring is closed (first == last)
    """
    if not geom or not isinstance(geom, dict):
        return None

    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None

    ring: Optional[List[List[float]]] = None

    try:
        if gtype == "Polygon":
            ring = coords[0]
        elif gtype == "MultiPolygon":
            ring = coords[0][0]
        else:
            # Point/LineString/etc. can't be stored in POLYGON column as-is
            logging.info(f"Unsupported geometry type for POLYGON storage: {gtype}")
            return None

        # ring is list of [lon, lat]
        if not ring or len(ring) < 3:
            return None

        # Close ring if necessary
        if ring[0] != ring[-1]:
            ring = ring + [ring[0]]

        # Build WKT: POLYGON((lon lat, lon lat, ...))
        # MySQL expects: X Y => lon lat
        pairs = []
        for pt in ring:
            lon, lat = float(pt[0]), float(pt[1])
            pairs.append(f"{lon} {lat}")
        return "POLYGON((" + ",".join(pairs) + "))"
    except Exception as e:
        logging.error(f"Failed converting geometry to polygon: {e}")
        return None


def check_equal_lengths(lists_dict: Dict[str, List[Any]]) -> bool:
    lengths = {name: len(lst) for name, lst in lists_dict.items()}
    for name, length in lengths.items():
        logging.info(f"{name}: {length}")
    return len(set(lengths.values())) == 1


#===================================================================
# KML
#===================================================================
def polygon_to_kml(
    polygon_wkt: str,
    event: str,
    title: str,
    link: str,
    summary: str,
    published_date: str,
    affected_area: List[str],
) -> str:
    # Remove 'POLYGON((' prefix and '))' suffix
    coords = polygon_wkt[len("POLYGON((") : -2]

    # coords string is "lon lat,lon lat,..."
    coord_pairs = []
    for coord in coords.split(","):
        parts = coord.strip().split()
        if len(parts) != 2:
            continue
        lon, lat = parts[0], parts[1]
        coord_pairs.append(f"{lon},{lat},0")

    kml_coords = " ".join(coord_pairs)

    area_text = ", ".join(affected_area)

    return f"""
    <Placemark>
        <name>{title}</name>
        <description><![CDATA[
            <a href="{link}">{title}</a><br/>
            <b>Event:</b> {event}<br/>
            <b>Summary:</b> {summary}<br/>
            <b>Published Date:</b> {published_date}<br/>
            <b>Affected Area:</b> {area_text}<br/>
        ]]></description>
        <Style>
            <PolyStyle>
                <color>#a00000ff</color>
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


def generate_kml(
    polygons_list: List[Optional[str]],
    events_list: List[str],
    titles_list: List[str],
    links_list: List[str],
    summaries_list: List[str],
    published_dates_list: List[str],
    areas_list: List[List[str]],
) -> str:
    placemarks = ""
    for i in range(len(polygons_list)):
        if polygons_list[i] is None:
            continue
        placemarks += polygon_to_kml(
            polygons_list[i],
            events_list[i],
            titles_list[i],
            links_list[i],
            summaries_list[i],
            published_dates_list[i],
            areas_list[i],
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>Polygons</name>
    {placemarks}
</Document>
</kml>
"""


#===================================================================
# HTML
#===================================================================
def generate_html(titles_list, links_list, areas_list, published_dates_list, update_time_iso: str) -> str:
    import pytz

    eastern = pytz.timezone("US/Eastern")

    # NWS "updated" isn't guaranteed in every response. If missing, fall back to "now".
    try:
        if update_time_iso:
            ut = datetime.fromisoformat(update_time_iso.replace("Z", "+00:00"))
        else:
            ut = datetime.now(timezone.utc)
        update_time_eastern = ut.astimezone(eastern)
        formatted_update_time = update_time_eastern.strftime("%B %d, %Y %I:%M %p %Z")
    except Exception:
        formatted_update_time = "Unknown"

    now = datetime.now(eastern)
    formatted_now = now.strftime("%B %d, %Y %I:%M %p %Z")

    combined_data = list(zip(published_dates_list, titles_list, links_list, areas_list))

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Weather Alerts</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
        <link rel="stylesheet" href="https://cdn.datatables.net/1.10.25/css/dataTables.bootstrap4.min.css">
        <style>
        body {{
            background-color: black;
            color: white;
        }}
        /* Make DataTables controls readable on dark background */
        .dataTables_wrapper .dataTables_length label,
        .dataTables_wrapper .dataTables_filter label,
        .dataTables_wrapper .dataTables_info,
        .dataTables_wrapper .dataTables_paginate {{
            color: white;
        }}
        .dataTables_wrapper .dataTables_filter input,
        .dataTables_wrapper .dataTables_length select {{
            color: black;
            background-color: white;
        }}
        .dataTables_wrapper .page-item .page-link {{
            color: white;
            background-color: #222;
            border-color: #444;
        }}
        .dataTables_wrapper .page-item.active .page-link {{
            background-color: #555;
            border-color: #777;
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
        #mapTable td {{
            padding: 0;
        }}
        #map {{
            height: 500px;
        }}
    </style>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-omnivore@0.3.3/leaflet-omnivore.min.js"></script>
    <script src="https://unpkg.com/esri-leaflet@2.5.3/dist/esri-leaflet.js"></script>
    <script>
        function initMap() {{
            var map = L.map('map').setView([37.7749, -122.4194], 4);
            L.esri.basemapLayer('Streets').addTo(map);

            var kmlLayer = omnivore.kml('{kmlfilename}')
                .on('ready', function() {{
                    try {{
                        map.fitBounds(kmlLayer.getBounds());
                    }} catch (e) {{
                        // If no polygons exist, bounds may fail; leave default view.
                    }}
                }})
                .on('layeradd', function(e) {{
                    var layer = e.layer;
                    if (layer.feature && layer.feature.properties && layer.feature.properties.description) {{
                        var description = layer.feature.properties.description;
                        layer.bindPopup(description);

                        if (description.includes('Tropical Storm')) {{
                            layer.setStyle({{ color: 'green', fillColor: 'green', fillOpacity: 0.5 }});
                        }} else if (description.includes('Hurricane')) {{
                            layer.setStyle({{ color: 'magenta', fillColor: 'magenta', fillOpacity: 0.5 }});
                        }} else if (description.includes('Severe Thunderstorm')) {{
                            layer.setStyle({{ color: 'orange', fillColor: 'orange', fillOpacity: 0.5 }});
                        }} else if (description.includes('Flood')) {{
                            layer.setStyle({{ color: 'blue', fillColor: 'blue', fillOpacity: 0.5 }});
                        }} else if (description.includes('Tornado')) {{
                            layer.setStyle({{ color: 'purple', fillColor: 'purple', fillOpacity: 0.5 }});
                        }}
                    }}
                }})
                .addTo(map);
        }}
        document.addEventListener('DOMContentLoaded', initMap);
    </script>
    </head>
    <body>
        <div class="container">
            <h1>Current NWS Weather Alerts</h1>
            <p>Information last updated by NWS: <b>{formatted_update_time}</b>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
            Script last run: <b>{formatted_now}</b><br>
            <a href="index.html">Home</a></p>

            <div class="table-container">
                <table id="mapTable" class="table table-bordered">
                    <tbody>
                        <tr>
                            <td><div id="map"></div></td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div class="table-container">
                <table id="alertsTable" class="table table-bordered">
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
        areas_text = ", ".join(areas)
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
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdn.datatables.net/1.10.25/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.10.25/js/dataTables.bootstrap4.min.js"></script>

<script>
  $(document).ready(function () {
    var table = $('#alertsTable').DataTable({
      pageLength: 25,
      order: [[0, 'desc']]
    });

    // Make the built-in search box filter ONLY the County:State column (index 2).
    var $input = $('#alertsTable_filter input');
    $input.attr('placeholder', 'Filter County:State (e.g., VA, Fairfax:VA)');

    // Remove DataTables' default global-search handler and replace with column-specific search
    $input.off('keyup.DT search.DT input.DT paste.DT cut.DT');

    $input.on('keyup change clear', function () {
      let v = (this.value || '').trim();

      // If user types exactly a 2-letter state code (e.g., OR, VA),
      // match ONLY the state portion after the colon in County:State.
      // Column often contains comma-separated list, so allow comma or end-of-string.
      if (/^[A-Za-z]{2}$/.test(v)) {
        v = v.toUpperCase();
        const pattern = ':' + v + '(?:,|$)'; // matches ":OR," or ":OR" end-of-cell
        table.column(2).search(pattern, true, false).draw(); // regex=true, smart=false
      } else {
        table.column(2).search(v, false, true).draw(); // normal substring search
      }
    });
  });
</script>
    </body>
    </html>
    """
    return html_content


#===================================================================
# MySQL insert (same behavior as v2.0)
#===================================================================
def insert_data(cursor, conn, date_sql, event, title, link, summary, areas, coordinates_wkt):
    """
    Insert a single alert row.

    Table defaults to alerts2 to match your existing script, but can be overridden with:
      export NWS_DB_TABLE=weather_alerts
    """
    table = DB_TABLE

    if coordinates_wkt is not None:
        insert_query = f"""
        INSERT INTO {table} (date, event, title, link, summary, areas, coordinates)
        VALUES (%s, %s, %s, %s, %s, %s, ST_GeomFromText(%s))
        """
        values = (date_sql, event, title, link, summary, json.dumps(areas), coordinates_wkt)
    else:
        insert_query = f"""
        INSERT INTO {table} (date, event, title, link, summary, areas, coordinates)
        VALUES (%s, %s, %s, %s, %s, %s, NULL)
        """
        values = (date_sql, event, title, link, summary, json.dumps(areas))

    try:
        cursor.execute(insert_query, values)
        conn.commit()
    except pymysql.MySQLError as e:
        logging.error(f"Error inserting data: {e}")



#===================================================================
# Fetch + parse JSON Alerts API
#===================================================================
_last_call_epoch = 0.0


def fetch_active_alerts_json(url: str) -> Optional[Dict[str, Any]]:
    global _last_call_epoch

    # crude self-throttle in case someone loops it
    now = time.time()
    if now - _last_call_epoch < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(max(0.0, MIN_SECONDS_BETWEEN_CALLS - (now - _last_call_epoch)))

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json, application/ld+json, application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        _last_call_epoch = time.time()
        if resp.status_code != 200:
            logging.error(f"NWS API error {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json()
    except Exception as e:
        logging.error(f"Failed to fetch/parse NWS API JSON: {e}")
        return None


def parse_immediate_alerts(data: Dict[str, Any]) -> None:
    """
    Populate the global lists with alerts that have urgency=Immediate.

    Even though the URL already filters urgency=Immediate, we still verify
    per-alert for safety.
    """
    global update_time

    # Many NWS API feature collections include an "updated" field; if not, keep blank.
    update_time = data.get("updated") or data.get("updateTime") or ""

    features = data.get("features", [])
    logging.info(f"Total features returned: {len(features)}")

    for feature in features:
        props = feature.get("properties", {}) or {}
        urgency = props.get("urgency")
        if urgency != "Immediate":
            continue

        immediate_features.append(feature)

        # Title: API has "headline" and "event". Your old title came from ATOM title.
        title = _clean_whitespace(props.get("headline") or props.get("event") or "NWS Alert")
        titles.append(title)

        # Link: Use feature id if present; otherwise use @id; else fall back to "uri" in props.
        link = feature.get("id") or props.get("@id") or props.get("uri") or ""
        links.append(_clean_whitespace(link))

        # Summary: use "description" (CAP-style) or "instruction" as backup.
        summary = _clean_whitespace(props.get("description") or props.get("instruction") or "")
        summaries.append(summary)

        # Event: store the "event" name (string)
        event = _clean_whitespace(props.get("event") or "")
        events.append(event)

        # Published date: closest match to your old "published" is "sent"
        sent_sql = _iso_to_sql_dt(props.get("sent")) or _iso_to_sql_dt(props.get("effective")) or ""
        published_dates.append(sent_sql)

        # Areas list: from areaDesc (string)
        area_desc = props.get("areaDesc") or ""
        affected_areas_list.append(_areas_from_areaDesc(area_desc))

        # Geometry -> polygon WKT
        geom = feature.get("geometry")
        poly_wkt = geojson_geometry_to_mysql_polygon(geom)
        if poly_wkt is None:
            logging.info("Polygon data is missing/unsupported for an entry.")
        polygons.append(poly_wkt)


#===================================================================
# main program
#===================================================================
def main() -> int:
    data = fetch_active_alerts_json(API_URL)
    if not data:
        logging.error("No data returned from NWS API.")
        return 1

    parse_immediate_alerts(data)
    logging.info(f"Number of Immediate-urgency alerts: {len(immediate_features)}")

    # list length sanity check
    if check_equal_lengths(lists):
        logging.info("All lists have the same length.")
    else:
        logging.error("Lists have different lengths.")

    # Generate KML
    kml_content = generate_kml(polygons, events, titles, links, summaries, published_dates, affected_areas_list)
    with open(kmlfilename, "w", encoding="utf-8") as f:
        f.write(kml_content)
    logging.info("KML file created successfully.")

    # Connect to database
    try:
        conn = pymysql.connect(
            user=db_config["user"],
            password=db_config["password"],
            host=db_config["host"],
            database=db_config["database"],
        )
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        conn = None

    # Insert into DB (if connected)
    if conn is not None:
        cursor = conn.cursor()
        for i in range(len(polygons)):
            insert_data(
                cursor,
                conn,
                published_dates[i],
                events[i],
                titles[i],
                links[i],
                summaries[i],
                affected_areas_list[i],
                polygons[i],
            )
        cursor.close()
        conn.close()
        logging.info("Data inserted successfully into the alerts2 table.")
    else:
        logging.info("Skipping DB insert (no DB connection).")

    # Generate JSON output file
    for i in range(len(polygons)):
        json_data["alerts"].append(
            {
                "date": published_dates[i],
                "event": events[i],
                "title": titles[i],
                "link": links[i],
                "summary": summaries[i],
                "areas": affected_areas_list[i],
                "coordinates": polygons[i],
            }
        )

    with open(jsonfilename, "w", encoding="utf-8") as jf:
        json.dump(json_data, jf, indent=4)
    logging.info(f"JSON data written to {jsonfilename} successfully.")

    # Generate HTML
    html_content = generate_html(titles, links, affected_areas_list, published_dates, update_time)
    with open(htmlfilename, "w", encoding="utf-8") as hf:
        hf.write(html_content)
    logging.info(f"HTML file '{htmlfilename}' generated successfully.")

    logging.info("/////////////////////////////////////////////////////////////////////////////////////\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



