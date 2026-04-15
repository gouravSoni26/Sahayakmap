"""
Resource allocation recommendations.

Deterministic Python scoring to identify the highest-priority redeployment.
The LLM in briefing.py uses the output of these functions to phrase the
recommendation in natural language.
"""
import logging
from datetime import datetime, timedelta, timezone

from fusion.spatial import haversine_km

logger = logging.getLogger(__name__)

ASSET_COVERAGE_RADIUS_KM = 100  # max useful deployment distance


def compute_top_recommendation(
    assets: list[dict],
    reports: list[dict],
    districts: list[dict],
) -> dict | None:
    """
    Find the district with highest flood severity and no nearby available assets.
    Returns a structured recommendation dict or None if situation is covered.
    """
    available_boats = [a for a in assets if a["type"] == "BOAT" and a["status"] == "AVAILABLE"]

    # Score districts by severity + population
    district_scores: list[tuple[float, dict]] = []
    for d in districts:
        d_reports = [r for r in reports if r.get("district_id") == d["id"]]
        if not d_reports:
            continue
        avg_sev = sum(r.get("severity", 1) for r in d_reports) / len(d_reports)
        pop_factor = min(d.get("population", 100_000) / 100_000, 5)
        score = avg_sev * 10 + pop_factor * 5
        district_scores.append((score, d))

    district_scores.sort(reverse=True)

    for score, district in district_scores:
        loc = district.get("location") or district.get("boundary")
        if not loc:
            continue

        # Check if any available boats are within range
        nearest_boat = _nearest_available_asset(available_boats, district)
        if nearest_boat is None:
            continue  # no boats at all, can't recommend
        if nearest_boat["distance_km"] > ASSET_COVERAGE_RADIUS_KM:
            return {
                "action": "redeploy",
                "to_district": district["name"],
                "from_district": nearest_boat["asset"].get("assigned_district_name", "base"),
                "asset_type": "BOAT",
                "asset_count": min(2, len(available_boats)),
                "eta_hours": round(nearest_boat["distance_km"] / 40, 1),  # 40 km/h average
                "reason": f"{district['name']} has severity {score / 10:.1f} flooding with no nearby assets",
                "confidence": 0.65,
            }

    return None


def _nearest_available_asset(assets: list[dict], district: dict) -> dict | None:
    if not assets:
        return None

    d_lat = district.get("lat") or 20.46
    d_lng = district.get("lng") or 85.88

    best = None
    best_dist = float("inf")
    for asset in assets:
        loc = asset.get("location", "")
        try:
            coords = loc.replace("POINT(", "").replace(")", "").split()
            a_lat, a_lng = float(coords[1]), float(coords[0])
            dist = haversine_km(d_lat, d_lng, a_lat, a_lng)
            if dist < best_dist:
                best_dist = dist
                best = {"asset": asset, "distance_km": dist}
        except (IndexError, ValueError):
            continue

    return best
