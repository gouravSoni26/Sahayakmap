# SahayakMap — Masterplan (Local LLM Edition)

## Using Llama 3.2:1B via Ollama

This is an adapted version of the SahayakMap masterplan designed to run entirely
with a local LLM (Llama 3.2 1B) via Ollama. Every architectural decision accounts
for the capabilities and limitations of a small parameter model.

---

## PART 1: Honest Assessment — Claude Sonnet vs Llama 3.2:1B

### What Changes When You Drop from 200B+ to 1B Parameters

| Capability | Claude Sonnet 4 | Llama 3.2:1B | Impact on SahayakMap |
|-----------|-----------------|--------------|---------------------|
| Complex multi-step reasoning | Excellent | Poor | Cannot do "analyze 5 data sources, find contradictions, reason about causes, generate recommendations" in one call |
| Structured JSON output | Reliable | Inconsistent | Often produces malformed JSON, missing fields, or adds extra text around JSON |
| Spatial reasoning | Good | Very limited | Cannot reliably reason about "district X is upstream of Y, so flooding there means Y floods in 6 hours" |
| Following complex system prompts | Excellent | Weak | Long system prompts get ignored or partially followed. Short, focused prompts only |
| Context window | 200K tokens | 2048-4096 tokens | Cannot feed all gauge data + social media + routes in one call. Must pre-filter aggressively |
| Nuanced language generation | Excellent | Basic but functional | Situation briefs will be simpler, less insightful. Adequate for templates |
| Classification tasks | Excellent | Good | Binary/categorical classification (severity HIGH/MED/LOW) works well even at 1B |
| Extraction tasks | Excellent | Decent | Pulling structured fields from text is feasible with clear examples |
| Summarization | Excellent | Adequate | Can summarize short texts. Struggles with multiple documents |
| Hallucination rate | Low | High | Will confidently generate plausible-sounding but wrong spatial/temporal claims |
| Inference speed (CPU) | N/A (API) | ~5-15 tok/sec | Each call takes 5-30 seconds on CPU. Must minimize number of calls |
| Inference speed (GPU) | N/A (API) | ~30-80 tok/sec | Faster but still design for fewer, smaller calls |
| Cost | ~$3-10/day at scale | $0 (electricity only) | Main advantage — completely free, completely offline |
| Privacy | Data leaves machine | Data stays local | Better for sensitive disaster data |
| Availability | Needs internet | Works offline | Critical advantage during actual disasters when connectivity is spotty |

### The 5 Critical Drawbacks

**1. Reasoning Depth is Shallow**
Claude Sonnet can receive 5 contradictory data sources and produce a nuanced analysis
explaining why the gauge says safe but social media says flooding (drainage congestion
vs river overflow). Llama 1B will either pick one source arbitrarily, generate a
generic "the situation is concerning" response, or hallucinate a causal explanation.

**Mitigation:** Move reasoning into CODE, not the LLM. Write Python functions that
detect contradictions, classify them by type, and compute severity. Use the LLM only
to convert the code's structured output into human-readable text.

**2. JSON Output is Unreliable**
The original masterplan relies on Claude returning well-formed JSON with specific
fields. Llama 1B frequently:
- Wraps JSON in markdown code fences
- Omits required fields
- Adds conversational text before/after the JSON
- Produces syntactically invalid JSON (trailing commas, unquoted keys)

**Mitigation:** Always parse with fallbacks. Use regex to extract JSON from surrounding
text. Define strict Pydantic models and validate. Have a default/fallback response for
every LLM call. Consider using Ollama's JSON mode (`format: "json"`) which constrains
output to valid JSON.

**3. Context Window is Tiny**
With 2048-4096 tokens, you cannot feed the model a full situation report. The original
masterplan's briefing prompt alone (system prompt + all gauge data + social media +
routes + assets) would exceed the context window.

**Mitigation:** Pre-compute everything in Python. Feed the LLM only a compressed
summary of the pre-computed analysis. The LLM's job shrinks from "analyze all data
and generate insights" to "convert this structured summary into a readable paragraph."

**4. Long System Prompts Get Ignored**
The original masterplan has elaborate system prompts with detailed rules. Llama 1B
will follow the first few instructions and forget the rest. Multi-paragraph system
prompts are wasted tokens.

**Mitigation:** Keep system prompts under 150 words. One task per call. Use few-shot
examples instead of abstract rules. The model learns from examples much better than
from instructions.

**5. Hallucination on Domain Knowledge**
If you ask Llama 1B "What is the danger level of the Mahanadi at Naraj?", it will
generate a confident-sounding number that is completely fabricated. It does not know
Indian river geography.

