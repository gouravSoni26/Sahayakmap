"""
Main data fusion engine.

Aggregates reports from all sources, applies confidence + freshness weighting,
detects conflicts, and produces the unified map data payload.
"""
import logging
from datetime import datetime, timedelta, timezone

from database import get_client
from fusion.confidence import compute_fused_confidence
from fusion.temporal import freshness_factor, get_half_life, is_stale
from fusion.spatial import detect_conflicts

logger = logging.getLogger(__name__)


async def get_fused_map_data(
    bbox: tuple[float, float, float, float] | None = None,
    hours: int = 6,
    min_severity: int = 1,
) -> dict:
    """
    Build the unified map data payload consumed by GET /api/map/data.

    Returns gauges, reports, assets, routes, camps, conflicts, and
    freshness metadata — all in a single response to minimize frontend
    round-trips.
    """
    db = get_client()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # Fetch all recent flood reports
    query = (
        db.table("flood_reports")
        .select("*")
        .gte("reported_at", since)
        .gte("severity", min_severity)
        .order("reported_at", desc=True)
    )
    reports_result = query.execute()
    reports = reports_result.data or []

    # Fetch gauge stations with current readings
    gauges_result = db.table("gauge_stations").select("*").execute()
    gauges = gauges_result.data or []

    # Fetch rescue assets
    assets_result = db.table("rescue_assets").select("*").execute()
    assets = assets_result.data or []

    # Fetch route status
    routes_result = (
        db.table("route_status")
        .select("*, routes(name, route_type)")
        .gte("expires_at", datetime.now(timezone.utc).isoformat())
        .execute()
    )
    routes = routes_result.data or []

    # Fetch active relief camps
    camps_result = (
        db.table("relief_camps")
        .select("*")
        .neq("status", "CLOSED")
        .execute()
    )
    camps = camps_result.data or []

    # Separate gauge reports from social media for conflict detection
    gauge_reports = [r for r in reports if r["source_type"] == "CWC_GAUGE"]
    social_reports = [r for r in reports if r["source_type"] == "SOCIAL_MEDIA"]
    conflicts = detect_conflicts(gauge_reports, social_reports)

    # Compute freshness metadata per source type
    source_freshness = _compute_source_freshness(reports)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gauges": gauges,
        "reports": _annotate_freshness(reports),
        "assets": assets,
        "routes": routes,
        "camps": camps,
        "conflicts": [c.__dict__ for c in conflicts],
        "source_freshness": source_freshness,
    }


def _annotate_freshness(reports: list[dict]) -> list[dict]:
    """Add freshness_factor and is_stale fields to each report."""
    for r in reports:
        source_type = r.get("source_type", "SOCIAL_MEDIA")
        reported_at = datetime.fromisoformat(r["reported_at"])
        hl = get_half_life(source_type)
        ff = freshness_factor(reported_at, hl)
        r["freshness_factor"] = round(ff, 3)
        r["is_stale"] = ff < 0.25
    return reports


def _compute_source_freshness(reports: list[dict]) -> dict:
    """Return {source_type: last_reported_at} for the freshness status bar."""
    freshness: dict[str, str] = {}
    for r in reports:
        st = r.get("source_type", "UNKNOWN")
        ra = r.get("reported_at", "")
        if st not in freshness or ra > freshness[st]:
            freshness[st] = ra
    return freshness
