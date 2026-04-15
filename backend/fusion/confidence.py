"""
Confidence scoring for flood reports.

Base confidence by source type, with corroboration boosts when multiple
independent sources agree within 5km and 1 hour.
"""

# Base confidence by source type (0.0 – 1.0)
BASE_CONFIDENCE: dict[str, float] = {
    "CWC_GAUGE": 0.95,
    "IMD_WEATHER": 0.75,
    "SATELLITE": 0.90,
    "DISTRICT_REPORT": 0.80,
    "SOCIAL_MEDIA": 0.30,
    "OSM_ROAD": 0.70,
    "ASSET_TRACKER": 0.85,
}

# Corroboration boosts
CORROBORATION_BOOST = {
    2: 0.15,   # 2 independent sources
    3: 0.25,   # 3+ independent sources
}
OFFICIAL_PLUS_SOCIAL_BOOST = 0.20
PHOTO_BOOST = 0.20  # social media report with image


def base_confidence(source_type: str) -> float:
    return BASE_CONFIDENCE.get(source_type, 0.50)


def apply_corroboration(confidence: float, corroborating_count: int) -> float:
    """
    Boost confidence when multiple independent reports agree.
    Only applied to SOCIAL_MEDIA reports — gauge data doesn't need this.
    """
    if corroborating_count >= 3:
        boost = CORROBORATION_BOOST[3]
    elif corroborating_count >= 2:
        boost = CORROBORATION_BOOST[2]
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
    """
    if not reports:
        return 0.0

    source_types = {r["source_type"] for r in reports}
    count = len(reports)

    # Base: average of individual confidences
    avg = sum(r.get("confidence", 0.5) for r in reports) / count

    # Diversity bonus: more source types = higher confidence
    diversity_bonus = min(len(source_types) * 0.05, 0.20)

    # Official + social corroboration
    has_official = bool(source_types & {"CWC_GAUGE", "DISTRICT_REPORT", "SATELLITE"})
    has_social = "SOCIAL_MEDIA" in source_types
    official_social_bonus = OFFICIAL_PLUS_SOCIAL_BOOST if (has_official and has_social) else 0.0

    return min(1.0, round(avg + diversity_bonus + official_social_bonus, 3))
