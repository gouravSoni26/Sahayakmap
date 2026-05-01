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
import math

logger = logging.getLogger(__name__)

# ── Flood polygon projection ───────────────────────────────────────────────────
# Radius formula: 2km base + 2km per metre above danger, capped at 15km.
# Examples: +1m → 4km, +3m → 8km.
_BASE_RADIUS_KM = 2.0
_SCALE_KM_PER_M = 2.0
_MAX_RADIUS_KM = 15.0

# Cumulative upstream→downstream travel lag for Mahanadi/Brahmani chain.
# travel_time_hrs ≈ river_distance_km / 5.0 (flood wave velocity for Mahanadi).
# TIKARPARA→MUNDULI: ~100km / 5 = 20h by formula, but CWC obs give 6h — use observed.
# MUNDULI→NARAJ: 2h observed, so cumulative from TIKARPARA = 8h.
# Other stations are heads of independent sub-basins — lag = 0.
_STATION_LAG_HRS: dict[str, float] = {
    "TIKARPARA": 0.0,
    "MUNDULI": 6.0,   # 6h downstream of TIKARPARA
    "NARAJ": 8.0,     # cumulative: TIKARPARA→MUNDULI (6h) + MUNDULI→NARAJ (2h)
}


def compute_flood_polygons(danger_gauges: list[dict]) -> list[dict]:
    """
    For each gauge above danger level, compute a projected flood polygon
    (GeoJSON circle approximation) centered on the gauge location.

    danger_gauges: list of dicts, each with:
        gauge_id, station_code, name, lat, lng, danger_level_m, water_level_m

    Returns a list of GeoJSON Feature objects (Polygon geometry).
    Properties per feature: gauge_id, station_code, name, water_level_m,
    danger_level_m, radius_km, lag_hrs.
    """
    features = []
    for g in danger_gauges:
        excess_m = g["water_level_m"] - g["danger_level_m"]
        if excess_m <= 0:
            continue
        radius_km = min(_BASE_RADIUS_KM + excess_m * _SCALE_KM_PER_M, _MAX_RADIUS_KM)
        lag_hrs = _STATION_LAG_HRS.get(g["station_code"], 0.0)
        features.append({
            "type": "Feature",
            "geometry": _circle_polygon(g["lat"], g["lng"], radius_km),
            "properties": {
                "gauge_id": g["gauge_id"],
                "station_code": g["station_code"],
                "name": g["name"],
                "water_level_m": round(g["water_level_m"], 2),
                "danger_level_m": round(g["danger_level_m"], 2),
                "radius_km": round(radius_km, 2),
                "lag_hrs": lag_hrs,
            },
        })
    return features


def _circle_polygon(lat: float, lng: float, radius_km: float, n_points: int = 32) -> dict:
    """
    Approximate a circle as a closed GeoJSON Polygon ring.

    Degree conversion:
      1° latitude  ≈ 111.32 km (constant)
      1° longitude ≈ 111.32 km × cos(lat) — shrinks toward poles
    """
    d_lat = radius_km / 111.32
    d_lng = radius_km / (111.32 * math.cos(math.radians(lat)))
    coords = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        coords.append([
            round(lng + d_lng * math.sin(angle), 6),
            round(lat + d_lat * math.cos(angle), 6),
        ])
    coords.append(coords[0])  # close the ring
    return {"type": "Polygon", "coordinates": [coords]}


# ── Flood progression (upstream→downstream time-lag) ──────────────────────────

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
        u_level = level_map.get(u_code, 0) # pyright: ignore[reportArgumentType, reportCallIssue]
        u_danger = upstream.get("danger_level_m", 999)

        if u_level < u_danger:
            continue  # upstream not in danger — no projection needed

        travel_hours = link.get("avg_travel_time_hrs") or 6
        d_code = downstream.get("station_code")
        current_level = level_map.get(d_code, 0) # pyright: ignore[reportArgumentType, reportCallIssue]
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
