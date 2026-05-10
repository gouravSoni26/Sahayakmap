# SahayakMap — How it all works, explained like you're 10

---

## The Big Question First

Imagine a flood is happening in Odisha. A rescue commander named Rajesh needs to know:
- Where is the water the worst RIGHT NOW?
- Where will it be worst in 6 hours?
- Where should he send his boats?

The problem? **The information is scattered everywhere** — river sensors, weather satellites, Twitter posts, government reports. Nobody has put it all together. SahayakMap does exactly that.

Think of it like this: **your body has eyes, ears, skin, and nose — all sensing the world. Your brain fuses it into one picture. SahayakMap is the brain for flood data.**

---

## The 5 Layers — From raw world to decision

```
WORLD (floods, rain, rivers)
        |
[1] INGESTION  — "Go collect the facts"
        |
[2] DATABASE   — "Remember the facts"
        |
[3] FUSION     — "Trust the facts, discard old/weak ones"
        |
[4] AI (Claude)— "Understand what the facts MEAN"
        |
[5] FRONTEND   — "Show Rajesh a map he can act on"
```

Let's go through each one.

---

## Layer 1 — INGESTION (The Scouts)

**Analogy:** Imagine you send scouts in every direction — one to check the river, one to watch the sky, one to read Twitter — and they all radio back to you.

In the code, these scouts are called **ingesters** and they run on a timer (every 15 minutes, every hour, etc.) using something called `APScheduler` — think of it as an alarm clock that wakes up code automatically.

What do the scouts go fetch?

| Scout | Source | What it gets |
|---|---|---|
| River Scout | CWC Gauge API | Water level in meters at each river station |
| Weather Scout | Open-Meteo API | How much rain is falling/coming |
| Road Scout | OSM (OpenStreetMap) | Which roads and bridges are open |
| Social Scout | Synthetic Twitter posts | "My village is flooded!" type reports |
| Satellite Scout | Synthetic imagery | Which areas are under water from above |

Each scout brings back a **`FloodReport`** — a single data point with: *where*, *what*, *when*, and — crucially — **how much to trust it** (confidence score, 0.0 to 1.0).

A government gauge reading? 0.95 trust. A random tweet? 0.30 trust. Three tweets saying the same thing? 0.65 trust. **The system knows not all information is equal.**

---

## Layer 2 — DATABASE (The Memory)

**Analogy:** Your brain can't just hold every sensory signal forever. It stores things in memory. The database is SahayakMap's memory.

The database is **Supabase** — which is just PostgreSQL (a very popular database) with a superpower called **PostGIS** added on top.

What's PostGIS? Normal databases store numbers and text. PostGIS lets you store **shapes and locations** — points, lines, polygons — and ask questions like:

> "Give me all flood reports within 50 km of this bridge."

Normal database: "I don't understand km or bridge shapes."
PostGIS: "Sure, here you go."

Key tables and what they store:

| Table | What's inside |
|---|---|
| `flood_reports` | Every data point collected: location, severity 1-5, water level, confidence, timestamp |
| `gauge_stations` | The physical river sensors: where they are, what "danger level" means for each |
| `alerts` | Auto-generated warnings: FLOOD_RISING, BRIDGE_SUBMERGED, CAMP_AT_RISK, etc. |
| `rescue_assets` | Boats, helicopters, trucks — where they are, what status |
| `relief_camps` | Evacuation camps — how full, how safe, how many hours until flood reaches them |
| `districts` | Odisha district boundaries as actual polygon shapes |
| `situation_briefs` | AI-written summaries of the current situation |

Everything has a **timestamp and an `expires_at`** field. Old data automatically becomes stale — like milk with an expiry date.

---

## Layer 3 — FUSION (The Judge)

**Analogy:** You asked 5 people "Is it raining outside?" Three say yes, one says no, one says "maybe drizzling." How do you decide? You use your judgment — who do you trust more? How long ago did they look?

This is exactly what the Fusion layer does. It's the most clever part of the system.

Two key concepts:

### Confidence Score (0.0 to 1.0)
How much do we trust this data point?

