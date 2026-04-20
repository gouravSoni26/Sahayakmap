"""
Rescue asset seed data — NDRF boats, helicopters, rescue teams, supply trucks
positioned across the Mahanadi basin districts.

Run via:  python -m seed.rescue_assets
"""
from database import get_client

RESCUE_ASSETS = [
    # Boats
    {"type": "BOAT", "name": "NDRF Boat B-01", "capacity": 15, "lat": 20.51, "lng": 86.42, "district": "Kendrapara", "status": "AVAILABLE"},
    {"type": "BOAT", "name": "NDRF Boat B-02", "capacity": 15, "lat": 20.51, "lng": 86.44, "district": "Kendrapara", "status": "AVAILABLE"},
    {"type": "BOAT", "name": "NDRF Boat B-03", "capacity": 12, "lat": 20.46, "lng": 85.88, "district": "Cuttack",    "status": "DEPLOYED"},
    {"type": "BOAT", "name": "NDRF Boat B-04", "capacity": 12, "lat": 20.85, "lng": 86.33, "district": "Jajpur",     "status": "AVAILABLE"},
    {"type": "BOAT", "name": "NDRF Boat B-05", "capacity": 10, "lat": 21.06, "lng": 86.50, "district": "Bhadrak",    "status": "AVAILABLE"},
    {"type": "BOAT", "name": "ODRAF Boat B-06", "capacity": 10, "lat": 20.27, "lng": 86.17, "district": "Jagatsinghpur", "status": "IN_TRANSIT"},

    # Helicopters
    {"type": "HELICOPTER", "name": "IAF Heli H-01", "capacity": 8,  "lat": 20.30, "lng": 85.84, "district": "Khordha",    "status": "AVAILABLE"},
    {"type": "HELICOPTER", "name": "IAF Heli H-02", "capacity": 8,  "lat": 20.46, "lng": 85.88, "district": "Cuttack",    "status": "DEPLOYED"},
    {"type": "HELICOPTER", "name": "NDRF Heli H-03", "capacity": 6, "lat": 21.06, "lng": 86.50, "district": "Bhadrak",    "status": "AVAILABLE"},

    # Rescue Teams
    {"type": "RESCUE_TEAM", "name": "NDRF Team RT-01", "capacity": 45, "lat": 20.46, "lng": 85.88, "district": "Cuttack",        "status": "DEPLOYED"},
    {"type": "RESCUE_TEAM", "name": "NDRF Team RT-02", "capacity": 45, "lat": 20.51, "lng": 86.42, "district": "Kendrapara",     "status": "AVAILABLE"},
    {"type": "RESCUE_TEAM", "name": "NDRF Team RT-03", "capacity": 45, "lat": 20.85, "lng": 86.33, "district": "Jajpur",         "status": "AVAILABLE"},
    {"type": "RESCUE_TEAM", "name": "ODRAF Team RT-04", "capacity": 30, "lat": 20.27, "lng": 86.17, "district": "Jagatsinghpur", "status": "AVAILABLE"},
    {"type": "RESCUE_TEAM", "name": "ODRAF Team RT-05", "capacity": 30, "lat": 19.38, "lng": 84.99, "district": "Ganjam",        "status": "AVAILABLE"},

    # Supply Trucks
    {"type": "SUPPLY_TRUCK", "name": "Supply Truck ST-01", "capacity": 5000, "lat": 20.46, "lng": 85.88, "district": "Cuttack",    "status": "AVAILABLE"},
    {"type": "SUPPLY_TRUCK", "name": "Supply Truck ST-02", "capacity": 5000, "lat": 20.51, "lng": 86.42, "district": "Kendrapara", "status": "IN_TRANSIT"},
    {"type": "SUPPLY_TRUCK", "name": "Supply Truck ST-03", "capacity": 3000, "lat": 21.06, "lng": 86.50, "district": "Bhadrak",    "status": "AVAILABLE"},
]


def seed():
    db = get_client()

    # Get district ID map
    districts = db.table("districts").select("id, name").execute().data or []
    district_map = {d["name"]: d["id"] for d in districts}

    rows = [
        {
            "type": a["type"],
            "name": a["name"],
            "capacity": a["capacity"],
            "location": f"POINT({a['lng']} {a['lat']})",
            "assigned_district_id": district_map.get(a["district"]),
            "status": a["status"],
        }
        for a in RESCUE_ASSETS
    ]

    result = db.table("rescue_assets").upsert(rows, on_conflict="name").execute()
    print(f"Seeded {len(result.data)} rescue assets")
    for a in result.data:
        print(f"  [{a['type']}] {a['name']} — {a['status']}")


if __name__ == "__main__":
    seed()
