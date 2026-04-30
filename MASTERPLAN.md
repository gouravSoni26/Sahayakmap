# SahayakMap — Masterplan

## Project Identity

**Name:** SahayakMap (सहायक = Helper)
**Tagline:** Real-time flood intelligence for India's disaster responders
**Capstone:** 100xEngineers Applied AI Capstone 5
**Deadline:** May 16, 2026
**Developer:** Solo (using Claude Code)

---

## Problem Statement

India's disaster responders operate with fragmented, contradictory, and delayed information during floods. The data exists — river gauge levels, weather radar, satellite imagery, social media reports, road network status — but no system fuses them into a single operational picture. The gap between available data and actionable intelligence costs lives.

**Primary User:** Rajesh Sharma — a battalion commander in India's NDRF, stationed in Cuttack, Odisha. He coordinates rescue operations across 15+ districts during monsoon. He needs to know: Where is the situation worst? Where will it be worst in 6 hours? Where should he send his teams?

**Focus Region:** Mahanadi River Basin, Odisha (proof of concept)

---

## What We're Building

A real-time flood intelligence platform that:

1. **Ingests** data from multiple sources (river gauges, weather, social media, road network, satellite)
2. **Fuses** them into a single temporally-coherent, spatially-accurate picture with conflict resolution
3. **Reasons** about what the fused data means operationally (AI intelligence layer)
4. **Displays** an interactive map with glanceable, actionable information
5. **Recommends** specific actions (redeployment, route changes, evacuation alerts)
6. **Projects** where the flood will be in 6 hours

**Scope Boundary:** This is a proof-of-concept for one river basin. We use real data where free APIs exist, and realistic synthetic data where they don't. The goal is to demonstrate the intelligence layer, not to build production-grade data pipelines for every source.

---

## Tech Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| **Frontend** | React 18 + Vite + Tailwind CSS | Fast build, modern, mobile-responsive |
| **Maps** | Leaflet.js + react-leaflet | Free, lightweight, great for custom overlays |
| **Backend** | FastAPI (Python 3.11+) | Async, fast, great for real-time data |
| **Database** | Supabase (free tier) | PostgreSQL + PostGIS for geospatial queries |
| **AI/LLM** | Claude API (claude-sonnet-4-20250514) | Situation reasoning, natural language briefings |
| **Weather API** | Open-Meteo (no key needed) | Free forecast + historical rainfall data |
| **Geocoding** | Nominatim (OSM) | Free, no API key |
| **Deployment** | Vercel (frontend) + Railway (backend) | Both have free tiers |
| **Version Control** | Git + GitHub | Standard |

### Key Libraries

**Backend (Python):**
- `fastapi`, `uvicorn` — API server
- `httpx` — async HTTP client for data ingestion
- `supabase-py` — Supabase client
- `geopandas`, `shapely` — geospatial processing
- `apscheduler` — periodic data ingestion jobs
- `anthropic` — Claude API client
- `pydantic` — data validation

**Frontend (JavaScript):**
- `react`, `react-dom` — UI framework
- `react-leaflet`, `leaflet` — map rendering
- `@tanstack/react-query` — data fetching/caching
- `tailwindcss` — styling
- `lucide-react` — icons
- `date-fns` — date formatting
- `zustand` — lightweight state management

---

## Domain Model

### Core Entities

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  DataSource      │     │  FloodReport     │     │  GaugeStation   │
│─────────────────│     │──────────────────│     │─────────────────│
│ id (uuid)       │     │ id (uuid)        │     │ id (uuid)       │
│ type (enum)     │     │ source_id (fk)   │     │ station_code    │
│ name            │     │ location (point) │     │ name            │
│ reliability     │     │ severity (1-5)   │     │ river_name      │
│ update_freq_min │     │ water_level_m    │     │ location (point)│
│ last_fetched_at │     │ confidence (0-1) │     │ danger_level_m  │
│ status (enum)   │     │ reported_at      │     │ warning_level_m │
└─────────────────┘     │ ingested_at      │     │ basin           │
                        │ expires_at       │     └─────────────────┘
                        │ raw_payload      │
                        └──────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  RescueAsset    │     │  Route           │     │  ReliefCamp     │
│─────────────────│     │──────────────────│     │─────────────────│
│ id (uuid)       │     │ id (uuid)        │     │ id (uuid)       │
│ type (enum)     │     │ name (e.g. NH16) │     │ name            │
│ name            │     │ geometry (line)  │     │ location (point)│
│ capacity        │     │ route_type(enum) │     │ elevation_m     │
│ location (point)│     │                  │     │ capacity        │
│ status (enum)   │     │                  │     │ current_pop     │
│ assigned_district│    │                  │     │ status (enum)   │
│ last_updated_at │     └──────────────────┘     │ flood_risk_hrs  │
└─────────────────┘                              └─────────────────┘

┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  District       │     │  Alert           │     │  SituationBrief │
│─────────────────│     │──────────────────│     │─────────────────│
│ id (uuid)       │     │ id (uuid)        │     │ id (uuid)       │
│ name            │     │ type (enum)      │     │ generated_at    │
│ state           │     │ severity (1-5)   │     │ region          │
│ boundary (poly) │     │ location (point) │     │ summary_text    │
│ population      │     │ title            │     │ key_risks[]     │
└─────────────────┘     │ description      │     │ recommendations│
                        │ affected_area    │     │ confidence      │
                        │ generated_at     │     │ data_freshness  │
                        │ acknowledged_at  │     │ stale_sources[] │
                        └──────────────────┘     └─────────────────┘

┌──────────────────┐    ┌─────────────────┐      ┌──────────────────┐
│  WeatherForecast │    │  DistrictStatus │      │ StationAdjacency │
│──────────────────│    │─────────────────│      │──────────────────│
│ id (uuid)        │    │ district_id (fk)│      │ upstream_id (fk) │
│ source_id (fk)   │    │ signal_strength │      │downstream_id (fk)│
│ location (point) │    │ last_report_at  │      │travel_time_hrs   │
│ district_id (fk) │    │ updated_at      │      └──────────────────┘
│ forecast_time    │    └─────────────────┘
│ rainfall_mm      │
│ wind_speed_kmh   │    ┌─────────────────┐
│ fetched_at       │    │   AlertReport   │
└──────────────────┘    │─────────────────│
                        │ alert_id (fk)   │
                        │ report_id (fk)  │
                        └─────────────────┘
