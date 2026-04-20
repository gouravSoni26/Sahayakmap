# Architecture & Design Decisions

This doc explains **why** things are built the way they are. Read this to understand the reasoning — you don't need to ask Claude.

---

## 1. Why these libraries?

### FastAPI (not Flask, not Django)
- **Async native** — we make 5+ concurrent DB calls in `briefing.py` using `asyncio.gather()`. Flask can't do this without hacks.
- **Auto-validation** — Pydantic models + Enums give free HTTP 422 errors for bad input. Django REST Framework does this too but is far heavier.
- **Auto-docs** — Swagger UI at `/docs` for free. Useful for capstone demo.
- **Simple** — no ORM, no migrations framework, no admin panel. We don't need those for a 4-week capstone.

### Supabase + PostGIS (not raw Postgres, not MongoDB)
- **PostGIS** — flood data is inherently geospatial. `ST_DWithin`, `ST_Distance`, `<->` for nearest-neighbor are impossible without it.
- **Supabase** — free tier with REST API, auth, realtime. No server to manage. The Python client is just a REST wrapper around Postgres.
- **Why not MongoDB?** — geospatial queries exist in Mongo, but JOINs don't. We JOIN flood_reports → data_sources → gauge_stations constantly.

### React + Leaflet (not Mapbox, not Google Maps)
- **Free** — Leaflet + OpenStreetMap tiles = no API key, no billing. Mapbox has a free tier but requires sign-up and has request limits.
- **React-Leaflet** — thin React wrappers around Leaflet. We control every marker, popup, and overlay directly.
- **Why not Mapbox GL JS?** — it's better for vector tiles and 3D, but we don't need either. Our overlays are simple circles and polygons.

### Zustand (not Redux, not Context)
- **3 KB, zero boilerplate** — Redux needs actions, reducers, slices. Zustand is one `create()` call.
- **Why not React Context?** — Context re-renders every consumer on any state change. Zustand uses selectors so only affected components re-render.

### React Query (not SWR, not manual fetch)
- **Polling built-in** — `refetchInterval: 30000` polls the backend every 30s. SWR can do this too, but React Query's devtools are better.
- **Cache + stale-while-revalidate** — shows old data instantly while fetching fresh data in background. Critical for a real-time dashboard.

### APScheduler (not Celery, not cron)
- **Single process** — Celery needs Redis/RabbitMQ as a broker. That's another server to deploy. APScheduler runs inside the FastAPI process.
- **Good enough** — we have 6 jobs running at 5-30 min intervals. Celery is for thousands of distributed tasks. This is a capstone, not a production fleet.

### httpx (not requests, not aiohttp)
- **Async** — `requests` is sync-only. We're in an async FastAPI app, so blocking `requests.get()` would block the entire event loop.
- **Why not aiohttp?** — aiohttp works, but httpx has a cleaner API (similar to `requests`) and supports both sync and async with the same interface.

### Anthropic SDK (not raw HTTP, not LangChain)
- **Official SDK** — typed responses, automatic retries, streaming support. Raw HTTP would need manual token counting and error handling.
- **Why not LangChain?** — LangChain adds 50+ dependencies and abstractions we don't need. We make exactly ONE type of LLM call (structured JSON generation). A direct SDK call is 5 lines of code.

### pydantic-settings (not python-dotenv directly)
- **Type safety** — `.env` values are parsed and validated at startup. If `SUPABASE_URL` is missing, the app crashes immediately with a clear error, not 10 minutes later when the first DB call fails.
- **Defaults** — `llm_fallback_to_templates: bool = True` means the app works without any LLM configured.

---

## 2. Why these hardcoded values?

### Temporal (half-lives and thresholds)

| Value | Why |
|-------|-----|
| `GAUGE_HALF_LIFE_MIN = 30` | CWC gauges report every 15 min. After 30 min (2 missed reports), something is probably wrong. |
| `STALE_THRESHOLD = 0.25` | This equals 2 half-lives. After 2 half-lives, data has lost 75% of its decision value. A commander shouldn't trust it. |
| `MIN_OPACITY = 0.2` | Never make data invisible — even stale data is better than no data in a disaster. The commander should see it exists but is old. |
| `ASSET_TRACKER half-life = 15 min` | GPS trackers update every 5-10 min. 15 min = 1-2 missed pings = asset might have lost signal. |

### Spatial (conflict detection)

| Value | Why |
|-------|-----|
| `CONFLICT_RADIUS_KM = 10` | Floods are localised. A social media report 10km from a gauge is "in the same area." Beyond 10km, they could be talking about different floods. |
| `CONFLICT_TIME_WINDOW_HR = 1` | A tweet from 5 hours ago shouldn't contradict a fresh gauge reading. Only compare sources that are temporally close. |
| `nearby_social >= 3` | One person tweeting "flood!" isn't reliable. Three people in the same area = corroboration. This avoids false conflicts from spam/jokes. |
| `cluster >= 4` for social-vs-social | Need at least 2 high AND 2 low severity reports to call it a contradiction. 4 is the mathematical minimum. |

### Confidence scoring

| Value | Why |
|-------|-----|
| `CWC_GAUGE = 0.95` | Calibrated government instruments. 0.95 not 1.0 because equipment can malfunction. |
| `SOCIAL_MEDIA = 0.30` | Single unverified citizen report. Could be exaggeration, wrong location, or spam. |
| `3+ corroborating = +0.25` | Multiple independent citizens reporting the same thing from the same area = very likely real. |
| `PHOTO_BOOST = 0.20` | Image evidence is harder to fake than text. Not +0.30 because photos can be old/reposted. |
| `diversity_bonus = 0.05 per type, max 0.20` | Different source types (gauge + social + satellite) confirming each other is much stronger than 10 tweets saying the same thing. |

