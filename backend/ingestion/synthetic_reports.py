"""
Synthetic district collector situation report generator.

Simulates structured SDMA situation reports that district offices submit
every 2-4 hours. Designed to occasionally be delayed (simulating the
reporting chain lag in real disasters).
"""
import logging
import random
from datetime import datetime, timezone

from database import get_client

logger = logging.getLogger(__name__)

DISTRICTS = [
    ("Kendrapara", 20.51, 86.42),
    ("Jagatsinghpur", 20.27, 86.17),
    ("Jajpur", 20.85, 86.33),
    ("Cuttack", 20.46, 85.88),
    ("Puri", 19.81, 85.83),
    ("Bhadrak", 21.06, 86.50),
    ("Ganjam", 19.38, 84.99),
    ("Khordha", 20.18, 85.60),
]


async def generate_district_reports() -> None:
    db = get_client()

    source_result = (
        db.table("data_sources").select("id").eq("type", "DISTRICT_REPORT").limit(1).execute()
    )
    source_id = source_result.data[0]["id"] if source_result.data else None

    rows = []
    for district, lat, lng in DISTRICTS:
        # Randomly skip some districts to simulate reporting gaps / silent districts
        if random.random() < 0.15:
            continue

        severity = random.choices([1, 2, 3, 4], weights=[20, 40, 30, 10])[0]
        affected_blocks = random.randint(0, 8)
        evacuated = random.randint(0, 5000) if severity >= 3 else 0

        description = (
            f"{district} District Report: {affected_blocks} blocks affected, "
            f"{evacuated} persons evacuated. "
            f"Roads blocked: {random.randint(0, 5)}. "
            f"Relief camps active: {random.randint(0, 4)}."
        )

        rows.append({
            "source_id": source_id,
            "source_type": "DISTRICT_REPORT",
            "location": f"POINT({lng:.4f} {lat:.4f})",
            "severity": severity,
            "confidence": 0.80,
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "description": description,
            "raw_payload": {
                "district": district,
                "affected_blocks": affected_blocks,
                "evacuated_count": evacuated,
                "casualties": random.randint(0, 3) if severity >= 4 else 0,
                "roads_blocked": random.randint(0, 5),
                "relief_camps_active": random.randint(0, 4),
                "synthetic": True,
            },
        })

    if rows:
        db.table("flood_reports").insert(rows).execute()
        logger.info("Generated %d district collector reports", len(rows))
