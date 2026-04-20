"""
Situation briefing generator.

Calls Claude API (or falls back to Ollama/Groq/template) every 15 minutes
to produce a plain-language briefing for the NDRF battalion commander.

Architecture: "Code Reasons, LLM Speaks"
Python does ALL analysis → LLM writes the narrative text only.
See MASTERPLAN_LOCAL_LLM.md for full design rationale.
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from config import settings
from database import get_client
from intelligence.projection import project_flood_progression

logger = logging.getLogger(__name__)

# ── Module-level constants ────────────────────────────────────────────────────

REGION = "Mahanadi Basin"

# How far back to look for flood reports in the analysis window
ANALYSIS_WINDOW_HOURS = 6

# A district with no reports for this long is flagged as "silent"
SILENT_DISTRICT_HOURS = 4

# Confidence returned when there are zero reports at all
CONFIDENCE_NO_DATA = 0.3

# Confidence penalty applied per silent district
SILENT_DISTRICT_PENALTY = 0.05

# Max assets / projections shown in the template fallback
MAX_TEMPLATE_ASSETS = 3
MAX_TEMPLATE_PROJECTIONS = 2

# Explicit column lists — never select("*") on heavy tables
GAUGE_COLUMNS = "id,name,location,danger_level_m,warning_level_m"
ASSET_COLUMNS = "id,name,type,status,location,assigned_district_id"

# Base confidence per source type — from CLAUDE.md confidence scoring table
BASE_CONFIDENCE: dict[str, float] = {
    "CWC_GAUGE":       0.95,
    "IMD_WEATHER":     0.75,
    "SATELLITE":       0.90,
    "DISTRICT_REPORT": 0.80,
    "SOCIAL_MEDIA":    0.30,
    "OSM_ROAD":        0.85,
}

# ── Module-level Anthropic client — created once, reused on every call ────────
_anthropic_client: anthropic.AsyncAnthropic | None = None


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic_client


# ── Prompt ────────────────────────────────────────────────────────────────────

BRIEFING_SYSTEM_PROMPT = """You are SahayakMap's intelligence engine assisting an NDRF \
battalion commander during flood operations in Odisha.

You will receive structured data about the current flood situation. Generate a concise \
situation briefing that a field commander can read in under 60 seconds.

Output Format (JSON):
{
  "summary": "2-3 sentence overview",
  "critical_developments": [{"location": "...", "situation": "...", "urgency": "HIGH|MEDIUM|LOW"}],
  "key_risks": [{"risk": "...", "affected_area": "...", "eta_hours": N, "confidence": 0.X}],
  "recommended_actions": [{"action": "...", "rationale": "...", "priority": 1, "assets_involved": ["..."]}],
  "data_gaps": ["stale or missing sources"],
  "confidence_note": "overall assessment of data quality"
}

