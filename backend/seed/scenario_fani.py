"""
Cyclone Fani Replay — pre-built simulation scenario.

Each step represents a point in the compressed demo timeline (see MASTERPLAN.md).
Step 0 = T+0h: Normal conditions. Step 8 = T+24h: Full scenario active.

Data in each step inserts into live tables so the rest of the system is unaware
it's a simulation. Steps are cumulative — each builds on the previous.

NOTE: flood_reports use `_source_type` (a private marker, not a DB column).
api/scenarios.py resolves these to actual `source_id` FKs before inserting.
`reported_at` is intentionally omitted here — api/scenarios.py injects a fresh
UTC timestamp at the moment each step is applied, so data is never stale.
`supporting_data` has been removed from alerts — linked reports are stored
in the alert_reports junction table instead.
"""

# Pre-defined scatter offsets for social media reports — approximate real
# neighbourhood-level spread (~0.5–3km apart) rather than a linear grid.
# Format: (lng_offset, lat_offset)
_JAJPUR_OFFSETS = [
    ( 0.000,  0.000), ( 0.018,  0.007), (-0.012,  0.014), ( 0.027,  0.003),
    ( 0.009,  0.019), (-0.021,  0.011), ( 0.035,  0.006), ( 0.003,  0.017),
    ( 0.022,  0.001), (-0.014,  0.021), ( 0.031,  0.009), ( 0.011,  0.024),
]

_JENAPUR_OFFSETS = [
    ( 0.000,  0.000),
    ( 0.009,  0.002),
    (-0.006,  0.003),
]

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
                "_source_type": "IMD_WEATHER",
                "location": "POINT(86.42 20.51)",
                "severity": 2,
                "confidence": 0.75,
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
                "_source_type": "CWC_GAUGE",
                "location": "POINT(85.79 20.47)",
                "severity": 3,
                "water_level_m": 22.3,
                "water_level_trend": "RISING",
                "confidence": 0.95,
                "description": "Naraj gauge at 22.3m (warning level: 22.0m). Rising.",
                "raw_payload": {"station_code": "NARAJ", "synthetic": True, "scenario_step": 2},
            },
        ] + [
            {
                "_source_type": "SOCIAL_MEDIA",
                "location": f"POINT({86.33 + dlng:.4f} {20.85 + dlat:.4f})",
                "severity": 3,
                "confidence": 0.35,
                "description": "Knee-deep water in Jajpur residential areas. Drainage blocked.",
                "raw_payload": {"synthetic": True, "scenario_step": 2, "report_index": i},
            }
            for i, (dlng, dlat) in enumerate(_JAJPUR_OFFSETS)
        ],
        "asset_updates": [],
        "alerts": [],
    },

    # Step 3 — T+9h: Naraj crosses danger. Bridge at Jenapur submerged.
    {
        "label": "T+9h: Naraj at danger. Jenapur bridge submerged.",
        "flood_reports": [
            {
                "_source_type": "CWC_GAUGE",
                "location": "POINT(85.79 20.47)",
                "severity": 4,
                "water_level_m": 25.9,
                "water_level_trend": "RISING",
                "confidence": 0.95,
                "description": "Naraj gauge at 25.9m — ABOVE DANGER LEVEL (25.5m). Rising 0.3m/hr.",
                "raw_payload": {"station_code": "NARAJ", "synthetic": True, "scenario_step": 3},
            },
        ] + [
            {
                "_source_type": "SOCIAL_MEDIA",
                "location": f"POINT({86.14 + dlng:.4f} {20.93 + dlat:.4f})",
                "severity": 4,
                "confidence": 0.50,
                "description": "Jenapur bridge submerged. Vehicles stuck. NH-53 blocked.",
                "raw_payload": {"synthetic": True, "scenario_step": 3, "has_image": True, "report_index": i},
            }
            for i, (dlng, dlat) in enumerate(_JENAPUR_OFFSETS)
        ],
        "asset_updates": [],
        "alerts": [
            {
                "type": "BRIDGE_SUBMERGED",
                "severity": 4,
                "location": "POINT(86.14 20.93)",
                "title": "Jenapur Bridge submerged — NH-53 blocked",
                "description": "3 independent reports confirm Jenapur bridge on NH-53 is submerged. Supply convoys must reroute via an alternate road — check current route status layer.",
                "recommended_action": "Reroute convoys — consult route status layer for open alternates north of Jenapur.",
            }
        ],
    },

    # Step 4 — T+12h: Forecast divergence. Boats deployed to Kendrapara
    #           but rain concentrated over Jagatsinghpur.
    {
        "label": "T+12h: Forecast divergence — wrong district.",
        "flood_reports": [
            {
                "_source_type": "SOCIAL_MEDIA",
                "location": "POINT(86.17 20.27)",
                "severity": 4,
                "confidence": 0.55,
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
                "description": "Open-Meteo forecast predicted 80mm/hr over Kendrapara. Actual heavy rainfall fell over Jagatsinghpur. Boats currently in Kendrapara report no activity there.",
                "recommended_action": "Redeploy available boats from Kendrapara to Jagatsinghpur — check asset panel for nearest available units and current travel routes.",
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
                "description": "Ganjam district has had zero situation reports for 4 hours. District collector unreachable. Possible communication infrastructure failure.",
                "recommended_action": "Contact Ganjam DC via alternate channel. Consider dispatching liaison team.",
            }
        ],
    },

    # Step 6 — T+18h: Satellite imagery arrives (12 hours old).
    {
        "label": "T+18h: Stale satellite imagery received.",
        "flood_reports": [
            {
                "_source_type": "SATELLITE",
                "location": "POINT(85.88 20.46)",
                "severity": 3,
                "confidence": 0.70,
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
                "description": "Flood projection model shows water reaching Erasama School Camp within 3 hours. Evacuees currently sheltering there require immediate re-evacuation to higher ground.",
                "recommended_action": "Move all persons from Erasama camp to nearest higher-elevation camp — check camp status panel for capacity and dispatch buses and boats as available.",
                "affected_population": 340,
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