**Mitigation:** NEVER ask the LLM for facts. All facts come from the database. The
LLM only transforms pre-verified data into natural language. This is the single most
important architectural rule.

---

## PART 2: The Design Pattern — "Code Reasons, LLM Speaks"

### Architecture Shift

**Original (Claude Sonnet):**
```
Raw Data → Ingestion → LLM (analyze + reason + generate) → Output
           The LLM does the heavy lifting
```

**Adapted (Llama 1B):**
```
Raw Data → Ingestion → Python Logic (analyze + reason) → Structured Result → LLM (narrate) → Output
           Python does the heavy lifting, LLM just writes the final text
```

This is the core insight: **treat the 1B model as a natural language interface, not
a reasoning engine.** All analysis, conflict detection, severity scoring, spatial
reasoning, and recommendations happen in deterministic Python code. The LLM's only
job is to take the code's structured output and convert it into a sentence or paragraph
that Rajesh can read.

### Example: Conflict Resolution

**Claude Sonnet approach (original):**
```
Prompt: "The CWC gauge at Naraj reads 24.5m (below danger level 25.5m) but
47 social media reports from Jajpur show knee-deep flooding. Analyze this
contradiction, explain possible causes, and recommend what to tell the commander."

Response: "The contradiction likely stems from drainage congestion rather than
river overflow. The Naraj gauge measures the Mahanadi's main channel, but Jajpur
is experiencing urban flooding from heavy localized rainfall that overwhelms storm
drains. Both sources are correct — they're measuring different phenomena. Recommend
treating Jajpur as a genuine flood zone (severity 3) despite the gauge reading,
and flag the distinction for the commander..."
```

**Llama 1B approach (adapted):**
```python
# Step 1: Python detects the contradiction
def detect_conflicts(gauge_data, social_reports):
    conflicts = []
    for gauge in gauge_data:
        nearby_reports = get_reports_within_km(gauge.location, 30, social_reports)
        if gauge.water_level < gauge.warning_level and len(nearby_reports) >= 5:
            avg_severity = mean([r.severity for r in nearby_reports])
            if avg_severity >= 3:
                conflicts.append({
                    "type": "GAUGE_VS_SOCIAL",
                    "gauge_station": gauge.name,
                    "gauge_level": gauge.water_level,
                    "gauge_status": "BELOW_WARNING",
                    "social_report_count": len(nearby_reports),
                    "social_avg_severity": avg_severity,
                    "affected_area": nearby_reports[0].district,
                    "likely_cause": "DRAINAGE_CONGESTION",  # rule-based
                    "recommended_severity": max(3, round(avg_severity)),
                    "confidence": min(0.7, 0.3 + len(nearby_reports) * 0.05)
                })
    return conflicts

# Step 2: LLM converts to natural language
prompt = f"""Write one sentence describing this flood situation for a rescue commander.

Data: Gauge at {c['gauge_station']} reads {c['gauge_level']}m (safe).
But {c['social_report_count']} citizen reports show flooding in {c['affected_area']}.
Likely cause: drainage congestion from local rainfall.
Severity: {c['recommended_severity']}/5.

Example: "Jajpur district shows flooding from drainage congestion (23 citizen reports)
despite normal Mahanadi gauge levels — treat as severity 3, local rainfall origin."

Sentence:"""
```

The Python code does ALL the reasoning. The LLM writes ONE sentence.
This is reliable even with a 1B model.

---

## PART 3: Strategies to Maximize Llama 1B Effectiveness

### Strategy 1: One Task Per Call

**Bad (too complex for 1B):**
```
Analyze these 5 alerts, rank them by urgency considering population,
time sensitivity, and available assets, then generate recommendations.
```

**Good (single focused task):**
```
Which is more urgent? Answer only A or B.
A: Bridge submerged on supply route, convoy 45 min away
B: Water level rising in district with 50,000 people, currently not dangerous

Answer:
```

### Strategy 2: Few-Shot Examples Over Instructions

**Bad (abstract instruction):**
```
System: Generate a concise situation summary considering data freshness,
source reliability, and spatial coverage. Flag any silent districts.
```

**Good (concrete examples):**
```
Convert this data into a situation summary.

Data: Naraj gauge: 26.3m (DANGER), rising 0.3m/hr. Jajpur: 47 reports, severity 4.
Ganjam: 0 reports in 4 hours (SILENT). Boats: 3 in Kendrapara, 0 in Jagatsinghpur.

Summary: CRITICAL — Naraj gauge at 26.3m and rising fast. Jajpur heavily flooded
with 47 ground reports. WARNING: Ganjam district silent for 4 hours, possible
communication failure. Asset gap: Jagatsinghpur has zero boats despite active flooding.

Data: {actual_current_data}

Summary:
```