```

### Enums

```
DataSourceType: CWC_GAUGE | IMD_WEATHER | SATELLITE | SOCIAL_MEDIA | DISTRICT_REPORT | OSM_ROAD | ASSET_TRACKER
DataSourceStatus: ACTIVE | DEGRADED | OFFLINE
AssetType: BOAT | HELICOPTER | RESCUE_TEAM | SUPPLY_TRUCK
AssetStatus: AVAILABLE | DEPLOYED | IN_TRANSIT | MAINTENANCE
RouteStatus: OPEN | PARTIALLY_BLOCKED | BLOCKED | SUBMERGED | UNKNOWN
CampStatus: ACTIVE | AT_RISK | EVACUATING | CLOSED
AlertType: FLOOD_RISING | BRIDGE_SUBMERGED | CAMP_AT_RISK | ASSET_MISPLACED | ROUTE_BLOCKED | SILENT_DISTRICT | FORECAST_DIVERGENCE
Severity: 1 (INFO) | 2 (ADVISORY) | 3 (WARNING) | 4 (CRITICAL) | 5 (EMERGENCY)
```

---

## Database Schema (Supabase + PostGIS)

**IMPORTANT:** Enable the PostGIS extension in Supabase dashboard before running migrations.

```sql
-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================
-- REFERENCE DATA (loaded once, updated rarely)
-- ============================================

CREATE TABLE districts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'Odisha',
    boundary GEOMETRY(Polygon, 4326),
    population INTEGER,
    area_sq_km REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE gauge_stations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    river_name TEXT NOT NULL,
    basin TEXT DEFAULT 'Mahanadi',
    location GEOMETRY(Point, 4326) NOT NULL,
    danger_level_m REAL NOT NULL,
    warning_level_m REAL NOT NULL,
    highest_flood_level_m REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,  -- e.g. "NH-16", "SH-12"
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    route_type TEXT CHECK (route_type IN ('national_highway', 'state_highway', 'district_road')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bridges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    route_id UUID REFERENCES routes(id),
    location GEOMETRY(Point, 4326) NOT NULL,
    flood_tolerance_m REAL,  -- water level at which bridge becomes impassable
    nearest_gauge_id UUID REFERENCES gauge_stations(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE relief_camps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    district_id UUID REFERENCES districts(id),
    elevation_m REAL NOT NULL,
    max_capacity INTEGER NOT NULL,
    current_population INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'AT_RISK', 'EVACUATING', 'CLOSED')),
    flood_risk_hours REAL,  -- estimated hours until flood reaches this elevation
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- DATA SOURCES & INGESTION
-- ============================================

CREATE TABLE data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('CWC_GAUGE', 'IMD_WEATHER', 'SATELLITE', 'SOCIAL_MEDIA', 'DISTRICT_REPORT', 'OSM_ROAD', 'ASSET_TRACKER')),
    name TEXT NOT NULL,
    base_reliability REAL DEFAULT 0.8 CHECK (base_reliability BETWEEN 0 AND 1),
    update_frequency_min INTEGER,
    last_fetched_at TIMESTAMPTZ,
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DEGRADED', 'OFFLINE')),
    config JSONB DEFAULT '{}',  -- connection details, URLs, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE flood_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    location GEOMETRY(Point, 4326) NOT NULL,
    district_id UUID REFERENCES districts(id),
    severity INTEGER CHECK (severity BETWEEN 1 AND 5),
    water_level_m REAL,
    water_level_trend TEXT CHECK (water_level_trend IN ('RISING', 'STABLE', 'FALLING')),
    confidence REAL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    reported_at TIMESTAMPTZ NOT NULL,  -- when the event was observed
    ingested_at TIMESTAMPTZ DEFAULT NOW(),  -- when our system got it
    expires_at TIMESTAMPTZ,  -- after this, data is stale
    raw_payload JSONB,
    description TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- OPERATIONAL DATA (changes frequently)
-- ============================================

