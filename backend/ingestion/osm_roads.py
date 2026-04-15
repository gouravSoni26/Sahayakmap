"""
OpenStreetMap road network loader via Overpass API.

Run once at startup (or via seed script) to load major highways and bridges
into the routes and bridges tables. Road STATUS is updated by the fusion layer
based on incoming flood reports.
"""
import logging

import httpx

from database import get_client

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OVERPASS_QUERY = """
[out:json][timeout:60];
area["name"="Odisha"]["admin_level"="4"]->.odisha;
(
  way["highway"~"trunk|primary"]["ref"](area.odisha);
  node["man_made"="bridge"]["highway"](area.odisha);
);
out geom;
"""


async def load_road_network() -> None:
    """
    Fetch major roads and bridges in Odisha from Overpass API and store in Supabase.
    This is a one-time load — call from a seed script, not the scheduler.
    """
    db = get_client()

    async with httpx.AsyncClient(timeout=90.0) as client:
        try:
            resp = await client.post(OVERPASS_URL, data={"data": OVERPASS_QUERY})
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Overpass API request failed: %s", e)
            return

    ways = [el for el in data.get("elements", []) if el["type"] == "way"]
    nodes = [el for el in data.get("elements", []) if el["type"] == "node"]

    logger.info("Overpass returned %d ways, %d nodes", len(ways), len(nodes))

    route_rows = []
    for way in ways:
        coords = way.get("geometry", [])
        if len(coords) < 2:
            continue
        linestring = "LINESTRING(" + ",".join(f"{c['lon']} {c['lat']}" for c in coords) + ")"
        ref = way.get("tags", {}).get("ref", "unknown")
        route_rows.append({
            "name": ref,
            "geometry": linestring,
            "route_type": way.get("tags", {}).get("highway", "unknown"),
        })

    if route_rows:
        db.table("routes").upsert(route_rows, on_conflict="name").execute()
        logger.info("Upserted %d routes", len(route_rows))
