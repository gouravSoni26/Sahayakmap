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

# Districts report every 2-4h. 4h silence = at least one missed report.
# During floods, silence often means communication failure — extremely dangerous.
SILENT_DISTRICT_HOURS = 4

# A flood 15km away can reach a camp in 1-4h depending on terrain.
# Gives enough lead time to start evacuation prep.
CAMP_RISK_PROXIMITY_KM = 15

# Need 3+ reports to confirm bridge submersion — avoids false alerts from single tweet.
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
    alert_pairs += await _check_bridge_submersion(db, now)
    alert_pairs += await _check_camps_flood_projection(db, now)

    # Fetch existing unacknowledged alert (type, title) pairs to skip duplicates
    existing = (
        db.table("alerts")
        .select("type, title")
        .is_("acknowledged_at", "null")
        .execute()
        .data or []
    )
    existing_keys = {(a["type"], a["title"]) for a in existing}

    inserted = 0
    for alert_data, report_ids in alert_pairs:
        key = (alert_data["type"], alert_data["title"])
        if key in existing_keys:
            continue
        result = db.table("alerts").insert(alert_data).execute()
        if result.data:
            inserted += 1
            existing_keys.add(key)  # prevent dupes within same run
            if report_ids:
                alert_id = result.data[0]["id"]
                junction_rows = [
                    {"alert_id": alert_id, "flood_report_id": rid} for rid in report_ids
                ]
                db.table("alert_reports").insert(junction_rows).execute()

    if inserted:
        logger.info("Generated %d new alerts (%d skipped as duplicates)", inserted, len(alert_pairs) - inserted)


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
            if isinstance(loc, dict) and loc.get("type") == "Point":
                c_lng, c_lat = loc["coordinates"]
            else:
                coords = loc.replace("POINT(", "").replace(")", "").split()
                c_lat, c_lng = float(coords[1]), float(coords[0])
        except (IndexError, ValueError, AttributeError, KeyError):
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


async def _check_bridge_submersion(db, now: datetime) -> list[tuple[dict, list[str]]]:
    bridges = (
        db.table("bridges")
        .select("id,name,location,flood_tolerance_m,nearest_gauge_id")
        .execute()
        .data or []
    )
    if not bridges:
        return []

    # Build gauge_id → station_code map for all nearest gauges in one query
    gauge_ids = [b["nearest_gauge_id"] for b in bridges if b.get("nearest_gauge_id")]
    if not gauge_ids:
        return []
    gauges = (
        db.table("gauge_stations")
        .select("id,station_code")
        .in_("id", gauge_ids)
        .execute()
        .data or []
    )
    gauge_code_map = {g["id"]: g["station_code"] for g in gauges}

    # CWC_GAUGE source IDs — same pattern as _check_gauge_thresholds
    cwc_sources = (
        db.table("data_sources").select("id").eq("type", "CWC_GAUGE").execute().data or []
    )
    cwc_source_ids = [s["id"] for s in cwc_sources]
    if not cwc_source_ids:
        return []

    # Batch-fetch recent CWC readings (ordered DESC so first match = latest per station)
    since = (now - timedelta(hours=3)).isoformat()
    gauge_reports = (
        db.table("flood_reports")
        .select("id,source_id,water_level_m,reported_at,raw_payload")
        .in_("source_id", cwc_source_ids)
        .gte("reported_at", since)
        .order("reported_at", desc=True)
        .execute()
        .data or []
    )

    # Batch-fetch corroboration reports (severity >= 3) for proximity checks
    severe_reports = (
        db.table("flood_reports")
        .select("*")
        .gte("reported_at", since)
        .gte("severity", 3)
        .execute()
        .data or []
    )

    alert_pairs = []
    for bridge in bridges:
        gauge_id = bridge.get("nearest_gauge_id")
        tolerance = bridge.get("flood_tolerance_m")
        if not gauge_id or not tolerance:
            continue

        station_code = gauge_code_map.get(gauge_id)
        if not station_code:
            continue

        # Latest reading for this gauge — first match in DESC-ordered list
        latest = next(
            (r for r in gauge_reports
             if r.get("raw_payload", {}).get("station_code") == station_code),
            None,
        )
        if not latest:
            continue
        water_level = latest.get("water_level_m")
        if not water_level or water_level < tolerance:
            continue

        loc = bridge.get("location", "")
        if not loc:
            continue
        try:
            if isinstance(loc, dict) and loc.get("type") == "Point":
                b_lng, b_lat = loc["coordinates"]
            else:
                coords = loc.replace("POINT(", "").replace(")", "").split()
                b_lat, b_lng = float(coords[1]), float(coords[0])
        except (IndexError, ValueError, AttributeError, KeyError):
            continue

        nearby = [
            r for r in severe_reports
            if _report_within_km(r, b_lat, b_lng, 2.0)
        ]
        if len(nearby) < BRIDGE_CORROBORATION_COUNT:
            continue

        alert_pairs.append(({
            "type": "BRIDGE_SUBMERGED",
            "severity": 4,
            "title": f"{bridge['name']} bridge — submersion risk",
            "description": (
                f"Gauge at {water_level:.2f}m exceeds {bridge['name']} flood tolerance "
                f"({tolerance:.2f}m). {len(nearby)} severity-3+ reports within 2km confirm flooding."
            ),
            "recommended_action": "Close bridge immediately. Reroute traffic and deploy water rescue teams.",
            "location": bridge["location"],
            "expires_at": (now + timedelta(hours=2)).isoformat(),
        }, [r["id"] for r in nearby]))
    return alert_pairs