### Strategy 3: Constrained Output Formats

**Bad (open-ended):**
```
What should the commander do about the flooding in Jagatsinghpur?
```

**Good (fill-in-the-blank):**
```
Complete this alert message. Use ONLY the data provided. Do not add any facts.

ALERT: {alert_type}
Location: {location}
Severity: {severity}/5
Situation: [write 1 sentence using the data below]
Action needed: [write 1 sentence]

Data: Water at 27.1m (danger: 25.5m), rising 0.4m/hr, 2 boats available 60km away,
estimated travel 3 hours, affected population 45,000.
```

### Strategy 4: Use Ollama's JSON Mode

Ollama supports `format: "json"` which constrains the model to output valid JSON.
This eliminates the most common failure mode.

```python
import httpx

async def llm_classify(text: str, categories: list[str]) -> str:
    response = await httpx.post("http://localhost:11434/api/generate", json={
        "model": "llama3.2:1b",
        "prompt": f'Classify this flood report into one category.\n\nReport: "{text}"\n\nCategories: {categories}\n\nRespond with JSON: {{"category": "...","confidence": 0.0-1.0}}',
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,  # low temperature for deterministic output
            "num_predict": 50    # limit output length
        }
    })
    result = response.json()
    return json.loads(result["response"])
```

### Strategy 5: Template-Based Generation with LLM Fill

Instead of asking the LLM to generate a full briefing, pre-build the template
in Python and use the LLM only to fill specific gaps.

```python
def generate_briefing(analysis: dict) -> str:
    """Python builds 90% of the briefing. LLM fills the narrative gaps."""

    # These parts are pure Python — no LLM needed
    header = f"SITUATION BRIEF — {analysis['timestamp']}"
    gauge_summary = format_gauge_table(analysis['gauges'])
    alert_list = format_alerts(analysis['alerts'])
    asset_table = format_assets(analysis['assets'])
    freshness = format_freshness(analysis['sources'])

    # Only use LLM for the 2-3 sentence narrative summary
    narrative = await llm_narrate(analysis['key_findings'])

    # Only use LLM for action recommendation phrasing
    action_text = await llm_phrase_action(analysis['top_recommendation'])

    return f"""
{header}

OVERVIEW: {narrative}

GAUGE STATUS:
{gauge_summary}

ACTIVE ALERTS ({len(analysis['alerts'])}):
{alert_list}

RECOMMENDED ACTION: {action_text}

ASSET POSITIONS:
{asset_table}

DATA FRESHNESS:
{freshness}
"""
```

### Strategy 6: Validation and Retry

Always validate LLM output. If it fails, retry once. If it fails again, use the
fallback (which is the Python-generated structured text without LLM narration).

```python
async def safe_llm_call(prompt: str, schema: type[BaseModel], max_retries: int = 2) -> BaseModel | None:
    for attempt in range(max_retries):
        try:
            raw = await call_ollama(prompt, format="json")
            parsed = json.loads(raw)
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt < max_retries - 1:
                continue  # retry
            logger.warning(f"LLM output failed validation after {max_retries} attempts: {e}")
            return None  # caller uses fallback
```

### Strategy 7: Pre-Compute Embeddings for Semantic Matching (Optional/Advanced)

If you have time, use Llama 3.2 1B's embedding capability (or a smaller embedding
model like `nomic-embed-text` via Ollama) to do semantic similarity between new
social media reports and known flood patterns. This is a task where even small
models excel.

```python
# "Does this report describe a bridge submersion?"
report_embedding = await get_embedding("Water over the bridge near Jenapur, vehicles stuck")
bridge_pattern = await get_embedding("Bridge submerged, road impassable, vehicles cannot cross")
similarity = cosine_similarity(report_embedding, bridge_pattern)
# similarity > 0.8 → classify as BRIDGE_SUBMERGED
```

---

## PART 4: Complete Adapted Tech Stack

| Layer | Technology | Change from Original |
|-------|-----------|---------------------|
| **Frontend** | React 18 + Vite + Tailwind CSS | No change |
| **Maps** | Leaflet.js + react-leaflet | No change |
| **Backend** | FastAPI (Python 3.11+) | No change |
| **Database** | Supabase (free tier) + PostGIS | No change |
| **AI/LLM** | **Ollama + Llama 3.2:1b (local)** | **CHANGED — runs locally, no API key needed** |
| **Weather API** | Open-Meteo | No change |
| **Geocoding** | Nominatim (OSM) | No change |
| **Deployment** | Vercel (frontend) + Railway (backend) | Backend needs Ollama — use local or a GPU-enabled host |

