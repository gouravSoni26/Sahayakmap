from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from database import get_db

router = APIRouter()


# ── Column lists ──────────────────────────────────────────────────────────────
# boundary is a heavy GEOMETRY polygon — excluded (frontend uses /api/map/data).

DISTRICT_COLUMNS = (
    "id,name,state,population,area_sq_km,created_at,"
    "district_status(signal_strength,last_report_at)"
)

REPORT_COLUMNS = (
    "id,district_id,severity,water_level_m,water_level_trend,"
    "confidence,reported_at,description,is_verified"
)

ASSET_COLUMNS = (
    "id,type,name,capacity,location,status,assigned_district_id,last_updated_at"
)

CAMP_COLUMNS = (
    "id,name,location,district_id,elevation_m,max_capacity,"
    "current_population,status,flood_risk_hours,last_updated_at"
)


# ── Custom exception ──────────────────────────────────────────────────────────
# Repository is a pure data layer — it must not know about HTTP.
# It raises RepositoryError. Endpoints and dependencies convert that to HTTP 503.

class RepositoryError(Exception):
    """Raised when a database operation fails."""
    pass


# ── Repository ────────────────────────────────────────────────────────────────
# All DB logic for districts lives here. Endpoints never touch Supabase directly.

class DistrictRepository:
    """All database operations for districts and their associated data."""

    def __init__(self, db: Client):
        self.db = db

    def get_all(self) -> list[dict]:
        """Fetch all districts with their operational status."""
        try:
            return (
                self.db.table("districts")
                .select(DISTRICT_COLUMNS)
                .execute()
                .data or []
            )
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch districts: {exc}") from exc

    def get_one(self, district_id: str) -> dict | None:
        """Fetch a single district by ID. Returns None if not found."""
        try:
            result = (
                self.db.table("districts")
                .select(DISTRICT_COLUMNS)
                .eq("id", district_id)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch district {district_id}: {exc}") from exc

    def get_reports(self, district_id: str, since: str, limit: int = 100) -> list[dict]:
        """Fetch flood reports for a district since a given ISO timestamp."""
        try:
            return (
                self.db.table("flood_reports")
                .select(REPORT_COLUMNS)
                .eq("district_id", district_id)
                .gte("reported_at", since)
                .order("reported_at", desc=True)
                .limit(limit)  # cap response size — a district can have thousands of reports
                .execute()
                .data or []
            )
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch reports for district {district_id}: {exc}") from exc

    def get_assets(self, district_id: str) -> list[dict]:
        """Fetch rescue assets assigned to a district, most recently updated first."""
        try:
            return (
                self.db.table("rescue_assets")
                .select(ASSET_COLUMNS)
                .eq("assigned_district_id", district_id)
                .order("last_updated_at", desc=True)
                .execute()
                .data or []
            )
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch assets for district {district_id}: {exc}") from exc

    def get_camps(self, district_id: str) -> list[dict]:
        """Fetch relief camps in a district, ordered alphabetically by name."""
        try:
            return (
                self.db.table("relief_camps")
                .select(CAMP_COLUMNS)
                .eq("district_id", district_id)
                .order("name")
                .execute()
                .data or []
            )
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch camps for district {district_id}: {exc}") from exc


# ── Dependencies ──────────────────────────────────────────────────────────────

def get_district_repository(db: Client = Depends(get_db)) -> DistrictRepository:
    """Builds and returns a DistrictRepository. FastAPI creates it per-request."""
    return DistrictRepository(db)


def get_valid_district(
    district_id: UUID,
    repo: DistrictRepository = Depends(get_district_repository),
) -> dict:
    """
    Security guard for district endpoints.

    Step 1 — UUID format: FastAPI validates via the UUID type hint.
              A malformed ID (e.g. 'potato') returns 422 before this runs.
    Step 2 — Existence check: raises 404 if district not found.
    Step 3 — Returns the full district dict so the endpoint skips a second DB call.
    """
    try:
        district = repo.get_one(str(district_id))
    except RepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if district is None:
        raise HTTPException(
            status_code=404,
            detail=f"District '{district_id}' not found.",
        )
    return district


# ── Endpoints ─────────────────────────────────────────────────────────────────
# Intentionally thin — no DB code, no validation logic.
# Each endpoint does exactly one thing: coordinate the response.

@router.get("/districts")
async def list_districts(
    repo: DistrictRepository = Depends(get_district_repository),
):
    """District overview with operational signal strength and last report time."""
    try:
        data = repo.get_all()
    except RepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"districts": data, "count": len(data)}


@router.get("/districts/{district_id}")
async def district_detail(
    hours: int = Query(default=6, ge=1, le=72),
    district: dict = Depends(get_valid_district),
    repo: DistrictRepository = Depends(get_district_repository),
):
    """
    District detail with recent flood reports, rescue assets, and relief camps.

    Optional:
    - hours: lookback window for flood reports (default 6, min 1, max 72)
    """
    district_id = district["id"]
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    try:
        reports = repo.get_reports(district_id, since)
        assets  = repo.get_assets(district_id)
        camps   = repo.get_camps(district_id)
    except RepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "district": district,
        "recent_reports": reports,
        "assets": assets,
        "camps": camps,
    }
