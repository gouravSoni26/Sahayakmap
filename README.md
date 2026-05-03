# SahayakMap — Real-Time Flood Intelligence for India's Disaster Responders

> **Capstone:** 100xEngineers Applied AI Capstone 5 | **Deadline:** May 16, 2026
> **Focus Region:** Mahanadi River Basin, Odisha

---

## The Problem

During India's monsoon floods, disaster responders face fragmented, contradictory, and delayed information. River gauge data, weather forecasts, social media reports, satellite imagery, and road network status all arrive through separate channels with no unified picture. The gap between available data and actionable intelligence costs lives.

**Primary User — Rajesh Sharma:** A battalion commander in India's National Disaster Response Force (NDRF), stationed in Cuttack, Odisha. He coordinates rescue operations across 15+ districts during monsoon season. He needs three answers fast:
- Where is the situation worst **right now**?
- Where will it be worst in **6 hours**?
- Where should he **send his teams**?

SahayakMap answers all three — in one screen, with AI-generated reasoning.

---

## What It Does

1. **Ingests** data from river gauges (CWC), weather (Open-Meteo), social media reports, satellite imagery, and district field reports
2. **Fuses** them into a single coherent picture with conflict detection and confidence scoring
3. **Reasons** using Claude to generate situation briefings, triage competing alerts, and resolve source contradictions
4. **Displays** an interactive map (Leaflet) with flood overlays, asset positions, route status, and alert pins
5. **Projects** flood extent 6 hours forward using gauge readings and terrain data
6. **Alerts** when a gauge crosses danger level, a bridge is submerged, a relief camp enters the flood zone, or a district goes silent

---

## Architecture

```
Data Sources
    |
    +-- CWC River Gauges (simulated, real station codes)
    +-- Open-Meteo Weather API (live, free)
    +-- Social Media Reports (synthetic -- X/Twitter API is paid)
    +-- Satellite Imagery (synthetic)
    +-- District Field Reports (synthetic)
    |
    v
ingestion/          APScheduler jobs poll sources every 60s
    |               Writes to: flood_reports, weather_forecasts
    v
fusion/             Confidence scoring + freshness decay
    |               Conflict detection between sources
    |               Spatial aggregation (PostGIS)
    v
intelligence/       Rule-based alert detection (Python)
    |               LLM generates: situation briefs, triage ranking,
    |               conflict resolution narratives
    v
FastAPI (port 8000) REST API -- /api/alerts, /api/briefing,
    |               /api/map/*, /api/scenario/*
    v
React + Leaflet     Interactive map, situation panel, demo controls
(port 5173)         React Query polling, Zustand map state
    |
    v
Deployed:           Railway (backend) + Vercel (frontend)
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Supabase + PostGIS | Geospatial queries (ST_DWithin, flood extent polygons) without managing a DB server |
| LLM for language only | Python detects all conditions. Claude only writes natural-language text. Every LLM call has a template fallback. |
| Confidence + half-life on every data point | Stale data is shown at reduced opacity — responders see data freshness at a glance |
| Synthetic data for paid sources | Twitter/X API is paid. Social media simulation is intentional, not a gap. |
| APScheduler in-process | No Redis/Celery dependency. Simpler for a capstone, sufficient for the load. |

---

## LLM Fallback Chain

Every LLM call goes through a three-level fallback so the app never fails silently:

```
1. Claude (claude-sonnet-4-20250514)   -- primary, best reasoning
       |  fails / times out
       v
2. Groq (llama-3.3-70b-versatile)     -- fast, free tier, cloud
       |  fails / not configured
       v
3. Ollama (llama3.2:1b, localhost)     -- fully offline, laptop GPU
       |  not running / unavailable
       v
4. Python template                     -- deterministic, always works
```

The fallback is transparent — the UI shows the same output regardless of which level generated it. Configure which providers are active via environment variables.

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project with the PostGIS extension enabled
- At least one LLM key: `ANTHROPIC_API_KEY` or `GROQ_API_KEY`

### 1. Database

In the Supabase SQL editor:

1. Enable PostGIS: `CREATE EXTENSION IF NOT EXISTS postgis;`
2. Run the full schema from `MASTERPLAN.md` — section "Database Schema"
3. Load seed data:

```bash
cd backend
source venv/Scripts/activate   # Windows
# source venv/bin/activate      # Mac/Linux
python -m seed.odisha_districts
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env
```

Edit `.env`:

```env
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# LLM -- at least one required
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...

# Optional overrides
ANTHROPIC_MODEL=claude-sonnet-4-20250514
LLM_PROVIDER=anthropic          # anthropic | groq | ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
SIMULATION_MODE=false
BRIEFING_INTERVAL_MIN=15
DATA_REFRESH_INTERVAL_SEC=60
CORS_ORIGINS=http://localhost:5173
LOG_LEVEL=INFO
```

Start the server:

```bash
uvicorn main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend
npm install

# Set the backend URL
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

npm run dev   # http://localhost:5173
```

### 4. Local LLM (optional)

For fully offline operation:

```bash
ollama pull llama3.2:1b
ollama serve   # runs at localhost:11434
```

Set `LLM_PROVIDER=ollama` in `.env`.

---

## Cyclone Fani Demo Scenario

The demo replays a compressed version of Cyclone Fani (2019) flooding in the Mahanadi basin. It showcases every system capability — conflict resolution, silent district detection, camp risk alerts, forecast divergence — in a 30-minute walkthrough.

### Start the Demo

1. Ensure the backend is running and seed data is loaded
2. Open the frontend at `http://localhost:5173`
3. Click **Demo Controls** in the bottom toolbar
4. Click **Load Scenario** and select `cyclone_fani`
5. Use **Play** (auto-advance every 3 minutes) or **Step** to advance manually