### Ollama Setup

```bash
# Install Ollama (if not already done)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model
ollama pull llama3.2:1b

# Verify it's running
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:1b",
  "prompt": "Hello",
  "stream": false
}'
```

### Python Ollama Client

```python
# backend/llm/client.py
import httpx
import json
from pydantic import BaseModel

OLLAMA_BASE = "http://localhost:11434"
MODEL = "llama3.2:1b"

async def generate(
    prompt: str,
    system: str = "",
    temperature: float = 0.2,
    max_tokens: int = 200,
    json_mode: bool = False
) -> str:
    """Call Ollama API with sensible defaults for our use case."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "top_p": 0.9,
        }
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
        result = response.json()
        return result.get("response", "").strip()


async def classify(text: str, categories: list[str]) -> dict:
    """Classify text into one of the given categories. Returns {category, confidence}."""
    cats = ", ".join(categories)
    prompt = (
        f"Classify this text into exactly one category.\n"
        f"Text: \"{text}\"\n"
        f"Categories: [{cats}]\n"
        f"Respond with JSON only: {{\"category\": \"...\", \"confidence\": 0.0-1.0}}"
    )
    raw = await generate(prompt, json_mode=True, max_tokens=50, temperature=0.1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"category": categories[0], "confidence": 0.0}


async def narrate(structured_data: str, example: str = "") -> str:
    """Convert structured data into a 1-2 sentence natural language summary."""
    few_shot = ""
    if example:
        few_shot = f"\nExample:\nData: gauge 26.3m danger, 47 reports Jajpur\nSentence: Naraj gauge critical at 26.3m with 47 ground reports confirming heavy flooding in Jajpur district.\n"

    prompt = (
        f"Write exactly one sentence summarizing this data for a rescue commander. "
        f"Use only the facts given. Do not add information.{few_shot}\n"
        f"Data: {structured_data}\n"
        f"Sentence:"
    )
    return await generate(prompt, max_tokens=80, temperature=0.3)
```

---

## PART 5: Redesigned Intelligence Layer

### Original vs Adapted — Side by Side

#### Situation Briefing

**Original (Claude Sonnet):** One LLM call with all data → full briefing with insights