- River gauge sensor: **0.95** (machine, calibrated, reliable)
- Official district report: **0.80** (human but verified)
- Single tweet: **0.30** (anonymous, unverified)
- Three tweets saying same thing: **0.65** (they're corroborating each other)

The fusion code also **boosts confidence** when multiple sources agree:
```
2 sources agreeing  → +0.15
3+ sources agreeing → +0.25
Official + social media agree → +0.20
```

### Freshness / Half-Life
**Analogy:** A weather forecast from 5 minutes ago is very useful. One from yesterday? Not so much. The older the data, the less weight it gets.

Each data type has a **half-life** (like radioactive decay):

| Data | Half-life |
|---|---|
| River gauge reading | 30 minutes |
| Weather forecast | 1 hour |
| Social media report | 2 hours |
| Satellite image | 6 hours |

The formula is:

```
effective_confidence = base_confidence x (0.5 ^ (age / half_life))
```

In plain words: **every half-life period, the data's trustworthiness halves.** A gauge reading from 2 hours ago is only worth 25% of a fresh one.

The visual result on the map? **Opacity.** Fresh, trusted data shows as bright and solid. Old, uncertain data shows as faded and transparent. Rajesh can literally *see* what to trust.

---

## Layer 4 — AI / INTELLIGENCE (The Analyst)

**Analogy:** You've now got all the cleaned, trusted data on a table. But data isn't intelligence. "River at 12.3m, danger level 11.5m" is a number. "The Mahanadi is 0.8m above danger level and rising — Cuttack district has 4-6 hours before critical infrastructure floods" is **understanding**. That's what the AI does.

The AI (Claude via Anthropic API) gets called in **three situations**:

### 1. Situation Briefing
Every hour (or on demand), the system sends Claude a structured prompt containing:
- Current water levels at all gauge stations
- Active alerts
- Asset positions
- Weather forecast
- Recent flood reports

Claude reads this and writes a **natural language briefing** — like a staff officer's morning report — with:
- Summary of current situation
- Key risks (what might go wrong in next 6 hours)
- Specific recommendations ("Move Boat-7 from Puri to Cuttack now")

**Critical rule in the code:** Python does ALL the math and analysis. Claude only translates numbers into words. This is intentional — LLMs can hallucinate numbers, but they're great at natural language. So we never ask Claude "what is the water level?" — we tell Claude "the water level is 12.3m, write a sentence about it."

### 2. Alert Generation
Python code detects the patterns. Example:
```
if water_level > danger_level:               → generate FLOOD_RISING alert
if bridge.flood_tolerance < water_level:     → generate BRIDGE_SUBMERGED alert
if camp.elevation < projected_water_level:   → generate CAMP_AT_RISK alert
```

For each alert, Claude writes a **human-readable description** and **action phrase** (e.g., "Evacuate Camp B immediately — estimated 3 hours until flood reaches elevation").

### 3. Fallback (Ollama / Local LLM)
If the Claude API is down or too expensive, the system falls back to **Llama 3.2** running locally via Ollama. The output is less polished but the system keeps working. There's also a **template fallback** — pure Python string templates — if even Ollama is down.

---

## Layer 5 — BACKEND / API (The Waiter)

**Analogy:** The kitchen (database + fusion + AI) is cooking. The customer (frontend map) is hungry. The waiter stands between them, takes orders, brings food. The waiter is the **FastAPI backend**.

FastAPI is a Python framework that creates **REST API endpoints** — URLs that the frontend can call to get data.

Key endpoints:

```
GET  /api/map/data        → Give me everything for the map (gauges, reports, assets, routes)
GET  /api/alerts          → Give me current warnings sorted by severity
GET  /api/briefing        → Give me the latest AI situation summary
GET  /api/gauges          → Give me all river sensor readings
GET  /api/assets          → Give me all rescue team positions
POST /api/scenario/tick   → Advance the simulation forward by N minutes
PUT  /api/alerts/{id}/ack → Mark this alert as "seen" by Rajesh
```

The frontend never touches the database directly. **It only talks to these API URLs.** This is a core security and architecture principle — separation of concerns.

---

## Layer 6 — FRONTEND (The Dashboard)

**Analogy:** All the intelligence in the world is useless if the commander can't see it in 2 seconds. The frontend is the cockpit — dials, maps, alerts — everything at a glance.

Built with React + Vite + Leaflet.js:

**React** — The UI framework. Think of it as LEGO — you build small pieces (components) and snap them together. Every panel, card, button is a component.

**Leaflet.js** — The map engine. Renders the actual map of Odisha with tiles from OpenStreetMap. On top of that map, SahayakMap draws:
- Colored circles at gauge stations (green → yellow → red based on water level)
- Faded vs bright markers (opacity = freshness x confidence — from the fusion layer)
- Route lines colored by status (green = open, red = blocked, grey = submerged)
- Camp markers with their flood risk countdown
- Asset positions (boats, helicopters)

**React Query** — Handles automatic data refreshing. Every 30 seconds it silently calls the API and updates the map. Rajesh never has to press "refresh."

**Zustand** — Lightweight state management. Remembers things like "which district is selected" or "is the sidebar open" across the whole app.

---

## The Complete Flow — One Scenario

Let's trace a single event from the real world to Rajesh's screen:

```
1. It starts raining heavily upstream (Hirakud dam area)

2. INGESTION (every 15 min):
   Weather scout calls Open-Meteo → gets "80mm rainfall forecast next 3h"
   River scout calls CWC API → gauge reads "water rising 0.4m/hr"
   → Both saved as FloodReports in Supabase with confidence scores

3. FUSION (on every API call):
   Checks ages → both are fresh → full confidence
   Two sources agree on rising water → confidence boosted +0.15
   Effective confidence: 0.95 (gauge) x boost = ~0.99

4. ALERT GENERATION (Python logic, every 5 min):
   current_level (12.1m) + rise_rate (0.4m/hr) x 6h = 14.5m
   danger_level = 11.5m → 14.5 >> 11.5
   → Creates FLOOD_RISING alert, severity=4 (CRITICAL)
   → Calls Claude: "Write a 2-sentence action description for this alert"
   → Claude returns: "Mahanadi rising rapidly near Cuttack. Deploy additional
      boats to sectors 7 and 9 within 2 hours."

5. API (/api/alerts):
   Frontend calls this endpoint every 30 seconds
   Gets back the new CRITICAL alert with Claude's description

6. FRONTEND:
   Alert panel lights up red
   Map shows gauge marker turning red, pulsing
   Sidebar shows AI briefing with Rajesh's action recommendations
   Rajesh sees it → clicks "Acknowledge" → PUT /api/alerts/{id}/ack

7. Rajesh deploys boats. Lives saved.
```

---

## The Architecture in One Picture

```
+----------------------------------------------------------+
|                    REACT FRONTEND                        |
|  Leaflet Map | Alert Panel | Briefing Sidebar | Assets   |
|         (React Query polls every 30 seconds)             |
+----------------------------------------------------------+
                          | HTTP REST API
+----------------------------------------------------------+
|                   FASTAPI BACKEND                        |
|  /api/map/data | /api/alerts | /api/briefing | ...       |
|                                                          |
|   FUSION ENGINE              INTELLIGENCE ENGINE         |
|   (confidence score +        (Claude API for             |
|    freshness decay)           natural language)          |
+----------------------------------------------------------+
                          | SQL queries
+----------------------------------------------------------+
|                SUPABASE (PostgreSQL + PostGIS)           |
|  flood_reports | alerts | gauge_stations | assets | ...  |
|                          |                               |
|              INGESTERS (APScheduler)                     |
|  Open-Meteo | CWC Gauges | OSM Roads | Synthetic data    |
+----------------------------------------------------------+
                          | (fallback)
+----------------------------------------------------------+
|           OLLAMA (Llama 3.2 — local LLM fallback)       |
+----------------------------------------------------------+
```

---

## The One Sentence Summary

**SahayakMap automatically collects flood data from many sources, scores each piece of data for trustworthiness and freshness, fuses conflicting information into a single coherent picture, asks Claude to explain what it means in plain English, and shows it all on an interactive map so a disaster commander can make life-saving decisions in seconds.**

That's it. Every file in this project exists to serve one of those five steps.
