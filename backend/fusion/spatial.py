"""
Spatial conflict detection and clustering.

Detects when data sources within the same geographic area provide
contradictory information — the key scenario from the capstone brief
(gauge says safe, social media says flooding).
"""
import logging
import math
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

CONFLICT_RADIUS_KM = 10.0   # cluster reports within this radius
CONFLICT_TIME_WINDOW_HR = 1  # and within this time window


class ConflictType(str, Enum):
    GAUGE_LOW_SOCIAL_HIGH = "GAUGE_LOW_SOCIAL_HIGH"    # drainage congestion scenario
    GAUGE_HIGH_SOCIAL_LOW = "GAUGE_HIGH_SOCIAL_LOW"    # flooding not yet reached populated areas
    SOCIAL_CONTRADICTS_SOCIAL = "SOCIAL_CONTRADICTS_SOCIAL"


@dataclass
class Conflict:
    type: ConflictType
    location_lat: float
    location_lng: float
    source_a_type: str
    source_b_type: str
    likely_cause: str
    recommended_severity: int
    fused_confidence: float
    both_valid: bool


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two lat/lng points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def detect_conflicts(gauge_reports: list[dict], social_reports: list[dict]) -> list[Conflict]:
    """
    Detect contradictions between gauge readings and social media reports
    in the same geographic area.
    """
    conflicts = []

    for gauge in gauge_reports:
        g_lat = gauge.get("lat", 0)
        g_lng = gauge.get("lng", 0)
        g_level = gauge.get("water_level_m", 0)
        g_warning = gauge.get("warning_level_m", 0)

        nearby_social = [
            r for r in social_reports
            if haversine_km(g_lat, g_lng, r.get("lat", 0), r.get("lng", 0)) <= CONFLICT_RADIUS_KM
        ]

        if len(nearby_social) < 3:
            continue  # need at least 3 corroborating reports to flag a conflict

        avg_severity = sum(r.get("severity", 1) for r in nearby_social) / len(nearby_social)

        if g_level < g_warning and avg_severity >= 3:
            # Gauge reads safe, but citizens report flooding
            conflicts.append(Conflict(
                type=ConflictType.GAUGE_LOW_SOCIAL_HIGH,
                location_lat=g_lat,
                location_lng=g_lng,
                source_a_type="CWC_GAUGE",
                source_b_type="SOCIAL_MEDIA",
                likely_cause="Drainage congestion from local rainfall, not river overflow. Both sources may be correct.",
                recommended_severity=max(3, round(avg_severity)),
                fused_confidence=min(0.70, 0.30 + len(nearby_social) * 0.05),
                both_valid=True,
            ))

        elif g_level >= gauge.get("danger_level_m", 999) and avg_severity <= 2:
            # Gauge is critical but no social reports — flooding hasn't reached populated areas yet
            conflicts.append(Conflict(
                type=ConflictType.GAUGE_HIGH_SOCIAL_LOW,
                location_lat=g_lat,
                location_lng=g_lng,
                source_a_type="CWC_GAUGE",
                source_b_type="SOCIAL_MEDIA",
                likely_cause="River level rising but flooding has not yet reached populated areas. Expect worsening.",
                recommended_severity=4,
                fused_confidence=0.80,
                both_valid=True,
            ))

    return conflicts
