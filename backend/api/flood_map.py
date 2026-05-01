"""
Flood extent map API.

GET /api/map/flood-extent — returns projected flood polygons as a GeoJSON
FeatureCollection, one circle polygon per gauge currently above danger level.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from shapely import wkb as shapely_wkb
from supabase import Client

from database import get_db
from intelligence.projection import compute_flood_polygons

logger = logging.getLogger(__name__)

router = APIRouter()

# Explicit column lists — never select("*") (CLAUDE.md rule)
_GAUGE_COLUMNS = "id,station_code,name,danger_level_m,location"
_CWC_REPORT_COLUMNS = "id,source_id,water_level_m,reported_at,raw_payload"

# Hardcoded gauge metadata — mirrors seed/gauge_stations.py.
# Used as fallback when gauge_stations table is not yet seeded.
# Keyed by station_code (uppercase, same as seed and scenario raw_payload).
_GAUGE_META: dict[str, dict] = {
    "NARAJ":     {"danger_level_m": 25.5, "lat": 20.47, "lng": 85.79},
    "MUNDULI":   {"danger_level_m": 26.0, "lat": 20.49, "lng": 85.75},
    "ALIPINGAL": {"danger_level_m": 43.0, "lat": 20.83, "lng": 83.88},
    "TIKARPARA": {"danger_level_m": 38.5, "lat": 20.58, "lng": 84.78},
    "JENAPUR":   {"danger_level_m": 15.8, "lat": 20.93, "lng": 86.14},
    "ANANDPUR":  {"danger_level_m": 38.0, "lat": 21.21, "lng": 86.12},
}


class RepositoryError(Exception):
    """Raised when a database operation fails."""


class MapRepository:
    """All database operations for the flood-extent endpoint."""

    def __init__(self, db: Client):
        self.db = db

    def get_all_gauges(self) -> list[dict]:
        """Fetch all gauge stations (metadata only — no readings)."""
        try:
            return (
                self.db.table("gauge_stations")
                .select(_GAUGE_COLUMNS)
                .execute()
                .data or []
            )
        except Exception as exc:
            logger.error("DB error fetching gauge stations: %s", exc)
            raise RepositoryError(f"Failed to fetch gauge stations: {exc}") from exc

    def get_cwc_source_ids(self) -> list[str]:
        """Return IDs of all CWC_GAUGE data sources."""
        try:
            rows = (
                self.db.table("data_sources")
                .select("id")
                .eq("type", "CWC_GAUGE")
                .execute()
                .data or []
            )
            return [r["id"] for r in rows]
        except Exception as exc:
            logger.error("DB error fetching CWC source IDs: %s", exc)
            raise RepositoryError(f"Failed to fetch CWC sources: {exc}") from exc

    def get_recent_cwc_reports(self, cwc_source_ids: list[str], since: str) -> list[dict]:
        """Fetch recent CWC gauge reports, newest first."""
        if not cwc_source_ids:
            return []
        try:
            return (
                self.db.table("flood_reports")
                .select(_CWC_REPORT_COLUMNS)
                .in_("source_id", cwc_source_ids)
                .gte("reported_at", since)
                .order("reported_at", desc=True)
                .execute()
                .data or []
            )
        except Exception as exc:
            logger.error("DB error fetching CWC reports: %s", exc)
            raise RepositoryError(f"Failed to fetch CWC reports: {exc}") from exc


def get_map_repository(db: Client = Depends(get_db)) -> MapRepository:
    """FastAPI dependency — builds and returns a MapRepository."""
    return MapRepository(db)


def _parse_gauge_location(gauge: dict) -> tuple[float, float] | None:
    """
    Parse a gauge station's location field into (lat, lng).

    Supabase returns GEOMETRY columns as EWKB hex strings.
    shapely.wkb.loads handles both standard WKB and PostGIS EWKB.
    Falls back to WKT 'POINT(lng lat)' for test/seed data.
    """
    loc = gauge.get("location")
    if not loc:
        return None
    # Primary: EWKB hex (production Supabase)
    try:
        geom = shapely_wkb.loads(loc, hex=True)
        return geom.y, geom.x  # lat, lng
    except Exception:
        pass
    # Fallback: WKT "POINT(lng lat)"
    try:
        coords = str(loc).replace("POINT(", "").replace(")", "").split()
        return float(coords[1]), float(coords[0])
    except (IndexError, ValueError):
        return None


@router.get("/map/flood-extent")
async def flood_extent(
    repo: MapRepository = Depends(get_map_repository),
):
    """
    Projected flood extent as GeoJSON FeatureCollection.

    Returns one Polygon per gauge station currently above danger level.
    Polygon radius grows proportionally to how far the reading exceeds danger:
    base 2km at danger level, +2km per extra metre, capped at 15km.

    Properties per feature: gauge_id, station_code, name, water_level_m,
    danger_level_m, radius_km, lag_hrs.
    """
    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=3)).isoformat()

    try:
        gauges = repo.get_all_gauges()
        cwc_ids = repo.get_cwc_source_ids()
        reports = repo.get_recent_cwc_reports(cwc_ids, since)
    except RepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # level_map: station_code → latest water_level_m (reports already DESC)
    level_map: dict[str, float] = {}
    for r in reports:
        code = (r.get("raw_payload") or {}).get("station_code")
        if code and code not in level_map and r.get("water_level_m"):
            level_map[code] = r["water_level_m"]

    # gauge_meta: station_code → {danger_level_m, lat, lng, gauge_id, name}
    # Primary: rows from gauge_stations table (authoritative, includes DB id).
    # Fallback: _GAUGE_META hardcoded constants for stations not yet seeded.
    # This makes the endpoint work even when gauge_stations is empty (e.g. demo
    # environment where only seed.odisha_districts has been run).
    gauge_meta: dict[str, dict] = {}
    for g in gauges:
        code = g.get("station_code")
        if not code:
            continue
        coords = _parse_gauge_location(g)
        if not coords:
            logger.warning("No parseable location for gauge %s — skipping", code)
            continue
        lat, lng = coords
        gauge_meta[code] = {
            "gauge_id": g["id"],
            "name": g.get("name", code),
            "danger_level_m": g.get("danger_level_m"),
            "lat": lat,
            "lng": lng,
        }

    # Merge hardcoded fallback for any station not returned by gauge_stations
    for code, meta in _GAUGE_META.items():
        if code not in gauge_meta:
            gauge_meta[code] = {
                "gauge_id": code,  # pseudo-id — no DB row yet
                "name": code.title(),
                **meta,
            }

    # Build danger_gauges: stations with a current reading at or above danger level
    danger_gauges = []
    for code, level in level_map.items():
        meta = gauge_meta.get(code)
        if not meta:
            continue
        danger = meta.get("danger_level_m")
        if not danger or level < danger:
            continue
        danger_gauges.append({
            "gauge_id": meta["gauge_id"],
            "station_code": code,
            "name": meta["name"],
            "lat": meta["lat"],
            "lng": meta["lng"],
            "danger_level_m": danger,
            "water_level_m": level,
        })

    features = compute_flood_polygons(danger_gauges)
    return {
        "type": "FeatureCollection",
        "features": features,
        "generated_at": now.isoformat(),
    }