Rules:
- Be specific: use place names, distances, time estimates
- Flag contradictions between sources explicitly
- Distinguish between what you KNOW from data and what you INFER
- When data is stale, say so with the timestamp
- If a district has gone silent, flag it as potentially critical
- Never generate false precision — if confidence is low, say so"""


# ── Helper functions ──────────────────────────────────────────────────────────

def _hash_analysis(analysis: dict) -> str:
    """Stable hash of analysis dict — used to skip regeneration when data hasn't changed."""
    serialized = json.dumps(analysis, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


def _compute_confidence(reports: list, silent_districts: list) -> float:
    """
    Weighted average of (base_confidence x freshness_factor) across all reports.
    Penalised by SILENT_DISTRICT_PENALTY per silent district.
    Clamped to [0.1, 1.0].
    """
    if not reports:
        return CONFIDENCE_NO_DATA
    scores = []
    for r in reports:
        src_type = (r.get("data_sources") or {}).get("type", "UNKNOWN")
        base = BASE_CONFIDENCE.get(src_type, 0.5)
        freshness = r.get("freshness_factor") or 1.0
        scores.append(base * freshness)
    avg = sum(scores) / len(scores)
    penalty = len(silent_districts) * SILENT_DISTRICT_PENALTY
    return round(max(0.1, min(1.0, avg - penalty)), 3)


def _build_source_freshness(reports: list) -> dict:
    """
    For each source type, record latest report timestamp and total count.
    Feeds the Freshness tab in the frontend.
    """
    freshness: dict[str, dict] = {}
    for r in reports:
        src_type = (r.get("data_sources") or {}).get("type", "UNKNOWN")
        reported_at = r.get("reported_at", "")
        if src_type not in freshness:
            freshness[src_type] = {"latest_at": reported_at, "count": 0}
        # Update latest_at separately so count is never reset
        if reported_at > freshness[src_type]["latest_at"]:
            freshness[src_type]["latest_at"] = reported_at
        freshness[src_type]["count"] += 1
    return freshness


# ── Main entry point ──────────────────────────────────────────────────────────

async def generate_situation_brief(force: bool = False) -> dict | None:
    """
    Generate and persist a situation briefing.
    Called by the scheduler every BRIEFING_INTERVAL_MIN minutes.
    Skips LLM call if underlying data hasn't changed since last brief,
    unless force=True (used by POST /briefing/generate).
    """
    db = get_client()
    analysis = await _build_analysis(db)
    input_hash = _hash_analysis(analysis)

    # Cache check — skipped when force=True so the button always produces a new brief
    if not force:
        last = (
            db.table("situation_briefs")
            .select("data_freshness")
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )
        if last.data:
            last_hash = (last.data[0].get("data_freshness") or {}).get("input_hash")
            if last_hash == input_hash:
                logger.info("Situation brief skipped — data unchanged (hash: %s)", input_hash)
                # Re-fetch the full row to return it
                full = (
                    db.table("situation_briefs")
                    .select("*")
                    .order("generated_at", desc=True)
                    .limit(1)
                    .execute()
                )
                return full.data[0] if full.data else None

    brief_text = await _call_llm(analysis)
    if brief_text is None:
        brief_text = _template_fallback(analysis)

    try:
        brief_json = json.loads(brief_text) if isinstance(brief_text, str) else brief_text
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON briefing, using as plain summary text")
        brief_json = {"summary": brief_text, "key_risks": [], "recommended_actions": []}

    record = {
        "region": REGION,
        "summary_text": brief_json.get("summary", ""),
        "key_risks": brief_json.get("key_risks", []),
        "recommendations": brief_json.get("recommended_actions", []),
        "stale_sources": brief_json.get("data_gaps", []),
        "overall_confidence": analysis["overall_confidence"],
        "data_freshness": {**analysis["source_freshness"], "input_hash": input_hash},
    }
    result = db.table("situation_briefs").insert(record).execute()
    logger.info("Situation brief generated and stored")
    return result.data[0] if result.data else None


# ── Analysis builder ──────────────────────────────────────────────────────────

async def _build_analysis(db) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=ANALYSIS_WINDOW_HOURS)).isoformat()
    silent_cutoff = (datetime.now(timezone.utc) - timedelta(hours=SILENT_DISTRICT_HOURS)).isoformat()

    # Run all 5 independent DB queries in parallel — cuts wait time from 5x to 1x
    reports, gauges, assets, adjacency, all_districts = await asyncio.gather(
        asyncio.to_thread(lambda: (
            db.table("flood_reports")
            .select("*, data_sources(type)")
            .gte("reported_at", since)
            .order("reported_at", desc=True)
            .execute()
            .data or []
        )),
        asyncio.to_thread(lambda: (
            db.table("gauge_stations")
            .select(GAUGE_COLUMNS)
            .execute()
            .data or []
        )),
        asyncio.to_thread(lambda: (
            db.table("rescue_assets")
            .select(ASSET_COLUMNS)
            .execute()
            .data or []
        )),
        asyncio.to_thread(lambda: (
            db.table("station_adjacency")
            .select("upstream_id, downstream_id, avg_travel_time_hrs")
            .execute()
            .data or []
        )),
        asyncio.to_thread(lambda: (
            db.table("districts")
            .select("id, name")
            .execute()
            .data or []
        )),
    )

    # Build a location-keyed map of the latest CWC water level for each gauge.
    # Supabase returns geometry as GeoJSON: {"type": "Point", "coordinates": [lng, lat]}
    # Coordinates rounded to 2dp to match ingestion precision from seed data.
    cwc_level_by_coords: dict[tuple, float] = {}
    for r in reports:
        if (r.get("data_sources") or {}).get("type") != "CWC_GAUGE":
            continue
        if not r.get("water_level_m"):
            continue
        loc = r.get("location")
        if isinstance(loc, dict) and loc.get("type") == "Point":
            lng, lat = loc["coordinates"]
            key = (round(lat, 2), round(lng, 2))
            if key not in cwc_level_by_coords:  # reports ordered newest-first
                cwc_level_by_coords[key] = r["water_level_m"]

    critical_gauges = []
    warning_gauges = []
    for g in gauges:
        loc = g.get("location")
        level = None
        if isinstance(loc, dict) and loc.get("type") == "Point":
            lng, lat = loc["coordinates"]
            level = cwc_level_by_coords.get((round(lat, 2), round(lng, 2)))

        if level and level >= g.get("danger_level_m", 999):
            critical_gauges.append(g["name"])
        elif level and level >= g.get("warning_level_m", 999):
            warning_gauges.append(g["name"])

    # Detect silent districts
    recent_district_ids = {
        r.get("district_id") for r in reports if r["reported_at"] >= silent_cutoff
    }
    silent = [d["name"] for d in all_districts if d["id"] not in recent_district_ids]

    projections = project_flood_progression(gauges, reports, adjacency)
    source_freshness = _build_source_freshness(reports)
    overall_confidence = _compute_confidence(reports, silent)

    return {
        "critical_gauges": critical_gauges,
        "warning_gauges": warning_gauges,
        "total_reports": len(reports),
        "silent_districts": silent,
        "available_assets": [a for a in assets if a["status"] == "AVAILABLE"],
        "projections": projections,
        "overall_confidence": overall_confidence,
        "source_freshness": source_freshness,
    }