### Projection model

| Value | Why |
|-------|-----|
| `transfer_factor = 0.8` | Not all water upstream reaches downstream — some spreads into floodplains. 80% is a conservative estimate for the Mahanadi. |
| `confidence = 0.60` | Projections are inherently uncertain. 0.60 means "more likely than not" but don't bet lives on it without confirmation. |
| `hours_ahead = 6` | Beyond 6 hours, too many variables change (rainfall, dam releases, terrain). Projections past 6h are unreliable. |

### Alert thresholds

| Value | Why |
|-------|-----|
| `SILENT_DISTRICT_HOURS = 4` | Districts report every 2-4 hours. 4h silence = at least one missed report. Could be communication failure during a flood — extremely dangerous. |
| `CAMP_RISK_PROXIMITY_KM = 15` | A flood 15km away can reach a camp in 1-4 hours depending on terrain. Gives time to start evacuation prep. |
| `alert expires_at = 2h` | Flood situations change fast. An alert older than 2h might no longer be accurate — force re-evaluation. |

### Synthetic data generation

| Value | Why |
|-------|-----|
| `severity weights [30,40,20,10]` | Most flood situations are moderate (severity 2-3). Critical/emergency situations are rare. Realistic distribution for training/demo. |
| `random.random() < 0.15` skip rate | 15% chance a district doesn't report = simulates the "silent district" scenario needed for the demo. |
| `corroborating = random.randint(0, 8)` | In real floods, a single incident generates 0-10+ tweets depending on population density. |
| `confidence = 0.30 + corroborating * 0.05, max 0.70` | More retweets/similar reports = higher confidence. Capped at 0.70 because social media alone can never be fully trusted. |

---

## 3. Why this architecture pattern?

### "Code Reasons, LLM Speaks"
The LLM is ONLY used to write natural language. All decisions (which alerts to fire, what severity, what conflicts exist) are made by deterministic Python code.

**Why:** LLMs hallucinate. If the LLM decides "this is severity 5" and it's wrong, people could die. But if Python code decides severity based on `water_level >= danger_level` and the LLM just writes "Jenapur station is above danger level, deploy rescue teams" — worst case the wording is awkward, but the decision is still correct.

**Template fallback:** Every LLM call has a `_template_fallback()`. If Claude API is down during an actual flood, the system still works. The briefing is less eloquent but contains the same data.

### Repository pattern + Dependency Injection
**Why Repository:** All DB queries for a table live in one class. When Supabase changes their API (they have before), you fix ONE file, not every endpoint.

**Why DI (Depends):** UUID validation, existence checks, and 404 responses happen in one reusable function. Without it, every endpoint repeats the same 5 lines of "is this a valid UUID? does this row exist?"

### Confidence × Freshness (not just severity)
Traditional disaster systems show severity only. A severity-5 alert from 6 hours ago might be resolved, but it still shows as red.

**Our model:** `effective_value = confidence × freshness_factor`. A high-confidence report that's 2 hours old (past half-life) fades visually. The commander sees at a glance: "this is old, I need fresh data" vs "this is real-time and trustworthy."

### Single table for all flood reports
Gauge readings, social media, district reports — all go into `flood_reports` with a `source_id` FK pointing to `data_sources`.

**Why:** The fusion engine treats all data uniformly. It doesn't care WHERE the data came from — it just scores confidence and freshness. This also means the Cyclone Fani replay demo works by inserting synthetic rows into the same table. The rest of the system can't tell it's a simulation.

### Exponential decay (not linear)
`freshness = 0.5 ^ (age / half_life)`

**Why not linear?** Linear decay implies data loses value at a constant rate. In reality, a gauge reading is nearly as good after 5 minutes as after 0 minutes, but after 2 hours it's drastically less useful. Exponential decay captures this — fast drop-off after the half-life, slow before it.

### Haversine distance (not Euclidean)
`haversine_km()` computes great-circle distance on a sphere.

**Why not just `sqrt((lat2-lat1)² + (lng2-lng1)²)`?** Because at latitude 20° (Odisha), 1 degree of longitude ≠ 1 degree of latitude in km. Euclidean distance in lat/lng space gives wrong answers. At 10km scale the error is small (~2%), but at 50km it matters.

**Why not PostGIS ST_Distance?** Because conflict detection runs in Python on already-fetched data. Making a DB call per pair of reports would be N² round-trips. Haversine in Python is fast enough for <1000 reports.

---

## 4. What could be different (alternatives you'd see in production)

| Current | Production alternative | Why we didn't |
|---------|----------------------|---------------|
| APScheduler (in-process) | Celery + Redis | Needs another server. Overkill for 6 jobs. |
| Sequential DB queries in engine.py | `asyncio.gather()` (already done in briefing.py) | engine.py still sequential — refactoring planned |
| `raw_payload->>'station_code'` JSON | Proper FK `gauge_station_id` on flood_reports | Schema change needed, deferred |
| Haversine in Python | PostGIS `ST_DWithin` in SQL | Would require restructuring to do conflict detection at DB level |
| MD5 hash for cache check | Redis cache with TTL | No Redis in stack. MD5 of analysis dict is simple and works. |
| Single-process FastAPI | Gunicorn + uvicorn workers | Single user (demo). Multi-worker adds complexity for no benefit. |
| Open-Meteo (free) | IMD API (official) | IMD has no public API. Would need scraping + approval. |
| Synthetic social data | Twitter/X API | Costs $100+/month. Synthetic lets us guarantee demo scenarios. |
