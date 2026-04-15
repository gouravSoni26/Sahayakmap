"""
Major routes and bridges for the Mahanadi basin.

These are pre-seeded with known major highways. The OSM Overpass loader
(ingestion/osm_roads.py) can supplement with full geometry later.

Run via:  python -m seed.routes_bridges
"""
from database import get_client

ROUTES = [
    {"name": "NH-16", "route_type": "national_highway",
     "start_lat": 20.46, "start_lng": 85.88, "end_lat": 20.85, "end_lng": 86.33},
    {"name": "NH-53", "route_type": "national_highway",
     "start_lat": 20.46, "start_lng": 85.88, "end_lat": 21.06, "end_lng": 86.50},
    {"name": "SH-12", "route_type": "state_highway",
     "start_lat": 20.51, "start_lng": 86.42, "end_lat": 20.27, "end_lng": 86.17},
    {"name": "NH-203", "route_type": "national_highway",
     "start_lat": 19.81, "start_lng": 85.83, "end_lat": 20.46, "end_lng": 85.88},
]

BRIDGES = [
    {"name": "Jenapur Bridge", "route": "NH-53",
     "lat": 20.93, "lng": 86.14,
     "flood_tolerance_m": 14.0,
     "nearest_gauge": "JENAPUR"},
    {"name": "Naraj Bridge", "route": "NH-16",
     "lat": 20.47, "lng": 85.79,
     "flood_tolerance_m": 24.0,
     "nearest_gauge": "NARAJ"},
]


def seed():
    db = get_client()

    route_rows = [
        {
            "name": r["name"],
            "route_type": r["route_type"],
            "geometry": (
                f"LINESTRING({r['start_lng']} {r['start_lat']},"
                f"{r['end_lng']} {r['end_lat']})"
            ),
        }
        for r in ROUTES
    ]
    route_result = db.table("routes").upsert(route_rows, on_conflict="name").execute()
    print(f"Seeded {len(route_result.data)} routes")

    # Get gauge IDs for bridge FK
    gauges = db.table("gauge_stations").select("id, station_code").execute().data or []
    gauge_map = {g["station_code"]: g["id"] for g in gauges}

    route_id_map = {r["name"]: r["id"] for r in route_result.data}

    bridge_rows = [
        {
            "name": b["name"],
            "route_id": route_id_map.get(b["route"]),
            "location": f"POINT({b['lng']} {b['lat']})",
            "flood_tolerance_m": b["flood_tolerance_m"],
            "nearest_gauge_id": gauge_map.get(b["nearest_gauge"]),
        }
        for b in BRIDGES
    ]
    bridge_result = db.table("bridges").upsert(bridge_rows, on_conflict="name").execute()
    print(f"Seeded {len(bridge_result.data)} bridges")


if __name__ == "__main__":
    seed()