**Adapted (Llama 1B):**
```python
# backend/intelligence/briefing.py

async def generate_situation_brief(db) -> SituationBrief:
    """Generate briefing using Python analysis + LLM narration."""

    # ========================================
    # STEP 1: Python does ALL the analysis
    # ========================================

    # Fetch current data
    gauges = await db.get_active_gauges()
    reports = await db.get_recent_reports(hours=6)
    assets = await db.get_all_assets()
    camps = await db.get_active_camps()
    routes = await db.get_route_status()
    sources = await db.get_source_freshness()

    # Analyze gauges
    critical_gauges = [g for g in gauges if g.water_level >= g.danger_level]
    warning_gauges = [g for g in gauges if g.warning_level <= g.water_level < g.danger_level]
    rising_gauges = [g for g in gauges if g.trend == "RISING"]

    # Detect conflicts
    conflicts = detect_gauge_vs_social_conflicts(gauges, reports)

    # Detect silent districts
    silent_districts = detect_silent_districts(db)

    # Analyze asset coverage
    asset_gaps = find_asset_gaps(assets, reports)  # districts with high severity but no assets

    # Assess camp risks
    at_risk_camps = assess_camp_flood_risk(camps, gauges, reports)

    # Check route status
    blocked_routes = [r for r in routes if r.status in ("BLOCKED", "SUBMERGED")]

    # Compute top recommendation (rule-based)
    recommendation = compute_top_recommendation(
        asset_gaps=asset_gaps,
        at_risk_camps=at_risk_camps,
        critical_gauges=critical_gauges,
        blocked_routes=blocked_routes
    )

    # Identify stale sources
    stale = [s for s in sources if s.is_stale]

    # ========================================
    # STEP 2: Build structured analysis object
    # ========================================

    analysis = {
        "critical_count": len(critical_gauges),
        "warning_count": len(warning_gauges),
        "rising_count": len(rising_gauges),
        "total_reports": len(reports),
        "conflict_count": len(conflicts),
        "silent_districts": [d.name for d in silent_districts],
        "asset_gaps": [g.district_name for g in asset_gaps],
        "at_risk_camps": [c.name for c in at_risk_camps],
        "blocked_routes": [r.name for r in blocked_routes],
        "stale_sources": [s.name for s in stale],
    }

    # ========================================
    # STEP 3: LLM generates ONLY the narrative
    # ========================================

    # Compress analysis into a tight data string for the LLM
    data_str = (
        f"{analysis['critical_count']} gauges at danger level, "
        f"{analysis['warning_count']} at warning, "
        f"{analysis['rising_count']} rising. "
        f"{analysis['total_reports']} ground reports in 6 hours. "
        f"{analysis['conflict_count']} source conflicts detected. "
    )
    if analysis['silent_districts']:
        data_str += f"SILENT districts: {', '.join(analysis['silent_districts'])}. "
    if analysis['asset_gaps']:
        data_str += f"No rescue assets in: {', '.join(analysis['asset_gaps'])}. "
    if analysis['at_risk_camps']:
        data_str += f"Camps at flood risk: {', '.join(analysis['at_risk_camps'])}. "

    summary = await narrate(data_str, example=(
        "Data: 2 gauges danger, 3 warning, 5 rising. 89 reports. 1 conflict. "
        "SILENT: Ganjam. No assets in: Jagatsinghpur.\n"
        "Sentence: Critical situation with 2 gauges above danger level and all "
        "5 monitored stations rising. Ganjam district has gone silent — possible "
        "communication failure. Jagatsinghpur has active flooding but zero rescue "
        "assets deployed."
    ))

    # ========================================
    # STEP 4: LLM phrases the recommendation
    # ========================================

    if recommendation:
        rec_data = (
            f"Action: {recommendation['action']}. "
            f"From: {recommendation['from_district']}. "
            f"To: {recommendation['to_district']}. "
            f"Assets: {recommendation['asset_count']} {recommendation['asset_type']}. "
            f"Route: {recommendation['route']}. "
            f"ETA: {recommendation['eta_hours']} hours. "
            f"Reason: {recommendation['reason']}."
        )
        action_text = await narrate(rec_data, example=(
            "Data: Action: redeploy. From: Kendrapara. To: Jagatsinghpur. "
            "Assets: 2 boats. Route: Devi River. ETA: 2.5 hours. "
            "Reason: Jagatsinghpur has severity 4 flooding with no boats.\n"
            "Sentence: Redeploy 2 boats from Kendrapara to Jagatsinghpur via "
            "Devi River route (ETA 2.5 hours) — Jagatsinghpur has critical "
            "flooding and zero rescue assets."
        ))
    else:
        action_text = "No immediate redeployment needed. Continue monitoring."

    # ========================================
    # STEP 5: Assemble final brief (Python)
    # ========================================

    return SituationBrief(
        summary_text=summary,
        key_risks=[
            {"location": g.name, "risk": "Above danger level", "severity": 5}
            for g in critical_gauges
        ] + [
            {"location": d, "risk": "District silent", "severity": 4}
            for d in analysis['silent_districts']
        ] + [
            {"location": c, "risk": "Camp in projected flood zone", "severity": 4}
            for c in analysis['at_risk_camps']
        ],
        recommendations=[{
            "action": action_text,
            "priority": 1,
            "confidence": recommendation.get('confidence', 0.5) if recommendation else None
        }],
        data_freshness={s.type: s.last_fetched_at for s in sources},
        stale_sources=[s.name for s in stale],
        overall_confidence=compute_overall_confidence(sources, gauges),
    )
```

#### Conflict Resolution

**Original:** Claude reasons about WHY sources disagree
**Adapted:** Python classifies the conflict type using rules, LLM writes the description

