"""
Confidence scoring for flood reports.

Base confidence by source type, with corroboration boosts when multiple
independent sources agree within 5km and 1 hour.
"""

import logging

logger = logging.getLogger(__name__)

# Base confidence by source type (0.0 – 1.0).
# Higher = more trustworthy by default. 0.95 not 1.0 because equipment can malfunction.
# Social media starts at 0.30 (unverified) and gets boosted by corroboration.
BASE_CONFIDENCE: dict[str, float] = {
    "CWC_GAUGE": 0.95,        # calibrated government instruments
    "IMD_WEATHER": 0.75,      # forecast accuracy degrades with horizon
    "SATELLITE": 0.90,        # high spatial accuracy but potentially stale
    "DISTRICT_REPORT": 0.80,  # official but manually compiled = delayed
    "SOCIAL_MEDIA": 0.30,     # single unverified citizen report
    "OSM_ROAD": 0.70,         # community-maintained, occasionally outdated
    "ASSET_TRACKER": 0.85,    # GPS hardware, reliable but can lose signal
}

# Corroboration boosts — only applied to SOCIAL_MEDIA reports.
# Why only social? Authoritative sources (gauges, satellite) don't need citizen
# corroboration. But a lone tweet is unreliable — multiple independent reports
# from the same area dramatically increase confidence.
CORROBORATION_BOOST_2_SOURCES = 0.15        # 2 people saying same thing = probably real
CORROBORATION_BOOST_3_PLUS_SOURCES = 0.25   # 3+ = very likely real
OFFICIAL_PLUS_SOCIAL_BOOST = 0.20           # gauge confirms what citizens report = strong
PHOTO_BOOST = 0.20  # image evidence harder to fake than text (but could be old/reposted)

# Source types considered "official" for corroboration purposes
OFFICIAL_SOURCE_TYPES = {"CWC_GAUGE", "DISTRICT_REPORT", "SATELLITE"}

# Corroboration boost is only meaningful for unverified citizen reports
CORROBORABLE_SOURCE_TYPES = {"SOCIAL_MEDIA"}


def base_confidence(source_type: str) -> float:
    return BASE_CONFIDENCE.get(source_type, 0.50)


def apply_corroboration(confidence: float, corroborating_count: int, source_type: str) -> float:
    """
    Boost confidence when multiple independent SOCIAL_MEDIA reports agree.
    Only applied to SOCIAL_MEDIA — authoritative sources (gauges, satellite,
    district reports) don't need citizen corroboration to be trusted.
    """
    if source_type not in CORROBORABLE_SOURCE_TYPES:
        return confidence

    if corroborating_count >= 3:
        boost = CORROBORATION_BOOST_3_PLUS_SOURCES
    elif corroborating_count >= 2:
        boost = CORROBORATION_BOOST_2_SOURCES
    else:
        return confidence
    return min(1.0, confidence + boost)


def apply_photo_boost(confidence: float, has_image: bool) -> float:
    if has_image:
        return min(1.0, confidence + PHOTO_BOOST)
    return confidence


def compute_fused_confidence(reports: list[dict]) -> float:
    """
    Compute a single fused confidence score from a list of nearby reports
    covering the same area. Higher when sources are diverse and numerous.

    Reports are expected to have a joined data_sources(type) object from Supabase.
    If the join is missing, the report is counted but logged as a warning —
    diversity bonus will be underestimated.
    """
    if not reports:
        return 0.0

    source_types = set()
    for r in reports:
        ds = r.get("data_sources") or {}
        src_type = ds.get("type")
        if src_type:
            source_types.add(src_type)
        else:
            logger.warning(
                "compute_fused_confidence: report id=%s is missing data_sources join — "
                "diversity bonus will be underestimated. Ensure the Supabase query "
                "includes .select('*, data_sources(type)').",
                r.get("id", "unknown"),
            )

    count = len(reports)

    # Base: average of individual confidences
    avg = sum(r.get("confidence", 0.5) for r in reports) / count

    # Diversity bonus: more source types = higher confidence (max +0.20)
    diversity_bonus = min(len(source_types) * 0.05, 0.20)

    # Official + social corroboration
    has_official = bool(source_types & OFFICIAL_SOURCE_TYPES)
    has_social = "SOCIAL_MEDIA" in source_types
    official_social_bonus = OFFICIAL_PLUS_SOCIAL_BOOST if (has_official and has_social) else 0.0

    return min(1.0, round(avg + diversity_bonus + official_social_bonus, 3))
