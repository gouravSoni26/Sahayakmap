from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from config import settings
from database import get_db
from intelligence.briefing import generate_situation_brief

router = APIRouter()

# Columns returned to the frontend — never select("*") on JSONB-heavy tables
LIST_COLUMNS = (
    "id,region,summary_text,key_risks,recommendations,"
    "stale_sources,overall_confidence,data_freshness,generated_at"
)


# ── Response model ────────────────────────────────────────────────────────────

class BriefResponse(BaseModel):
    id: str
    region: str
    summary_text: str
    key_risks: list[Any]
    recommendations: list[Any]
    stale_sources: list[Any]
    overall_confidence: float
    data_freshness: dict[str, Any]
    generated_at: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/briefing", response_model=dict[str, BriefResponse])
async def latest_briefing(db: Client = Depends(get_db)):
    """Latest AI-generated situation brief."""
    result = (
        db.table("situation_briefs")
        .select(LIST_COLUMNS)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="No briefing generated yet — trigger POST /api/briefing/generate",
        )
    return {"brief": result.data[0]}


@router.post("/briefing/generate", response_model=dict[str, BriefResponse])
async def force_generate(db: Client = Depends(get_db)):
    """Force-generate a new situation brief immediately."""
    # Rate-limit: prevent API budget drain from rapid repeated calls
    last = (
        db.table("situation_briefs")
        .select("generated_at")
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    if last.data:
        last_at = datetime.fromisoformat(last.data[0]["generated_at"])
        # Supabase may return a naive timestamp (no +00:00 suffix). Make it
        # timezone-aware before subtracting — mixing naive and aware datetimes
        # raises TypeError at runtime.
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - last_at).total_seconds()
        if age_seconds < settings.force_generate_cooldown_sec:
            retry_after = int(settings.force_generate_cooldown_sec - age_seconds)
            raise HTTPException(
                status_code=429,
                detail=f"Brief generated {int(age_seconds)}s ago. Retry after {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

    brief = await generate_situation_brief(force=True)
    if brief is None:
        raise HTTPException(
            status_code=500,
            detail="Briefing generation failed — check backend logs for details.",
        )
    return {"brief": brief}
