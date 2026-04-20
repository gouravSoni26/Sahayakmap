"""
Data sources registry — seed the data_sources table.
This must be run before synthetic ingestion jobs start,
as flood_reports.source_id references this table.

Run via:  python -m seed.data_sources
"""
from database import get_client

DATA_SOURCES = [
    {
        "type": "CWC_GAUGE",
        "name": "CWC River Gauge Network",
        "base_reliability": 0.95,
        "update_frequency_min": 15,
        "status": "ACTIVE",
        "config": {"stations": ["NARAJ", "MUNDULI", "ALIPINGAL", "TIKARPARA", "JENAPUR", "ANANDPUR"]},
    },
    {
        "type": "IMD_WEATHER",
        "name": "Open-Meteo Weather Forecast",
        "base_reliability": 0.75,
        "update_frequency_min": 30,
        "status": "ACTIVE",
        "config": {"base_url": "https://api.open-meteo.com/v1", "grid_points": 8},
    },
    {
        "type": "SOCIAL_MEDIA",
        "name": "Synthetic Social Media Reports",
        "base_reliability": 0.30,
        "update_frequency_min": 10,
        "status": "ACTIVE",
        "config": {"synthetic": True, "note": "Replace with real Twitter/X API in production"},
    },
    {
        "type": "DISTRICT_REPORT",
        "name": "District Collector Situation Reports",
        "base_reliability": 0.80,
        "update_frequency_min": 120,
        "status": "ACTIVE",
        "config": {"synthetic": True, "districts": 8},
    },
    {
        "type": "SATELLITE",
        "name": "Copernicus EMS Satellite Imagery",
        "base_reliability": 0.90,
        "update_frequency_min": 720,
        "status": "ACTIVE",
        "config": {"synthetic": True, "lag_hours": 12, "note": "Pre-processed flood extent overlays"},
    },
    {
        "type": "OSM_ROAD",
        "name": "OpenStreetMap Road Network",
        "base_reliability": 0.70,
        "update_frequency_min": None,
        "status": "ACTIVE",
        "config": {"source": "Overpass API", "load": "once"},
    },
]


def seed():
    db = get_client()
    result = db.table("data_sources").upsert(DATA_SOURCES, on_conflict="name").execute()
    print(f"Seeded {len(result.data)} data sources")
    for s in result.data:
        print(f"  [{s['type']}] {s['name']}")


if __name__ == "__main__":
    seed()
