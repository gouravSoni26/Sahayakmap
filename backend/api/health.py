import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Explicit column list — config JSONB excluded (contains connection strings/URLs)
SOURCE_COLUMNS = "id,type,name,status,last_fetched_at,update_frequency_min"

# Widened to 24h to cover all half-life windows in the system:
#   river gauge = 30min, social media = 2h, district report = 3h,
#   satellite = 6h — a 2h window silently cut off the longer-lived sources.
FRESHNESS_WINDOW_HOURS = 24


@router.get("/health")
async def health(db: Client = Depends(get_db)):
    """System status and data source freshness."""
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=FRESHNESS_WINDOW_HOURS)).isoformat()

    # ── Fetch data sources ────────────────────────────────────────────────────
    try:
        sources = db.table("data_sources").select(SOURCE_COLUMNS).execute().data or []
    except Exception as exc:
        logger.error("Health check database error fetching data_sources: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database unreachable: {exc}")

    # Build source_id → type lookup so we can map flood_reports rows back to
    # a source type (flood_reports has source_id FK, not source_type directly)
    source_type_map: dict[str, str] = {s["id"]: s["type"] for s in sources}

    # ── Fetch recent flood reports ────────────────────────────────────────────
    try:
        reports = (
            db.table("flood_reports")
            .select("source_id,reported_at")
            .gte("reported_at", since)
            .order("reported_at", desc=True)
            .execute()
            .data or []
        )
    except Exception as exc:
        logger.error("Health check database error fetching flood_reports: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database unreachable: {exc}")

    # Build freshness map: source_type → most recent reported_at
    # Reports are sorted newest-first, so the first occurrence per source_id is
    # already the latest — no extra max() needed.
    freshness: dict[str, str] = {}
    for r in reports:
        source_type = source_type_map.get(r["source_id"])
        if source_type and source_type not in freshness:
            freshness[source_type] = r["reported_at"]

    # ── Compute overall system status ─────────────────────────────────────────
    # Derived from individual source statuses — never hardcoded.
    if not sources:
        overall_status = "critical"
    elif all(s["status"] == "OFFLINE" for s in sources):
        overall_status = "critical"
    elif any(s["status"] in ("DEGRADED", "OFFLINE") for s in sources):
        overall_status = "degraded"
    else:
        overall_status = "ok"

    # ── Detect stalled scheduler jobs ─────────────────────────────────────────
    # Each data source has an update_frequency_min. If last_fetched_at is older
    # than 2× that window, the APScheduler job for that source has likely stopped.
    # Example: gauge job fires every 15 min → flag if last fetch > 30 min ago.
    stale_schedulers: list[str] = []
    for s in sources:
        freq = s.get("update_frequency_min")
        last_fetched = s.get("last_fetched_at")
        if freq and last_fetched:
            last = datetime.fromisoformat(last_fetched)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last) > timedelta(minutes=freq * 2):
                stale_schedulers.append(s["type"])

    return {
        "status": overall_status,
        "timestamp": now.isoformat(),
        "data_sources": [
            {
                "type": s["type"],
                "name": s["name"],
                "status": s["status"],
                "last_fetched_at": s.get("last_fetched_at"),
            }
            for s in sources
        ],
        "source_freshness": freshness,
        "stale_schedulers": stale_schedulers,
    }
