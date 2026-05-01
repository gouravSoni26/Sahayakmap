from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from database import get_db

router = APIRouter()

# ── Column list for list view ────────────────────────────────────────────────
# Excludes heavy fields: raw_payload (large JSONB) and description (long text).
# Those are only fetched in a detail view (GET /alerts/{id}).
LIST_COLUMNS = (
    "id,type,severity,title,district_id,location,"
    "generated_at,acknowledged_at,expires_at,recommended_action"
)
# Detail view adds description (excluded from list view — long text field).
DETAIL_COLUMNS = (
    "id,type,severity,title,description,district_id,location,"
    "generated_at,acknowledged_at,expires_at,recommended_action"
)
# Explicit columns for linked flood_reports — never select("*").
REPORT_COLUMNS = "id,source_type,severity,description,location,reported_at"


# ── Query Builder ────────────────────────────────────────────────────────────

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


def _apply_cursor(q, cursor: str):
    """
    Composite cursor filter: 'ISO_timestamp|uuid'

    Using generated_at alone as a cursor skips alerts that share the same
    timestamp at a page boundary (strict .lt() excludes them on the next page).
    The composite cursor adds id as a tiebreaker so no row is ever skipped.
    """
    parts = cursor.split("|", 1)
    if len(parts) == 2:
        cursor_time, cursor_id = parts
        return q.or_(
            f"generated_at.lt.{cursor_time},"
            f"and(generated_at.eq.{cursor_time},id.lt.{cursor_id})"
        )
    # Legacy single-field cursor — kept for backwards compatibility
    return q.lt("generated_at", cursor)


