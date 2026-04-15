from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from supabase import Client

from database import get_db

router = APIRouter()


@router.get("/health")
async def health(db: Client = Depends(get_db)):
    """System status and data source freshness."""
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=2)).isoformat()

    # Check when each source type last reported
    reports = (
        db.table("flood_reports")
        .select("source_type, reported_at")
        .gte("reported_at", since)
        .order("reported_at", desc=True)
        .execute()
        .data or []
    )

    freshness: dict[str, str] = {}
    for r in reports:
        st = r["source_type"]
        if st not in freshness:
            freshness[st] = r["reported_at"]

    sources = db.table("data_sources").select("*").execute().data or []

    return {
        "status": "ok",
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
    }
