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

    # Composite cursor: ISO_timestamp|uuid — prevents skipping rows with identical timestamps.
    next_cursor = (
        f"{data[-1]['generated_at']}|{data[-1]['id']}"
        if len(data) == limit else None
    )

    return {"alerts": data, "count": len(data), "next_cursor": next_cursor}


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
    # .select() is required — without it Supabase returns no data and result.data
    # is always empty, making the success check below always raise 409.
    result = (
        db.table("alerts")
        .update(update_payload)
        .eq("id", str(alert_id))
        .is_("acknowledged_at", "null")
        .select("id,acknowledged_at")  # type: ignore
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=409,
            detail="Alert was acknowledged by a concurrent request. Please refresh.",
        )

    return {"ok": True, "alert": result.data[0]}
