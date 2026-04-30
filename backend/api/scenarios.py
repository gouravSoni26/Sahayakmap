"""
Simulation scenario API endpoints.

POST /api/scenario/load  — load the Cyclone Fani replay scenario
POST /api/scenario/tick  — advance by one timestep

Scenario data inserts into the same tables as real data.
The rest of the system is unaware it's a simulation.

Scenario state is kept in-memory (_state dict) rather than in data_sources,
because "SIMULATION" is not a valid data_sources.type enum value.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory scenario state (reset on server restart — acceptable for demo)
_state: dict = {"scenario": None, "current_step": 0, "total_steps": 0}


class LoadRequest(BaseModel):
    scenario: str = "cyclone_fani"


class TickRequest(BaseModel):
    steps: int = Field(default=1, ge=1, description="Number of steps to advance (min 1)")


@router.post("/scenario/load")
async def load_scenario(body: LoadRequest, db: Client = Depends(get_db)):
    """
    Load a pre-built simulation scenario.
    Resets the step counter and applies step 0.
    """
    from seed.scenario_fani import SCENARIO_STEPS
    if body.scenario != "cyclone_fani":
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {body.scenario}")

    _state["scenario"] = body.scenario
    _state["current_step"] = 0
    _state["total_steps"] = len(SCENARIO_STEPS)

    await _apply_step(db, SCENARIO_STEPS[0])

    return {"ok": True, "scenario": body.scenario, "total_steps": len(SCENARIO_STEPS)}


@router.post("/scenario/tick")
async def tick_scenario(body: TickRequest, db: Client = Depends(get_db)):
    """Advance the simulation by N timesteps."""
    from seed.scenario_fani import SCENARIO_STEPS

    if not _state["scenario"]:
        raise HTTPException(status_code=400, detail="No scenario loaded. Call /scenario/load first.")

    current_step = _state["current_step"]
    new_step = min(current_step + body.steps, _state["total_steps"] - 1)

    for step_idx in range(current_step + 1, new_step + 1):
        await _apply_step(db, SCENARIO_STEPS[step_idx])
        _state["current_step"] = step_idx  # advance only after successful apply

    new_step = _state["current_step"]

    return {
        "ok": True,
        "step": new_step,
        "label": SCENARIO_STEPS[new_step]["label"],
        "total_steps": _state["total_steps"],
        "complete": new_step >= _state["total_steps"] - 1,
    }


@router.get("/scenario/state")
async def scenario_state():
    """Current simulation state."""
    return _state


def _as_ewkt(wkt: str) -> str:
    """Add SRID=4326 prefix if missing so PostgREST/PostGIS accepts the geometry."""
    if wkt and not wkt.startswith("SRID="):
        return f"SRID=4326;{wkt}"
    return wkt


async def _apply_step(db: Client, step: dict) -> None:
    """Insert a scenario timestep's data into the live tables."""
    errors: list[str] = []

    # Resolve _source_type markers to actual source_id FKs
    flood_reports = step.get("flood_reports", [])
    if flood_reports:
        needed_types = {r["_source_type"] for r in flood_reports if "_source_type" in r}
        sources_result = (
            db.table("data_sources")
            .select("id, type")
            .in_("type", list(needed_types))
            .execute()
        )
        source_id_map = {s["type"]: s["id"] for s in (sources_result.data or [])}

        # Fail fast if any required source type is not seeded — silent None would
        # cause every insert in this step to hit a NOT NULL constraint violation.
        missing = needed_types - source_id_map.keys()
        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"data_sources table missing rows for types: {sorted(missing)}. Run seed scripts first.",
            )

        now = datetime.now(timezone.utc).isoformat()
        for report in flood_reports:
            row = {k: v for k, v in report.items() if k != "_source_type"}
            try:
                source_type = report["_source_type"]
                row["source_id"] = source_id_map[source_type]
                row["source_type"] = source_type
            except KeyError as e:
                raise HTTPException(status_code=400, detail=f"Invalid source_type: {e}")
            row.setdefault("reported_at", now)
            if "location" in row:
                row["location"] = _as_ewkt(row["location"])
            try:
                result = db.table("flood_reports").insert(row).execute()
                if not result.data:
                    errors.append(f"flood_report insert returned no data: {row.get('description', '')[:60]}")
            except Exception as exc:
                logger.error("Unexpected error inserting flood_report: %s", exc)
                errors.append(f"flood_report insert failed: {exc}")

    for asset in step.get("asset_updates", []):
        try:
            db.table("rescue_assets").update(asset["data"]).eq("id", asset["id"]).execute()
        except Exception as exc:
            logger.error("Unexpected error updating asset id=%s: %s", asset.get("id"), exc)
            errors.append(f"asset update failed for id={asset.get('id')}: {exc}")

    alerts_to_insert = step.get("alerts", [])
    if alerts_to_insert:
        existing_alerts = (
            db.table("alerts")
            .select("type, title")
            .is_("acknowledged_at", "null")
            .execute()
            .data or []
        )
        existing_alert_keys = {(a["type"], a["title"]) for a in existing_alerts}

        for alert in alerts_to_insert:
            key = (alert.get("type"), alert.get("title"))
            if key in existing_alert_keys:
                continue
            row = dict(alert)
            if "location" in row:
                row["location"] = _as_ewkt(row["location"])
            try:
                result = db.table("alerts").insert(row).execute()
                if not result.data:
                    errors.append(f"alert insert returned no data: {row.get('title', '')[:60]}")
                else:
                    existing_alert_keys.add(key)
            except Exception as exc:
                logger.error("Unexpected error inserting alert: %s", exc)
                errors.append(f"alert insert failed: {exc}")

    if errors:
        raise HTTPException(status_code=500, detail={"step_errors": errors})
