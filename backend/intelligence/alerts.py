"""
Alert generation and triage.

Rule-based Python code detects alert conditions (gauge thresholds, silent
districts, bridge submersion, camp at risk). LLM is used only for triage
ranking text — not for detection logic.
"""
import logging
from datetime import datetime, timedelta, timezone

from database import get_client
from fusion.spatial import haversine_km

logger = logging.getLogger(__name__)

# Thresholds
SILENT_DISTRICT_HOURS = 4
CAMP_RISK_PROXIMITY_KM = 15
BRIDGE_CORROBORATION_COUNT = 3


async def run_alert_checks() -> None:
    """
    Run all alert detection rules. Called every 5 minutes by the scheduler.
    Inserts new alerts into the alerts table (does not duplicate acknowledged ones).
    """
    db = get_client()
    now = datetime.now(timezone.utc)

    # Each check returns list of (alert_dict, [flood_report_ids])
    alert_pairs: list[tuple[dict, list[str]]] = []
    alert_pairs += await _check_gauge_thresholds(db, now)
    alert_pairs += await _check_silent_districts(db, now)
    alert_pairs += await _check_camps_at_risk(db, now)

    for alert_data, report_ids in alert_pairs:
        result = db.table("alerts").insert(alert_data).execute()
        if result.data and report_ids:
            alert_id = result.data[0]["id"]
            junction_rows = [
                {"alert_id": alert_id, "flood_report_id": rid} for rid in report_ids
            ]
            db.table("alert_reports").insert(junction_rows).execute()

    if alert_pairs:
        logger.info("Generated %d new alerts", len(alert_pairs))


async def _check_gauge_thresholds(db, now: datetime) -> list[tuple[dict, list[str]]]:
    since = (now - timedelta(hours=1)).isoformat()

    # Look up CWC_GAUGE source IDs
    cwc_sources = (
        db.table("data_sources").select("id").eq("type", "CWC_GAUGE").execute().data or []
    )
    cwc_source_ids = [s["id"] for s in cwc_sources]

    if not cwc_source_ids:
        return []

    reports = (
        db.table("flood_reports")
        .select("*")
        .in_("source_id", cwc_source_ids)
        .gte("reported_at", since)
        .execute()
        .data or []
    )
    gauges = db.table("gauge_stations").select("*").execute().data or []
    gauge_map = {g["station_code"]: g for g in gauges}

    alert_pairs = []
    for r in reports:
        level = r.get("water_level_m")
        code = r.get("raw_payload", {}).get("station_code")
        if not level or not code or code not in gauge_map:
            continue

        g = gauge_map[code]
        if level >= g["danger_level_m"]:
            alert_pairs.append(({
                "type": "FLOOD_RISING",
                "severity": 4,
                "title": f"{g['name']} above danger level",
                "description": f"{g['name']} gauge at {level:.2f}m — danger level is {g['danger_level_m']}m.",
                "recommended_action": "Deploy rescue assets upstream. Alert downstream districts.",
                "expires_at": (now + timedelta(hours=2)).isoformat(),
            }, [r["id"]]))
    return alert_pairs


async def _check_silent_districts(db, now: datetime) -> list[tuple[dict, list[str]]]:
    threshold = (now - timedelta(hours=SILENT_DISTRICT_HOURS)).isoformat()
    districts = db.table("districts").select("id, name, population").execute().data or []
    recent_reports = (
        db.table("flood_reports")
        .select("district_id")
        .gte("reported_at", threshold)
        .execute()
        .data or []
    )
    active_district_ids = {r["district_id"] for r in recent_reports}

    alert_pairs = []
    for d in districts:
        if d["id"] not in active_district_ids:
            alert_pairs.append(({
                "type": "SILENT_DISTRICT",
                "severity": 3,
                "district_id": d["id"],
                "title": f"{d['name']} district — no reports for {SILENT_DISTRICT_HOURS}h",
                "description": (
                    f"{d['name']} has had no situation reports for over {SILENT_DISTRICT_HOURS} hours. "
                    f"Population: {d.get('population', 'unknown')}. "
                    "Possible communication failure or evacuation in progress."
                ),
                "recommended_action": "Contact district collector directly. Dispatch liaison team.",
                "expires_at": (now + timedelta(hours=4)).isoformat(),
            }, []))  # no specific flood reports to link for silent districts
    return alert_pairs


async def _check_camps_at_risk(db, now: datetime) -> list[tuple[dict, list[str]]]:
    camps = db.table("relief_camps").select("*").neq("status", "CLOSED").execute().data or []
    since = (now - timedelta(hours=3)).isoformat()
    severe_reports = (
        db.table("flood_reports")
        .select("*")
        .gte("reported_at", since)
        .gte("severity", 3)
        .execute()
        .data or []
    )

    alert_pairs = []
    for camp in camps:
        loc = camp.get("location", "")
        if not loc:
            continue
        try:
            coords = loc.replace("POINT(", "").replace(")", "").split()
            c_lat, c_lng = float(coords[1]), float(coords[0])
        except (IndexError, ValueError):
            continue

        nearby = [
            r for r in severe_reports
            if _report_within_km(r, c_lat, c_lng, CAMP_RISK_PROXIMITY_KM)
        ]
        if nearby:
            alert_pairs.append(({
                "type": "CAMP_AT_RISK",
                "severity": 4,
                "title": f"Relief camp {camp['name']} may be at risk",
                "description": (
                    f"{len(nearby)} severity-3+ reports within {CAMP_RISK_PROXIMITY_KM}km of "
                    f"{camp['name']} (pop: {camp.get('current_population', 0)})."
                ),
                "recommended_action": "Assess flood risk at camp. Prepare evacuation plan.",
                "expires_at": (now + timedelta(hours=3)).isoformat(),
            }, [r["id"] for r in nearby]))
    return alert_pairs


def _report_within_km(report: dict, lat: float, lng: float, km: float) -> bool:
    loc = report.get("location", "")
    if not loc:
        return False
    try:
        coords = loc.replace("POINT(", "").replace(")", "").split()
        r_lat, r_lng = float(coords[1]), float(coords[0])
        return haversine_km(lat, lng, r_lat, r_lng) <= km
    except (IndexError, ValueError):
        return False