```python
# backend/fusion/conflicts.py

# Rule-based conflict classification — NO LLM needed
CONFLICT_RULES = {
    "GAUGE_LOW_SOCIAL_HIGH": {
        "condition": lambda g, s: g.water_level < g.warning_level and s.avg_severity >= 3,
        "likely_cause": "Drainage congestion from local rainfall, not river overflow",
        "recommended_severity": lambda g, s: max(3, round(s.avg_severity)),
        "confidence": lambda g, s: min(0.7, 0.3 + s.report_count * 0.05),
        "both_valid": True,
    },
    "GAUGE_HIGH_SOCIAL_LOW": {
        "condition": lambda g, s: g.water_level >= g.danger_level and s.avg_severity <= 2,
        "likely_cause": "River level rising but flooding has not yet reached populated areas",
        "recommended_severity": lambda g, s: 4,  # trust the gauge, situation worsening
        "confidence": lambda g, s: 0.8,
        "both_valid": True,
    },
    "SOCIAL_CONTRADICTS_SOCIAL": {
        "condition": lambda a, b: abs(a.avg_severity - b.avg_severity) >= 2,
        "likely_cause": "Reports from different micro-locations with varying flood impact",
        "recommended_severity": lambda a, b: max(a.avg_severity, b.avg_severity),
        "confidence": lambda a, b: 0.5,
        "both_valid": True,
    },
}

def classify_conflict(source_a, source_b) -> dict:
    """Rule-based conflict classification. No LLM needed."""
    for conflict_type, rules in CONFLICT_RULES.items():
        if rules["condition"](source_a, source_b):
            return {
                "type": conflict_type,
                "likely_cause": rules["likely_cause"],
                "recommended_severity": rules["recommended_severity"](source_a, source_b),
                "confidence": rules["confidence"](source_a, source_b),
                "both_valid": rules["both_valid"],
            }
    return {"type": "UNKNOWN", "likely_cause": "Insufficient data to classify", "confidence": 0.3}

# LLM is used ONLY to generate the human-readable description
async def describe_conflict(conflict: dict, source_a, source_b) -> str:
    data = (
        f"Conflict: {conflict['type']}. "
        f"Source A: {source_a.type} says {source_a.summary}. "
        f"Source B: {source_b.type} says {source_b.summary}. "
        f"Cause: {conflict['likely_cause']}. "
        f"Both can be correct: {conflict['both_valid']}."
    )
    return await narrate(data)
```

#### Alert Triage

**Original:** Claude ranks alerts by analyzing population, time sensitivity, assets
**Adapted:** Python scores each alert numerically, LLM only writes the description

```python
# backend/intelligence/alerts.py

def score_alert(alert, assets, districts) -> float:
    """Deterministic scoring function. No LLM needed."""
    score = 0.0

    # Severity weight (1-5 → 0-50 points)
    score += alert.severity * 10

    # Population at risk (more people = higher score)
    district = get_district(alert.district_id, districts)
    if district:
        pop_factor = min(district.population / 100_000, 5)  # cap at 5x
        score += pop_factor * 5

    # Time sensitivity (is it getting worse?)
    if alert.type in ("FLOOD_RISING", "CAMP_AT_RISK"):
        score += 15  # time-critical alerts get a boost

    # Asset availability (worse if no assets nearby)
    nearby_assets = get_assets_within_km(alert.location, 50, assets)
    if len(nearby_assets) == 0:
        score += 20  # no nearby assets = more urgent
    elif len(nearby_assets) <= 2:
        score += 10

    # Silent district bonus (unknown = potentially critical)
    if alert.type == "SILENT_DISTRICT":
        score += 15

    # Recency (newer alerts score slightly higher)
    hours_old = (now() - alert.generated_at).total_seconds() / 3600
    score -= min(hours_old * 2, 10)  # decay over time

    return score

def triage_alerts(alerts, assets, districts, top_n=3) -> list:
    """Score and rank all alerts. Pure Python."""
    scored = [(a, score_alert(a, assets, districts)) for a in alerts]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]
```

#### Flood Progression Model

**No LLM needed at all.** This is pure math.

```python
# backend/intelligence/projection.py

def project_flood_progression(gauges: list, hours_ahead: int = 6) -> list:
    """Simple upstream → downstream time-lag projection.

    If station A is upstream of station B with a 4-hour travel time,
    and A is currently at danger level, then B will likely reach danger
    level in ~4 hours (adjusted by rise rate).
    """
    projections = []
    for gauge in gauges:
        if gauge.trend != "RISING" or not gauge.upstream_station:
            continue

        upstream = get_station(gauge.upstream_station_id)
        if not upstream:
            continue

        # If upstream is above danger, downstream will follow
        if upstream.water_level >= upstream.danger_level:
            eta_hours = gauge.avg_travel_time_hrs or 6  # default 6h if unknown
            projected_level = gauge.water_level + (gauge.rise_rate_m_per_hr * eta_hours)

            projections.append({
                "station": gauge.name,
                "current_level": gauge.water_level,
                "projected_level_m": projected_level,
                "projected_status": "DANGER" if projected_level >= gauge.danger_level else "WARNING",
                "eta_hours": eta_hours,
                "based_on": f"Upstream station {upstream.name} at {upstream.water_level}m",
                "confidence": 0.6,  # simple model, moderate confidence
            })

    return projections


def assess_camp_risk(camps, projections, gauges) -> list:
    """Check if any relief camps are in the projected flood zone."""
    at_risk = []
    for camp in camps:
        nearest_gauge = get_nearest_gauge(camp.location, gauges)
        projection = next((p for p in projections if p['station'] == nearest_gauge.name), None)

        if projection and projection['projected_level_m'] >= camp.elevation_m:
            hours_until_risk = max(0, (camp.elevation_m - nearest_gauge.water_level) / nearest_gauge.rise_rate_m_per_hr) if nearest_gauge.rise_rate_m_per_hr > 0 else None
            at_risk.append({
                "camp": camp.name,
                "population": camp.current_population,
                "elevation_m": camp.elevation_m,
                "projected_water_m": projection['projected_level_m'],
                "hours_until_risk": hours_until_risk,
                "nearest_gauge": nearest_gauge.name,
            })

    return sorted(at_risk, key=lambda x: x.get('hours_until_risk') or 999)
```

