import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from shapely import wkb as shapely_wkb
from supabase import Client

from database import get_db
from fusion.engine import get_fused_map_data

logger = logging.getLogger(__name__)

router = APIRouter()

# Explicit column lists — never select("*") in list endpoints (CLAUDE.md rule #6)
_GAUGE_COLUMNS = (
    "id, station_code, name, river_name, basin, "
    "danger_level_m, warning_level_m, highest_flood_level_m, location"
)
_CAMP_COLUMNS = (
    "id, name, status, elevation_m, max_capacity, current_population, "
    "flood_risk_hours, district_id, last_updated_at, location, districts(name)"
)
_CAMP_STATUS_CLOSED = "CLOSED"

# Hour range constants — avoids magic numbers in Query() calls
_DEFAULT_MAP_HOURS = 6
_MAX_MAP_HOURS = 24
_DEFAULT_HISTORY_HOURS = 24
_MAX_HISTORY_HOURS = 72


def _add_lat_lng(record: dict) -> dict:
    """
    Parse the PostGIS WKB hex location field into plain lat/lng floats.

    Supabase returns GEOMETRY columns as EWKB hex strings (e.g. '0101000020E6100000...').
    Leaflet and the React frontend need plain {lat, lng} numbers — not WKB.
    shapely.wkb.loads handles both standard WKB and PostGIS EWKB transparently.
    """
    loc = record.get("location")
    if not loc:
        return record
    try:
        geom = shapely_wkb.loads(loc, hex=True)
        record["lat"] = round(geom.y, 6)
        record["lng"] = round(geom.x, 6)
    except Exception as e:
        logger.warning("Failed to parse WKB location for record %s: %s", record.get("id"), e)
        record["lat"] = None
        record["lng"] = None
    return record


@router.get("/map/data")
async def map_data(
    hours: int = Query(default=_DEFAULT_MAP_HOURS, ge=1, le=_MAX_MAP_HOURS),
    min_severity: int = Query(default=1, ge=1, le=5),
    bbox: str | None = Query(default=None, description="lat1,lng1,lat2,lng2"),
):
    """
    Fused map data: gauge stations, flood reports, rescue assets,
    route status, relief camps, and detected conflicts.
    """
    parsed_bbox = None
    if bbox:
        try:
            parts = [float(x) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox must have exactly 4 values")
            lat1, lng1, lat2, lng2 = parts
            if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
                raise ValueError("Latitude out of bounds (must be -90 to 90)")
            if not (-180 <= lng1 <= 180 and -180 <= lng2 <= 180):
                raise ValueError("Longitude out of bounds (must be -180 to 180)")
            parsed_bbox = (lat1, lng1, lat2, lng2)
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid bbox: {e}",
            )

    return await get_fused_map_data(bbox=parsed_bbox, hours=hours, min_severity=min_severity)


@router.get("/gauges")
async def gauges(
    db: Client = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """All gauge stations with latest readings."""
    stations = (
        db.table("gauge_stations")
        .select(_GAUGE_COLUMNS)
        .range(offset, offset + limit - 1)
        .execute()
        .data or []
    )
    return {"gauges": [_add_lat_lng(s) for s in stations], "count": len(stations)}


@router.get("/gauges/{station_id}/history")
async def gauge_history(
    station_id: UUID,
    hours: int = Query(default=_DEFAULT_HISTORY_HOURS, ge=1, le=_MAX_HISTORY_HOURS),
    db: Client = Depends(get_db),
):
    """Water level history for a gauge station."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    station = (
        db.table("gauge_stations")
        .select("id, station_code, name, river_name, danger_level_m, warning_level_m, location")
        .eq("id", str(station_id))
        .single()
        .execute()
        .data
    )
    if not station:
        raise HTTPException(status_code=404, detail="Gauge station not found")

    station = _add_lat_lng(station)

    # Filter flood_reports for this specific station via station_code stored in raw_payload.
    # cwc_gauge.py stores {"station_code": code, ...} in raw_payload on every insert.
    reports = (
        db.table("flood_reports")
        .select("water_level_m, water_level_trend, reported_at, confidence")
        .filter("raw_payload->>station_code", "eq", station["station_code"])
        .gte("reported_at", since)
        .order("reported_at")
        .execute()
        .data or []
    )

    return {"station": station, "history": reports}


@router.get("/routes/status")
async def route_status(db: Client = Depends(get_db)):
    """Current road and bridge status (non-expired, one record per route)."""
    now = datetime.now(timezone.utc).isoformat()
    statuses = (
        db.table("route_status")
        .select("id, route_id, status, confidence, reported_at, expires_at, routes(name, route_type)")
        .gte("expires_at", now)
        .order("reported_at", desc=True)
        .execute()
        .data or []
    )
    # Deduplicate — keep only the most recent status per route.
    # statuses is already ordered newest-first, so the first hit per route_id wins.
    # Without this, the same road could appear multiple times with stale duplicate overlays.
    seen: set[str] = set()
    deduped = []
    for s in statuses:
        rid = s.get("route_id")
        if rid and rid not in seen:
            seen.add(rid)
            deduped.append(s)
    return {"routes": deduped}


@router.get("/camps")
async def camps(
    db: Client = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Active relief camps with flood risk estimates."""
    result = (
        db.table("relief_camps")
        .select(_CAMP_COLUMNS)
        .neq("status", _CAMP_STATUS_CLOSED)
        .order("flood_risk_hours", desc=False, nullsfirst=False)
        .range(offset, offset + limit - 1)
        .execute()
        .data or []
    )
    return {"camps": [_add_lat_lng(c) for c in result], "count": len(result)}
