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
import httpx
from fastapi import HTTPException

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
- Never generate false precision — if confidence is low, say so
- In assets_involved, use ONLY the exact asset names from the available_assets data provided — never invent or paraphrase asset names"""


# ── Helper functions ──────────────────────────────────────────────────────────

def _hash_analysis(analysis: dict) -> str:
    """Stable hash of analysis dict — used to skip regeneration when data hasn't changed."""
    serialized = json.dumps(analysis, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode()).hexdigest()


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences that Groq/some LLMs wrap JSON responses in."""
    text = text.strip()
    if text.startswith("```"):
        # Drop the opening fence line (```json or ``` alone)
        newline = text.find("\n")
        text = text[newline + 1:] if newline != -1 else text[3:]
        # Drop the closing fence
        if text.endswith("```"):
            text = text[:-3].rstrip()
    return text


def _repair_truncated_json(text: str) -> str:
    """
    Best-effort repair of a truncated JSON string.
    Finds the last complete top-level value, closes any open array, and
    closes the root object so json.loads has a fighting chance.
    Only applied when the text does not already end with '}'.
    """
    text = text.rstrip()
    if text.endswith("}"):
        return text

    logger.warning("Groq response appears truncated (does not end with '}') — attempting repair")

    # Walk backwards to find the last complete key-value pair boundary
    # i.e. the last '}' or '"]' that closes a value before the cut-off
    for marker in ("}", "]"):
        idx = text.rfind(marker)
        if idx != -1:
            truncated = text[: idx + 1]
            # Count unmatched braces/brackets to decide what to close
            opens = truncated.count("{") - truncated.count("}")
            arr_opens = truncated.count("[") - truncated.count("]")
            closing = "]" * max(arr_opens, 0) + "}" * max(opens, 0)
            if closing:
                repaired = truncated + "\n" + closing
                logger.warning("Repaired truncated JSON by appending %r", closing)
                return repaired
            return truncated

    return text  # nothing salvageable; let json.loads report the error


def _normalize_llm_text(text: str) -> str:
    """Replace typographic unicode characters that break json.loads."""
    return (
        text
        .replace("\u2011", "-")   # non-breaking hyphen → hyphen
        .replace("\u2013", "-")   # en-dash → hyphen
        .replace("\u2014", "-")   # em-dash → hyphen
        .replace("\u201c", '"')   # left double quote → "
        .replace("\u201d", '"')   # right double quote → "
        .replace("\u2018", "'")   # left single quote → '
        .replace("\u2019", "'")   # right single quote → '
        .replace("\u00a0", " ")   # non-breaking space → space
    )


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


def _build_asset_summary(analysis: dict) -> str:
    """Comma-separated list of available asset names for LLM context (capped at 12)."""
    assets = analysis.get("available_assets", [])[:12]
    if not assets:
        return "none available"
    return ", ".join(
        f"{a['name']} ({a.get('type', '?')}, {a.get('status', '?')})"
        for a in assets
    )


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

    # Strip fences → normalize unicode → repair truncation → parse
    cleaned_text = _strip_code_fences(brief_text) if isinstance(brief_text, str) else brief_text
    cleaned_text = _normalize_llm_text(cleaned_text) if isinstance(cleaned_text, str) else cleaned_text
    cleaned_text = _repair_truncated_json(cleaned_text) if isinstance(cleaned_text, str) else cleaned_text
    try:
        brief_json = json.loads(cleaned_text) if isinstance(cleaned_text, str) else cleaned_text
        logger.info(f"brief_json parsed OK, keys: {list(brief_json.keys())}")
        # Guard: Groq occasionally double-encodes — json.loads returns a str, not a dict
        if isinstance(brief_json, str):
            logger.debug("LLM response was double-encoded JSON — parsing inner string")
            brief_json = json.loads(brief_json)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed at pos {e.pos}, line {e.lineno}, col {e.colno}: {e.msg}")
        logger.warning(f"CONTEXT: {cleaned_text[max(0,e.pos-50):e.pos+50]!r}")
        brief_json = {}

    # Trace the parsed shape so mismatches are visible in logs
    if isinstance(brief_json, dict):
        logger.debug(
            "brief_json parsed OK — keys=%s  summary[:80]=%r",
            list(brief_json.keys()),
            (brief_json.get("summary") or "")[:80],
        )
    else:
        logger.warning("brief_json is not a dict after parse (type=%s) — falling back", type(brief_json).__name__)
        brief_json = {}

    # Map LLM fields → DB columns; fall back to raw text if summary is missing/empty
    parsed_summary = brief_json.get("summary", "")
    record = {
        "region": REGION,
        "summary_text": parsed_summary if parsed_summary else brief_text,
        "key_risks": brief_json.get("key_risks", []),
        "recommendations": brief_json.get("recommended_actions", []),
        "stale_sources": brief_json.get("data_gaps", []),
        "overall_confidence": analysis["overall_confidence"],
        "data_freshness": {**analysis["source_freshness"], "input_hash": input_hash},
    }
    logger.debug("Inserting brief — summary_text[:80]=%r", record["summary_text"][:80])
    result = db.table("situation_briefs").insert(record).execute()
    logger.info("Situation brief generated and stored")
    return result.data[0] if result.data else None


# ── Analysis builder ──────────────────────────────────────────────────────────

async def _build_analysis(db) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=ANALYSIS_WINDOW_HOURS)).isoformat()
    silent_cutoff = (datetime.now(timezone.utc) - timedelta(hours=SILENT_DISTRICT_HOURS)).isoformat()

    # Run all 5 independent DB queries in parallel — cuts wait time from 5x to 1x
    try:
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
        logger.debug("Analysis data fetched successfully")
    except Exception as e:
        logger.error("Failed to fetch analysis data: %s", e)
        raise HTTPException(status_code=503, detail="Failed to build analysis")

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


# ── Ollama prompt condenser ───────────────────────────────────────────────────

def _condense_for_ollama(analysis: dict) -> str:
    """
    Build a <150-word prompt for Llama 1B.
    Llama 1B ignores long system prompts — compress to key facts only.
    Output must match BRIEFING_SYSTEM_PROMPT's JSON schema.
    """
    parts = [
        "Generate a JSON situation briefing for a flood rescue commander in Odisha.",
        f"Critical gauges: {', '.join(analysis['critical_gauges']) or 'none'}.",
        f"Warning gauges: {', '.join(analysis['warning_gauges']) or 'none'}.",
        f"Reports in last 6h: {analysis['total_reports']}.",
        f"Silent districts: {', '.join(analysis['silent_districts']) or 'none'}.",
        f"Available assets: {_build_asset_summary(analysis)}.",
    ]
    if analysis.get("projections"):
        proj = analysis["projections"][0]
        parts.append(
            f"Flood wave projected at {proj.get('station', '?')} in {proj.get('eta_hours', '?')}h."
        )
    parts.append(
        'Return JSON: {"summary": "2-3 sentences", "critical_developments": [], '
        '"key_risks": [], "recommended_actions": [], "data_gaps": [], "confidence_note": ""}.'
    )
    return " ".join(parts)


# ── LLM call ─────────────────────────────────────────────────────────────────

async def _call_llm(analysis: dict) -> str | None:
    """
    Try each LLM provider in order, falling through on failure.
    Chain: Anthropic Claude → Groq → Ollama → return None (template fallback).
    Not gated on LLM_PROVIDER — Groq and Ollama are automatic fallbacks.
    """
    asset_summary = _build_asset_summary(analysis)
    user_content = (
        f"Available assets (use exact names in assets_involved):\n{asset_summary}\n\n"
        + json.dumps(analysis, default=str)
    )

    # Branch 1: Anthropic Claude (primary)
    if settings.anthropic_api_key:
        try:
            client = _get_anthropic_client()
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.llm_max_tokens,
                system=BRIEFING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            return message.content[0].text  # pyright: ignore[reportAttributeAccessIssue]
        except Exception as e:
            logger.warning("Claude API call failed, trying next fallback: %s", e)

    # Branch 2: Groq (Llama 3.2 via cloud — free tier, OpenAI-compatible)
    if settings.groq_api_key:
        logger.info("Using Groq fallback")
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                    json={
                        "model": "openai/gpt-oss-120b",
                        "messages": [
                            {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
                            {"role": "user", "content": user_content},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 2000,
                    },
                )
                resp.raise_for_status()
                groq_text = resp.json()["choices"][0]["message"]["content"].strip()
                logger.warning(f"GROQ RAW RESPONSE FIRST 200 CHARS: {groq_text[:200]!r}")
                return groq_text
        except Exception as e:
            logger.warning("Groq fallback failed, trying Ollama: %s", e)

    # Branch 3: Ollama (local Llama 3.2 — offline, zero cost)
    # Health-check first — skip silently if Ollama isn't running.
    try:
        async with httpx.AsyncClient(timeout=5.0) as hc:
            health = await hc.get(f"{settings.ollama_base_url}/api/tags")
        if health.status_code == 200:
            logger.info("Using Ollama fallback")
            async with httpx.AsyncClient(timeout=settings.llm_timeout_sec) as client:
                resp = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json={
                        "model": settings.ollama_model,
                        "prompt": _condense_for_ollama(analysis),
                        "stream": False,
                        "options": {"temperature": 0.2, "num_predict": 800},
                    },
                )
                resp.raise_for_status()
                return resp.json()["response"].strip()
    except Exception as e:
        logger.warning("Ollama fallback failed: %s", e)

    if not settings.llm_fallback_to_templates:
        raise RuntimeError("All LLM providers failed and llm_fallback_to_templates is disabled")
    return None  # caller uses _template_fallback()


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

    _preposition_assets = [
        a["name"] for a in analysis.get("available_assets", [])
        if a.get("type") in ("BOAT", "RESCUE_TEAM") and a.get("status") == "AVAILABLE"
    ][:MAX_TEMPLATE_ASSETS]

    for proj in analysis.get("projections", [])[:MAX_TEMPLATE_PROJECTIONS]:
        recommended_actions.append({
            "action": f"Pre-position assets near {proj.get('station', 'downstream station')}",
            "rationale": f"Flood wave projected to arrive in ~{proj.get('eta_hours', '?')} hours",
            "priority": 2,
            "assets_involved": _preposition_assets,
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
