from fastapi import APIRouter, Depends, Query
from supabase import Client

from database import get_db
from fusion.engine import get_fused_map_data

router = APIRouter()


@router.get("/map/data")
async def map_data(
    hours: int = Query(default=6, ge=1, le=24),
    min_severity: int = Query(default=1, ge=1, le=5),
    db: Client = Depends(get_db),
):
    """
    Fused map data: gauge stations, flood reports, rescue assets,
    route status, relief camps, and detected conflicts.
    """
    return await get_fused_map_data(hours=hours, min_severity=min_severity)


@router.get("/gauges")
async def gauges(db: Client = Depends(get_db)):
    """All gauge stations with latest readings."""
    stations = db.table("gauge_stations").select("*").execute().data or []
    return {"gauges": stations}


@router.get("/gauges/{station_id}/history")
async def gauge_history(
    station_id: str,
    hours: int = Query(default=24, ge=1, le=72),
    db: Client = Depends(get_db),
):
    """Water level history for a gauge station."""
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    station = db.table("gauge_stations").select("*").eq("id", station_id).single().execute().data
    reports = (
        db.table("flood_reports")
        .select("water_level_m, water_level_trend, reported_at, confidence")
        .eq("source_type", "CWC_GAUGE")
        .gte("reported_at", since)
        .order("reported_at")
        .execute()
        .data or []
    )
    return {"station": station, "history": reports}


@router.get("/routes/status")
async def route_status(db: Client = Depends(get_db)):
    """Current road and bridge status."""
    statuses = (
        db.table("route_status")
        .select("*, routes(name, route_type, geometry)")
        .order("reported_at", desc=True)
        .execute()
        .data or []
    )
    return {"routes": statuses}


@router.get("/camps")
async def camps(db: Client = Depends(get_db)):
    """Active relief camps with flood risk estimates."""
    camps = (
        db.table("relief_camps")
        .select("*, districts(name)")
        .neq("status", "CLOSED")
        .order("flood_risk_hours")
        .execute()
        .data or []
    )
    return {"camps": camps}
