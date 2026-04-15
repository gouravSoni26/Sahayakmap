from fastapi import APIRouter, Depends, Query
from supabase import Client

from database import get_db

router = APIRouter()


@router.get("/alerts")
async def list_alerts(
    min_severity: int = Query(default=1, ge=1, le=5),
    unacknowledged_only: bool = Query(default=False),
    district_id: str | None = Query(default=None),
    db: Client = Depends(get_db),
):
    """Active alerts sorted by severity descending."""
    query = (
        db.table("alerts")
        .select("*")
        .gte("severity", min_severity)
        .order("severity", desc=True)
        .order("generated_at", desc=True)
    )
    if unacknowledged_only:
        query = query.eq("acknowledged", False)
    if district_id:
        query = query.eq("district_id", district_id)

    return {"alerts": query.execute().data or []}


@router.put("/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: str, db: Client = Depends(get_db)):
    """Mark an alert as acknowledged."""
    from datetime import datetime, timezone
    result = (
        db.table("alerts")
        .update({"acknowledged": True, "acknowledged_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", alert_id)
        .execute()
    )
    return {"ok": True, "alert": result.data[0] if result.data else None}
