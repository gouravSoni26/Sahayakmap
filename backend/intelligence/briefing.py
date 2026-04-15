"""
Situation briefing generator.

Calls Claude API (or falls back to Ollama/Groq/template) every 15 minutes
to produce a plain-language briefing for the NDRF battalion commander.

Architecture: "Code Reasons, LLM Speaks"
Python does ALL analysis → LLM writes the narrative text only.
See MASTERPLAN_LOCAL_LLM.md for full design rationale.
"""
import json
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from config import settings
from database import get_client
from intelligence.projection import project_flood_progression

logger = logging.getLogger(__name__)

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


async def generate_situation_brief() -> dict | None:
    """
    Generate and persist a situation briefing.
    Called by the scheduler every BRIEFING_INTERVAL_MIN minutes.
    """
    db = get_client()
    analysis = await _build_analysis(db)

    brief_text = await _call_llm(analysis)
    if brief_text is None:
        brief_text = _template_fallback(analysis)

    try:
        brief_json = json.loads(brief_text) if isinstance(brief_text, str) else brief_text
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON briefing, using as plain summary text")
        brief_json = {"summary": brief_text, "key_risks": [], "recommended_actions": []}

    record = {
        "region": "Mahanadi Basin",
        "summary_text": brief_json.get("summary", ""),
        "key_risks": brief_json.get("key_risks", []),
        "recommendations": brief_json.get("recommended_actions", []),
        "stale_sources": brief_json.get("data_gaps", []),
        "overall_confidence": analysis.get("overall_confidence", 0.5),
        "data_freshness": analysis.get("source_freshness", {}),
    }
    result = db.table("situation_briefs").insert(record).execute()
    logger.info("Situation brief generated and stored")
    return result.data[0] if result.data else None


async def _build_analysis(db) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    reports = db.table("flood_reports").select("*").gte("reported_at", since).execute().data or []
    gauges = db.table("gauge_stations").select("*").execute().data or []
    assets = db.table("rescue_assets").select("*").execute().data or []

    critical_gauges = []
    warning_gauges = []
    for g in gauges:
        level = next(
            (r["water_level_m"] for r in reports
             if r["source_type"] == "CWC_GAUGE" and r.get("water_level_m")),
            None,
        )
        if level and level >= g.get("danger_level_m", 999):
            critical_gauges.append(g["name"])
        elif level and level >= g.get("warning_level_m", 999):
            warning_gauges.append(g["name"])

    # Detect silent districts (no reports in 4 hours)
    four_hrs_ago = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
    recent_districts = {r.get("district_id") for r in reports if r["reported_at"] >= four_hrs_ago}
    all_districts = db.table("districts").select("id, name").execute().data or []
    silent = [d["name"] for d in all_districts if d["id"] not in recent_districts]

    projections = project_flood_progression(gauges, reports)

    return {
        "critical_gauges": critical_gauges,
        "warning_gauges": warning_gauges,
        "total_reports": len(reports),
        "silent_districts": silent,
        "available_assets": [a for a in assets if a["status"] == "AVAILABLE"],
        "projections": projections,
        "overall_confidence": 0.7 if not silent else 0.5,
        "source_freshness": {},
    }


async def _call_llm(analysis: dict) -> str | None:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=BRIEFING_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(analysis, default=str)}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error("Claude API call failed: %s", e)

    if settings.llm_fallback_to_templates:
        return None  # caller uses template
    return None


def _template_fallback(analysis: dict) -> str:
    """Pure Python briefing template used when LLM is unavailable."""
    parts = []
    if analysis["critical_gauges"]:
        parts.append(f"CRITICAL: {', '.join(analysis['critical_gauges'])} above danger level.")
    if analysis["warning_gauges"]:
        parts.append(f"WARNING: {', '.join(analysis['warning_gauges'])} approaching danger level.")
    if analysis["silent_districts"]:
        parts.append(f"SILENT districts (no reports 4h+): {', '.join(analysis['silent_districts'])}.")
    if not parts:
        parts.append("Situation stable. All gauges below warning level.")

    return json.dumps({
        "summary": " ".join(parts),
        "key_risks": [],
        "recommended_actions": [],
        "data_gaps": analysis.get("silent_districts", []),
        "confidence_note": "Template fallback — LLM unavailable",
    })
