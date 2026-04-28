from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from database import get_db

router = APIRouter()


# ── Enums ─────────────────────────────────────────────────────────────────────

class AssetType(str, Enum):
    BOAT = "BOAT"
    HELICOPTER = "HELICOPTER"
    RESCUE_TEAM = "RESCUE_TEAM"
    SUPPLY_TRUCK = "SUPPLY_TRUCK"


class AssetStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DEPLOYED = "DEPLOYED"
    IN_TRANSIT = "IN_TRANSIT"
    MAINTENANCE = "MAINTENANCE"


# ── Column lists ──────────────────────────────────────────────────────────────

LIST_COLUMNS = "id,type,name,capacity,location,status,assigned_district_id,last_updated_at,districts(name)"
UPDATE_COLUMNS = "id,type,name,capacity,location,status,assigned_district_id,last_updated_at"


# ── Request body models ───────────────────────────────────────────────────────

class PositionUpdate(BaseModel):
    lat: float
    lng: float


class StatusUpdate(BaseModel):
    status: AssetStatus


# ── Query Builder ─────────────────────────────────────────────────────────────

@dataclass
class Filter:
    """A single optional query filter — only applied when active is True."""
    active: bool
    apply: Callable


def build_query(base_query, filters: list[Filter]):
    """Apply all active filters to the base query and return the result."""
    for f in filters:
        if f.active:
            base_query = f.apply(base_query)
    return base_query


# ══════════════════════════════════════════════════════════════════════════════
# ALTERNATIVE 1 — Repository Pattern
# The AssetRepository class owns ALL database logic for rescue_assets.
# Endpoints never talk to the DB directly — they go through the repository.
# If the database changes (e.g. switch from Supabase to Postgres directly),
# only this class needs to change. Endpoints stay exactly the same.
# ══════════════════════════════════════════════════════════════════════════════

class AssetRepository:
    """All database operations for the rescue_assets table live here."""

    def __init__(self, db: Client):
        # The repository holds the DB client — passed in at creation time
        self.db = db

    def get_all(
        self,
        asset_type: AssetType | None,
        status: AssetStatus | None,
        district_id: str | None,
    ) -> list[dict]:
        """Fetch all assets, with optional filters applied."""
        base_query = self.db.table("rescue_assets").select(LIST_COLUMNS)

        filters = [
            Filter(
                active=asset_type is not None,
                apply=lambda q: q.eq("type", asset_type.value), # pyright: ignore[reportOptionalMemberAccess]
            ),
            Filter(
                active=status is not None,
                apply=lambda q: q.eq("status", status.value), # pyright: ignore[reportOptionalMemberAccess]
            ),
            Filter(
                active=district_id is not None,
                apply=lambda q: q.eq("assigned_district_id", district_id),
            ),
        ]

        return build_query(base_query, filters).execute().data or []

    def update_position(self, asset_id: str, lat: float, lng: float) -> dict | None:
        """Move an asset to a new location. Returns updated row or None if not found."""
        self.db.table("rescue_assets").update({
            "location": f"SRID=4326;POINT({lng} {lat})",
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", asset_id).execute()
        result = self.db.table("rescue_assets").select(UPDATE_COLUMNS).eq("id", asset_id).execute()
        return result.data[0] if result.data else None

    def update_status(self, asset_id: str, status: AssetStatus) -> dict | None:
        """Change an asset's operational status. Returns updated row or None if not found."""
        self.db.table("rescue_assets").update({
            "status": status.value,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", asset_id).execute()
        result = self.db.table("rescue_assets").select(UPDATE_COLUMNS).eq("id", asset_id).execute()
        return result.data[0] if result.data else None


# ══════════════════════════════════════════════════════════════════════════════
# ALTERNATIVE 4 — Dependency Injection for Validation
# get_asset_repository() and get_valid_asset() are reusable Depends() functions.
# Any endpoint that needs a validated asset just declares it as a parameter —
# FastAPI runs the dependency automatically before the endpoint function runs.
# ══════════════════════════════════════════════════════════════════════════════

def get_asset_repository(db: Client = Depends(get_db)) -> AssetRepository:
    """
    Dependency that builds and returns an AssetRepository.
    Endpoints declare: repo: AssetRepository = Depends(get_asset_repository)
    FastAPI creates it automatically on every request.
    """
    return AssetRepository(db)


def get_valid_asset(
    asset_id: UUID,
    repo: AssetRepository = Depends(get_asset_repository),
) -> str:
    """
    Dependency that validates the asset_id format (UUID) AND confirms the
    asset exists in the database. Raises 404 if not found.

    Endpoints declare: asset_id: str = Depends(get_valid_asset)
    They receive the clean string ID if valid, or FastAPI stops with 404.

    This means NO endpoint needs to write its own existence check — ever.
    """
    # Check the asset exists by trying to fetch just its id
    result = (
        repo.db.table("rescue_assets")
        .select("id")
        .eq("id", str(asset_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")

    # Return the string form of the UUID for use in the endpoint
    return str(asset_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────
# Notice how clean these are now:
# - No DB code inside endpoints (that's the Repository's job)
# - No existence checks inside endpoints (that's get_valid_asset's job)
# - Each endpoint does exactly ONE thing: handle the HTTP request

@router.get("/assets")
async def list_assets(
    asset_type: AssetType | None = Query(default=None),
    status: AssetStatus | None = Query(default=None),
    district_id: str | None = Query(default=None),
    repo: AssetRepository = Depends(get_asset_repository),
):
    """
    All rescue assets with current positions and status.

    Optional filters:
    - asset_type: BOAT | HELICOPTER | RESCUE_TEAM | SUPPLY_TRUCK
    - status:     AVAILABLE | DEPLOYED | IN_TRANSIT | MAINTENANCE
    - district_id: UUID of the assigned district
    """
    data = repo.get_all(asset_type, status, district_id)
    return {"assets": data, "count": len(data)}


@router.put("/assets/{asset_id}/position")
async def update_position(
    body: PositionUpdate,
    asset_id: str = Depends(get_valid_asset),  # validated UUID + existence check
    repo: AssetRepository = Depends(get_asset_repository),
):
    """
    Update asset position (used in simulation / manual tracking).
    WKT format: POINT(lng lat) — longitude first, latitude second (GIS standard).
    """
    asset = repo.update_position(asset_id, body.lat, body.lng)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return {"asset": asset}


@router.put("/assets/{asset_id}/status")
async def update_status(
    body: StatusUpdate,
    asset_id: str = Depends(get_valid_asset),  # validated UUID + existence check
    repo: AssetRepository = Depends(get_asset_repository),
):
    """Update asset operational status."""
    asset = repo.update_status(asset_id, body.status)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
    return {"asset": asset}
