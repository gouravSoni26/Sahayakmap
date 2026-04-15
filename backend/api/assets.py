from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from database import get_db

router = APIRouter()


class PositionUpdate(BaseModel):
    lat: float
    lng: float


class StatusUpdate(BaseModel):
    status: str  # AVAILABLE | DEPLOYED | IN_TRANSIT | MAINTENANCE


@router.get("/assets")
async def list_assets(db: Client = Depends(get_db)):
    """All rescue assets with current positions and status."""
    assets = db.table("rescue_assets").select("*, districts(name)").execute().data or []
    return {"assets": assets}


@router.put("/assets/{asset_id}/position")
async def update_position(asset_id: str, body: PositionUpdate, db: Client = Depends(get_db)):
    """Update asset position (used in simulation / manual tracking)."""
    from datetime import datetime, timezone
    result = (
        db.table("rescue_assets")
        .update({
            "location": f"POINT({body.lng} {body.lat})",
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", asset_id)
        .execute()
    )
    return {"asset": result.data[0] if result.data else None}


@router.put("/assets/{asset_id}/status")
async def update_status(asset_id: str, body: StatusUpdate, db: Client = Depends(get_db)):
    """Update asset operational status."""
    from datetime import datetime, timezone
    result = (
        db.table("rescue_assets")
        .update({
            "status": body.status,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", asset_id)
        .execute()
    )
    return {"asset": result.data[0] if result.data else None}
