"""
Temporal freshness model.

Every data point has a half-life — the time after which its decision value
drops by 50%. Used both for visual encoding (map opacity) and for the fusion
engine's weighting when data conflicts.
"""
import math
from datetime import datetime, timezone
from enum import Enum


class DataType(str, Enum):
    RIVER_GAUGE = "RIVER_GAUGE"
    WEATHER_SHORT = "WEATHER_SHORT"    # next 3h forecast
    WEATHER_LONG = "WEATHER_LONG"      # 12-24h forecast
    SOCIAL_MEDIA = "SOCIAL_MEDIA"
    SATELLITE = "SATELLITE"
    ROAD_STATUS = "ROAD_STATUS"
    DISTRICT_REPORT = "DISTRICT_REPORT"


# Half-life in minutes for each data type
HALF_LIFE_MINUTES: dict[DataType, float] = {
    DataType.RIVER_GAUGE: 30,
    DataType.WEATHER_SHORT: 60,
    DataType.WEATHER_LONG: 180,
    DataType.SOCIAL_MEDIA: 120,
    DataType.SATELLITE: 360,
    DataType.ROAD_STATUS: 240,
    DataType.DISTRICT_REPORT: 180,
}

# Map from source_type string → DataType
SOURCE_TYPE_MAP: dict[str, DataType] = {
    "CWC_GAUGE": DataType.RIVER_GAUGE,
    "IMD_WEATHER": DataType.WEATHER_SHORT,
    "SOCIAL_MEDIA": DataType.SOCIAL_MEDIA,
    "SATELLITE": DataType.SATELLITE,
    "OSM_ROAD": DataType.ROAD_STATUS,
    "DISTRICT_REPORT": DataType.DISTRICT_REPORT,
}


def get_half_life(source_type: str) -> float:
    """Return half-life in minutes for a given source type."""
    data_type = SOURCE_TYPE_MAP.get(source_type, DataType.SOCIAL_MEDIA)
    return HALF_LIFE_MINUTES[data_type]


def freshness_factor(reported_at: datetime, half_life_minutes: float) -> float:
    """
    Returns a value between 0.0 and 1.0.
    1.0 = just reported, 0.5 = one half-life old, 0.0 = infinitely stale.
    Uses exponential decay: f(t) = 0.5 ^ (age / half_life)
    """
    now = datetime.now(timezone.utc)
    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=timezone.utc)

    age_minutes = (now - reported_at).total_seconds() / 60
    if age_minutes <= 0:
        return 1.0

    return math.pow(0.5, age_minutes / half_life_minutes)


def is_stale(reported_at: datetime, source_type: str, threshold: float = 0.25) -> bool:
    """
    Returns True if the freshness factor is below the threshold.
    Default threshold of 0.25 ≈ 2 half-lives old.
    """
    hl = get_half_life(source_type)
    return freshness_factor(reported_at, hl) < threshold


def opacity_from_freshness(factor: float) -> float:
    """
    Map freshness factor to a UI opacity value (0.2 – 1.0).
    Very stale data is rendered at 20% opacity, never fully invisible.
    """
    return round(max(0.2, factor), 2)
