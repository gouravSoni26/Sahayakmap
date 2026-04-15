from fastapi import APIRouter, Depends
from supabase import Client

from database import get_db

router = APIRouter()


@router.get("/briefing")
async def latest_briefing(db: Client = Depends(get_db)):
    """Latest AI-generated situation brief."""
    result = (
        db.table("situation_briefs")
        .select("*")
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    brief = result.data[0] if result.data else None
    return {"brief": brief}


@router.post("/briefing/generate")
async def force_generate(db: Client = Depends(get_db)):
    """Force-generate a new situation brief immediately."""
    from intelligence.briefing import generate_situation_brief
    brief = await generate_situation_brief()
    return {"brief": brief}
