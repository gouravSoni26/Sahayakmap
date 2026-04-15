"""
CWC river gauge data ingestion.

Real CWC data is available from https://ffs.india-water.gov.in but requires
scraping HTML tables. Until that is implemented, this module generates
realistic synthetic gauge readings based on known Mahanadi station metadata.

TODO: Implement real CWC scraping once the dashboard endpoint is identified.
"""
import logging
import random
from datetime import datetime, timezone

from database import get_client
from seed.gauge_stations import GAUGE_STATIONS

logger = logging.getLogger(__name__)


async def fetch_gauge_readings() -> None:
    """
    Fetch current water level readings for all Mahanadi gauge stations.
    Currently generates synthetic data; replace with real CWC scrape.
    """
    db = get_client()

    # Fetch station IDs from DB
    result = db.table("gauge_stations").select("id, station_code, danger_level_m, warning_level_m").execute()
    stations = {s["station_code"]: s for s in result.data}

    rows = []
    for code, meta in GAUGE_STATIONS.items():
        station = stations.get(code)
        if not station:
            continue

        level = _synthetic_level(meta)
        trend = _trend(level, meta)

        rows.append({
            "source_type": "CWC_GAUGE",
            "location": f"POINT({meta['lng']} {meta['lat']})",
            "severity": _level_to_severity(level, meta),
            "water_level_m": level,
            "water_level_trend": trend,
            "confidence": 0.95,
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "raw_payload": {"station_code": code, "synthetic": True},
            "description": f"{meta['name']} at {level:.2f}m ({trend})",
        })

    if rows:
        db.table("flood_reports").insert(rows).execute()
        logger.info("Inserted %d gauge readings", len(rows))


def _synthetic_level(meta: dict) -> float:
    """Generate a plausible water level near warning/danger thresholds."""
    base = meta["warning_level_m"] * 0.85
    noise = random.gauss(0, meta["danger_level_m"] * 0.05)
    return round(max(0.1, base + noise), 2)


def _trend(level: float, meta: dict) -> str:
    if level >= meta["warning_level_m"]:
        return "RISING"
    if level >= meta["warning_level_m"] * 0.9:
        return "STABLE"
    return "FALLING"


def _level_to_severity(level: float, meta: dict) -> int:
    danger = meta["danger_level_m"]
    warning = meta["warning_level_m"]
    if level >= danger:
        return 4
    if level >= warning:
        return 3
    if level >= warning * 0.9:
        return 2
    return 1