---

## PART 6: Where the LLM IS Used (Specific Call Inventory)

Total LLM calls per briefing cycle: **4-6 small calls** instead of 1-3 large calls.
Each call: **<100 tokens input, <80 tokens output.**

| # | Purpose | Input | Output | Fallback if LLM fails |
|---|---------|-------|--------|----------------------|
| 1 | Narrate situation summary | Compressed data string (~80 tokens) | 1-2 sentences (~40 tokens) | Use template: "{n} gauges critical, {m} districts affected" |
| 2 | Phrase top recommendation | Structured action data (~60 tokens) | 1 sentence (~30 tokens) | Use template: "Redeploy {n} {type} from {A} to {B}, ETA {t}h" |
| 3 | Describe conflict (per conflict) | Conflict classification (~50 tokens) | 1 sentence (~30 tokens) | Use `likely_cause` field directly |
| 4 | Classify social media report (per report) | Report text (~30 tokens) | Category + confidence (~10 tokens) | Default to "UNCLASSIFIED" with 0.0 confidence |
| 5 | Generate alert description (per alert) | Alert data (~50 tokens) | 1-2 sentences (~40 tokens) | Use template with data fields |

**Estimated total per 15-min cycle:** ~500 tokens input, ~200 tokens output.
At 10 tok/sec on CPU: ~70 seconds of LLM time per cycle. Well within the 15-min window.

---

## PART 7: Model Upgrade Path

Design the system so you can swap models without changing application code.

```python
# backend/llm/client.py

class LLMClient:
    """Abstraction layer — swap models without changing callers."""

    def __init__(self, provider: str = "ollama", model: str = "llama3.2:1b"):
        self.provider = provider
        self.model = model
        self.base_url = {
            "ollama": "http://localhost:11434",
        }[provider]

    async def generate(self, prompt: str, **kwargs) -> str:
        if self.provider == "ollama":
            return await self._ollama_generate(prompt, **kwargs)
        raise ValueError(f"Unknown provider: {self.provider}")

    async def _ollama_generate(self, prompt, system="", temperature=0.2,
                                max_tokens=200, json_mode=False):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            return resp.json().get("response", "").strip()


# Usage
llm = LLMClient(provider="ollama", model="llama3.2:1b")

# To upgrade later, just change the model:
# llm = LLMClient(provider="ollama", model="llama3.2:3b")
# llm = LLMClient(provider="ollama", model="mistral:7b")
# llm = LLMClient(provider="ollama", model="phi3:14b")
```

### Recommended Upgrade Path (if hardware allows)

| Model | Size | When to Use |
|-------|------|-------------|
| Llama 3.2:1b | ~1.3 GB | Default. Works on any machine including your Windows 10 setup |
| Llama 3.2:3b | ~2.0 GB | Better coherence for narration. Use if you have 8GB+ RAM |
| Phi-3 Mini (3.8B) | ~2.3 GB | Excellent instruction following for its size. Strong upgrade |
| Mistral 7B | ~4.1 GB | Major quality jump. Needs 16GB RAM or a GPU |
| Llama 3.1:8b | ~4.7 GB | Best open-source balance of quality and speed |

The "Code Reasons, LLM Speaks" architecture means upgrading models improves
the NARRATION quality but doesn't change the ANALYSIS quality. The analysis
is always deterministic Python — the model just makes it sound better.

---

## PART 8: Deployment Consideration

### The Ollama Problem for Deployment

Vercel and Railway free tiers do NOT support running Ollama (no persistent
process, no GPU). Options:

**Option A: Keep LLM local, deploy API without it**
- Deploy backend to Railway WITHOUT Ollama
- Backend uses template-based fallbacks (no LLM narration)
- For live demo, run backend locally with Ollama
- Deployed version works but has more "robotic" text

