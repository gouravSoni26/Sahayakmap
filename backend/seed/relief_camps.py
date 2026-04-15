"""
Known relief camp locations for the Mahanadi basin.

Manually curated for the demo. Elevations are approximate (source: SRTM 30m).

Run via:  python -m seed.relief_camps
"""
from database import get_client

RELIEF_CAMPS = [
    {
        "name": "Erasama School Camp",
        "lat": 20.22, "lng": 86.38,
        "district_name": "Jagatsinghpur",
        "elevation_m": 4.5,   # low elevation — at risk in demo scenario
        "max_capacity": 500,
        "current_population": 340,
    },
    {
        "name": "Kendrapara District Camp",
        "lat": 20.51, "lng": 86.42,
        "district_name": "Kendrapara",
        "elevation_m": 12.0,
        "max_capacity": 1000,
        "current_population": 120,
    },
    {
        "name": "Cuttack Collectorate Camp",
        "lat": 20.46, "lng": 85.88,
        "district_name": "Cuttack",
        "elevation_m": 28.0,
        "max_capacity": 2000,
        "current_population": 0,
    },
    {
        "name": "Jajpur Relief Centre",
        "lat": 20.85, "lng": 86.33,
        "district_name": "Jajpur",
        "elevation_m": 18.0,
        "max_capacity": 800,
        "current_population": 85,
    },
    {
        "name": "Bhadrak Community Hall",
        "lat": 21.06, "lng": 86.50,
        "district_name": "Bhadrak",
        "elevation_m": 22.0,
        "max_capacity": 600,
        "current_population": 0,
    },
]


def seed():
    db = get_client()

    # Get district ID map
    districts = db.table("districts").select("id, name").execute().data or []
    district_map = {d["name"]: d["id"] for d in districts}

    rows = []
    for c in RELIEF_CAMPS:
        rows.append({
            "name": c["name"],
            "location": f"POINT({c['lng']} {c['lat']})",
            "district_id": district_map.get(c["district_name"]),
            "elevation_m": c["elevation_m"],
            "max_capacity": c["max_capacity"],
            "current_population": c["current_population"],
            "status": "ACTIVE",
        })

    result = db.table("relief_camps").upsert(rows, on_conflict="name").execute()
    print(f"Seeded {len(result.data)} relief camps")


if __name__ == "__main__":
    seed()
