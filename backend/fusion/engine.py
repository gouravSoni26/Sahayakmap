"""
Main data fusion engine.

Aggregates reports from all sources, applies confidence + freshness weighting,
detects conflicts, and produces the unified map data payload.
"""
import logging
from datetime import datetime, timedelta, timezone

from database import get_client
from fusion.temporal import freshness_factor, get_half_life, STALE_THRESHOLD
from fusion.spatial import detect_conflicts

logger = logging.getLogger(__name__)

# Use the shared threshold from temporal.py so is_stale() and engine agree.
_STALE_THRESHOLD = STALE_THRESHOLD
_CAMP_STATUS_CLOSED = "CLOSED"

# Explicit column lists — never select("*") in list endpoints (CLAUDE.md rule #6).
# Include warning/danger thresholds because the engine merges them into gauge
# flood reports for conflict detection.
_GAUGE_COLUMNS = (
    "id, station_code, name, river_name, basin, "
    "danger_level_m, warning_level_m, highest_flood_level_m, location"
)
_ASSET_COLUMNS = "id, name, type, status, capacity, operator, district_id, location, last_updated_at"
_CAMP_COLUMNS = (
    "id, name, status, elevation_m, max_capacity, current_population, "
    "flood_risk_hours, district_id, location"
)


def _loc_to_lat_lng(location) -> tuple[float, float] | None:
    """
    Extract (lat, lng) from a Supabase PostGIS GeoJSON location object.

    Supabase returns geometry columns as GeoJSON: {type: "Point", coordinates: [lng, lat]}.
    Returns None if location is missing or not a recognised shape.
    """
    if not location:
        return None
    if isinstance(location, dict):
        coords = location.get("coordinates")
        if coords and len(coords) >= 2:
            lng, lat = coords[0], coords[1]
            return (float(lat), float(lng))
    return None


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
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=hours)).isoformat()

    # Fetch all recent flood reports, joining data_sources to get source type
    query = (
        db.table("flood_reports")
        .select("*, data_sources(type)")
        .gte("reported_at", since)
        .gte("severity", min_severity)
        .order("reported_at", desc=True)
    )
    reports_result = query.execute()
    reports = reports_result.data or []

    # Fetch gauge stations with current readings
    gauges_result = db.table("gauge_stations").select(_GAUGE_COLUMNS).execute()
    gauges = gauges_result.data or []

    # Fetch rescue assets
    assets_result = db.table("rescue_assets").select(_ASSET_COLUMNS).execute()
    assets = assets_result.data or []

    # Fetch route status
    routes_result = (
        db.table("route_status")
        .select("*, routes(name, route_type)")
        .gte("expires_at", now.isoformat())
        .execute()
    )
    routes = routes_result.data or []

    # Fetch active relief camps
    camps_result = (
        db.table("relief_camps")
        .select(_CAMP_COLUMNS)
        .neq("status", _CAMP_STATUS_CLOSED)
        .execute()
    )
    camps = camps_result.data or []

    # Annotate flat lat/lng onto every record so spatial functions and the bbox
    # filter can use plain number comparisons instead of re-parsing GeoJSON each time.
    for collection in (reports, gauges, assets, camps):
        for record in collection:
            coords = _loc_to_lat_lng(record.get("location"))
            if coords:
                record["lat"], record["lng"] = coords

    # Apply bounding box filter if provided — keeps only records whose location
    # falls within the visible map area. This reduces payload size when the user
    # is zoomed into a specific district instead of viewing all of Odisha.
    # Routes are intentionally excluded: they are LineString geometries, not points.
    # A point-based bbox check is meaningless for a road that spans many km.
    # Proper route clipping requires PostGIS ST_Intersects — deferred to a future query.
    if bbox:
        reports = [r for r in reports if _in_bbox(r, bbox)]
        gauges = [g for g in gauges if _in_bbox(g, bbox)]
        assets = [a for a in assets if _in_bbox(a, bbox)]
        camps = [c for c in camps if _in_bbox(c, bbox)]

    # Build a station lookup (station_code → station row) so we can merge
    # warning/danger thresholds into gauge flood reports for conflict detection.
    # spatial.detect_conflicts needs these threshold fields on each gauge report.
    station_by_code: dict[str, dict] = {}
    for g in gauges:
        code = g.get("station_code")
        if code:
            station_by_code[code] = g

    # Separate gauge reports from social media for conflict detection.
    # Merge station thresholds into gauge reports so detect_conflicts can compare
    # water_level_m against the actual warning/danger thresholds.
    gauge_reports = []
    for r in reports:
        if _source_type(r) != "CWC_GAUGE":
            continue
        station_code = (r.get("raw_payload") or {}).get("station_code")
        station = station_by_code.get(station_code or "", {})
        gauge_reports.append({
            **r,
            "warning_level_m": station.get("warning_level_m", r.get("warning_level_m", 0)),
            "danger_level_m": station.get("danger_level_m", r.get("danger_level_m", 999)),
        })

    social_reports = [r for r in reports if _source_type(r) == "SOCIAL_MEDIA"]
    conflicts = detect_conflicts(gauge_reports, social_reports)

    # Compute freshness metadata per source type
    source_freshness = _compute_source_freshness(reports)

    return {
        "generated_at": now.isoformat(),
        "gauges": gauges,
        "reports": _annotate_freshness(reports),
        "assets": assets,
        "routes": routes,
        "camps": camps,
        "conflicts": [c.__dict__ for c in conflicts],
        "source_freshness": source_freshness,
    }


def _source_type(report: dict) -> str:
    """Extract source type from the joined data_sources object."""
    return (report.get("data_sources") or {}).get("type", "UNKNOWN")


def _annotate_freshness(reports: list[dict]) -> list[dict]:
    """Add freshness_factor and is_stale fields to each report."""
    for r in reports:
        ra_str = r.get("reported_at")
        if not ra_str:
            r["freshness_factor"] = 0.0
            r["is_stale"] = True
            continue
        try:
            reported_at = datetime.fromisoformat(ra_str)
        except ValueError:
            r["freshness_factor"] = 0.0
            r["is_stale"] = True
            continue
        st = _source_type(r)
        hl = get_half_life(st)
        ff = freshness_factor(reported_at, hl)
        r["freshness_factor"] = round(ff, 3)
        r["is_stale"] = ff < _STALE_THRESHOLD
    return reports


def _compute_source_freshness(reports: list[dict]) -> dict:
    """Return {source_type: last_reported_at ISO string} for the freshness status bar."""
    latest: dict[str, datetime] = {}
    for r in reports:
        st = _source_type(r)
        ra_str = r.get("reported_at", "")
        if not ra_str:
            continue
        try:
            ra = datetime.fromisoformat(ra_str)
            if ra.tzinfo is None:
                ra = ra.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if st not in latest or ra > latest[st]:
            latest[st] = ra
    return {st: dt.isoformat() for st, dt in latest.items()}


def _in_bbox(record: dict, bbox: tuple[float, float, float, float]) -> bool:
    """
    Return True if a record's location falls within the bbox.

    Reads the flat lat/lng fields that were stamped onto every record by
    _loc_to_lat_lng() earlier in get_fused_map_data. Records without a
    parseable location are always included — we never silently drop data.

    bbox is (lat1, lng1, lat2, lng2) — southwest corner to northeast corner.
    """
    lat = record.get("lat")
    lng = record.get("lng")
    if lat is None or lng is None:
        return True
    lat1, lng1, lat2, lng2 = bbox
    return lng1 <= lng <= lng2 and lat1 <= lat <= lat2
