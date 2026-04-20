"""
Spatial conflict detection and clustering.

Detects when data sources within the same geographic area provide
contradictory information — the key scenario from the capstone brief
(gauge says safe, social media says flooding).
"""
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from fusion.confidence import compute_fused_confidence

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


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO timestamp string to a timezone-aware datetime. Returns None on failure."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _social_vs_social_conflicts(social_reports: list[dict], window_seconds: float) -> list[Conflict]:
    """
    Find clusters of nearby social reports that contradict each other —
    some reporting flooding, others reporting normal conditions in the same area.
    Requires at least 2 high-severity AND 2 low-severity reports in the cluster.
    """
    conflicts = []
    clustered: set[str] = set()  # tracks report IDs, not list positions

    for anchor in social_reports:
        anchor_id = anchor.get("id")
        if anchor_id in clustered:
            continue
        a_lat = anchor.get("lat", 0)
        a_lng = anchor.get("lng", 0)
        a_dt = _parse_dt(anchor.get("reported_at"))

        cluster = [anchor]
        for other in social_reports:
            other_id = other.get("id")
            if other_id == anchor_id or other_id in clustered:
                continue
            if haversine_km(a_lat, a_lng, other.get("lat", 0), other.get("lng", 0)) > CONFLICT_RADIUS_KM:
                continue
            if a_dt is not None:
                o_dt = _parse_dt(other.get("reported_at"))
                if o_dt is not None and abs((a_dt - o_dt).total_seconds()) > window_seconds:
                    continue
            cluster.append(other)

        if len(cluster) < 4:
            continue  # need meaningful sample size for social-vs-social

        severities = [r.get("severity", 1) for r in cluster]
        high_count = sum(1 for s in severities if s >= 3)
        low_count = sum(1 for s in severities if s <= 2)

        if high_count >= 2 and low_count >= 2:
            clustered.update(r.get("id") for r in cluster)
            avg_severity = sum(severities) / len(severities)
            conflicts.append(Conflict(
                type=ConflictType.SOCIAL_CONTRADICTS_SOCIAL,
                location_lat=a_lat,
                location_lng=a_lng,
                source_a_type="SOCIAL_MEDIA",
                source_b_type="SOCIAL_MEDIA",
                likely_cause=(
                    f"Mixed social reports: {high_count} report flooding, {low_count} report normal "
                    "conditions in the same area. Possible localised flooding or misinformation."
                ),
                recommended_severity=max(2, round(avg_severity)),
                fused_confidence=compute_fused_confidence(cluster),
                both_valid=False,  # contradictory — one side must be wrong or flooding is hyper-localised
            ))

    return conflicts


def detect_conflicts(gauge_reports: list[dict], social_reports: list[dict]) -> list[Conflict]:
    """
    Detect contradictions between gauge readings and social media reports
    in the same geographic area and within CONFLICT_TIME_WINDOW_HR of each other.
    Also detects social-vs-social contradictions within the same cluster.
    """
    conflicts = []
    window_seconds = CONFLICT_TIME_WINDOW_HR * 3600

    for gauge in gauge_reports:
        g_lat = gauge.get("lat", 0)
        g_lng = gauge.get("lng", 0)
        g_level = gauge.get("water_level_m", 0)
        # Default to inf so a missing threshold never triggers a false conflict.
        # A gauge without a configured warning level is not in danger.
        g_warning = gauge.get("warning_level_m") or float("inf")
        g_danger = gauge.get("danger_level_m") or (g_warning + 2.0)
        g_confidence = gauge.get("confidence", 0.85)
        g_dt = _parse_dt(gauge.get("reported_at"))

        nearby_social = []
        for r in social_reports:
            if haversine_km(g_lat, g_lng, r.get("lat", 0), r.get("lng", 0)) > CONFLICT_RADIUS_KM:
                continue
            # Only compare reports that are temporally close — a tweet from 5 hours
            # ago should not be used to contradict a fresh gauge reading.
            if g_dt is not None:
                r_dt = _parse_dt(r.get("reported_at"))
                if r_dt is not None and abs((g_dt - r_dt).total_seconds()) > window_seconds:
                    continue
            nearby_social.append(r)

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
                fused_confidence=compute_fused_confidence(nearby_social),
                both_valid=True,
            ))

        elif g_level >= g_warning and avg_severity <= 2:
            # Gauge elevated (warning or above) but no social reports yet.
            # Was previously only triggered at danger_level — now also catches the
            # warning-to-danger middle ground so silent-district cases are not missed.
            if g_level >= g_danger:
                overshoot = g_level - g_danger
                severity = 5 if overshoot >= 2.0 else 4
            else:
                severity = 3  # above warning but below danger — flag, not yet critical

            conflicts.append(Conflict(
                type=ConflictType.GAUGE_HIGH_SOCIAL_LOW,
                location_lat=g_lat,
                location_lng=g_lng,
                source_a_type="CWC_GAUGE",
                source_b_type="SOCIAL_MEDIA",
                likely_cause="River level rising but flooding has not yet reached populated areas. Expect worsening.",
                recommended_severity=severity,
                fused_confidence=g_confidence,  # trust the calibrated gauge
                both_valid=True,
            ))

    conflicts.extend(_social_vs_social_conflicts(social_reports, window_seconds))
    return conflicts