# ── LLM call ─────────────────────────────────────────────────────────────────

async def _call_llm(analysis: dict) -> str | None:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        try:
            client = _get_anthropic_client()
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.llm_max_tokens,
                system=BRIEFING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(analysis, default=str)}],
            )
            return message.content[0].text  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as e:
            logger.error("Claude API call failed: %s", e)

    if not settings.llm_fallback_to_templates:
        raise RuntimeError("LLM unavailable and llm_fallback_to_templates is disabled")
    return None  # caller uses template


# ── Template fallback ─────────────────────────────────────────────────────────

def _template_fallback(analysis: dict) -> str:
    """
    Pure Python briefing when LLM is unavailable.
    Populates all 5 output fields from real analysis data.
    """
    parts = []
    critical_developments = []
    key_risks = []
    recommended_actions = []

    for name in analysis["critical_gauges"]:
        parts.append(f"CRITICAL: {name} above danger level.")
        critical_developments.append({
            "location": name,
            "situation": "River above danger level — immediate risk to life",
            "urgency": "HIGH",
        })
        key_risks.append({
            "risk": f"{name} above danger level",
            "affected_area": name,
            "eta_hours": 0,
            "confidence": 0.95,
        })

    for name in analysis["warning_gauges"]:
        parts.append(f"WARNING: {name} approaching danger level.")
        critical_developments.append({
            "location": name,
            "situation": "River at warning level — monitor closely",
            "urgency": "MEDIUM",
        })
        key_risks.append({
            "risk": f"{name} approaching danger level",
            "affected_area": name,
            "eta_hours": 2,
            "confidence": 0.90,
        })

    if analysis["silent_districts"]:
        names = ", ".join(analysis["silent_districts"])
        parts.append(f"SILENT districts (no reports {SILENT_DISTRICT_HOURS}h+): {names}.")
        key_risks.append({
            "risk": "Communication blackout — situation unknown",
            "affected_area": names,
            "eta_hours": None,
            "confidence": 0.5,
        })

    if analysis["critical_gauges"] and analysis["available_assets"]:
        asset_names = [
            a.get("name", "Asset")
            for a in analysis["available_assets"][:MAX_TEMPLATE_ASSETS]
        ]
        recommended_actions.append({
            "action": f"Deploy to {', '.join(analysis['critical_gauges'])} immediately",
            "rationale": "Rivers above danger level require immediate rescue presence",
            "priority": 1,
            "assets_involved": asset_names,
        })

    for proj in analysis.get("projections", [])[:MAX_TEMPLATE_PROJECTIONS]:
        recommended_actions.append({
            "action": f"Pre-position assets near {proj.get('station', 'downstream station')}",
            "rationale": f"Flood wave projected to arrive in ~{proj.get('eta_hours', '?')} hours",
            "priority": 2,
            "assets_involved": [],
        })

    if not parts:
        parts.append("Situation stable. All gauges below warning level.")

    return json.dumps({
        "summary": " ".join(parts),
        "critical_developments": critical_developments,
        "key_risks": key_risks,
        "recommended_actions": recommended_actions,
        "data_gaps": analysis.get("silent_districts", []),
        "confidence_note": (
            f"Template fallback — LLM unavailable. "
            f"Data confidence: {analysis['overall_confidence']:.0%}"
        ),
    })
