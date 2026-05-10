"""
Rescue asset seed data — NDRF boats, helicopters, rescue teams, supply trucks
positioned across the Mahanadi basin districts.

Run via:  python -m seed.rescue_assets
"""
import logging

from database import get_client

logger = logging.getLogger(__name__)

RESCUE_ASSETS = [
    # Boats
    {"type": "BOAT", "name": "NDRF Boat B-01", "capacity": 15, "lat": 20.512, "lng": 86.421, "district": "Kendrapara", "status": "AVAILABLE"},
    {"type": "BOAT", "name": "NDRF Boat B-02", "capacity": 15, "lat": 20.51,  "lng": 86.44,  "district": "Kendrapara", "status": "AVAILABLE"},
    {"type": "BOAT", "name": "NDRF Boat B-03", "capacity": 12, "lat": 20.462, "lng": 85.882, "district": "Cuttack",    "status": "DEPLOYED"},
    {"type": "BOAT", "name": "NDRF Boat B-04", "capacity": 12, "lat": 20.852, "lng": 86.332, "district": "Jajpur",     "status": "AVAILABLE"},
    {"type": "BOAT", "name": "NDRF Boat B-05", "capacity": 10, "lat": 21.062, "lng": 86.502, "district": "Bhadrak",    "status": "AVAILABLE"},
    {"type": "BOAT", "name": "ODRAF Boat B-06", "capacity": 10, "lat": 20.272, "lng": 86.172, "district": "Jagatsinghpur", "status": "IN_TRANSIT"},

    # Helicopters
    {"type": "HELICOPTER", "name": "IAF Heli H-01", "capacity": 8,  "lat": 20.30,  "lng": 85.84,  "district": "Khordha", "status": "AVAILABLE"},
    {"type": "HELICOPTER", "name": "IAF Heli H-02", "capacity": 8,  "lat": 20.458, "lng": 85.878, "district": "Cuttack", "status": "DEPLOYED"},
    {"type": "HELICOPTER", "name": "NDRF Heli H-03", "capacity": 6, "lat": 21.058, "lng": 86.498, "district": "Bhadrak", "status": "AVAILABLE"},

    # Rescue Teams
    {"type": "RESCUE_TEAM", "name": "NDRF Team RT-01", "capacity": 45, "lat": 20.460, "lng": 85.876, "district": "Cuttack",        "status": "DEPLOYED"},
    {"type": "RESCUE_TEAM", "name": "NDRF Team RT-02", "capacity": 45, "lat": 20.508, "lng": 86.419, "district": "Kendrapara",     "status": "AVAILABLE"},
    {"type": "RESCUE_TEAM", "name": "NDRF Team RT-03", "capacity": 45, "lat": 20.848, "lng": 86.328, "district": "Jajpur",         "status": "AVAILABLE"},
    {"type": "RESCUE_TEAM", "name": "ODRAF Team RT-04", "capacity": 30, "lat": 20.268, "lng": 86.168, "district": "Jagatsinghpur", "status": "AVAILABLE"},
    {"type": "RESCUE_TEAM", "name": "ODRAF Team RT-05", "capacity": 30, "lat": 19.38,  "lng": 84.99,  "district": "Ganjam",        "status": "AVAILABLE"},

    # Supply Trucks
    {"type": "SUPPLY_TRUCK", "name": "Supply Truck ST-01", "capacity": 5000, "lat": 20.456, "lng": 85.874, "district": "Cuttack",    "status": "AVAILABLE"},
    {"type": "SUPPLY_TRUCK", "name": "Supply Truck ST-02", "capacity": 5000, "lat": 20.506, "lng": 86.417, "district": "Kendrapara", "status": "IN_TRANSIT"},
    {"type": "SUPPLY_TRUCK", "name": "Supply Truck ST-03", "capacity": 3000, "lat": 21.056, "lng": 86.496, "district": "Bhadrak",    "status": "AVAILABLE"},
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

    db.table("rescue_assets").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    result = db.table("rescue_assets").insert(rows).execute()
    logger.info(f"Seeded {len(result.data)} rescue assets")
    for a in result.data:
        logger.info(f"  [{a['type']}] {a['name']} — {a['status']}")


if __name__ == "__main__":
    seed()
