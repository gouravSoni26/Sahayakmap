"""
Simulation scenario API endpoints.

POST /api/scenario/load  — load the Cyclone Fani replay scenario
POST /api/scenario/tick  — advance by one timestep

Scenario data inserts into the same tables as real data.
The rest of the system is unaware it's a simulation.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from config import settings
from database import get_db

router = APIRouter()


class LoadRequest(BaseModel):
    scenario: str = "cyclone_fani"


class TickRequest(BaseModel):
    steps: int = 1


@router.post("/scenario/load")
async def load_scenario(body: LoadRequest, db: Client = Depends(get_db)):
    """
    Load a pre-built simulation scenario.
    Clears current simulation data and initialises the first timestep.
    """
    from seed.scenario_fani import SCENARIO_STEPS
    if body.scenario != "cyclone_fani":
        return {"error": f"Unknown scenario: {body.scenario}"}

    # Store scenario state in a simple KV via Supabase
    db.table("data_sources").upsert({
        "type": "SIMULATION",
        "name": f"scenario:{body.scenario}",
        "config": {"current_step": 0, "total_steps": len(SCENARIO_STEPS)},
        "status": "ACTIVE",
    }, on_conflict="name").execute()

    # Seed step 0
    await _apply_step(db, SCENARIO_STEPS[0])

    return {"ok": True, "scenario": body.scenario, "total_steps": len(SCENARIO_STEPS)}


@router.post("/scenario/tick")
async def tick_scenario(body: TickRequest, db: Client = Depends(get_db)):
    """Advance the simulation by N timesteps."""
    from seed.scenario_fani import SCENARIO_STEPS

    state = (
        db.table("data_sources")
        .select("config")
        .eq("type", "SIMULATION")
        .limit(1)
        .execute()
        .data
    )
    if not state:
        return {"error": "No scenario loaded. Call /scenario/load first."}

    current_step = state[0]["config"].get("current_step", 0)
    new_step = min(current_step + body.steps, len(SCENARIO_STEPS) - 1)

    for step_idx in range(current_step + 1, new_step + 1):
        await _apply_step(db, SCENARIO_STEPS[step_idx])

    db.table("data_sources").update(
        {"config": {"current_step": new_step, "total_steps": len(SCENARIO_STEPS)}}
    ).eq("type", "SIMULATION").execute()

    return {
        "ok": True,
        "step": new_step,
        "total_steps": len(SCENARIO_STEPS),
        "complete": new_step >= len(SCENARIO_STEPS) - 1,
    }


async def _apply_step(db: Client, step: dict) -> None:
    """Insert a scenario timestep's data into the live tables."""
    for report in step.get("flood_reports", []):
        db.table("flood_reports").insert(report).execute()
    for asset in step.get("asset_updates", []):
        db.table("rescue_assets").update(asset["data"]).eq("id", asset["id"]).execute()
    for alert in step.get("alerts", []):
        db.table("alerts").insert(alert).execute()
