
#==================================================================
#NWS_Alerts
#Updated v1.1 8/23/2020 added state codes to listings on html
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
#==================================================================

#==================================================================
#Imports
#==================================================================
from bs4 import BeautifulSoup
import datetime
import requests

#===================================================================
#Variables
#===================================================================
r  = requests.get("https://alerts.weather.gov/cap/us.php?x=0")
date_time = str(datetime.datetime.now().strftime("%m-%d-%y %H%M"))
#kmlfilename = "nws_alerts" + " " + date_time + ".kml"
data = r.text
soup = BeautifulSoup(data, "lxml")
entries = soup.find_all("entry")
counter = 0


#===================================================================
#file names - change to suit your needs
#===================================================================
kmlfilename = "/home/medukonis/bin/nws_alerts.kml"
httpfilename = "/home/medukonis/bin/nws_alerts.html"


#===================================================================
#Lists
#===================================================================
#Several different lists are needed to hold the various data points
#Probably can be refactored now that it is working

#im_list holds objects with immediate urgency only from NWS
im_list=[]
#split_ist is a list of lists. Code below will break down elements of im_list into individual parts
split_list=[]
#list of lat/long pairs that make up each polygon
latlonglist =[]
#list or coordinates with added ",0" on the end
coord_list=[]
#list to hold the reverse order (long/lat)
reverse = []



#Grab all of the alerts that have "Immediate" urgency
#Each entry will be text only and an object in a list containing several fields
#description, coordinates, link to more info, etc...
for s in entries:
    if "<cap:urgency>Immediate" in str(s):
        im_list.append(s.text)   

#Below 2 lines gives a list of lists
#each of the objects in im_lists above are broken down further
#by splitting at each new line.

for x in im_list:
    split_list.append(x.split('\n'))

#write out info to HTML file for reading   
file = open(httpfilename, "w", encoding='utf-8')
file.write("<html> <head></head> <body>")
file.write("<h2>NWS Weather Alerts with <i>Immediate</i> Urgency</h2>")
file.write("<h3>Pulled: " + date_time +"</h3>")

#Writeout only the parts we want
for x in split_list:
    file.write("<p><b>State: </b>" + str(x[25][:2]) + "<br>")  #Grab first two letters of split list item 25 - state code
    file.write("<a href=\"" + str(x[1]) + "\" target=\"_blank\">" + str(x[1]) + "</a><br>")
    file.write(str(x[7]) + "<br>")
    file.write("<b>Summary:</b>\n" + str(x[9]) + "<br>")
    file.write("<b>Counties Affected:</b>\n" + str(x[19]) + "<br>")
    latlonglist.append(x[20].split(' '))
file.write("</body></html>")
file.close()  
for x in latlonglist:
    coord_list.append([y + ",0" for y in x])

#Write info to KML file for google earth layer - visualization
file = open(kmlfilename, "w", encoding='utf-8')
file.write("<?xml version='1.0' encoding='UTF-8'?>\n")
file.write("<kml xmlns='http://www.opengis.net/kml/2.2'>\n")
file.write("<Document>\n")
file.write("<LookAt>\n")
file.write("<longitude>-97.3372222</longitude>\n")
file.write("<latitude>37.6922222</latitude>\n")
file.write("<altitude>0</altitude>\n")
file.write("<range>5000000</range>\n")
file.write("<heading>0.626662975928317</heading>\n")
file.write("<altitudeMode>relativeToGround</altitudeMode>\n")
file.write("<tilt>0</tilt>\n")
file.write("</LookAt>\n")
for x in coord_list:
    file.write("<Placemark>\n")
#name and data
    file.write("<name>" + str(split_list[counter][7])+ "</name>\n") 
    file.write("<description>\n")
    file.write(str(split_list[counter][9])+ "\n\n")
    file.write(str(split_list[counter][1])+ "\n")
    file.write("</description>\n")
    file.write("\t<visibility>0</visibility>\n")
    file.write("\t<Polygon>\n")
    file.write("\t\t<extrude>0</extrude>\n")
    file.write("\t\t<outerBoundaryIs>\n")
    file.write("\t\t<LinearRing>\n")
    file.write("\t\t<coordinates>\n")

#===========================================================
#coordintates have to be reversed to be read correctly
#by google earth.
#===========================================================
    for y in x:
        reverse.append(y.split(','))
    for z in reverse:
        file.write("\t\t\t" + z[1] + ",")
        file.write(z[0] + ",")
        if len(reverse) > 2:
            file.write(z[2] + "\n")
        else:
            file.write(z[2] + "\n")
    #test_file = open("coord.txt", "a", encoding='utf-8')
    #for t in range(len(reverse)):
    #    test_file.write(str(reverse[t]))
    #    test_file.write("\n")
    #test_file.close()
    reverse=[]
#===========================================================
    
    file.write("\t\t</coordinates>\n")
    file.write("\t\t</LinearRing>\n")
    file.write("\t\t</outerBoundaryIs>\n")
    file.write("\t</Polygon>\n")
    file.write("<Style>\n")
    file.write("<PolyStyle>\n")
    file.write("<color>#a00000ff</color>")
    file.write("<outline>0</outline>")
    file.write("</PolyStyle>\n")
    file.write("</Style>\n")
    file.write("</Placemark>\n")
    counter = counter + 1
file.write("</Document>\n")
file.write("</kml>")
file.close()
