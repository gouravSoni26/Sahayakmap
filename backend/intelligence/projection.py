"""
Flood progression model.

Simple upstream → downstream time-lag projection.
If station A is upstream of station B with a 4-hour travel time,
and A is currently at danger level, B will likely reach danger level
in ~4 hours (adjusted for current rise rate).

No LLM needed — pure deterministic math.

Adjacency data comes from the station_adjacency table (fetched by the caller)
rather than a single upstream_station_id FK, supporting multi-tributary networks.
"""
import logging

logger = logging.getLogger(__name__)


def project_flood_progression(
    gauges: list[dict],
    reports: list[dict],
    adjacency: list[dict],
    hours_ahead: int = 6,
) -> list[dict]:
    """
    For each gauge with an upstream station in the adjacency table, project
    whether the downstream station will reach danger level within hours_ahead hours.

    adjacency: rows from station_adjacency(upstream_id, downstream_id, avg_travel_time_hrs)
    """
    # Build gauge level map from recent CWC reports
    level_map: dict[str, float] = {}
    trend_map: dict[str, str] = {}
    for r in reports:
        source_type = (r.get("data_sources") or {}).get("type")
        if source_type != "CWC_GAUGE":
            continue
        code = r.get("raw_payload", {}).get("station_code")
        if code and r.get("water_level_m"):
            level_map[code] = r["water_level_m"]
            trend_map[code] = r.get("water_level_trend", "STABLE")

    # Build gauge lookup by id
    gauge_by_id: dict[str, dict] = {g["id"]: g for g in gauges}

    projections = []

    for link in adjacency:
        upstream = gauge_by_id.get(link["upstream_id"])
        downstream = gauge_by_id.get(link["downstream_id"])
        if not upstream or not downstream:
            continue

        u_code = upstream.get("station_code")
        u_level = level_map.get(u_code, 0)
        u_danger = upstream.get("danger_level_m", 999)

        if u_level < u_danger:
            continue  # upstream not in danger — no projection needed

        travel_hours = link.get("avg_travel_time_hrs") or 6
        d_code = downstream.get("station_code")
        current_level = level_map.get(d_code, 0)
        danger_level = downstream.get("danger_level_m", 999)

        if travel_hours <= hours_ahead:
            # 80% transfer: not all upstream water reaches downstream — some spreads
            # into floodplains. 0.8 is conservative for Mahanadi river basin geography.
            projected_level = current_level + (u_level - u_danger) * 0.8
            status = "DANGER" if projected_level >= danger_level else "WARNING"

            projections.append({
                "station_code": d_code,
                "station_name": downstream.get("name"),
                "current_level_m": current_level,
                "projected_level_m": round(projected_level, 2),
                "danger_level_m": danger_level,
                "projected_status": status,
                "eta_hours": travel_hours,
                "based_on_station": upstream.get("name"),
                "confidence": 0.60,  # projections are inherently uncertain — "more likely than not"
            })

    return projections
