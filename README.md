# NWS Weather Alerts (Immediate Urgency)

Retrieves **immediate-urgency weather alerts** from the **U.S. National Weather Service (NWS)**, stores them in MySQL, and generates KML/HTML/JSON outputs.

The script:
- Queries NWS for **Urgency = Immediate**
- Parses alert metadata and affected geographic areas
- Stores alerts in MySQL (including **JSON** and **POLYGON** types)
- Generates:
  - **KML** for Google Earth
  - **HTML** dashboard with searchable/sortable alert listings
  - **JSON** output for reuse elsewhere

---

## Features

- NWS-compliant API access with a proper `User-Agent`
- MySQL storage using native **JSON** and **POLYGON**
- Automatic KML generation for geospatial visualization
- HTML dashboard with:
  - Search, sort, paging (DataTables)
  - County:State–specific filtering
  - Embedded interactive map
- Logging for troubleshooting and audit

---

## Version History

### v3.0 — JSON API Migration (Current)

**Why this update exists**

The National Weather Service moved alert distribution to a **JSON/GeoJSON-based service** at `api.weather.gov`.  
This project was updated to consume the new JSON endpoint so it remains reliable and future-proof.

**Key changes**
- Migrated from XML parsing to the official NWS JSON API:
  - `https://api.weather.gov/alerts/active?urgency=Immediate`
- Preserved the same outputs and general behavior (HTML, KML, JSON, MySQL)
- Improved handling of GeoJSON `Polygon` and `MultiPolygon`
- Fixed HTML/DataTables initialization issues and improved County:State filtering
- Improved timestamp handling (script run time vs NWS update time)

---

### v2.0 — XML Parsing and Database Enhancements (05/26/2024)

- Refactored script to use `xml.etree.ElementTree` for proper XML parsing
- Added structured logging
- Added MySQL storage
- Updated schema usage to support:
  - `JSON` for affected areas
  - `POLYGON` for alert geometry

---

### v2.1 — HTML Enhancements (06/15/2024)

- Added search, sort, and paging options via DataTables and jQuery in `generate_html()`

---

## Database Schema

Compatible MySQL table:

```sql
CREATE TABLE alerts2 (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  date DATETIME,
  event TEXT,
  title TEXT,
  link TEXT,
  summary TEXT,
  areas JSON,
  coordinates POLYGON
);
```

---

## Requirements

- Python 3.9+
- MySQL 8.0+ (for JSON + spatial support)
- Python packages:
  - `requests`
  - `mysql-connector-python`
  - `pytz`

Install packages:

```bash
python3 -m pip install requests mysql-connector-python pytz
```

---

## Configuration

Set environment variables (recommended):

```bash
export NWS_USER_AGENT="yourdomain.com (youremail@example.com)"
export NWS_DB_USER="dbuser"
export NWS_DB_PASSWORD="dbpassword"
export NWS_DB_HOST="localhost"
export NWS_DB_NAME="weather_alerts"
export NWS_DB_TABLE="alerts2"
```

> **Note:** NWS expects a valid `User-Agent` that identifies your application and provides contact info.

---

## Usage

Run the script:

```bash
python3 nws_alerts_v3.0_json.py
```

Generated outputs (filenames may vary depending on your script settings):
- `nws_alerts.kml`
- `nws_alerts.html`
- `nws_alerts.json`
- `nws_alerts.log`

---

## Known Limitations

- Some alerts have no polygon geometry (expected for certain alert types)
- `MultiPolygon` alerts may be simplified for DB compatibility if your schema stores only one `POLYGON`
- HTML dependencies may be loaded via CDN (local bundling is a future improvement)

---

## Roadmap / TODO

- Bundle DataTables/JS dependencies locally (optional)
- Add links to generated KML/JSON files in the HTML
- Add alert de-duplication using NWS alert IDs
- Provide example cron scheduling instructions

---

## License

Public domain / educational use. Use at your own risk. No warranty expressed or implied.