# ── Request body for acknowledge ─────────────────────────────────────────────
# acknowledged_by requires a DB migration before use:
#   ALTER TABLE alerts ADD COLUMN acknowledged_by TEXT;
class AckRequest(BaseModel):
    acknowledged_by: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def list_alerts(
    min_severity: int = Query(default=1, ge=1, le=5),
    unacknowledged_only: bool = Query(default=False),
    district_id: UUID | None = Query(default=None),
    include_expired: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(
        default=None,
        description="Pass next_cursor from a previous response to fetch the next page. Format: ISO_timestamp|uuid.",
    ),
    db: Client = Depends(get_db),
):
    """
    Active alerts sorted by severity desc, then generated_at desc.

    Pagination: cursor-based. On first call omit cursor. Each response
    includes next_cursor — pass it as ?cursor=... to fetch the next page.
    next_cursor is null when there are no more results.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    base_query = (
        db.table("alerts")
        .select(LIST_COLUMNS)
        .gte("severity", min_severity)
        .order("severity", desc=True)
        .order("generated_at", desc=True)
        .order("id", desc=True)   # tiebreaker — makes cursor pagination deterministic
        .limit(limit)
    )

    filters = [
        Filter(
            active=not include_expired,
            apply=lambda q: q.or_(f"expires_at.is.null,expires_at.gt.{now_iso}"),
        ),
        Filter(
            active=unacknowledged_only,
            apply=lambda q: q.is_("acknowledged_at", "null"),
        ),
        Filter(
            active=district_id is not None,
            apply=lambda q: q.eq("district_id", district_id),
        ),
        # Cursor filter: composite (generated_at|id) handles same-timestamp ties.
        # Plain .lt("generated_at") would skip rows sharing the boundary timestamp.
        Filter(
            active=cursor is not None,
            apply=lambda q: _apply_cursor(q, cursor),
        ),
    ]

    query = build_query(base_query, filters)
    data = query.execute().data or []

    # Deduplicate by (type, title) — scenario ticks can accumulate many records
    # with identical type+title but different UUIDs. Keep the most recent per pair
    # (data is already sorted generated_at desc so first occurrence wins).
    seen_keys: set[tuple] = set()
    deduped: list = []
    for row in data:
        key = (row.get("type"), row.get("title"))
        if key not in seen_keys:
            seen_keys.add(key)
            deduped.append(row)
    data = deduped

    # Composite cursor: ISO_timestamp|uuid — prevents skipping rows with identical timestamps.
    next_cursor = (
        f"{data[-1]['generated_at']}|{data[-1]['id']}"
        if len(data) == limit else None
    )

    return {"alerts": data, "count": len(data), "next_cursor": next_cursor}


# ── Repository ───────────────────────────────────────────────────────────────

class AlertRepository:
    """All database operations for the alerts table live here."""

    def __init__(self, db: Client):
        self.db = db

    def get_by_id(self, alert_id: str) -> dict | None:
        """Fetch a single alert plus its linked flood_reports. Returns None if not found."""
        result = self.db.table("alerts").select(DETAIL_COLUMNS).eq("id", alert_id).execute()
        if not result.data:
            return None
        alert = result.data[0]

        # Resolve linked report IDs via alert_reports junction table
        junction = (
            self.db.table("alert_reports")
            .select("flood_report_id")
            .eq("alert_id", alert_id)
            .execute()
            .data or []
        )
        report_ids = [r["flood_report_id"] for r in junction]
        reports = []
        if report_ids:
            reports = (
                self.db.table("flood_reports")
                .select(REPORT_COLUMNS)
                .in_("id", report_ids)
                .execute()
                .data or []
            )
        alert["flood_reports"] = reports
        return alert


# ── Dependency Injection ──────────────────────────────────────────────────────

def get_alert_repository(db: Client = Depends(get_db)) -> AlertRepository:
    return AlertRepository(db)


def get_valid_alert(
    alert_id: UUID,
    repo: AlertRepository = Depends(get_alert_repository),
) -> str:
    """
    Dependency that validates the alert_id format (UUID) AND confirms the
    alert exists. Raises 404 if not found, 422 if UUID is malformed.
    """
    result = (
        repo.db.table("alerts")
        .select("id")
        .eq("id", str(alert_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return str(alert_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/alerts/{alert_id}")
async def get_alert(
    alert_id: str = Depends(get_valid_alert),
    repo: AlertRepository = Depends(get_alert_repository),
):
    """
    Full alert detail including linked flood_reports via alert_reports junction.
    - 404 if alert_id does not exist.
    - 422 if alert_id is not a valid UUID.
    """
    alert = repo.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")
    return {"alert": alert}


@router.put("/alerts/{alert_id}/ack")
async def acknowledge_alert(
    alert_id: UUID,  # FastAPI auto-validates UUID format — returns HTTP 422 if malformed
    body: AckRequest = AckRequest(),
    db: Client = Depends(get_db),
):
    """
    Mark an alert as acknowledged.
    - 404 if the alert ID does not exist.
    - 409 if the alert was already acknowledged (includes who/when).
    - 409 if a race condition is detected between check and update.
    """
    # ── Step 1: Check the alert exists and its current ack state ──────────────
    # acknowledged_by is intentionally excluded here — the column requires a DB
    # migration (ALTER TABLE alerts ADD COLUMN acknowledged_by TEXT) and selecting
    # a missing column causes Supabase to return a 400 error.
    existing = (
        db.table("alerts")
        .select("id,acknowledged_at")
        .eq("id", str(alert_id))
        .execute()
    )

    if not existing.data:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    current = existing.data[0]

    if current["acknowledged_at"] is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Alert is already acknowledged.",
                "acknowledged_at": current["acknowledged_at"],
            },
        )

    # ── Step 2: Build update payload ─────────────────────────────────────────
    update_payload = {"acknowledged_at": datetime.now(timezone.utc).isoformat()}
    if body.acknowledged_by:
        update_payload["acknowledged_by"] = body.acknowledged_by

    # ── Step 3: Optimistic lock — only update if still unacknowledged ─────────
    # The .is_("acknowledged_at", "null") condition ensures that if another request
    # acknowledged between Step 1 and Step 3, this update will match 0 rows.
    # NOTE: .select() must NOT be chained after filter methods — postgrest-py's
    # SyncFilterRequestBuilder does not expose .select(). The update() call
    # already returns the updated rows in result.data by default.
    result = (
        db.table("alerts")
        .update(update_payload)
        .eq("id", str(alert_id))
        .is_("acknowledged_at", "null")
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=409,
            detail="Alert was acknowledged by a concurrent request. Please refresh.",
        )

    return {"ok": True, "alert": result.data[0]}
