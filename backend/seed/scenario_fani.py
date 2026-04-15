"""
Cyclone Fani Replay — pre-built simulation scenario.

Each step represents a point in the compressed demo timeline (see MASTERPLAN.md).
Step 0 = T+0h: Normal conditions. Step 8 = T+24h: Full scenario active.

Data in each step inserts into live tables so the rest of the system is unaware
it's a simulation. Steps are cumulative — each builds on the previous.
"""
from datetime import datetime, timezone

_NOW = datetime.now(timezone.utc).isoformat()

SCENARIO_STEPS = [
    # Step 0 — T+0h: Normal. IMD forecast shows heavy rainfall approaching.
    {
        "label": "T+0h: Normal conditions — cyclone approaching",
        "flood_reports": [],
        "asset_updates": [],
        "alerts": [],
    },

    # Step 1 — T+3h: Rainfall begins. Open-Meteo shows 80mm/hr over Kendrapara.
    {
        "label": "T+3h: Heavy rainfall begins",
        "flood_reports": [
            {
                "source_type": "IMD_WEATHER",
                "location": "POINT(86.42 20.51)",
                "severity": 2,
                "confidence": 0.75,
                "reported_at": _NOW,
                "description": "IMD: 80mm/hr rainfall forecast over Kendrapara and Jagatsinghpur.",
                "raw_payload": {"synthetic": True, "scenario_step": 1},
            }
        ],
        "asset_updates": [],
        "alerts": [],
    },

    # Step 2 — T+6h: Naraj crosses warning. 12 social reports from Jajpur
    #           but CWC gauge at Jajpur still normal → CONTRADICTION SCENARIO
    {
        "label": "T+6h: Naraj at warning. Jajpur contradiction.",
        "flood_reports": [
            {
                "source_type": "CWC_GAUGE",
                "location": "POINT(85.79 20.47)",
                "severity": 3,
                "water_level_m": 22.3,
                "water_level_trend": "RISING",
                "confidence": 0.95,
                "reported_at": _NOW,
                "description": "Naraj gauge at 22.3m (warning level: 22.0m). Rising.",
                "raw_payload": {"station_code": "NARAJ", "synthetic": True, "scenario_step": 2},
            },
        ] + [
            {
                "source_type": "SOCIAL_MEDIA",
                "location": f"POINT({86.33 + i * 0.01} {20.85 + i * 0.005})",
                "severity": 3,
                "confidence": 0.35,
                "reported_at": _NOW,
                "description": "Knee-deep water in Jajpur residential areas. Drainage blocked.",
                "raw_payload": {"synthetic": True, "scenario_step": 2, "corroborating_reports": i},
            }
            for i in range(12)
        ],
        "asset_updates": [],
        "alerts": [],
    },

    # Step 3 — T+9h: Naraj crosses danger. Bridge at Jenapur submerged.
    {
        "label": "T+9h: Naraj at danger. Jenapur bridge submerged.",
        "flood_reports": [
            {
                "source_type": "CWC_GAUGE",
                "location": "POINT(85.79 20.47)",
                "severity": 4,
                "water_level_m": 25.9,
                "water_level_trend": "RISING",
                "confidence": 0.95,
                "reported_at": _NOW,
                "description": "Naraj gauge at 25.9m — ABOVE DANGER LEVEL (25.5m). Rising 0.3m/hr.",
                "raw_payload": {"station_code": "NARAJ", "synthetic": True, "scenario_step": 3},
            },
        ] + [
            {
                "source_type": "SOCIAL_MEDIA",
                "location": f"POINT({86.14 + i * 0.005} {20.93})",
                "severity": 4,
                "confidence": 0.50,
                "reported_at": _NOW,
                "description": "Jenapur bridge submerged. Vehicles stuck. NH-53 blocked.",
                "raw_payload": {"synthetic": True, "scenario_step": 3, "has_image": True},
            }
            for i in range(3)
        ],
        "asset_updates": [],
        "alerts": [
            {
                "type": "BRIDGE_SUBMERGED",
                "severity": 4,
                "location": "POINT(86.14 20.93)",
                "title": "Jenapur Bridge submerged — NH-53 blocked",
                "description": "3 independent reports confirm Jenapur bridge on NH-53 is submerged. Supply convoys must reroute.",
                "recommended_action": "Reroute convoys via NH-16 through Cuttack.",
                "supporting_data": {"bridge": "Jenapur", "route": "NH-53", "scenario_step": 3},
            }
        ],
    },

    # Step 4 — T+12h: Forecast divergence. Boats deployed to Kendrapara
    #           but rain concentrated over Jagatsinghpur.
    {
        "label": "T+12h: Forecast divergence — wrong district.",
        "flood_reports": [
            {
                "source_type": "SOCIAL_MEDIA",
                "location": "POINT(86.17 20.27)",
                "severity": 4,
                "confidence": 0.55,
                "reported_at": _NOW,
                "description": "Severe flooding in Jagatsinghpur. No rescue boats seen. People on rooftops.",
                "raw_payload": {"synthetic": True, "scenario_step": 4, "corroborating_reports": 7},
            }
        ],
        "asset_updates": [],
        "alerts": [
            {
                "type": "FORECAST_DIVERGENCE",
                "severity": 3,
                "title": "Rainfall concentrated in Jagatsinghpur — not Kendrapara",
                "description": "Open-Meteo forecast predicted 80mm/hr over Kendrapara. Actual heavy rainfall fell over Jagatsinghpur. 2 boats are in Kendrapara with no reports there.",
                "recommended_action": "Redeploy 2 boats from Kendrapara to Jagatsinghpur via Devi River route. ETA 2.5 hours.",
                "supporting_data": {"scenario_step": 4},
            }
        ],
    },

    # Step 5 — T+15h: Ganjam goes silent.
    {
        "label": "T+15h: Ganjam district silent.",
        "flood_reports": [],
        "asset_updates": [],
        "alerts": [
            {
                "type": "SILENT_DISTRICT",
                "severity": 3,
                "title": "Ganjam district — no reports for 4 hours",
                "description": "Ganjam district (population 3.5M) has had zero situation reports for 4 hours. District collector unreachable. Possible communication infrastructure failure.",
                "recommended_action": "Contact Ganjam DC via alternate channel. Consider dispatching liaison team.",
                "supporting_data": {"district": "Ganjam", "scenario_step": 5},
            }
        ],
    },

    # Step 6 — T+18h: Satellite imagery arrives (12 hours old).
    {
        "label": "T+18h: Stale satellite imagery received.",
        "flood_reports": [
            {
                "source_type": "SATELLITE",
                "location": "POINT(85.88 20.46)",
                "severity": 3,
                "confidence": 0.70,
                "reported_at": _NOW,
                "description": "Sentinel-1 SAR imagery (captured 12 hours ago) shows flood extent in Cuttack and Kendrapara districts. Note: situation may have changed.",
                "raw_payload": {"synthetic": True, "scenario_step": 6, "capture_lag_hours": 12},
            }
        ],
        "asset_updates": [],
        "alerts": [],
    },

    # Step 7 — T+21h: Erasama camp at risk.
    {
        "label": "T+21h: Erasama camp in projected flood zone.",
        "flood_reports": [],
        "asset_updates": [],
        "alerts": [
            {
                "type": "CAMP_AT_RISK",
                "severity": 4,
                "location": "POINT(86.38 20.22)",
                "title": "Erasama School Camp — projected flood in 3 hours",
                "description": "Flood projection model shows water reaching Erasama School Camp elevation (4.5m) within 3 hours. 340 evacuees currently sheltering there require re-evacuation.",
                "recommended_action": "Immediately move 340 persons from Erasama camp to Kendrapara District Camp (elevation 12m). Dispatch 2 buses + 1 boat.",
                "affected_population": 340,
                "supporting_data": {"camp": "Erasama School Camp", "scenario_step": 7},
            }
        ],
    },

    # Step 8 — T+24h: Full picture active. All scenarios live.
    {
        "label": "T+24h: Full situation — triage scenario.",
        "flood_reports": [],
        "asset_updates": [],
        "alerts": [],
    },
]
