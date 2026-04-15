"""
Odisha district reference data.

Boundaries should be loaded from a GeoJSON file (geoBoundaries / GADM).
This script loads the 8 districts most relevant to the Mahanadi basin
with approximate centroids and population estimates.

Run via:  python -m seed.odisha_districts
"""
from database import get_client

# Key districts for the demo — approximate centroids and 2021 census populations
DISTRICTS = [
    {"name": "Cuttack",        "lat": 20.46, "lng": 85.88, "population": 2_624_470},
    {"name": "Kendrapara",     "lat": 20.51, "lng": 86.42, "population": 1_440_892},
    {"name": "Jagatsinghpur",  "lat": 20.27, "lng": 86.17, "population": 1_136_604},
    {"name": "Jajpur",         "lat": 20.85, "lng": 86.33, "population": 1_826_275},
    {"name": "Puri",           "lat": 19.81, "lng": 85.83, "population": 1_498_604},
    {"name": "Bhadrak",        "lat": 21.06, "lng": 86.50, "population": 1_506_522},
    {"name": "Ganjam",         "lat": 19.38, "lng": 84.99, "population": 3_529_031},
    {"name": "Khordha",        "lat": 20.18, "lng": 85.60, "population": 2_251_673},
]


def seed():
    db = get_client()
    rows = [
        {
            "name": d["name"],
            "state": "Odisha",
            "population": d["population"],
            # Boundary geometry would come from GeoJSON — placeholder point for now
            "boundary": f"POINT({d['lng']} {d['lat']})",
            "signal_strength": 1.0,
        }
        for d in DISTRICTS
    ]
    result = db.table("districts").upsert(rows, on_conflict="name").execute()
    print(f"Seeded {len(result.data)} districts")


if __name__ == "__main__":
    seed()
