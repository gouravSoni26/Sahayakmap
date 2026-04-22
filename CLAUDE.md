# CLAUDE.md

## Project

**SahayakMap** — Real-time flood intelligence platform for India's NDRF disaster responders.
Capstone deadline: **May 16, 2026**. Focus region: Mahanadi River Basin, Odisha.

## Planning Documents

| File | Purpose |
|------|---------|
| `MASTERPLAN.md` | Single source of truth — full stack, DB schema, API, UI, weekly plan |
| `docs/REFERENCE.md` | API endpoints, enums, scoring tables, coding patterns |
| `MASTERPLAN_LOCAL_LLM.md` | Llama 3.2:1b via Ollama fallback architecture |
| `TOOL_CALLING_ARCHITECTURE.md` | Tool calling patterns for LLM layer |

## Development Commands

### Backend (FastAPI)
```bash
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000
pytest tests/test_fusion.py -v
python -m seed.odisha_districts
```

### Frontend (React + Vite)
```bash
cd frontend && npm install
npm run dev          # port 5173
npm run build
```

### Local LLM
```bash
ollama pull llama3.2:1b
ollama serve         # localhost:11434
```

### Database
Supabase SQL editor — schema in MASTERPLAN.md. PostGIS must be enabled first.

## Architecture (summary)

```
ingestion/ → flood_reports table → fusion/ (confidence + freshness) → intelligence/ (briefing, alerts) → FastAPI → React
```

**LLM rule:** Python does ALL analysis. LLM only generates natural language (briefings, action phrases, conflict descriptions). Every LLM call has a template fallback.

**Confidence model:** Every data point has confidence (0.0–1.0) + half-life. Displayed as opacity on map. Details in `docs/REFERENCE.md`.

**Simulation:** `POST /api/scenario/load` + `/tick` — synthetic data into same tables. Frontend has demo controls.

## Key Design Decisions

1. Supabase + PostGIS for geospatial (ST_DWithin, ST_Distance)
2. APScheduler for ingestion intervals
3. React Query for polling, Zustand for map state
4. Synthetic data is intentional (Twitter/X API is paid)

## Environment Variables

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `GROQ_API_KEY`, `SIMULATION_MODE`, `VITE_API_BASE_URL`

## graphify

Knowledge graph at `graphify-out/`. For architecture/codebase questions, read `graphify-out/GRAPH_REPORT.md` instead of exploring files manually. After modifying code, run `graphify update .` (AST-only, no API cost).

## SahayakMap Project Rules

- Always use Repository Pattern (XxxRepository class) for DB logic
- Always use Query Builder Pattern (Filter dataclass) for optional params
- Never refactor files not mentioned in the current task
- Fusion functions should be standalone — no class wrapping unless asked
- Match existing enum and UUID patterns from alerts.py / assets.py
- Never select("*") — always use explicit LIST_COLUMNS / UPDATE_COLUMNS

## Deferred Items
- Issue #18 (Ollama URL config) — do NOT touch until Week 3 intelligence layer