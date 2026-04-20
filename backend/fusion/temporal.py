"""
Temporal freshness model.

Every data point has a half-life — the time after which its decision value
drops by 50%. Used both for visual encoding (map opacity) and for the fusion
engine's weighting when data conflicts.
"""
import logging
import math
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


# Staleness threshold: freshness_factor below this = stale.
# 0.25 = 2 half-lives elapsed = data has lost 75% of decision value.
# Why 0.25? A commander should not trust data that's missed 2+ update cycles.
STALE_THRESHOLD = 0.25

# Never make data invisible — even stale data is better than no data in a disaster.
# The commander should see it exists but know it's old (via reduced opacity).
MIN_OPACITY = 0.2


class DataType(str, Enum):
    RIVER_GAUGE = "RIVER_GAUGE"
    WEATHER_SHORT = "WEATHER_SHORT"    # next 3h forecast
    WEATHER_LONG = "WEATHER_LONG"      # 12-24h forecast
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    SATELLITE = "SATELLITE"
    ROAD_STATUS = "ROAD_STATUS"
    DISTRICT_REPORT = "DISTRICT_REPORT"
    ASSET_TRACKER = "ASSET_TRACKER"


# Half-life in minutes for each data type.
# Why these values? Each is ~2× the expected update interval for that source.
# After 1 half-life with no update, something is probably wrong.
# After 2 half-lives (STALE_THRESHOLD), data is unreliable for decisions.
HALF_LIFE_MINUTES: dict[DataType, float] = {
    DataType.RIVER_GAUGE: 30,       # CWC updates every 15 min → 30 min = 2 missed
    DataType.WEATHER_SHORT: 60,     # hourly forecasts → stale after 1h
    DataType.WEATHER_LONG: 180,     # 12-24h forecasts drift slowly → 3h is fine
    DataType.SOCIAL_MEDIA: 120,     # tweets go stale fast but 2h covers reporting lag
    DataType.SATELLITE: 360,        # satellite passes are 6-12h apart
    DataType.ROAD_STATUS: 240,      # road conditions change slowly unless active flooding
    DataType.DISTRICT_REPORT: 180,  # district offices report every 2-4h
    DataType.ASSET_TRACKER: 15,     # GPS pings every 5-10 min → 15 min = 2 missed
}

# Map from source_type string (DB/API) → DataType.
# IMD_WEATHER maps to SHORT by default; callers can pass forecast_horizon_hours
# to get_half_life() to select WEATHER_LONG when appropriate.
SOURCE_TYPE_MAP: dict[str, DataType] = {
    "CWC_GAUGE": DataType.RIVER_GAUGE,
    "IMD_WEATHER": DataType.WEATHER_SHORT,
    "SOCIAL_MEDIA": DataType.SOCIAL_MEDIA,
    "SATELLITE": DataType.SATELLITE,
    "OSM_ROAD": DataType.ROAD_STATUS,
    "DISTRICT_REPORT": DataType.DISTRICT_REPORT,
    "ASSET_TRACKER": DataType.ASSET_TRACKER,
}


def get_half_life(source_type: str, forecast_horizon_hours: float | None = None) -> float:
    """Return half-life in minutes for a given source type.

    For IMD_WEATHER, pass forecast_horizon_hours to distinguish short-range
    (≤3h → 60 min half-life) from long-range (>3h → 180 min half-life).
    """
    data_type = SOURCE_TYPE_MAP.get(source_type)
    if data_type is None:
        logger.warning("Unknown source_type %r — no half-life mapping exists", source_type)
        data_type = DataType.SOCIAL_MEDIA

    if data_type == DataType.WEATHER_SHORT and forecast_horizon_hours and forecast_horizon_hours > 3:
        data_type = DataType.WEATHER_LONG

    return HALF_LIFE_MINUTES[data_type]


def freshness_factor(
    reported_at: datetime,
    half_life_minutes: float,
    now: datetime | None = None,
) -> float:
    """
    Returns a value between 0.0 and 1.0.
    1.0 = just reported, 0.5 = one half-life old, 0.0 = infinitely stale.
    Uses exponential decay: f(t) = 0.5 ^ (age / half_life)

    Pass `now` to override wall-clock time (for simulation mode and testing).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age_minutes = (now - reported_at).total_seconds() / 60
    if age_minutes <= 0:
        return 1.0

    # Exponential decay: value drops by half every half_life_minutes.
    # Why exponential (not linear)? Data is nearly as good at 5 min as at 0 min,
    # but drastically less useful after 2 half-lives. Linear would overpenalize fresh data.
    return math.pow(0.5, age_minutes / half_life_minutes)


def is_stale(
    reported_at: datetime,
    source_type: str,
    threshold: float = STALE_THRESHOLD,
    now: datetime | None = None,
) -> bool:
    """
    Returns True if the freshness factor is below the threshold.
    Default threshold of 0.25 ≈ 2 half-lives old.
    """
    hl = get_half_life(source_type)
    return freshness_factor(reported_at, hl, now=now) < threshold


class FreshnessState(str, Enum):
    """Visual state for map rendering (matches MASTERPLAN visual encoding spec)."""
    FRESH = "FRESH"                # full opacity, solid border
    AGING = "AGING"                # reduced opacity, solid border
    VERY_STALE = "VERY_STALE"      # low opacity, dashed border
    OFFLINE = "OFFLINE"            # faded + warning icon


def visual_state(factor: float, source_online: bool = True) -> FreshnessState:
    """
    Determine the visual rendering state from a freshness factor.

    MASTERPLAN spec:
      - Full opacity        → fresh (factor > 0.5, i.e. within 1 half-life)
      - 50% opacity         → past half-life (0.25 < factor ≤ 0.5)
      - Dashed border       → past 2× half-life (factor ≤ 0.25)
      - Faded + warning     → source offline
    """
    if not source_online:
        return FreshnessState.OFFLINE
    if factor > 0.5:
        return FreshnessState.FRESH
    if factor > STALE_THRESHOLD:
        return FreshnessState.AGING
    return FreshnessState.VERY_STALE


def opacity_from_freshness(factor: float) -> float:
    """
    Map freshness factor to a UI opacity value (MIN_OPACITY – 1.0).
    Very stale data is rendered at minimum opacity, never fully invisible.
    """
    return round(max(MIN_OPACITY, factor), 2)
