"""
CWC river gauge data ingestion.

Real CWC data is available from https://ffs.india-water.gov.in but requires
scraping HTML tables. Until that is implemented, this module generates
realistic synthetic gauge readings based on known Mahanadi station metadata.

TODO (production): Implement real CWC scraping from https://ffs.india-water.gov.in
For now, all records generated here are SYNTHETIC — mark them accordingly.
"""
import logging
import random
from datetime import datetime, timedelta, timezone

from database import get_client
from seed.gauge_stations import GAUGE_STATIONS

logger = logging.getLogger(__name__)

# 0.95: calibrated government instrument. Not 1.0 because equipment can malfunction.
_CWC_BASE_CONFIDENCE = 0.95

# CWC gauges report every 15 min. After 30 min with no update = 2 missed reports.
_GAUGE_HALF_LIFE_MIN = 30
# expires_at = 2× half-life = STALE_THRESHOLD. After this, the reading is unreliable.
_GAUGE_EXPIRES_AFTER_MIN = _GAUGE_HALF_LIFE_MIN * 2


async def fetch_gauge_readings() -> None:
    """
    Fetch current water level readings for all Mahanadi gauge stations.
    Currently generates synthetic data; replace with real CWC scrape.
    """
    db = get_client()

    # Resolve the CWC_GAUGE data source ID — required for flood_reports.source_id (NOT NULL).
    # This source row must exist; run seed.data_sources before the scheduler starts.
    source_result = (
        db.table("data_sources").select("id").eq("type", "CWC_GAUGE").limit(1).execute()
    )
    if not source_result.data:
        logger.error(
            "No CWC_GAUGE row in data_sources — run seed.data_sources first. Skipping gauge fetch."
        )
        return
    cwc_source_id = source_result.data[0]["id"]

    # Fetch station IDs from DB
    result = db.table("gauge_stations").select("id, station_code, danger_level_m, warning_level_m").execute()
    stations = {s["station_code"]: s for s in result.data}

    # Single timestamp for the whole batch — all readings are from the same fetch cycle.
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(minutes=_GAUGE_EXPIRES_AFTER_MIN)).isoformat()

    rows = []
    for code, meta in GAUGE_STATIONS.items():
        station = stations.get(code)
        if not station:
            logger.warning("Station %s not found in DB — run seed.gauge_stations first", code)
            continue

        level = _synthetic_level(meta)
        trend = _trend(level, meta)

        rows.append({
            "source_id": cwc_source_id,
            "source_type": "SYNTHETIC",
            "location": f"POINT({meta['lng']} {meta['lat']})",
            "severity": _level_to_severity(level, meta),
            "water_level_m": level,
            "water_level_trend": trend,
            "confidence": _CWC_BASE_CONFIDENCE,
            "reported_at": now.isoformat(),
            "expires_at": expires_at,
            "raw_payload": {"station_code": code, "synthetic": True},
            "description": f"{meta['name']} at {level:.2f}m ({trend})",
        })

    if not rows:
        logger.warning("No gauge rows to insert — all stations missing from DB")
        return

    insert_result = db.table("flood_reports").insert(rows).execute()
    if insert_result.data:
        logger.info("Inserted %d gauge readings", len(insert_result.data))
    else:
        logger.error("Gauge insert returned no data — check DB constraints or source_id")


def _synthetic_level(meta: dict) -> float:
    """Generate a plausible water level near warning/danger thresholds.

    Clamped between 0.1m (minimum detectable) and 1.5× danger level
    (physically impossible to exceed by much before measurement stops).
    """
    base = meta["warning_level_m"] * 0.85
    noise = random.gauss(0, meta["danger_level_m"] * 0.05)
    return round(min(max(0.1, base + noise), meta["danger_level_m"] * 1.5), 2)


def _trend(level: float, meta: dict) -> str:
    if level >= meta["warning_level_m"]:
        return "RISING"
    if level >= meta["warning_level_m"] * 0.9:
        return "STABLE"
    return "FALLING"


def _level_to_severity(level: float, meta: dict) -> int:
    danger = meta["danger_level_m"]
    warning = meta["warning_level_m"]
    if level >= danger * 1.1:   # 10%+ above danger level = EMERGENCY
        return 5
    if level >= danger:
        return 4
    if level >= warning:
        return 3
    if level >= warning * 0.9:
        return 2
    return 1
