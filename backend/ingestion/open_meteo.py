"""
Open-Meteo weather forecast ingestion.
Free API, no key required. Fetches hourly precipitation forecasts
for a grid of points across the Mahanadi basin.
"""
import logging
from datetime import datetime, timezone

import httpx

from config import settings
from database import get_client

logger = logging.getLogger(__name__)

# Grid of lat/lng points covering the Mahanadi basin
FORECAST_GRID = [
    {"name": "Cuttack",       "lat": 20.46, "lng": 85.88},
    {"name": "Puri",          "lat": 19.81, "lng": 85.83},
    {"name": "Bhubaneswar",   "lat": 20.30, "lng": 85.84},
    {"name": "Kendrapara",    "lat": 20.51, "lng": 86.42},
    {"name": "Jagatsinghpur", "lat": 20.27, "lng": 86.17},
    {"name": "Jajpur",        "lat": 20.85, "lng": 86.33},
    {"name": "Sambalpur",     "lat": 21.46, "lng": 83.97},
    {"name": "Bolangir",      "lat": 20.71, "lng": 83.48},
]


async def fetch_weather_forecasts() -> None:
    """Fetch 3-day hourly forecasts for all grid points and upsert into Supabase."""
    db = get_client()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for point in FORECAST_GRID:
            try:
                params = {
                    "latitude": point["lat"],
                    "longitude": point["lng"],
                    "hourly": "precipitation,rain,temperature_2m,windspeed_10m,winddirection_10m",
                    "forecast_days": 3,
                    "timezone": "Asia/Kolkata",
                }
                resp = await client.get(f"{settings.open_meteo_base_url}/forecast", params=params)
                resp.raise_for_status()
                data = resp.json()

                rows = _parse_forecast(data, point)
                if rows:
                    db.table("weather_forecasts").upsert(rows).execute()
                    logger.debug("Inserted %d forecast rows for %s", len(rows), point["name"])

            except Exception as e:
                logger.error("Failed to fetch forecast for %s: %s", point["name"], e)


def _parse_forecast(data: dict, point: dict) -> list[dict]:
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    rows = []
    for i, t in enumerate(times):
        rows.append({
            "location": f"POINT({point['lng']} {point['lat']})",
            "forecast_time": t,
            "rainfall_mm": hourly.get("precipitation", [None])[i],
            "temperature_c": hourly.get("temperature_2m", [None])[i],
            "wind_speed_kmh": hourly.get("windspeed_10m", [None])[i],
            "wind_direction_deg": hourly.get("winddirection_10m", [None])[i],
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source": "open-meteo",
        })
    return rows