async def _check_camps_flood_projection(db, now: datetime) -> list[tuple[dict, list[str]]]:
    """
    Fire CAMP_AT_RISK when a relief camp falls inside or within 2km of a
    projected flood polygon.

    Flood polygon radius = 2km base + 2km per extra metre above danger (cap 15km),
    matching the formula in projection.py / GET /api/map/flood-extent.

    Secondary trigger: camp elevation < 10m within the polygon itself (no 2km buffer)
    — low-elevation camps are at elevated risk from even marginal flooding.

    Uses haversine proximity (same pattern as _check_camps_at_risk) rather than
    PostGIS RPC, because the polygon center (gauge location) is the natural pivot
    and the polygon is a circle — haversine ≡ ST_DWithin for this geometry.
    """
    camps = (
        db.table("relief_camps")
        .select("id,name,location,elevation_m,current_population")
        .neq("status", "CLOSED")
        .execute()
        .data or []
    )
    if not camps:
        return []

    cwc_sources = (
        db.table("data_sources").select("id").eq("type", "CWC_GAUGE").execute().data or []
    )
    cwc_source_ids = [s["id"] for s in cwc_sources]
    if not cwc_source_ids:
        return []

    since = (now - timedelta(hours=3)).isoformat()
    reports = (
        db.table("flood_reports")
        .select("source_id,water_level_m,raw_payload")
        .in_("source_id", cwc_source_ids)
        .gte("reported_at", since)
        .order("reported_at", desc=True)
        .execute()
        .data or []
    )
    # level_map: station_code → latest reading (reports already DESC)
    level_map: dict[str, float] = {}
    for r in reports:
        code = (r.get("raw_payload") or {}).get("station_code")
        if code and code not in level_map and r.get("water_level_m"):
            level_map[code] = r["water_level_m"]

    gauges = (
        db.table("gauge_stations")
        .select("id,station_code,name,danger_level_m,location")
        .execute()
        .data or []
    )

    # Build above-danger gauges with parsed location + computed radius
    danger_gauges: list[dict] = []
    for g in gauges:
        code = g.get("station_code")
        level = level_map.get(code)
        danger = g.get("danger_level_m")
        if not level or not danger or level < danger:
            continue
        loc = g.get("location", "")
        if not loc:
            continue
        try:
            if isinstance(loc, dict) and loc.get("type") == "Point":
                g_lng, g_lat = loc["coordinates"]
            else:
                coords = str(loc).replace("POINT(", "").replace(")", "").split()
                g_lat, g_lng = float(coords[1]), float(coords[0])
        except (IndexError, ValueError, AttributeError, KeyError):
            continue
        excess_m = level - danger
        radius_km = min(2.0 + excess_m * 2.0, 15.0)
        danger_gauges.append({
            "station_code": code,
            "name": g["name"],
            "lat": g_lat,
            "lng": g_lng,
            "danger_level_m": danger,
            "water_level_m": level,
            "radius_km": radius_km,
        })

    if not danger_gauges:
        return []

    alert_pairs = []
    for camp in camps:
        loc = camp.get("location", "")
        if not loc:
            continue
        try:
            if isinstance(loc, dict) and loc.get("type") == "Point":
                c_lng, c_lat = loc["coordinates"]
            else:
                coords = str(loc).replace("POINT(", "").replace(")", "").split()
                c_lat, c_lng = float(coords[1]), float(coords[0])
        except (IndexError, ValueError, AttributeError, KeyError):
            continue

        elevation = camp.get("elevation_m") or 999.0

        triggering: dict | None = None
        for dg in danger_gauges:
            dist_km = haversine_km(c_lat, c_lng, dg["lat"], dg["lng"])
            # Primary: inside polygon + 2km buffer
            if dist_km <= dg["radius_km"] + 2.0:
                triggering = dg
                break
            # Secondary: low-elevation camp inside polygon (no buffer)
            if elevation < 10.0 and dist_km <= dg["radius_km"]:
                triggering = dg
                break

        if not triggering:
            continue

        above_m = triggering["water_level_m"] - triggering["danger_level_m"]
        alert_pairs.append(({
            "type": "CAMP_AT_RISK",
            "severity": 4,
            "title": f"Relief camp {camp['name']} may be at risk",
            "description": (
                f"{camp['name']} is within the projected flood zone of {triggering['name']} gauge "
                f"({triggering['water_level_m']:.2f}m — {above_m:.1f}m above danger). "
                f"Projected flood radius: {triggering['radius_km']:.1f}km. "
                f"Camp elevation: {elevation:.0f}m. "
                f"Population at risk: {camp.get('current_population', 0)}."
            ),
            "recommended_action": (
                "Assess evacuation urgency. Identify high-ground routes. "
                "Coordinate with district collector for transport assets."
            ),
            "expires_at": (now + timedelta(hours=3)).isoformat(),
        }, []))
    return alert_pairs


def _report_within_km(report: dict, lat: float, lng: float, km: float) -> bool:
    loc = report.get("location", "")
    if not loc:
        return False
    try:
        if isinstance(loc, dict) and loc.get("type") == "Point":
            r_lng, r_lat = loc["coordinates"]
        else:
            coords = loc.replace("POINT(", "").replace(")", "").split()
            r_lat, r_lng = float(coords[1]), float(coords[0])
        return haversine_km(lat, lng, r_lat, r_lng) <= km
    except (IndexError, ValueError, AttributeError, KeyError):
        return False
