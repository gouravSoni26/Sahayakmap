"""
Mahanadi Basin CWC gauge station metadata.
Source: MASTERPLAN.md — Data Sources section.

Run via:  python -m seed.gauge_stations
"""
from database import get_client

# Keyed by station_code — also used by cwc_gauge.py for synthetic data
GAUGE_STATIONS: dict[str, dict] = {
    "NARAJ": {
        "station_code": "NARAJ",
        "name": "Naraj",
        "river_name": "Mahanadi",
        "basin": "Mahanadi",
        "lat": 20.47, "lng": 85.79,
        "danger_level_m": 25.5,
        "warning_level_m": 22.0,
        "highest_flood_level_m": 28.96,
    },
    "MUNDULI": {
        "station_code": "MUNDULI",
        "name": "Munduli",
        "river_name": "Mahanadi",
        "basin": "Mahanadi",
        "lat": 20.49, "lng": 85.75,
        "danger_level_m": 26.0,
        "warning_level_m": 23.0,
        "highest_flood_level_m": 29.10,
    },
    "ALIPINGAL": {
        "station_code": "ALIPINGAL",
        "name": "Alipingal",
        "river_name": "Mahanadi",
        "basin": "Mahanadi",
        "lat": 20.83, "lng": 83.88,
        "danger_level_m": 43.0,
        "warning_level_m": 39.0,
        "highest_flood_level_m": 47.00,
    },
    "TIKARPARA": {
        "station_code": "TIKARPARA",
        "name": "Tikarpara",
        "river_name": "Mahanadi",
        "basin": "Mahanadi",
        "lat": 20.58, "lng": 84.78,
        "danger_level_m": 38.5,
        "warning_level_m": 34.0,
        "highest_flood_level_m": 43.75,
    },
    "JENAPUR": {
        "station_code": "JENAPUR",
        "name": "Jenapur",
        "river_name": "Brahmani",
        "basin": "Brahmani",
        "lat": 20.93, "lng": 86.14,
        "danger_level_m": 15.8,
        "warning_level_m": 13.0,
        "highest_flood_level_m": 17.50,
    },
    "ANANDPUR": {
        "station_code": "ANANDPUR",
        "name": "Anandpur",
        "river_name": "Baitarani",
        "basin": "Baitarani",
        "lat": 21.21, "lng": 86.12,
        "danger_level_m": 38.0,
        "warning_level_m": 34.0,
        "highest_flood_level_m": 41.60,
    },
}

# Upstream → downstream river adjacency with travel times.
# Used to seed station_adjacency table (replaces the old upstream_station_id FK).
# TIKARPARA is ~6hrs upstream of MUNDULI; MUNDULI is ~2hrs upstream of NARAJ.
ADJACENCY = [
    {"upstream": "TIKARPARA", "downstream": "MUNDULI", "avg_travel_time_hrs": 6},
    {"upstream": "MUNDULI",   "downstream": "NARAJ",   "avg_travel_time_hrs": 2},
]


def seed():
    db = get_client()

    rows = []
    for code, s in GAUGE_STATIONS.items():
        rows.append({
            "station_code": s["station_code"],
            "name": s["name"],
            "river_name": s["river_name"],
            "basin": s["basin"],
            "location": f"POINT({s['lng']} {s['lat']})",
            "danger_level_m": s["danger_level_m"],
            "warning_level_m": s["warning_level_m"],
            "highest_flood_level_m": s.get("highest_flood_level_m"),
        })

    result = db.table("gauge_stations").upsert(rows, on_conflict="station_code").execute()
    print(f"Seeded {len(result.data)} gauge stations")

    # Seed station_adjacency for flood progression projection
    station_map = {s["station_code"]: s["id"] for s in result.data}
    adjacency_rows = []
    for link in ADJACENCY:
        up_id = station_map.get(link["upstream"])
        down_id = station_map.get(link["downstream"])
        if up_id and down_id:
            adjacency_rows.append({
                "upstream_id": up_id,
                "downstream_id": down_id,
                "avg_travel_time_hrs": link["avg_travel_time_hrs"],
            })

    if adjacency_rows:
        db.table("station_adjacency").upsert(
            adjacency_rows, on_conflict="upstream_id,downstream_id"
        ).execute()
        print(f"Seeded {len(adjacency_rows)} station adjacency links")


if __name__ == "__main__":
    seed()
