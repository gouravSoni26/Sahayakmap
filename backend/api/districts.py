from fastapi import APIRouter, Depends
from supabase import Client

from database import get_db

router = APIRouter()


@router.get("/districts")
async def list_districts(db: Client = Depends(get_db)):
    """District overview: signal strength and recent report count."""
    districts = db.table("districts").select("*").execute().data or []
    return {"districts": districts}


@router.get("/districts/{district_id}")
async def district_detail(district_id: str, db: Client = Depends(get_db)):
    """District detail with all associated data."""
    from datetime import datetime, timedelta, timezone
    since = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()

    district = db.table("districts").select("*").eq("id", district_id).single().execute().data
    reports = (
        db.table("flood_reports")
        .select("*")
        .eq("district_id", district_id)
        .gte("reported_at", since)
        .order("reported_at", desc=True)
        .execute()
        .data or []
    )
    assets = (
        db.table("rescue_assets")
        .select("*")
        .eq("assigned_district_id", district_id)
        .execute()
        .data or []
    )
    camps = (
        db.table("relief_camps")
        .select("*")
        .eq("district_id", district_id)
        .execute()
        .data or []
    )

    return {
        "district": district,
        "recent_reports": reports,
        "assets": assets,
        "camps": camps,
    }
