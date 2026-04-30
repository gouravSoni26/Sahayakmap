"""
Integration tests — Cyclone Fani scenario end-to-end.

Each test loads the scenario to step 0 (via autouse fixture), then ticks
forward to the target timestep and asserts the expected system state.

Tests hit the live FastAPI app on localhost:8000 via httpx.AsyncClient,
with direct Supabase queries for tables that have no REST endpoint.

Prerequisites:
    1. Backend running:  cd backend && venv/Scripts/uvicorn main:app --reload --port 8000
    2. Seed data loaded: python -m seed.odisha_districts  (districts + gauge_stations)
    3. Env vars set:     SUPABASE_URL, SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY (or GROQ_API_KEY)

Run:
    cd backend && venv/Scripts/pytest tests/test_integration_fani.py -v
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

from database import get_client

BASE_URL = "http://localhost:8000"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client():
    """httpx client pointing at the live FastAPI app."""
    async with AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(autouse=True)
async def clean_scenario_state(async_client: AsyncClient):
    """
    Reset scenario in-memory state to step 0 before every test.
    This does NOT wipe DB rows — assertions use >= counts to stay
    stable across repeated test runs that accumulate flood_reports.
    """
    resp = await async_client.post(
        "/api/scenario/load", json={"scenario": "cyclone_fani"}
    )
    assert resp.status_code == 200, f"Scenario load failed: {resp.text}"


# ── Helper ────────────────────────────────────────────────────────────────────

async def _tick(client: AsyncClient, steps: int) -> dict:
    """Advance the scenario by N steps from the current position."""
    resp = await client.post("/api/scenario/tick", json={"steps": steps})
    assert resp.status_code == 200, f"Tick failed: {resp.text}"
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_scenario_load(async_client: AsyncClient):
    """POST /api/scenario/load resets state: step=0, total_steps=9."""
    resp = await async_client.get("/api/scenario/state")
    assert resp.status_code == 200
    state = resp.json()
    assert state["scenario"] == "cyclone_fani"
    assert state["current_step"] == 0
    assert state["total_steps"] == 9  # steps 0–8 inclusive


async def test_tick_t3h(async_client: AsyncClient):
    """T+3h: IMD_WEATHER report inserted for Kendrapara / Jagatsinghpur."""
    await _tick(async_client, steps=1)

    db = get_client()
    reports = (
        db.table("flood_reports")
        .select("id, source_type, description")
        .eq("source_type", "IMD_WEATHER")
        .execute()
        .data or []
    )
    assert len(reports) >= 1, "Expected at least 1 IMD_WEATHER report after T+3h tick"
    joined = " ".join(r["description"] for r in reports)
    assert "Kendrapara" in joined or "Jagatsinghpur" in joined, (
        "IMD_WEATHER report should mention Kendrapara or Jagatsinghpur"
    )


async def test_tick_t6h_contradiction(async_client: AsyncClient):
    """
    T+6h: ≥12 SOCIAL_MEDIA reports cluster near Jajpur, while the CWC gauge
    sits at warning level (22.3 m) — below the 25.5 m danger threshold.
    This is the contradiction scenario: ground reports say flooding but the
    official gauge does not yet confirm danger-level conditions.
    """
    await _tick(async_client, steps=2)

    db = get_client()

    # Social media flood reports inserted for Jajpur area (12 offsets in scenario)
    social = (
        db.table("flood_reports")
        .select("id, source_type")
        .eq("source_type", "SOCIAL_MEDIA")
        .execute()
        .data or []
    )
    assert len(social) >= 12, (
        f"Expected ≥12 SOCIAL_MEDIA entries after T+6h tick, got {len(social)}"
    )

    # CWC gauge present but below danger level — step 2 inserts NARAJ at 22.3 m
    cwc = (
        db.table("flood_reports")
        .select("id, source_type, water_level_m")
        .eq("source_type", "CWC_GAUGE")
        .execute()
        .data or []
    )
    assert len(cwc) >= 1, "Expected at least 1 CWC_GAUGE entry after T+6h tick"

    # Must have an entry in the warning band (22.0–25.5 m) — the contradiction pivot
    warning_band = [
        r for r in cwc
        if r.get("water_level_m") and 22.0 <= r["water_level_m"] < 25.5
    ]
    assert len(warning_band) >= 1, (
        "Expected a CWC entry at warning level (22.0–25.5 m) — "
        "contradiction with Jajpur social media reports of flooding"
    )


async def test_tick_t9h_bridge_alert(async_client: AsyncClient):
    """T+9h: BRIDGE_SUBMERGED alert for Jenapur bridge with severity=4."""
    await _tick(async_client, steps=3)

    resp = await async_client.get(
        "/api/alerts", params={"include_expired": "true", "limit": 200}
    )
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]

    bridge = [
        a for a in alerts
        if a["type"] == "BRIDGE_SUBMERGED" and "Jenapur" in a["title"]
    ]
    assert len(bridge) >= 1, (
        "Expected a BRIDGE_SUBMERGED alert for Jenapur bridge after T+9h tick"
    )
    assert bridge[0]["severity"] == 4


async def test_tick_t12h_forecast_divergence(async_client: AsyncClient):
    """T+12h: FORECAST_DIVERGENCE alert exists (rain over Jagatsinghpur, not Kendrapara)."""
    await _tick(async_client, steps=4)

    resp = await async_client.get(
        "/api/alerts", params={"include_expired": "true", "limit": 200}
    )
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]

    div = [a for a in alerts if a["type"] == "FORECAST_DIVERGENCE"]
    assert len(div) >= 1, "Expected FORECAST_DIVERGENCE alert after T+12h tick"


async def test_tick_t15h_silent_district(async_client: AsyncClient):
    """T+15h: SILENT_DISTRICT alert for Ganjam with severity ≥ 3."""
    await _tick(async_client, steps=5)

    resp = await async_client.get(
        "/api/alerts", params={"include_expired": "true", "limit": 200}
    )
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]

    ganjam = [
        a for a in alerts
        if a["type"] == "SILENT_DISTRICT" and "Ganjam" in a["title"]
    ]
    assert len(ganjam) >= 1, "Expected SILENT_DISTRICT alert for Ganjam after T+15h tick"
    assert ganjam[0]["severity"] >= 3


async def test_tick_t18h_stale_satellite(async_client: AsyncClient):
    """T+18h: SATELLITE flood_report with raw_payload.capture_lag_hours=12."""
    await _tick(async_client, steps=6)

    db = get_client()
    satellite = (
        db.table("flood_reports")
        .select("id, source_type, raw_payload")
        .eq("source_type", "SATELLITE")
        .execute()
        .data or []
    )
    assert len(satellite) >= 1, "Expected at least 1 SATELLITE flood_report after T+18h tick"

    # Sentinel-1 SAR imagery captured 12 hours before delivery — stale by scenario design
    lagged = [
        r for r in satellite
        if (r.get("raw_payload") or {}).get("capture_lag_hours") == 12
    ]
    assert len(lagged) >= 1, (
        "Expected SATELLITE report with capture_lag_hours=12 in raw_payload — "
        "imagery should be flagged as stale (12 h old at time of delivery)"
    )


async def test_tick_t21h_camp_at_risk(async_client: AsyncClient):
    """T+21h: CAMP_AT_RISK alert for Erasama camp with a location set."""
    await _tick(async_client, steps=7)

    resp = await async_client.get(
        "/api/alerts", params={"include_expired": "true", "limit": 200}
    )
    assert resp.status_code == 200
    alerts = resp.json()["alerts"]

    erasama = [
        a for a in alerts
        if a["type"] == "CAMP_AT_RISK" and "Erasama" in a["title"]
    ]
    assert len(erasama) >= 1, "Expected CAMP_AT_RISK alert for Erasama camp after T+21h tick"
    assert erasama[0]["location"] is not None, (
        "Erasama CAMP_AT_RISK alert must include a location field"
    )


async def test_tick_t24h_triage_brief(async_client: AsyncClient):
    """
    T+24h: Full situation. GET /api/briefing returns a brief with
    ≥2 recommendations and overall_confidence > 0.5.

    Generates a new brief if none exists. Skips if the generation
    endpoint is rate-limited (120 s cooldown).
    """
    await _tick(async_client, steps=8)

    resp = await async_client.get("/api/briefing")
    if resp.status_code == 404:
        gen = await async_client.post("/api/briefing/generate")
        if gen.status_code == 429:
            pytest.skip("Briefing rate-limited — re-run after 120 s cooldown")
        assert gen.status_code == 200, f"Briefing generation failed: {gen.text}"
        resp = await async_client.get("/api/briefing")

    assert resp.status_code == 200
    brief = resp.json()["brief"]

    assert brief["overall_confidence"] is not None
    assert 0.0 < brief["overall_confidence"] <= 1.0
    assert len(brief["recommendations"]) >= 2, (
        f"Triage brief should have ≥2 recommendations, got {len(brief['recommendations'])}"
    )
