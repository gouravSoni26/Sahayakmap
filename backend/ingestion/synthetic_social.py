"""
Synthetic social media report generator.

Simulates citizen flood reports that would come from Twitter/X in a real deployment.
Designed to produce the specific contradiction and corroboration scenarios from
the Cyclone Fani demo (see MASTERPLAN.md — Simulation / Demo Scenario).
"""
import logging
import random
from datetime import datetime, timezone

from database import get_client

logger = logging.getLogger(__name__)

TEMPLATES = [
    "{severity_word} water on {road} near {place}. {action}. #OdishaFlood",
    "{place} area completely submerged. {people} people stranded. Need boats urgently.",
    "Bridge near {place} is {bridge_status}. {vehicle_type} vehicles stuck since {hours}hrs.",
    "Relief camp at {place} running low on {supplies}. Urgently needed.",
    "Water entered houses in {locality}, {place}. Level rising fast.",
    "{place} to {place2} route blocked due to flooding. Use alternate via {alternate}.",
]

PLACES = [
    ("Kendrapara", 20.51, 86.42, "Kendrapara"),
    ("Jagatsinghpur", 20.27, 86.17, "Jagatsinghpur"),
    ("Jajpur", 20.85, 86.33, "Jajpur"),
    ("Cuttack", 20.46, 85.88, "Cuttack"),
    ("Puri", 19.81, 85.83, "Puri"),
    ("Bhadrak", 21.06, 86.50, "Bhadrak"),
]

SEVERITY_WORDS = ["Knee-deep", "Waist-deep", "Ankle-deep", "Chest-deep"]
ROADS = ["NH-16", "SH-12", "NH-53", "SH-9", "NH-203"]
ACTIONS = ["People evacuating by boat", "Vehicles submerged", "Traffic halted", "Residents moving to roof"]
BRIDGE_STATUSES = ["submerged", "partially blocked", "damaged"]
VEHICLE_TYPES = ["Heavy", "Light", "Bus"]
SUPPLIES = ["food", "drinking water", "medicines", "tarpaulins"]


async def generate_social_reports(count: int = 3) -> None:
    """Generate a batch of synthetic social media reports and insert into flood_reports."""
    db = get_client()

    # Get active data sources of type SOCIAL_MEDIA
    source_result = db.table("data_sources").select("id").eq("type", "SOCIAL_MEDIA").limit(1).execute()
    source_id = source_result.data[0]["id"] if source_result.data else None

    rows = []
    for _ in range(count):
        place_name, lat, lng, district = random.choice(PLACES)
        lat += random.uniform(-0.05, 0.05)
        lng += random.uniform(-0.05, 0.05)

        # Realistic distribution: most reports are moderate, critical is rare.
        severity = random.choices([2, 3, 4, 5], weights=[30, 40, 20, 10])[0]
        text = _generate_text(place_name)
        # More retweets/similar reports = higher confidence. Capped at 0.70 because
        # social media alone can never be fully trusted (could be coordinated misinformation).
        corroborating = random.randint(0, 8)
        confidence = min(0.30 + corroborating * 0.05, 0.70)

        rows.append({
            "source_id": source_id,
            "location": f"POINT({lng:.4f} {lat:.4f})",
            "severity": severity,
            "confidence": round(confidence, 2),
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "description": text,
            "raw_payload": {
                "platform": "twitter",
                "synthetic": True,
                "corroborating_reports": corroborating,
                "has_image": random.random() > 0.7,
            },
        })

    if rows:
        db.table("flood_reports").insert(rows).execute()
        logger.debug("Generated %d synthetic social media reports", len(rows))


def _generate_text(place: str) -> str:
    template = random.choice(TEMPLATES)
    place2_name = random.choice([p[0] for p in PLACES if p[0] != place])
    return template.format(
        severity_word=random.choice(SEVERITY_WORDS),
        road=random.choice(ROADS),
        place=place,
        place2=place2_name,
        action=random.choice(ACTIONS),
        people=random.randint(50, 500),
        bridge_status=random.choice(BRIDGE_STATUSES),
        vehicle_type=random.choice(VEHICLE_TYPES),
        hours=random.randint(2, 12),
        supplies=random.choice(SUPPLIES),
        locality=f"Ward {random.randint(1, 20)}",
        alternate=f"via NH-{random.randint(10, 99)}",
    )
