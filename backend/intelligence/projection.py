"""
Flood progression model.

Simple upstream → downstream time-lag projection.
If station A is upstream of station B with a 4-hour travel time,
and A is currently at danger level, B will likely reach danger level
in ~4 hours (adjusted for current rise rate).

No LLM needed — pure deterministic math.
"""
import logging

logger = logging.getLogger(__name__)


def project_flood_progression(gauges: list[dict], reports: list[dict], hours_ahead: int = 6) -> list[dict]:
    """
    For each gauge with an upstream station, project whether the downstream
    station will reach danger level within hours_ahead hours.
    """
    # Build gauge level map from recent CWC reports
    level_map: dict[str, float] = {}
    trend_map: dict[str, str] = {}
    for r in reports:
        if r.get("source_type") != "CWC_GAUGE":
            continue
        code = r.get("raw_payload", {}).get("station_code")
        if code and r.get("water_level_m"):
            level_map[code] = r["water_level_m"]
            trend_map[code] = r.get("water_level_trend", "STABLE")

    projections = []

    for gauge in gauges:
        code = gauge.get("station_code")
        upstream_id = gauge.get("upstream_station_id")
        if not upstream_id:
            continue

        # Find upstream station
        upstream = next((g for g in gauges if g["id"] == upstream_id), None)
        if not upstream:
            continue

        u_code = upstream.get("station_code")
        u_level = level_map.get(u_code, 0)
        u_danger = upstream.get("danger_level_m", 999)

        if u_level < u_danger:
            continue  # upstream not in danger — no projection needed

        travel_hours = gauge.get("avg_travel_time_hrs") or 6
        current_level = level_map.get(code, 0)
        danger_level = gauge.get("danger_level_m", 999)

        # Simple linear projection based on upstream overflow
        # Real model would use hydraulic routing, but this is adequate for PoC
        if travel_hours <= hours_ahead:
            projected_level = current_level + (u_level - u_danger) * 0.8  # 80% transfer factor
            status = "DANGER" if projected_level >= danger_level else "WARNING"

            projections.append({
                "station_code": code,
                "station_name": gauge.get("name"),
                "current_level_m": current_level,
                "projected_level_m": round(projected_level, 2),
                "danger_level_m": danger_level,
                "projected_status": status,
                "eta_hours": travel_hours,
                "based_on_station": upstream.get("name"),
                "confidence": 0.60,
            })

    return projections
