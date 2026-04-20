-- ============================================================
-- SahayakMap — Initial Schema Migration
-- Run this in the Supabase SQL editor (dashboard → SQL Editor)
-- IMPORTANT: Enable PostGIS extension first (step 1 below)
-- ============================================================

-- Step 1: Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- REFERENCE DATA (loaded once, updated rarely)
-- ============================================================

CREATE TABLE IF NOT EXISTS districts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'Odisha',
    boundary GEOMETRY(Polygon, 4326),
    population INTEGER,
    area_sq_km REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gauge_stations (
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

CREATE TABLE IF NOT EXISTS routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,  -- e.g. "NH-16", "SH-12"
    geometry GEOMETRY(LineString, 4326) NOT NULL,
    route_type TEXT CHECK (route_type IN ('national_highway', 'state_highway', 'district_road')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bridges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    route_id UUID REFERENCES routes(id),
    location GEOMETRY(Point, 4326) NOT NULL,
    flood_tolerance_m REAL,
    nearest_gauge_id UUID REFERENCES gauge_stations(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS relief_camps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    location GEOMETRY(Point, 4326) NOT NULL,
    district_id UUID REFERENCES districts(id),
    elevation_m REAL NOT NULL,
    max_capacity INTEGER NOT NULL,
    current_population INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'AT_RISK', 'EVACUATING', 'CLOSED')),
    flood_risk_hours REAL,
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- DATA SOURCES & INGESTION
-- ============================================================

CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('CWC_GAUGE', 'IMD_WEATHER', 'SATELLITE', 'SOCIAL_MEDIA', 'DISTRICT_REPORT', 'OSM_ROAD', 'ASSET_TRACKER')),
    name TEXT NOT NULL,
    base_reliability REAL DEFAULT 0.8 CHECK (base_reliability BETWEEN 0 AND 1),
    update_frequency_min INTEGER,
    last_fetched_at TIMESTAMPTZ,
    status TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DEGRADED', 'OFFLINE')),
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flood_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    location GEOMETRY(Point, 4326) NOT NULL,
    district_id UUID REFERENCES districts(id),
    severity INTEGER CHECK (severity BETWEEN 1 AND 5),
    water_level_m REAL,
    water_level_trend TEXT CHECK (water_level_trend IN ('RISING', 'STABLE', 'FALLING')),
    confidence REAL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    reported_at TIMESTAMPTZ NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    raw_payload JSONB,
    description TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- OPERATIONAL DATA (changes frequently)
-- ============================================================

CREATE TABLE IF NOT EXISTS rescue_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('BOAT', 'HELICOPTER', 'RESCUE_TEAM', 'SUPPLY_TRUCK')),
    name TEXT NOT NULL,
    capacity INTEGER,
    location GEOMETRY(Point, 4326) NOT NULL,
    assigned_district_id UUID REFERENCES districts(id),
    status TEXT DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'DEPLOYED', 'IN_TRANSIT', 'MAINTENANCE')),
    last_updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS route_status (
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

CREATE TABLE IF NOT EXISTS weather_forecasts (
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

-- ============================================================
-- AI-GENERATED OUTPUTS
-- ============================================================

CREATE TABLE IF NOT EXISTS alerts (
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
    acknowledged_at TIMESTAMPTZ,  -- NULL = unacknowledged
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS situation_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region TEXT DEFAULT 'Mahanadi Basin',
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    summary_text TEXT NOT NULL,
    key_risks JSONB,
    recommendations JSONB,
    overall_confidence REAL,
    data_freshness JSONB,
    stale_sources JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- DERIVED / JUNCTION TABLES
-- ============================================================

-- Operational district state (separated from static districts table)
CREATE TABLE IF NOT EXISTS district_status (
    district_id UUID PRIMARY KEY REFERENCES districts(id) ON DELETE CASCADE,
    signal_strength REAL DEFAULT 1.0 CHECK (signal_strength BETWEEN 0 AND 1),
    last_report_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- River network adjacency — supports multiple upstream contributors (DAG)
CREATE TABLE IF NOT EXISTS station_adjacency (
    upstream_id UUID NOT NULL REFERENCES gauge_stations(id) ON DELETE CASCADE,
    downstream_id UUID NOT NULL REFERENCES gauge_stations(id) ON DELETE CASCADE,
    avg_travel_time_hrs REAL,
    PRIMARY KEY (upstream_id, downstream_id),
    CHECK (upstream_id <> downstream_id)
);

-- Alert ↔ FloodReport junction — replaces JSONB array, enforces FK integrity
CREATE TABLE IF NOT EXISTS alert_reports (
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    flood_report_id UUID NOT NULL REFERENCES flood_reports(id) ON DELETE CASCADE,
    PRIMARY KEY (alert_id, flood_report_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_flood_reports_location ON flood_reports USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_flood_reports_reported_at ON flood_reports(reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_flood_reports_district ON flood_reports(district_id);
CREATE INDEX IF NOT EXISTS idx_gauge_stations_location ON gauge_stations USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_rescue_assets_location ON rescue_assets USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_relief_camps_location ON relief_camps USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity DESC, generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(acknowledged_at, expires_at);
CREATE INDEX IF NOT EXISTS idx_route_status_active ON route_status(status, expires_at);
CREATE INDEX IF NOT EXISTS idx_weather_forecasts_time ON weather_forecasts(forecast_time, district_id);
CREATE INDEX IF NOT EXISTS idx_station_adjacency_downstream ON station_adjacency(downstream_id);
CREATE INDEX IF NOT EXISTS idx_alert_reports_alert ON alert_reports(alert_id);
CREATE INDEX IF NOT EXISTS idx_district_status_last_report ON district_status(last_report_at);
