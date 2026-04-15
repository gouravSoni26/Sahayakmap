# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**SahayakMap** — Real-time flood intelligence platform for India's NDRF disaster responders.
Capstone deadline: **May 16, 2026**. Primary user: NDRF battalion commander in Cuttack, Odisha.
Focus region: Mahanadi River Basin, Odisha.

## Planning Documents (read before coding)

| File | Purpose |
|------|---------|
| `MASTERPLAN.md` | Single source of truth — full stack, DB schema, API design, UI layout, week-by-week plan |
| `MASTERPLAN_LOCAL_LLM.md` | Adapted architecture using Llama 3.2:1b via Ollama instead of Claude API |
| `TOOL_CALLING_ARCHITECTURE.md` | Tool calling patterns for the LLM intelligence layer |

## Development Commands

Commands assume the structure defined in MASTERPLAN.md (not yet scaffolded as of Apr 15).

### Backend (FastAPI)
```bash
# Install dependencies
cd backend && pip install -r requirements.txt

# Run dev server
uvicorn main:app --reload --port 8000

# Run a specific test
pytest tests/test_fusion.py -v
pytest tests/ -k "test_conflict" -v

# Seed reference data
python -m seed.odisha_districts
python -m seed.gauge_stations
python -m seed.relief_camps
python -m seed.routes_bridges
```

### Frontend (React + Vite)
```bash
cd frontend && npm install
npm run dev          # Vite dev server on port 5173
npm run build        # Production build
npm run preview      # Preview production build
```

### Local LLM (Ollama)
```bash
ollama pull llama3.2:1b
ollama serve         # starts on http://localhost:11434
```

### Database
Run migrations in Supabase SQL editor — the complete schema is in MASTERPLAN.md under "Database Schema (Supabase + PostGIS)". PostGIS extension must be enabled first.

## Architecture

### Directory Structure
Defined in MASTERPLAN.md. Key layout:
```
sahayakmap/
├── backend/
│   ├── ingestion/     # data fetchers (CWC gauge, Open-Meteo, OSM, synthetic generators)
│   ├── fusion/        # confidence scoring, staleness, spatial conflict detection
│   ├── intelligence/  # AI briefing, alert triage, flood projection
│   ├── api/           # FastAPI route handlers
│   └── seed/          # one-time reference data loaders
└── frontend/
    └── src/
        ├── components/Map/    # Leaflet layers (gauges, flood overlay, assets, routes)
        ├── components/Panel/  # Situation panel, alert list, asset panel
        ├── hooks/             # react-query data fetchers
        └── stores/            # Zustand map state
```

### Data Flow
```
Real sources (Open-Meteo, OSM, CWC scrape)  ─┐
Synthetic sources (social media, district      ├─→ flood_reports table
  reports, satellite overlay)                ─┘        │
                                                        ▼
                                              fusion/ engine
                                            (confidence + freshness + conflict detection)
                                                        │
                                                        ▼
                                            intelligence/ layer
                                            (briefing, alerts, triage, projection)
                                                        │
                                                        ▼
                                              FastAPI → React frontend
```

### LLM Architecture — "Code Reasons, LLM Speaks"

**Primary choice: Claude API** (`claude-sonnet-4-20250514`) for full reasoning capability.
**Local fallback: Ollama + Llama 3.2:1b** — see `MASTERPLAN_LOCAL_LLM.md`.

Rule: **Python code does ALL analysis** (scoring, sorting, conflict classification, flood projection). The LLM is called only to:
1. Generate the 2-3 sentence narrative summary in a situation brief
2. Phrase the top recommended action in natural language
3. Write one-sentence conflict descriptions
4. Classify free-text social media reports

Every LLM call must have a template-based fallback. The system must produce useful output even with the LLM disabled.

### Confidence + Freshness Model

Every data point has a **confidence score (0.0–1.0)** and a **half-life** (time after which decision value drops 50%). This is the core UI differentiator — displayed as opacity on the map and explicit staleness indicators. See MASTERPLAN.md for the full scoring table.

### Simulation Mode

`POST /api/scenario/load` + `POST /api/scenario/tick` drive the "Cyclone Fani Replay" demo. Synthetic data inserts into the same tables as real data — the rest of the system is unaware it's a simulation. Frontend has a demo controls bar.

## Key Design Decisions

1. **Supabase + PostGIS** for all geospatial queries — use `ST_DWithin`, `ST_Distance`, `<->` operator for nearest-neighbor. Schema is in MASTERPLAN.md.
2. **APScheduler** runs ingestion jobs on fixed intervals (gauge: 15 min, weather: 30 min, synthetic social: variable).
3. **React Query** for all frontend data fetching — polling intervals vary by data type.
4. **Zustand** for shared map UI state (selected layer, active alert, time filter).
5. **Synthetic data is intentional** — Twitter/X API is paid. Synthetic generators are designed to produce the specific contradiction/silent-district/forecast-divergence scenarios the demo requires.

## Environment Variables

Defined in `.env.example` in MASTERPLAN.md. Key vars:
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — backend DB access
- `ANTHROPIC_API_KEY` — Claude API (primary LLM)
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL` — local LLM fallback
- `GROQ_API_KEY` — cloud Llama fallback for deployed version
- `SIMULATION_MODE=false` — set true to enable demo scenario controls
- `VITE_API_BASE_URL` — frontend points to backend
