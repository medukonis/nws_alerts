# nws_alerts
Retrieves nws weather alerts from US National Weather Service with immediate urgency, plots polygons of affected areas in KML file for google earth.  Also writes an HTML file with the list of alerts and a JSON file if you want to import the data into something else.

5/26/2024
V2.0 of script
revamp entire script to utilize xml.etree.ElementTree for proper
xml parsing. Added logging, mysql storage supports POLYGON and
JSON data types updated data types in script to utilize.

sample mysql table, compatible with this script
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
6/15/2024
added search, sort, and paging options from DataTables and jquery to generate_htmlfunction
TODO install these localy
TODO add links for kml, json files.
TODO clarify updated date/time to show date/time script was run and date/time nwsupdated their info.
TODO look at changing published date to UTC or EASTERN?  Right now they are local