**Option B: Use a free cloud GPU (limited)**
- Google Colab (free tier) can run Ollama + expose via ngrok
- Not reliable for production, but works for a demo session
- Lightning.ai has a free tier with GPU access

**Option C: Hybrid — use Groq free tier as cloud fallback**
- Groq offers free API access to Llama models (rate-limited)
- Use local Ollama in development, Groq API in deployed version
- Same model family, similar outputs
- Groq free tier: 30 requests/min for Llama models
- URL: https://console.groq.com (free API key)

```python
# Hybrid client that falls back to Groq if Ollama is unavailable
class LLMClient:
    def __init__(self):
        self.ollama_available = self._check_ollama()
        self.groq_key = os.getenv("GROQ_API_KEY")

    async def generate(self, prompt, **kwargs):
        if self.ollama_available:
            return await self._ollama_generate(prompt, **kwargs)
        elif self.groq_key:
            return await self._groq_generate(prompt, **kwargs)
        else:
            return None  # caller uses template fallback

    async def _groq_generate(self, prompt, system="", temperature=0.2,
                              max_tokens=200, json_mode=False):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.groq_key}"},
                json={
                    "model": "llama-3.2-1b-preview",
                    "messages": [
                        {"role": "system", "content": system} if system else None,
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"} if json_mode else None,
                }
            )
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
```

**Recommendation:** Go with Option C. Use Ollama locally for development and demo,
Groq free tier for the deployed version. Same Llama 3.2 model, zero cost,
and the deployment actually works.

---

## PART 9: Updated Environment Variables

```env
# .env.example (Local LLM Edition)

# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbG...
SUPABASE_SERVICE_KEY=eyJhbG...

# LLM Configuration
LLM_PROVIDER=ollama                    # or "groq" for cloud fallback
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
GROQ_API_KEY=gsk_...                   # free tier, optional fallback

# Open-Meteo (no key needed)
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1

# App Config
BRIEFING_INTERVAL_MIN=15
DATA_REFRESH_INTERVAL_SEC=60
SIMULATION_MODE=false
LLM_FALLBACK_TO_TEMPLATES=true         # use templates if LLM is unavailable
LLM_MAX_RETRIES=2
LLM_TIMEOUT_SEC=60
LOG_LEVEL=INFO

# Frontend (Vite)
VITE_API_BASE_URL=http://localhost:8000
VITE_MAP_CENTER_LAT=20.46
VITE_MAP_CENTER_LNG=85.88
VITE_MAP_DEFAULT_ZOOM=8
```

---

## PART 10: Updated Database Schema

No changes from the original masterplan. The database schema is identical because
the schema stores RESULTS of analysis, not the method used to produce them.
The `situation_briefs` and `alerts` tables store the same fields whether the
text was generated by Claude Sonnet or Llama 1B or pure Python templates.

Refer to the original MASTERPLAN.md for the complete SQL schema.

---

## PART 11: Updated Build Plan

The week-by-week plan is the same as the original MASTERPLAN.md with these changes:

**Week 1 Addition:**
- Install Ollama and pull `llama3.2:1b`
- Set up the `LLMClient` abstraction layer
- Test basic generation and JSON mode
- Verify response times on your hardware

**Week 3 Changes (Intelligence Layer):**
- Build rule-based analysis functions FIRST (Python)
- Build template-based fallback briefings
- THEN add LLM narration on top
- Test: the system should produce useful output even if the LLM is completely disabled
- The LLM makes it BETTER, but isn't REQUIRED

**Week 4 Addition:**
- Set up Groq free tier account as deployment fallback
- Test hybrid Ollama → Groq → Template fallback chain
- Deploy with Groq as the LLM backend

---

## Summary: Decision Framework

When building any feature, ask:

1. **Can Python do this deterministically?** → Do it in Python. (Scoring, sorting, distance calculations, threshold checks, trend detection)

2. **Does it need understanding of language?** → Use the LLM. (Classifying free-text reports, generating readable summaries)

3. **Does it need deep reasoning?** → Do it in Python with rules, then use LLM to explain the result. (Conflict resolution, recommendations, triage)

4. **What if the LLM is down?** → Every LLM call has a template fallback. The system degrades gracefully from "eloquent briefing" to "structured data display." Both are useful.

The goal is a system where the intelligence comes from your CODE, and the
communication comes from the LLM. That's an architecture that works at any
model size.

---

*This document is adapted from MASTERPLAN.md for local LLM deployment.
Both documents share the same database schema, API structure, frontend
design, and data source configuration. The difference is entirely in the
intelligence layer architecture.*