### What You Will See

| Step | Sim Time | Event |
|------|----------|-------|
| T+0h | Baseline | All gauges normal. IMD forecast shows approaching cyclone. |
| T+3h | Rain begins | Open-Meteo: 80mm/hr over Kendrapara and Jagatsinghpur. |
| T+6h | Contradiction | Naraj gauge crosses warning level. 12 social media reports from Jajpur show flooding — but the CWC gauge there reads normal. AI flags the conflict with an explanation. |
| T+9h | Bridge alert | Naraj crosses danger level. Jenapur bridge reported submerged by 3 independent sources. Route blocked alert fires. Supply convoy needs rerouting. |
| T+12h | Forecast divergence | Boats were pre-deployed to Kendrapara based on earlier forecast — but rainfall concentrated over Jagatsinghpur instead. AI recommends redeployment. |
| T+15h | Silent district | Ganjam district: no reports for 4 hours, district collector unreachable. Silent district alert fires. Population at risk: 3.8M. |
| T+18h | Stale satellite | Satellite imagery arrives — 12 hours old. Confirms some flood areas, contradicts others. Displayed at reduced opacity with a staleness warning. |
| T+21h | Camp at risk | Erasama school relief camp enters the projected flood zone. 340 people need re-evacuation. |
| T+24h | Triage | All scenarios active simultaneously. AI ranks top 3 alerts by urgency, available assets, and time sensitivity. |

### Via API (no UI)

```bash
# Load scenario
curl -X POST http://localhost:8000/api/scenario/load \
  -H "Content-Type: application/json" \
  -d '{"scenario": "cyclone_fani"}'

# Advance one step
curl -X POST http://localhost:8000/api/scenario/tick \
  -H "Content-Type: application/json" \
  -d '{"steps": 1}'
```

---

## Running Tests

```bash
cd backend
source venv/Scripts/activate

# Integration tests -- requires backend running on localhost:8000
pytest tests/test_integration_fani.py -v

# Unit tests (fusion engine)
pytest tests/test_fusion.py -v
```

The integration test suite runs all 9 Fani scenario steps end-to-end and asserts system state at each tick.

---

## Deployment

### Backend — Railway

1. Create a new Railway project and connect this GitHub repo
2. Set the **root directory** to `backend/`
3. Set the **start command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from the `.env` section above
5. Deploy — Railway auto-detects Python and installs from `requirements.txt`

The `railway.toml` in `backend/` configures the build and health check endpoint automatically.

### Frontend — Vercel

1. Create a new Vercel project and connect this GitHub repo
2. Set the **root directory** to `frontend/`
3. Add the environment variable: `VITE_API_BASE_URL=https://your-railway-app.up.railway.app`
4. Deploy — Vercel auto-detects Vite

### CORS

Once deployed, add the Vercel URL to `CORS_ORIGINS` on Railway:

```
CORS_ORIGINS=https://your-app.vercel.app
```

---

## Project Structure

```
.
+-- backend/
|   +-- main.py                  # FastAPI app, CORS, router registration
|   +-- config.py                # Pydantic settings -- all env vars typed here
|   +-- database.py              # Supabase client singleton
|   +-- api/                     # REST endpoints (alerts, assets, briefing, map, scenario)
|   +-- ingestion/               # Data source adapters + APScheduler jobs
|   +-- fusion/                  # Confidence scoring, conflict detection, spatial math
|   +-- intelligence/            # Alert rules (alerts.py), AI briefing (briefing.py)
|   +-- seed/                    # One-time data loaders (districts, gauge stations)
|   +-- simulation/              # Cyclone Fani scenario generator
|   +-- tests/                   # Integration + unit tests
+-- frontend/
|   +-- src/
|   |   +-- components/          # Map, AlertPanel, SituationBrief, DemoControls
|   |   +-- hooks/               # React Query hooks (useAlerts, useBriefing, useMapData)
|   |   +-- store/               # Zustand stores (map state, demo state)
|   +-- index.html
+-- MASTERPLAN.md                # Full specification -- single source of truth
+-- docs/REFERENCE.md            # API reference, enums, scoring tables
+-- graphify-out/                # Auto-generated knowledge graph (AST-only)
```

---

## Confidence and Freshness Model

Every data point carries two quality dimensions visualised on the map:

**Confidence (0.0 to 1.0)** — based on source type and corroboration:

| Source | Base Confidence |
|--------|----------------|
| CWC River Gauge | 0.95 |
| Satellite Imagery | 0.90 |
| District Report (official) | 0.80 |
| IMD Weather Forecast | 0.75 |
| Social Media (3+ corroborating) | 0.65 |
| Social Media (single report) | 0.30 |

Three corroborating sources within 5km and 1 hour boost confidence by +0.25.

**Freshness (half-life decay)** — each source type has a half-life after which its decision value drops 50%:

| Data Type | Half-Life |
|-----------|-----------|
| River gauge reading | 30 min |
| Social media report | 2 hr |
| Road / bridge status | 4 hr |
| Satellite image | 6 hr |

**Map encoding:** Full opacity = fresh data. 50% opacity = past half-life. Dashed border = very stale. Faded + warning icon = source offline.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite + Tailwind CSS |
| Maps | Leaflet.js + react-leaflet |
| State | React Query (server state) + Zustand (map/UI state) |
| Backend | FastAPI + Uvicorn (Python 3.11) |
| Database | Supabase (PostgreSQL + PostGIS) |
| AI | Claude API -> Groq -> Ollama -> template fallback |
| Scheduling | APScheduler (in-process, no Redis needed) |
| Deployment | Railway (backend) + Vercel (frontend) |