CREATE TABLE rescue_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('BOAT', 'HELICOPTER', 'RESCUE_TEAM', 'SUPPLY_TRUCK')),
    name TEXT NOT NULL,
    capacity INTEGER,  -- persons for boat/heli, kg for truck
    location GEOMETRY(Point, 4326) NOT NULL,
    assigned_district_id UUID REFERENCES districts(id),
    status TEXT DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'DEPLOYED', 'IN_TRANSIT', 'MAINTENANCE')),
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE route_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    route_id UUID REFERENCES routes(id),
    segment_start GEOMETRY(Point, 4326),
    segment_end GEOMETRY(Point, 4326),
    status TEXT DEFAULT 'UNKNOWN' CHECK (status IN ('OPEN', 'PARTIALLY_BLOCKED', 'BLOCKED', 'SUBMERGED', 'UNKNOWN')),
    source_id UUID REFERENCES data_sources(id),
    confidence REAL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    reported_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE weather_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location GEOMETRY(Point, 4326) NOT NULL,
    district_id UUID REFERENCES districts(id),
    forecast_time TIMESTAMPTZ NOT NULL,
    rainfall_mm REAL,
    temperature_c REAL,
    wind_speed_kmh REAL,
    wind_direction_deg REAL,
    source_id UUID REFERENCES data_sources(id),
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- AI-GENERATED OUTPUTS
-- ============================================

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    location GEOMETRY(Point, 4326),
    district_id UUID REFERENCES districts(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_population INTEGER,
    recommended_action TEXT,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,  -- NULL = unacknowledged; set to timestamp when acknowledged
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE situation_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region TEXT DEFAULT 'Mahanadi Basin',
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    summary_text TEXT NOT NULL,
    key_risks JSONB,  -- array of {location, risk_description, severity, eta_hours}
    recommendations JSONB,  -- array of {action, rationale, priority, affected_assets}
    overall_confidence REAL,
    data_freshness JSONB,  -- {source_type: last_updated_at} map
    stale_sources JSONB,  -- array of source names that are stale/offline
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- DERIVED / JUNCTION TABLES
-- ============================================

-- Operational district state (split from static districts reference table)
CREATE TABLE district_status (
    district_id UUID PRIMARY KEY REFERENCES districts(id) ON DELETE CASCADE,
    signal_strength REAL DEFAULT 1.0 CHECK (signal_strength BETWEEN 0 AND 1),  -- 0=silent, 1=normal reporting
    last_report_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- River network adjacency (replaces single upstream_station_id FK in gauge_stations)
-- Supports multiple upstream contributors per station (DAG topology)
CREATE TABLE station_adjacency (
    upstream_id UUID NOT NULL REFERENCES gauge_stations(id) ON DELETE CASCADE,
    downstream_id UUID NOT NULL REFERENCES gauge_stations(id) ON DELETE CASCADE,
    avg_travel_time_hrs REAL,  -- time for water to travel between these two stations
    PRIMARY KEY (upstream_id, downstream_id),
    CHECK (upstream_id <> downstream_id)
);

-- Junction table replacing alerts.supporting_data JSONB — enforces referential integrity
CREATE TABLE alert_reports (
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    flood_report_id UUID NOT NULL REFERENCES flood_reports(id) ON DELETE CASCADE,
    PRIMARY KEY (alert_id, flood_report_id)
);

-- ============================================
-- INDEXES for performance
-- ============================================

CREATE INDEX idx_flood_reports_location ON flood_reports USING GIST(location);
CREATE INDEX idx_flood_reports_reported_at ON flood_reports(reported_at DESC);
CREATE INDEX idx_flood_reports_district ON flood_reports(district_id);
CREATE INDEX idx_gauge_stations_location ON gauge_stations USING GIST(location);
CREATE INDEX idx_rescue_assets_location ON rescue_assets USING GIST(location);
CREATE INDEX idx_relief_camps_location ON relief_camps USING GIST(location);
CREATE INDEX idx_alerts_severity ON alerts(severity DESC, generated_at DESC);
CREATE INDEX idx_alerts_active ON alerts(acknowledged_at, expires_at);
CREATE INDEX idx_route_status_active ON route_status(status, expires_at);
CREATE INDEX idx_weather_forecasts_time ON weather_forecasts(forecast_time, district_id);
CREATE INDEX idx_station_adjacency_downstream ON station_adjacency(downstream_id);
CREATE INDEX idx_alert_reports_alert ON alert_reports(alert_id);
CREATE INDEX idx_district_status_last_report ON district_status(last_report_at);
```

### Key PostGIS Queries the System Uses

```sql
-- Find all flood reports within 50km of a point
SELECT * FROM flood_reports
WHERE ST_DWithin(location, ST_SetSRID(ST_MakePoint(85.8, 20.4), 4326)::geography, 50000)
AND reported_at > NOW() - INTERVAL '6 hours';

-- Find rescue assets nearest to a crisis point
SELECT *, ST_Distance(
    location::geography,
    ST_SetSRID(ST_MakePoint(85.8, 20.4), 4326)::geography
) / 1000 AS distance_km
FROM rescue_assets
WHERE status = 'AVAILABLE'
ORDER BY location <-> ST_SetSRID(ST_MakePoint(85.8, 20.4), 4326)
LIMIT 5;

-- Find relief camps at risk (flood reports nearby + low elevation)
SELECT rc.*, COUNT(fr.id) AS nearby_reports, AVG(fr.severity) AS avg_severity
FROM relief_camps rc
LEFT JOIN flood_reports fr ON ST_DWithin(rc.location, fr.location, 0.1)  -- ~10km
    AND fr.reported_at > NOW() - INTERVAL '3 hours'
    AND fr.severity >= 3
WHERE rc.status = 'ACTIVE'
GROUP BY rc.id
HAVING COUNT(fr.id) > 0
ORDER BY avg_severity DESC;

-- Detect "silent districts" — districts with no recent reports
SELECT d.name, d.population,
    MAX(fr.reported_at) AS last_report,
    EXTRACT(EPOCH FROM (NOW() - MAX(fr.reported_at))) / 3600 AS hours_since_report
FROM districts d
LEFT JOIN flood_reports fr ON d.id = fr.district_id
GROUP BY d.id
HAVING MAX(fr.reported_at) IS NULL
    OR MAX(fr.reported_at) < NOW() - INTERVAL '4 hours'
ORDER BY d.population DESC;
```

---

## API Structure (FastAPI)

### Directory Structure

```
sahayakmap/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Environment variables, settings
│   ├── database.py              # Supabase client setup
│   │
│   ├── ingestion/               # Data ingestion layer
│   │   ├── __init__.py
│   │   ├── scheduler.py         # APScheduler setup
│   │   ├── cwc_gauge.py         # CWC river gauge scraper
│   │   ├── open_meteo.py        # Open-Meteo weather API
│   │   ├── osm_roads.py         # OpenStreetMap road network
│   │   ├── synthetic_social.py  # Synthetic social media generator
│   │   └── synthetic_reports.py # Synthetic district reports
│   │
│   ├── fusion/                  # Data fusion & conflict resolution
│   │   ├── __init__.py
│   │   ├── engine.py            # Main fusion engine
│   │   ├── confidence.py        # Confidence scoring
│   │   ├── temporal.py          # Time-alignment & staleness
│   │   └── spatial.py           # Spatial conflict resolution
│   │
│   ├── intelligence/            # AI reasoning layer
│   │   ├── __init__.py
│   │   ├── briefing.py          # Generate situation briefs via Claude
│   │   ├── alerts.py            # Alert generation & triage
│   │   ├── recommendations.py   # Resource allocation suggestions
│   │   └── projection.py        # Simple flood progression model
│   │
│   ├── api/                     # API routes
│   │   ├── __init__.py
│   │   ├── map_data.py          # GET /api/map — fused map data
│   │   ├── alerts.py            # GET /api/alerts — active alerts
│   │   ├── briefing.py          # GET /api/briefing — situation brief
│   │   ├── assets.py            # GET/PUT /api/assets — rescue assets
│   │   ├── districts.py         # GET /api/districts — district status
│   │   └── health.py            # GET /api/health — system status
│   │
│   └── seed/                    # Reference data loading
│       ├── odisha_districts.py  # District boundaries & population
│       ├── gauge_stations.py    # CWC station metadata
│       ├── relief_camps.py      # Known relief camp locations
│       └── routes_bridges.py    # Major routes & bridge data
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   │
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   │   ├── FloodMap.jsx        # Main Leaflet map
│   │   │   │   ├── GaugeMarkers.jsx    # River gauge markers
│   │   │   │   ├── FloodOverlay.jsx    # Flood extent overlay
│   │   │   │   ├── AssetMarkers.jsx    # Rescue asset positions
│   │   │   │   ├── RouteLayer.jsx      # Road status overlay
│   │   │   │   ├── CampMarkers.jsx     # Relief camp markers
│   │   │   │   └── AlertPopup.jsx      # Alert detail popup
│   │   │   │
│   │   │   ├── Panel/
│   │   │   │   ├── SituationPanel.jsx  # Side panel with AI briefing
│   │   │   │   ├── AlertList.jsx       # Prioritized alert list
│   │   │   │   ├── AssetPanel.jsx      # Asset deployment status
│   │   │   │   └── DataFreshness.jsx   # Source freshness indicators
│   │   │   │
│   │   │   └── common/
│   │   │       ├── SeverityBadge.jsx
│   │   │       ├── ConfidenceBar.jsx
│   │   │       └── TimeAgo.jsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useMapData.js           # Fetch fused map data
│   │   │   ├── useAlerts.js            # Fetch & poll alerts
│   │   │   ├── useBriefing.js          # Fetch AI briefing
│   │   │   └── useAssets.js            # Fetch asset positions
│   │   │
│   │   ├── stores/
│   │   │   └── mapStore.js             # Zustand store for map state
│   │   │
│   │   └── utils/
│   │       ├── severity.js             # Color coding helpers
│   │       ├── freshness.js            # Data freshness logic
│   │       └── constants.js            # Map defaults, Odisha coords
│   │
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
├── .env.example
├── requirements.txt
├── package.json
├── README.md
└── MASTERPLAN.md                # This file
```

### API Endpoints

```
GET  /api/health                — System status + data source freshness
GET  /api/map/data              — Fused map data (gauges, reports, assets, routes)
     Query params: ?bbox=lat1,lng1,lat2,lng2&hours=6&min_severity=2

GET  /api/gauges                — All gauge stations with current readings
GET  /api/gauges/{id}/history   — Water level history for a station (24h)

GET  /api/alerts                — Active alerts, sorted by severity
     ?min_severity=1&district_id=X&unacknowledged_only=true
     &include_expired=false&limit=50&cursor=<ISO timestamp>
     Response: {alerts[], count, next_cursor}
     Pagination: cursor-based (pass next_cursor from previous response)
PUT  /api/alerts/{id}/ack       — Acknowledge an alert
     Body (optional): {acknowledged_by: string}
     Returns 404 (not found) | 409 (already acknowledged or race condition)
     Note: acknowledged_by requires DB migration — ALTER TABLE alerts ADD COLUMN acknowledged_by TEXT

GET  /api/briefing              — Latest AI-generated situation brief
POST /api/briefing/generate     — Force-generate a new brief

GET  /api/assets                — All rescue assets with positions
     ?asset_type=BOAT|HELICOPTER|RESCUE_TEAM|SUPPLY_TRUCK
     &status=AVAILABLE|DEPLOYED|IN_TRANSIT|MAINTENANCE
     &district_id=X
     Response: {assets[], count}
PUT  /api/assets/{id}/position  — Update asset position (simulation)
     Body: {lat: float, lng: float}
     Returns 404 if asset not found
PUT  /api/assets/{id}/status    — Update asset status
     Body: {status: AVAILABLE|DEPLOYED|IN_TRANSIT|MAINTENANCE}
     Returns 404 if asset not found

GET  /api/districts             — District overview (signal strength, report counts)
GET  /api/districts/{id}        — District detail with all associated data

GET  /api/routes/status         — Road/bridge status overview
GET  /api/camps                 — Relief camp status + flood risk

POST /api/scenario/load         — Load a simulation scenario (e.g. Cyclone Fani replay)
POST /api/scenario/tick         — Advance simulation by N minutes
```

---

## Data Sources — Detailed Integration Plan

### 1. CWC River Gauge Data (REAL)

**Source:** `https://ffs.india-water.gov.in` or `https://indiawris.gov.in`
**Method:** Scrape/parse. CWC doesn't have a clean API — the data is in HTML tables or JSON served to their web dashboards. Use browser dev tools to find the actual data endpoints.
**Fallback:** If CWC is hard to scrape, use synthetic data modeled on real Mahanadi gauge stations (Naraj, Munduli, Alipingal, Tikarpara, etc.) with realistic water level patterns.
**Update Frequency:** Every 15 minutes (matching CWC reporting)
**Fields:** station_code, water_level_m, danger_level_m, timestamp, trend

**Key Mahanadi Basin Stations:**
| Station | River | Lat | Lng | Danger Level (m) |
|---------|-------|-----|-----|-------------------|
| Naraj | Mahanadi | 20.47 | 85.79 | 25.5 |
| Munduli | Mahanadi | 20.49 | 85.75 | 26.0 |
| Alipingal | Mahanadi | 20.83 | 83.88 | 43.0 |
| Tikarpara | Mahanadi | 20.58 | 84.78 | 38.5 |
| Jenapur | Brahmani | 20.93 | 86.14 | 15.8 |
| Anandpur | Baitarani | 21.21 | 86.12 | 38.0 |

### 2. Weather Forecast (REAL)

**Source:** Open-Meteo API (https://open-meteo.com) — completely free, no API key
**Endpoint:** `https://api.open-meteo.com/v1/forecast`
**Method:** Direct HTTP GET

```python
# Example: Rainfall forecast for Cuttack
params = {
    "latitude": 20.46,
    "longitude": 85.88,
    "hourly": "precipitation,rain,temperature_2m,windspeed_10m,winddirection_10m",
    "forecast_days": 3,
    "timezone": "Asia/Kolkata"
}
response = httpx.get("https://api.open-meteo.com/v1/forecast", params=params)
```

**Grid Points:** Fetch forecasts for 8-10 points across the Mahanadi basin to get spatial coverage.
**Update Frequency:** Every 30 minutes

### 3. OpenStreetMap Road Network (REAL)

**Source:** Overpass API (free, no key)
**Method:** Query for major roads and bridges in Odisha

```
# Overpass query for NH and SH roads in Odisha
[out:json];
area["name"="Odisha"]["admin_level"="4"]->.odisha;
(
  way["highway"~"trunk|primary|secondary"]["ref"](area.odisha);
  node["bridge"]["highway"](area.odisha);
);
out geom;
```

**Load:** Once at startup, store in PostGIS. Road STATUS is updated via synthetic reports.
**Note:** This gives us the road/bridge network. Status (open/blocked/submerged) comes from the fusion layer.

### 4. Social Media Signals (SYNTHETIC)

**Why Synthetic:** Twitter/X API is paid. No free alternative gives geotagged flood posts.
**Approach:** Generate realistic synthetic social media reports that simulate what citizen reports look like during a flood event.

```python
# Synthetic social media report generator
synthetic_tweet = {
    "text": "Knee-deep water on NH-16 near Jajpur. People evacuating by boat. #OdishaFlood",
    "location": {"lat": 20.85, "lng": 86.33},
    "timestamp": "2026-07-15T14:23:00+05:30",
    "confidence": 0.4,  # unverified citizen report
    "source_type": "SOCIAL_MEDIA",
    "has_image": True,
    "corroborating_reports": 0  # increases as more reports come from same area
}
```

**Key Design:** Synthetic tweets are generated to create the specific scenarios from the capstone brief:
- Gauge says safe, social media says flooding (drainage congestion scenario)
- Bridge reported submerged by 3 independent sources
- Silent district (no reports = possible communication collapse)

### 5. District Collector Reports (SYNTHETIC)

**Format:** Structured JSON simulating what an SDMA situation report contains.
**Fields:** district, affected_blocks, evacuated_count, casualties, infrastructure_damage, relief_camps_active, roads_blocked, request_for_resources
**Update Frequency:** Every 2-4 hours (simulating real reporting cadence with realistic delays)

### 6. Satellite Imagery (SIMULATED OVERLAY)

**Approach:** We won't process actual satellite imagery (too complex for solo capstone). Instead:
- Use pre-existing flood extent polygons from past events (Copernicus EMS has open data)
- Or generate approximate flood extent polygons from gauge data + elevation model
- Display these as a GeoJSON overlay on the map with a "captured at" timestamp showing it's 12-24 hours old

This lets us demonstrate the "satellite sees everything, 12 hours late" scenario from the brief without needing actual satellite processing.

### 7. Population & Elevation (REAL, STATIC)

**Population:** WorldPop (https://www.worldpop.org/) — free raster data for India at 100m resolution
**Elevation:** SRTM 30m data via OpenTopography (free) or Mapzen Terrain Tiles
**Load:** Pre-processed and stored in Supabase as district-level aggregates and relief camp elevations

---

## AI Intelligence Layer — Claude API Integration

### Prompt Architecture

The AI layer uses Claude API for three functions:

#### 1. Situation Briefing Generator

Called every 15 minutes or on-demand. Produces a plain-language briefing.

```python
BRIEFING_SYSTEM_PROMPT = """You are SahayakMap's intelligence engine assisting an NDRF
battalion commander during flood operations in Odisha.

You will receive structured data about the current flood situation. Generate a concise
situation briefing that a field commander can read in under 60 seconds.

Output Format (JSON):
{
  "summary": "2-3 sentence overview of the situation",
  "critical_developments": [
    {"location": "...", "situation": "...", "urgency": "HIGH|MEDIUM|LOW"}
  ],
  "key_risks": [
    {"risk": "...", "affected_area": "...", "eta_hours": N, "confidence": 0.X}
  ],
  "recommended_actions": [
    {"action": "...", "rationale": "...", "priority": 1, "assets_involved": ["..."]}
  ],
  "data_gaps": ["sources that are stale or missing"],
  "confidence_note": "overall assessment of data quality"
}

Rules:
- Be specific: use place names, distances, time estimates
- Flag contradictions between sources explicitly
- Distinguish between what you KNOW from data and what you INFER
- When data is stale, say so with the timestamp
- Recommendations must account for travel time and road conditions
- If a district has gone silent, flag it as potentially critical
- Never generate false precision — if confidence is low, say so
"""
```

#### 2. Conflict Resolution

When data sources contradict (gauge says safe, social media says flooding):

```python
CONFLICT_PROMPT = """Two data sources provide contradictory information about flooding
in {location}.

Source A ({source_a_type}, confidence: {conf_a}):
{source_a_data}

Source B ({source_b_type}, confidence: {conf_b}):
{source_b_data}

Analyze this contradiction. Consider:
1. Could both be correct? (e.g., river gauge vs drainage congestion)
2. What is the most likely explanation?
3. What confidence should the fused assessment have?
4. What additional data would resolve this?

Respond in JSON:
{
  "assessment": "...",
  "both_valid": true/false,
  "explanation": "...",
  "fused_severity": 1-5,
  "fused_confidence": 0.0-1.0,
  "data_needed": ["..."]
}
"""
```

#### 3. Alert Triage

When multiple alerts fire simultaneously, prioritize them:

```python
TRIAGE_PROMPT = """You have {n} active alerts for the Mahanadi basin flood operations.
The commander can focus on at most 3 items right now.

Current alerts:
{alerts_json}

Current asset positions:
{assets_json}

Rank the top 3 alerts by urgency, considering:
- Population at risk
- Time sensitivity (will the situation worsen if not addressed in the next hour?)
- Available assets nearby
- Whether the alert is actionable (can the commander DO something about it?)

Respond in JSON:
{
  "top_alerts": [
    {"alert_id": "...", "rank": 1, "reason": "...", "suggested_response": "..."}
  ],
  "deferred": [
    {"alert_id": "...", "reason_deferred": "..."}
  ]
}
"""
```

### Claude API Usage Budget

On the free/starter tier, budget carefully:
- Situation briefs: 1 call every 15 min = ~96/day
- Conflict resolution: ~10-20/day (only when contradictions detected)
- Alert triage: ~20-30/day
- Estimated daily tokens: ~200K input, ~50K output

**Cost Control:** Cache briefs in Supabase. Don't regenerate unless underlying data changed. Use hash of input data to detect changes.

---

## Simulation / Demo Scenario

### "Cyclone Fani Replay" (Demo Mode)

For the capstone demo, build a simulation mode that replays a flood event with time-compressed data. This showcases all system capabilities without needing a live disaster.

**Scenario Timeline (compressed to 30 minutes for demo):**

| Demo Time | Sim Time | Event |
|-----------|----------|-------|
| 0:00 | T+0h | Cyclone approaching. IMD forecast shows heavy rainfall. All gauges normal. |
| 0:03 | T+3h | Rainfall begins. Open-Meteo shows 80mm/hr over Kendrapara and Jagatsinghpur. |
| 0:06 | T+6h | Naraj gauge crosses warning level. 12 social media reports from Jajpur (drainage flooding). CWC gauge at Jajpur still normal → **Contradiction Scenario.** |
| 0:09 | T+9h | Naraj crosses danger level. Bridge at Jenapur reported submerged (3 independent social media reports) → **Route blocked alert.** Supply convoy needs rerouting. |
| 0:12 | T+12h | Boats deployed to Kendrapara per earlier forecast. But rainfall concentrated over Jagatsinghpur instead → **Forecast divergence scenario.** AI recommends redeployment. |
| 0:15 | T+15h | Ganjam district goes silent — no reports for 4 hours, district collector unreachable → **Silent district alert.** |
| 0:18 | T+18h | Satellite imagery arrives (12 hours old) showing flood extent. Confirms some areas, contradicts others → **Stale satellite scenario.** |
| 0:21 | T+21h | Relief camp at Erasama school now in projected flood zone (flood expanding) → **Camp at risk alert.** 340 people need re-evacuation. |
| 0:25 | T+24h | Full situation brief with all scenarios active. Multiple alerts competing for attention → **Triage scenario.** |
| 0:30 | End | Summary: show what decisions the system supported, what it flagged that manual processes would have missed. |

**Implementation:**
- Pre-generate all synthetic data for each timestep
- `POST /api/scenario/load` loads the scenario
- `POST /api/scenario/tick` advances by one step
- Frontend has a "demo controls" bar with play/pause/step buttons
- Data inserts into the same tables as real data — the rest of the system doesn't know it's a simulation

---

## Confidence & Freshness Model

Every piece of data in the system has two quality dimensions:

### Confidence Score (0.0 - 1.0)

| Source Type | Base Confidence | Notes |
|-------------|----------------|-------|
| CWC Gauge | 0.95 | Calibrated instrument |
| IMD Forecast | 0.75 | Decreases with forecast horizon |
| Satellite Imagery | 0.90 | High spatial accuracy, but stale |
| District Report (official) | 0.80 | Verified but delayed |
| Social Media (single) | 0.30 | Unverified |
| Social Media (3+ corroborating) | 0.65 | Cross-verified |
| Social Media (with photo) | 0.50 | Visual evidence |

**Corroboration Boost:** When multiple independent sources report the same thing within 5km and 1 hour, confidence increases:
- 2 sources: +0.15
- 3+ sources: +0.25
- Official + social: +0.20

### Freshness / Staleness

Every data point has a **half-life** — the time after which its decision value drops by 50%:

| Data Type | Half-Life | Rationale |
|-----------|-----------|-----------|
| River gauge reading | 30 min | Water levels change quickly |
| Weather forecast (next 3h) | 1 hour | Short-term forecasts degrade |
| Weather forecast (12-24h) | 3 hours | Longer forecasts less reliable |
| Social media report | 2 hours | Situation on ground changes |
| Satellite image | 6 hours | Flood boundary shifts |
| Road/bridge status | 4 hours | Conditions can change |
| District report | 3 hours | Delayed by reporting chain |

**Visual Encoding on Map:**
- Full opacity = fresh data
- 50% opacity = past half-life
- Dashed border = past 2x half-life (very stale)
- Faded + warning icon = source offline

---

## UI Design Principles

### The 3 AM Test

Every UI decision must pass this test: "Can Rajesh use this on a phone screen at 3 AM in driving rain, with 3 hours of sleep, while coordinating 200 rescuers?"

### Layout

```
┌─────────────────────────────────────────────────────┐
│ [☰] SahayakMap — Mahanadi Basin    [⚡3 alerts] [🔄] │
├───────────────────────────────┬─────────────────────┤
│                               │ SITUATION BRIEF     │
│                               │ ─────────────────── │
│                               │ 🔴 Naraj: 26.3m     │
│         INTERACTIVE MAP       │    (+0.3m/hr)       │
│                               │ ⚠️ Jajpur: social   │
│     (Leaflet, full height)    │    reports conflict  │
│                               │    with gauge        │
│     [gauge markers]           │ 🔇 Ganjam: silent    │
│     [flood overlay]           │    4hrs, pop 3.8M    │
│     [asset positions]         │                     │
│     [route status]            │ TOP ACTION:          │
│     [alert pins]              │ Redeploy 2 boats    │
│                               │ Kendrapara →        │
│                               │ Jagatsinghpur       │
│                               │ via Devi River      │
│                               │ ETA: 2.5 hrs        │
├───────────────────────────────┴─────────────────────┤
│ [Gauges] [Alerts] [Assets] [Routes] [Demo Controls] │
└─────────────────────────────────────────────────────┘
```

### Color System

| Severity | Color | Meaning |
|----------|-------|---------|
| 1 - Normal | `#22c55e` (green) | Below warning level |
| 2 - Advisory | `#eab308` (yellow) | Approaching warning level |
| 3 - Warning | `#f97316` (orange) | Between warning and danger level |
| 4 - Critical | `#ef4444` (red) | At or above danger level |
| 5 - Emergency | `#7c2d12` (dark red, pulsing) | Life-threatening, immediate action needed |

### Mobile Responsive

- Map takes full screen on mobile
- Situation panel becomes a bottom drawer (swipe up)
- Alerts as push-notification style cards
- Large touch targets (min 44px)

---

## Week-by-Week Build Plan (with Claude Code commands)

### Week 1: Foundation (Apr 16-22)

**Day 1-2: Project scaffold**
```bash
# Claude Code tasks
/dev  # scaffold React + Vite + Tailwind frontend
/dev  # scaffold FastAPI backend with folder structure
/dev  # create Supabase migration file from schema above
```
- Initialize Git repo
- Set up Supabase project + enable PostGIS
- Run database migration
- Set up .env with Supabase URL/key + Claude API key

**Day 3-4: Seed reference data**
- Load Odisha district boundaries (GeoJSON from geoBoundaries or GADM)
- Load Mahanadi gauge station metadata
- Load major routes from OSM Overpass API
- Load relief camp locations (manually curated for demo)

**Day 5-7: Basic map + first data source**
- React app showing Leaflet map centered on Odisha
- Gauge station markers on map (color-coded by water level)
- Open-Meteo integration pulling rainfall forecasts
- Basic polling (refetch every 60 seconds)

**Week 1 Deliverable:** Map with colored gauge markers + weather overlay

### Week 2: Multi-Source Fusion (Apr 23-29)

**Day 1-2: Additional data sources**
- Synthetic social media report generator
- Synthetic district collector reports
- Route/bridge status system
- All sources writing to flood_reports table

**Day 3-4: Fusion engine**
- Confidence scoring module
- Temporal freshness calculation (half-life model)
- Spatial clustering (group nearby reports)
- Conflict detection (flag when sources disagree within 10km)

**Day 5-7: Map integration**
- Social media report markers on map (different icon)
- Route status overlay (green/yellow/red road segments)
- Relief camp markers with capacity info
- Rescue asset markers (draggable for simulation)
- Data freshness indicators (opacity based on staleness)

**Week 2 Deliverable:** Multi-layer map with all data sources + freshness visualization

### Week 3: Intelligence Layer (Apr 30 - May 6)

**Day 1-2: Claude API integration**
- Briefing generator with system prompt
- Conflict resolution prompts
- Response parsing and storage in Supabase

**Day 3-4: Alert system**
- Alert generation rules (gauge threshold, silent district, bridge submerged, camp at risk)
- Alert triage via Claude API
- Alert acknowledgment flow

**Day 5-7: Situation panel**
- Side panel showing AI-generated brief
- Alert list sorted by severity
- Recommended actions with map highlighting
- "Why this alert?" expandable detail

**Week 3 Deliverable:** AI briefings + prioritized alerts + recommendations

### Week 4: Demo Scenario + Polish (May 7-13)

**Day 1-2: Simulation engine**
- Cyclone Fani replay scenario data generation
- Scenario loader + ticker endpoints
- Demo control bar in frontend

**Day 3-4: Flood projection**
- Simple upstream→downstream time-lag model
- Flood extent projection (buffer gauge locations based on level + elevation)
- Relief camp risk assessment (projected flood vs camp elevation)

**Day 5-7: Polish**
- Mobile responsive layout
- Loading states, error handling
- Performance optimization (reduce API calls)
- Deploy to Vercel + Railway

**Week 4 Deliverable:** Complete demo-ready application

### Week 5: Submission (May 14-16)

- Write README with setup instructions
- Record demo video walking through the Cyclone Fani replay scenario
- Document architecture decisions and tradeoffs
- Final deployment check

---

## Environment Variables

```env
# .env.example

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbG...
SUPABASE_SERVICE_KEY=eyJhbG...  # for backend only

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Open-Meteo (no key needed, but configure base URL)
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1

# App Config
BRIEFING_INTERVAL_MIN=15
DATA_REFRESH_INTERVAL_SEC=60
SIMULATION_MODE=false
LOG_LEVEL=INFO

# Frontend (Vite)
VITE_API_BASE_URL=http://localhost:8000
VITE_MAP_CENTER_LAT=20.46
VITE_MAP_CENTER_LNG=85.88
VITE_MAP_DEFAULT_ZOOM=8
```

---

## Key Design Decisions & Tradeoffs

1. **Synthetic data instead of real social media:** Honest about what we can't access for free. The synthetic data is designed to showcase the scenarios from the capstone brief. Mention in documentation that production would use real social media APIs.

2. **Claude API for reasoning instead of local Ollama:** The capstone needs impressive reasoning (conflict resolution, triage). Claude Sonnet handles this much better than Llama 3.2 1B. Use Claude API for the intelligence layer, keep Ollama as a mentioned fallback for offline/degraded mode.

3. **React over Streamlit:** More work, but the capstone brief emphasizes "glanceable on a phone at 3 AM." Streamlit can't deliver that. Claude Code will scaffold React quickly.

4. **Supabase over raw PostgreSQL:** Free tier includes PostGIS, real-time subscriptions, auth (if needed), and a nice dashboard for debugging. Reduces ops work for a solo developer.

5. **Simulation mode over live data:** A controlled demo scenario is more impressive than waiting for a real flood. The Cyclone Fani replay lets us showcase ALL system capabilities in a 30-minute demo.

6. **Confidence + freshness as first-class UI:** This is the key differentiator from a basic GIS tool. Showing the user WHAT the system knows AND how much to trust it is the core UX innovation.

---

## How to Use This Document with Claude Code

1. Open Claude Code in your project directory
2. Share this MASTERPLAN.md as context: `@MASTERPLAN.md`
3. Use slash commands from gstack to drive development:
   - `/dev` for coding tasks ("scaffold the FastAPI backend per the masterplan")
   - `/qa` for testing ("write tests for the fusion engine")
   - `/designer` for UI refinement ("make the alert cards mobile-friendly")
   - `/office-hours` for planning ("let's review week 2 progress and adjust")

Start with: "Read MASTERPLAN.md and scaffold the project structure for Week 1, starting with the backend."

---

*This document is the single source of truth for the SahayakMap capstone project. Update it as design decisions evolve.*

---

## Implementation Log

### Apr 17, 2026 — api/ layer improvements (alerts.py + assets.py)

**Patterns established (apply to all future api/ files):**
- Query Builder Pattern — `Filter` dataclass list replaces if-else chains for optional query params
- Repository Pattern — `XxxRepository` class centralizes all DB logic; endpoints stay clean
- Dependency Injection — `get_valid_<entity>()` reusable `Depends()` function handles UUID format + existence check for all endpoints that take an entity ID
- Enum types — all fixed-value fields use `str, Enum` subclass; FastAPI validates at API layer before DB is touched
- UUID path params — always type path params as `UUID`, convert to `str` for Supabase
- Explicit column lists — `LIST_COLUMNS` and `UPDATE_COLUMNS` constants replace `select("*")`
- `.select()` after `.update()` — required for Supabase to return the updated row

**alerts.py changes:**
- Added expiry filter (`include_expired` param, default off)
- Replaced offset pagination with cursor-based pagination (`cursor` + `next_cursor`)
- Added `acknowledged_by` field to ack endpoint (requires DB migration)
- Added optimistic lock on acknowledge (409 on race condition)
- UUID validation on alert_id path param
- 404 on missing alert_id

**assets.py changes:**
- Added `asset_type`, `status`, `district_id` filters to list endpoint
- Applied Repository Pattern (AssetRepository class)
- Applied Dependency Injection (get_valid_asset, get_asset_repository)
- Enum validation on AssetStatus and AssetType
- UUID validation on asset_id path param
- 404 on missing asset_id
- Fixed update endpoints to return updated row via `.select()`

### Apr 29, 2026 — Week 2 closed + LLM fallback chain

- AssetMarkers.jsx: draggable markers with PATCH on dragend
- DemoControls.jsx: scenario simulation panel, bottom-left
- briefing.py: full fallback chain — Claude → Groq → Ollama → template
- config.py: startup validation fixed, Groq-only deploys now work
- Issue #18 resolved: Ollama URL config unblocked

### Apr 29, 2026 — Week 3 Day 1 complete

- briefing.py: full LLM fallback chain implemented (Claude → Groq → Ollama → template)
- config.py: startup validation fixed, Groq-only deploys work
- Groq model: openai/gpt-oss-120b (active, verified)
- Day 1 verified: Groq firing, natural language briefings confirmed
- Issue #18 resolved: Ollama URL config unblocked
- ANTHROPIC_API_KEY deferred to demo day (May 14-15)

### Apr 29, 2026 — Week 3 Day 2 complete

- AlertList.jsx: accordion expandable added
- Collapsed: title + severity badge + ack button
- Expanded: full description, recommended_action, type badge, timestamp
- Chevron tooltip: "Why this alert?"

### Apr 29, 2026 — Week 3 Progress Summary (resume point)

COMPLETED:
- Week 2 fully closed:
  - AssetMarkers.jsx: draggable markers with dragend → PUT /api/assets/:id/position
  - DemoControls.jsx: scenario simulation panel, bottom-left, polls /api/scenario/state
  - App.jsx: DemoControls wired alongside FloodMap

- Week 3 Day 1: LLM fallback chain
  - briefing.py: Claude → Groq → Ollama → template fallback chain
  - config.py: startup validation fixed, Groq-only deploys work
  - Issue #18 resolved: Ollama URL config unblocked
  - Groq model: openai/gpt-oss-120b (verified working)
  - ANTHROPIC_API_KEY deferred to demo day (May 14-15)

- Week 3 Day 2: Alert expandable
  - AlertList.jsx: accordion expandable per alert row
  - Collapsed: title + severity badge + ack button
  - Expanded: description, recommended_action, type badge, timestamp
  - Chevron tooltip: "Why this alert?"

NEXT (resume here):
- Week 3 Day 3: Bridge submersion alert rule + GET /api/alerts/{alert_id} detail endpoint
  - File: backend/intelligence/alerts.py → implement _check_bridge_submersion()
  - File: backend/api/alerts.py → add detail endpoint with alert_reports junction
- Week 3 Day 4: Recommended actions → map highlighting via Zustand
  - Files: SituationPanel.jsx, mapStore.js, AssetMarkers.jsx
- Week 3 Day 5-7: Integration test + Cyclone Fani scenario end-to-end

### Apr 29, 2026 — Week 3 Day 3 complete

- intelligence/alerts.py: implemented _check_bridge_submersion()
  - Joins bridges table with nearest_gauge_id → gauge_stations (water_level_m, name)
  - Skips bridges where water_level_m < flood_tolerance_m
  - Queries severity-3+ flood_reports within last 3h, filters to within 2km via haversine_km
  - Emits BRIDGE_SUBMERGED alert (severity=4) only if corroborating reports >= BRIDGE_CORROBORATION_COUNT
  - BRIDGE_CORROBORATION_COUNT = 3 defined as module-level constant (line 25)
  - Wired into run_alert_checks() after _check_camps_at_risk()
  - Linked report IDs flow into alert_reports junction table via existing run_alert_checks() loop

- api/alerts.py: added GET /api/alerts/{alert_id} detail endpoint
  - DETAIL_COLUMNS: LIST_COLUMNS + description
  - REPORT_COLUMNS: explicit columns for linked flood_reports
  - AlertRepository.get_by_id(): fetches alert row + resolves alert_reports junction → flood_reports, embedded as alert["flood_reports"]
  - get_valid_alert() / get_alert_repository(): exact DI pattern from assets.py
  - UUID malformed → 422, not found → 404
  - Endpoint delegates entirely to repository, no inline DB code


  ### Apr 29, 2026 — Week 3 Day 3 complete

- intelligence/alerts.py: implemented _check_bridge_submersion()
  - 3 pre-loop queries (no N+1): gauge_stations (id, station_code map) → data_sources (CWC_GAUGE ids) → flood_reports (latest CWC readings, ordered DESC)
  - Skips bridges where latest water_level_m < flood_tolerance_m
  - Corroboration: severity-3+ flood_reports within last 3h, filtered to within 2km via haversine_km
  - Emits BRIDGE_SUBMERGED alert (severity=4) only if corroborating reports >= BRIDGE_CORROBORATION_COUNT
  - BRIDGE_CORROBORATION_COUNT = 3 as module-level constant (line 25) alongside SILENT_DISTRICT_HOURS and CAMP_RISK_PROXIMITY_KM
  - Wired into run_alert_checks() after _check_camps_at_risk()
  - Bug fixed: original FK join select("*, gauge_stations(water_level_m, name)") failed (column doesn't exist on static table) — replaced with 3-query pattern

- api/alerts.py: added GET /api/alerts/{alert_id} detail endpoint
  - DETAIL_COLUMNS: LIST_COLUMNS + description
  - REPORT_COLUMNS: explicit columns for linked flood_reports
  - AlertRepository.get_by_id(): fetches alert row + resolves alert_reports junction → flood_reports, embedded as alert["flood_reports"]
  - get_valid_alert() / get_alert_repository(): exact DI pattern from assets.py
  - UUID malformed → 422, not found → 404
  - Endpoint delegates entirely to repository, no inline DB code
  - Verified via Swagger: 200 with correct shape, flood_reports array present

  ### Apr 30, 2026 — Week 3 Day 4 complete

- mapStore.js: added highlighting state
  - highlightedAssetIds: [], highlightedDistrict: null
  - setHighlightedAssets(), setHighlightedDistrict(), clearHighlights()

- SituationPanel.jsx: recommended actions → map highlighting
  - parseBrief(): defensive JSON parse of summary_text (handles Groq raw string)
  - Renders summary, critical_developments, recommended_actions with scroll
  - resolveAssetIds(): matches action.assets_involved name strings → UUIDs via useAssets()
  - onMouseEnter → setHighlightedAssets(resolved UUIDs); onMouseLeave → clearHighlights()

- AssetMarkers.jsx: highlight rendering
  - isHighlighted: UUID match OR name substring match fallback
  - Highlighted markers: pulsing ring via @keyframes + zIndexOffset={1000}

- briefing.py: Groq response parse pipeline fixed
  - _strip_code_fences(): removes ```json fences
  - _normalize_llm_text(): sanitizes unicode (smart quotes, non-breaking hyphen, em-dash)
  - _repair_truncated_json(): closes unterminated JSON from token cutoff
  - max_tokens increased to 2000 for Groq call
  - Double-decode guard + non-dict guard added

NEXT (resume here):
- Week 3 Day 5-7: Integration test + Cyclone Fani scenario end-to-end

## Deferred Items (add to existing Deferred section)
- _check_gauge_thresholds() uses select("*") — fix to explicit columns in Week 4 polish
- GET /api/alerts/{alert_id} missing Pydantic response_model — add in Week 4 polish
