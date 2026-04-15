# SahayakMap — Tool Calling Architecture

## Programmatic Tool Calling with Llama 3.2:1B via Ollama

This document provides the complete architecture for adding programmatic tool
calling to SahayakMap, allowing the LLM to autonomously query data sources,
run analysis, and compose situation briefs by calling your Python functions.

---

## PART 1: What is Tool Calling and Why It Matters for SahayakMap

### Without Tool Calling (Previous Architecture)

```
User asks: "What's the situation in Jagatsinghpur?"
    │
    ▼
Python code fetches ALL data from ALL sources
    │
    ▼
Python code runs ALL analysis
    │
    ▼
Compressed result → LLM → Natural language response
```

The problem: Python code runs everything upfront. The LLM is just a text formatter.
It cannot decide "I need more data about this district" or "let me check the routes."

### With Tool Calling (New Architecture)

```
User asks: "What's the situation in Jagatsinghpur?"
    │
    ▼
LLM receives the question + list of available tools
    │
    ▼
LLM decides: "I need to call get_district_status(district='Jagatsinghpur')"
    │
    ▼
System executes the function, returns result to LLM
    │
    ▼
LLM decides: "Water is rising. Let me call get_nearby_assets(lat=20.27, lng=86.17)"
    │
    ▼
System executes, returns result
    │
    ▼
LLM decides: "No boats nearby. Let me call get_route_status(from='Kendrapara', to='Jagatsinghpur')"
    │
    ▼
System executes, returns result
    │
    ▼
LLM composes final answer using ALL gathered data
```

The LLM becomes an **agent** that decides what information it needs and fetches
it step by step. This is more flexible, more impressive for the capstone demo,
and closer to how a real intelligence system would work.

---

## PART 2: How Tool Calling Works in Ollama

### The Basic Flow

```
┌──────────┐     1. User message + tool definitions      ┌──────────┐
│          │ ──────────────────────────────────────────▶  │          │
│  Your    │     2. LLM responds with tool_calls          │  Ollama  │
│  Python  │ ◀──────────────────────────────────────────  │  (Llama  │
│  Code    │     3. Execute tools, send results back      │  3.2:1B) │
│          │ ──────────────────────────────────────────▶  │          │
│          │     4. LLM generates final response          │          │
│          │ ◀──────────────────────────────────────────  │          │
└──────────┘                                              └──────────┘
```

### Ollama Tool Calling API Format

```python
import httpx

# Step 1: Send message with tool definitions
response = await httpx.post("http://localhost:11434/api/chat", json={
    "model": "llama3.2:1b",
    "stream": False,
    "messages": [
        {"role": "user", "content": "What's the flood status in Jagatsinghpur?"}
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_district_status",
                "description": "Get current flood status for a district in Odisha",
                "parameters": {
                    "type": "object",
                    "required": ["district_name"],
                    "properties": {
                        "district_name": {
                            "type": "string",
                            "description": "Name of the district, e.g. Jagatsinghpur, Kendrapara, Puri"
                        }
                    }
                }
            }
        }
    ]
})

data = response.json()

# Step 2: LLM responds with tool_calls (not text)
# data["message"] looks like:
# {
#     "role": "assistant",
#     "content": "",
#     "tool_calls": [
#         {
#             "function": {
#                 "name": "get_district_status",
#                 "arguments": {"district_name": "Jagatsinghpur"}
#             }
#         }
#     ]
# }

# Step 3: Execute the tool and send result back
tool_result = get_district_status("Jagatsinghpur")

response2 = await httpx.post("http://localhost:11434/api/chat", json={
    "model": "llama3.2:1b",
    "stream": False,
    "messages": [
        {"role": "user", "content": "What's the flood status in Jagatsinghpur?"},
        data["message"],  # assistant message with tool_calls
        {"role": "tool", "tool_name": "get_district_status", "content": str(tool_result)}
    ]
})

# Step 4: LLM generates final response using the tool result
final = response2.json()
print(final["message"]["content"])
# "Jagatsinghpur is currently experiencing severe flooding with water levels
#  at 27.1m (danger level: 25.5m). 23 ground reports confirm flooding across
#  3 blocks. No rescue boats are currently deployed in the district."
```

---

## PART 3: SahayakMap Tool Definitions

### The 8 Tools

These are the functions the LLM can call. Each is a thin wrapper around a
database query or computation. Keep descriptions SHORT and crystal clear —
a 1B model needs simplicity.

```python
# backend/tools/definitions.py

SAHAYAKMAP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_gauge_readings",
            "description": "Get current water level readings from river gauge stations. Returns station name, water level, danger level, and trend.",
            "parameters": {
                "type": "object",
                "properties": {
                    "river_name": {
                        "type": "string",
                        "description": "River name to filter by. Options: Mahanadi, Brahmani, Baitarani, all"
                    },
                    "status_filter": {
                        "type": "string",
                        "description": "Filter by status. Options: all, danger, warning, normal",
                        "enum": ["all", "danger", "warning", "normal"]
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_district_status",
            "description": "Get flood situation summary for a specific district. Returns flood reports count, severity, population affected, and signal strength.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_name": {
                        "type": "string",
                        "description": "District name in Odisha. Examples: Jagatsinghpur, Kendrapara, Puri, Jajpur, Ganjam, Cuttack, Balasore"
                    }
                },
                "required": ["district_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_nearby_assets",
            "description": "Find rescue assets (boats, helicopters, teams) near a location. Returns asset type, distance, status, and capacity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_name": {
                        "type": "string",
                        "description": "District to search near"
                    },
                    "asset_type": {
                        "type": "string",
                        "description": "Type of asset. Options: all, BOAT, HELICOPTER, RESCUE_TEAM, SUPPLY_TRUCK",
                        "enum": ["all", "BOAT", "HELICOPTER", "RESCUE_TEAM", "SUPPLY_TRUCK"]
                    },
                    "radius_km": {
                        "type": "number",
                        "description": "Search radius in kilometers. Default 50."
                    }
                },
                "required": ["district_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_route_status",
            "description": "Check if roads and bridges between two locations are passable. Returns route segments with status (OPEN, BLOCKED, SUBMERGED).",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_district": {
                        "type": "string",
                        "description": "Starting district"
                    },
                    "to_district": {
                        "type": "string",
                        "description": "Destination district"
                    }
                },
                "required": ["from_district", "to_district"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get rainfall forecast for next 24 hours for a district. Returns hourly rainfall in mm, wind speed, and alert level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_name": {
                        "type": "string",
                        "description": "District name"
                    },
                    "hours_ahead": {
                        "type": "integer",
                        "description": "Forecast horizon in hours. Default 24, max 72."
                    }
                },
                "required": ["district_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_relief_camps",
            "description": "Get status of relief camps. Returns camp name, location, capacity, current population, and flood risk level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_name": {
                        "type": "string",
                        "description": "Filter by district. Use 'all' for all districts."
                    },
                    "at_risk_only": {
                        "type": "boolean",
                        "description": "If true, only return camps that are at risk of flooding. Default false."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_alerts",
            "description": "Get current active alerts sorted by severity. Returns alert type, location, severity (1-5), and description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_severity": {
                        "type": "integer",
                        "description": "Minimum severity to return. 1=info, 3=warning, 5=emergency. Default 1."
                    },
                    "district_name": {
                        "type": "string",
                        "description": "Filter by district. Omit for all districts."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_flood_projection",
            "description": "Get projected flood levels for the next 6 hours based on upstream gauge data and rainfall forecast. Returns projected water levels and at-risk areas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "district_name": {
                        "type": "string",
                        "description": "District to project for. Use 'all' for basin-wide projection."
                    }
                },
                "required": []
            }
        }
    }
]
```

---

## PART 4: Tool Implementations

Each tool is a Python function that queries Supabase and returns a compact string.
**Important:** Return strings, not dicts. The LLM handles strings better.
Keep returns SHORT — the 1B model's context window is limited.

```python
# backend/tools/implementations.py

from database import get_supabase
from datetime import datetime, timedelta

db = get_supabase()


async def get_gauge_readings(river_name: str = "all", status_filter: str = "all") -> str:
    """Fetch gauge readings from Supabase."""
    query = db.table("gauge_stations").select(
        "name, river_name, water_level_m, danger_level_m, warning_level_m, trend, last_updated_at"
    )

    if river_name != "all":
        query = query.eq("river_name", river_name)

    result = query.execute()
    stations = result.data

    # Filter by status
    if status_filter == "danger":
        stations = [s for s in stations if s["water_level_m"] >= s["danger_level_m"]]
    elif status_filter == "warning":
        stations = [s for s in stations if s["warning_level_m"] <= s["water_level_m"] < s["danger_level_m"]]
    elif status_filter == "normal":
        stations = [s for s in stations if s["water_level_m"] < s["warning_level_m"]]

    if not stations:
        return f"No gauge stations found matching river={river_name}, status={status_filter}."

    # Format as compact text (saves tokens)
    lines = []
    for s in stations:
        level = s["water_level_m"]
        danger = s["danger_level_m"]
        status = "DANGER" if level >= danger else "WARNING" if level >= s["warning_level_m"] else "NORMAL"
        trend = s.get("trend", "unknown")
        lines.append(f"- {s['name']} ({s['river_name']}): {level}m / danger:{danger}m [{status}] trend:{trend}")

    return f"Gauge readings ({len(stations)} stations):\n" + "\n".join(lines)


async def get_district_status(district_name: str) -> str:
    """Get flood situation for a district."""
    # Get district info
    district = db.table("districts").select("*").ilike("name", f"%{district_name}%").single().execute().data

    if not district:
        return f"District '{district_name}' not found."

    # Get recent flood reports for this district
    six_hours_ago = (datetime.utcnow() - timedelta(hours=6)).isoformat()
    reports = db.table("flood_reports").select("severity, confidence, source_type, reported_at") \
        .eq("district_id", district["id"]) \
        .gte("reported_at", six_hours_ago) \
        .execute().data

    report_count = len(reports)
    avg_severity = sum(r["severity"] for r in reports) / report_count if reports else 0
    source_breakdown = {}
    for r in reports:
        src = r["source_type"]
        source_breakdown[src] = source_breakdown.get(src, 0) + 1

    # Check signal strength (silent district detection)
    last_report = max((r["reported_at"] for r in reports), default=None)
    hours_since_report = None
    if last_report:
        last_dt = datetime.fromisoformat(last_report.replace("Z", "+00:00"))
        hours_since_report = (datetime.utcnow().replace(tzinfo=last_dt.tzinfo) - last_dt).total_seconds() / 3600

    # Get assets in district
    assets = db.table("rescue_assets").select("type, status") \
        .eq("assigned_district_id", district["id"]).execute().data

    available_assets = [a for a in assets if a["status"] == "AVAILABLE"]

    result = f"District: {district['name']}\n"
    result += f"Population: {district.get('population', 'unknown')}\n"
    result += f"Reports (6h): {report_count}, avg severity: {avg_severity:.1f}/5\n"
    result += f"Sources: {source_breakdown}\n"
    result += f"Assets: {len(available_assets)} available of {len(assets)} total\n"

    if hours_since_report is not None:
        result += f"Last report: {hours_since_report:.1f} hours ago\n"
    else:
        result += "Last report: NONE — district may be SILENT\n"

    if hours_since_report and hours_since_report > 4:
        result += "⚠️ WARNING: No reports in 4+ hours. Possible communication failure.\n"

    return result


async def get_nearby_assets(district_name: str, asset_type: str = "all", radius_km: float = 50) -> str:
    """Find rescue assets near a district."""
    # Get district center point
    district = db.table("districts").select("name, center_lat, center_lng") \
        .ilike("name", f"%{district_name}%").single().execute().data

    if not district:
        return f"District '{district_name}' not found."

    lat, lng = district["center_lat"], district["center_lng"]

    # PostGIS query for nearby assets
    query = f"""
        SELECT name, type, status, capacity,
            ST_Distance(
                location::geography,
                ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography
            ) / 1000 AS distance_km
        FROM rescue_assets
        WHERE ST_DWithin(
            location::geography,
            ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography,
            {radius_km * 1000}
        )
    """
    if asset_type != "all":
        query += f" AND type = '{asset_type}'"
    query += " ORDER BY distance_km"

    result = db.rpc("run_query", {"sql": query}).execute()
    assets = result.data

    if not assets:
        return f"No {asset_type} assets found within {radius_km}km of {district_name}."

    lines = []
    for a in assets:
        lines.append(f"- {a['name']} ({a['type']}): {a['distance_km']:.0f}km away, status:{a['status']}, capacity:{a['capacity']}")

    return f"Assets near {district_name} ({len(assets)} found within {radius_km}km):\n" + "\n".join(lines)


async def get_route_status(from_district: str, to_district: str) -> str:
    """Check road status between two districts."""
    # Query route segments between districts
    routes = db.table("route_status").select(
        "routes(name), status, confidence, reported_at"
    ).execute().data

    # Simplified — in production, use PostGIS to find routes geometrically
    lines = []
    blocked = 0
    for r in routes:
        route_name = r.get("routes", {}).get("name", "Unknown route")
        status = r["status"]
        if status in ("BLOCKED", "SUBMERGED"):
            blocked += 1
        lines.append(f"- {route_name}: {status} (confidence: {r['confidence']:.0%})")

    header = f"Routes from {from_district} to {to_district}: {len(routes)} segments checked, {blocked} blocked/submerged\n"

    if blocked > 0:
        header += f"⚠️ WARNING: {blocked} route segments are impassable. Alternative routes may be needed.\n"

    return header + "\n".join(lines[:10])  # Limit to 10 to save tokens


async def get_weather_forecast(district_name: str, hours_ahead: int = 24) -> str:
    """Get rainfall forecast."""
    district = db.table("districts").select("name, center_lat, center_lng") \
        .ilike("name", f"%{district_name}%").single().execute().data

    if not district:
        return f"District '{district_name}' not found."

    forecasts = db.table("weather_forecasts").select("forecast_time, rainfall_mm, wind_speed_kmh") \
        .eq("district_id", district.get("id")) \
        .gte("forecast_time", datetime.utcnow().isoformat()) \
        .order("forecast_time") \
        .limit(hours_ahead) \
        .execute().data

    if not forecasts:
        return f"No forecast data available for {district_name}."

    total_rain = sum(f["rainfall_mm"] for f in forecasts)
    max_rain_hr = max(f["rainfall_mm"] for f in forecasts)
    max_wind = max(f["wind_speed_kmh"] for f in forecasts)

    alert = "NORMAL"
    if max_rain_hr > 60:
        alert = "EXTREME"
    elif max_rain_hr > 30:
        alert = "HEAVY"
    elif max_rain_hr > 15:
        alert = "MODERATE"

    return (
        f"Forecast for {district_name} (next {hours_ahead}h):\n"
        f"Total rainfall: {total_rain:.0f}mm\n"
        f"Peak hourly rainfall: {max_rain_hr:.0f}mm/hr\n"
        f"Max wind speed: {max_wind:.0f} km/h\n"
        f"Alert level: {alert}\n"
    )


async def get_relief_camps(district_name: str = "all", at_risk_only: bool = False) -> str:
    """Get relief camp status."""
    query = db.table("relief_camps").select("name, district_id, max_capacity, current_population, status, elevation_m, flood_risk_hours")

    if district_name != "all":
        district = db.table("districts").select("id").ilike("name", f"%{district_name}%").single().execute().data
        if district:
            query = query.eq("district_id", district["id"])

    if at_risk_only:
        query = query.eq("status", "AT_RISK")

    camps = query.execute().data

    if not camps:
        return "No relief camps found matching the criteria."

    lines = []
    for c in camps:
        occupancy = f"{c['current_population']}/{c['max_capacity']}"
        risk = ""
        if c.get("flood_risk_hours"):
            risk = f" ⚠️ FLOOD RISK in {c['flood_risk_hours']:.0f}h"
        lines.append(f"- {c['name']}: {occupancy} people, status:{c['status']}, elevation:{c['elevation_m']}m{risk}")

    return f"Relief camps ({len(camps)} total):\n" + "\n".join(lines)


async def get_active_alerts(min_severity: int = 1, district_name: str = None) -> str:
    """Get active alerts."""
    query = db.table("alerts").select("type, severity, title, description, district_id") \
        .eq("acknowledged", False) \
        .gte("severity", min_severity) \
        .order("severity", desc=True) \
        .limit(10)

    alerts = query.execute().data

    if not alerts:
        return "No active alerts."

    lines = []
    severity_labels = {1: "INFO", 2: "ADVISORY", 3: "WARNING", 4: "CRITICAL", 5: "EMERGENCY"}
    for a in alerts:
        label = severity_labels.get(a["severity"], "UNKNOWN")
        lines.append(f"- [{label}] {a['title']}: {a['description'][:100]}")

    return f"Active alerts ({len(alerts)}):\n" + "\n".join(lines)


async def get_flood_projection(district_name: str = "all") -> str:
    """Get flood projections."""
    # This calls the Python-based projection engine from the Local LLM masterplan
    from intelligence.projection import project_flood_progression, assess_camp_risk

    gauges = await get_all_gauges()  # internal helper
    projections = project_flood_progression(gauges, hours_ahead=6)

    if not projections:
        return "No significant flood progression projected in the next 6 hours."

    lines = []
    for p in projections:
        lines.append(
            f"- {p['station']}: current {p['current_level']:.1f}m → projected {p['projected_level_m']:.1f}m "
            f"in {p['eta_hours']:.0f}h [{p['projected_status']}] (confidence: {p['confidence']:.0%})"
        )

    return f"Flood projections (next 6h):\n" + "\n".join(lines)


# ============================================
# TOOL REGISTRY — maps names to functions
# ============================================

TOOL_REGISTRY = {
    "get_gauge_readings": get_gauge_readings,
    "get_district_status": get_district_status,
    "get_nearby_assets": get_nearby_assets,
    "get_route_status": get_route_status,
    "get_weather_forecast": get_weather_forecast,
    "get_relief_camps": get_relief_camps,
    "get_active_alerts": get_active_alerts,
    "get_flood_projection": get_flood_projection,
}
```

---

## PART 5: The Agent Loop

This is the core engine. It sends the user's question to the LLM with the
tool definitions, executes any tool calls, feeds results back, and loops
until the LLM produces a final text response (no more tool calls).

```python
# backend/agent/loop.py

import httpx
import json
import logging
from tools.definitions import SAHAYAKMAP_TOOLS
from tools.implementations import TOOL_REGISTRY

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "llama3.2:1b"
MAX_TOOL_ROUNDS = 4       # prevent infinite loops
MAX_TOOLS_PER_ROUND = 3   # limit parallel calls for 1B model


SYSTEM_PROMPT = """You are SahayakMap, a flood intelligence assistant for NDRF rescue operations in Odisha, India.

You help commanders understand the current flood situation by calling tools to fetch real-time data.

Rules:
- Call tools to get data BEFORE answering. Never guess or make up data.
- Be specific: use district names, water levels in meters, asset counts.
- If a district has no recent reports, flag it as potentially silent.
- Keep responses concise. The commander is busy.
- After gathering enough data, give a clear situation summary and recommended action.
"""


async def run_agent(user_message: str) -> dict:
    """
    Run the agentic tool-calling loop.

    Returns:
        {
            "response": str,           # Final LLM response text
            "tool_calls_made": list,    # Log of all tool calls
            "rounds": int,             # Number of agent rounds
            "error": str | None        # Error if any
        }
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]

    tool_calls_log = []

    for round_num in range(MAX_TOOL_ROUNDS):
        logger.info(f"Agent round {round_num + 1}")

        # Call Ollama with tools
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(OLLAMA_URL, json={
                    "model": MODEL,
                    "messages": messages,
                    "tools": SAHAYAKMAP_TOOLS,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,    # low temp for reliable tool selection
                        "num_predict": 512,    # enough for tool calls + short responses
                        "num_ctx": 4096,       # use full context window
                    }
                })
                result = resp.json()
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return {
                "response": f"LLM service unavailable. Error: {str(e)}",
                "tool_calls_made": tool_calls_log,
                "rounds": round_num + 1,
                "error": str(e)
            }

        assistant_message = result.get("message", {})
        tool_calls = assistant_message.get("tool_calls", [])

        # If no tool calls, the LLM has produced its final response
        if not tool_calls:
            final_text = assistant_message.get("content", "No response generated.")
            logger.info(f"Agent finished after {round_num + 1} rounds")
            return {
                "response": final_text,
                "tool_calls_made": tool_calls_log,
                "rounds": round_num + 1,
                "error": None
            }

        # Execute tool calls
        # Add assistant message (with tool_calls) to conversation
        messages.append(assistant_message)

        # Limit parallel calls for 1B model reliability
        calls_to_execute = tool_calls[:MAX_TOOLS_PER_ROUND]

        for call in calls_to_execute:
            func_name = call["function"]["name"]
            func_args = call["function"].get("arguments", {})

            logger.info(f"Executing tool: {func_name}({func_args})")

            # Look up and execute the function
            func = TOOL_REGISTRY.get(func_name)
            if func is None:
                tool_result = f"Error: Unknown tool '{func_name}'"
                logger.warning(f"Unknown tool called: {func_name}")
            else:
                try:
                    tool_result = await func(**func_args)
                except TypeError as e:
                    # Handle wrong arguments (common with 1B models)
                    logger.warning(f"Tool {func_name} argument error: {e}")
                    try:
                        # Retry with no arguments (use defaults)
                        tool_result = await func()
                    except Exception:
                        tool_result = f"Error calling {func_name}: {str(e)}"
                except Exception as e:
                    tool_result = f"Error: {str(e)}"
                    logger.error(f"Tool {func_name} execution error: {e}")

            # Log the call
            tool_calls_log.append({
                "round": round_num + 1,
                "function": func_name,
                "arguments": func_args,
                "result_preview": tool_result[:200] if isinstance(tool_result, str) else str(tool_result)[:200]
            })

            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_name": func_name,
                "content": str(tool_result)
            })

    # Max rounds reached
    logger.warning("Agent hit max rounds limit")
    return {
        "response": "Analysis incomplete — maximum tool calls reached. Partial data was gathered.",
        "tool_calls_made": tool_calls_log,
        "rounds": MAX_TOOL_ROUNDS,
        "error": "max_rounds_reached"
    }
```

---

## PART 6: Handling 1B Model Limitations in Tool Calling

### Problem 1: Model Calls Wrong Tool or Wrong Arguments

The 1B model sometimes picks the wrong tool or passes malformed arguments.

**Solution: Argument Sanitization Layer**

```python
# backend/agent/sanitize.py

def sanitize_tool_call(func_name: str, arguments: dict) -> tuple[str, dict]:
    """Fix common mistakes the 1B model makes with tool calls."""

    # Fix 1: Normalize district names (model might use wrong casing or spelling)
    DISTRICT_ALIASES = {
        "jagatsinghpur": "Jagatsinghpur",
        "jagatsingpur": "Jagatsinghpur",  # common typo
        "kendrapada": "Kendrapara",
        "kendrapara": "Kendrapara",
        "puri": "Puri",
        "jajpur": "Jajpur",
        "ganjam": "Ganjam",
        "cuttack": "Cuttack",
        "balasore": "Balasore",
        "bhubaneswar": "Khordha",  # model might use city instead of district
    }

    for key in ["district_name", "from_district", "to_district"]:
        if key in arguments and isinstance(arguments[key], str):
            normalized = arguments[key].strip().lower()
            if normalized in DISTRICT_ALIASES:
                arguments[key] = DISTRICT_ALIASES[normalized]

    # Fix 2: Ensure numeric types
    for key in ["radius_km", "hours_ahead", "min_severity"]:
        if key in arguments:
            try:
                if key == "min_severity":
                    arguments[key] = int(arguments[key])
                else:
                    arguments[key] = float(arguments[key])
            except (ValueError, TypeError):
                del arguments[key]  # remove bad value, let default apply

    # Fix 3: Ensure boolean types
    if "at_risk_only" in arguments:
        val = arguments["at_risk_only"]
        if isinstance(val, str):
            arguments["at_risk_only"] = val.lower() in ("true", "yes", "1")

    # Fix 4: Model sometimes calls a tool that doesn't exist
    # Map common hallucinated tool names to real ones
    TOOL_ALIASES = {
        "check_flood_status": "get_district_status",
        "flood_status": "get_district_status",
        "check_weather": "get_weather_forecast",
        "find_boats": "get_nearby_assets",
        "get_boats": "get_nearby_assets",
        "check_routes": "get_route_status",
        "road_status": "get_route_status",
    }
    if func_name in TOOL_ALIASES:
        func_name = TOOL_ALIASES[func_name]

    return func_name, arguments
```

### Problem 2: Model Doesn't Call Any Tools

Sometimes the 1B model ignores the tools and tries to answer directly
(usually with hallucinated data).

**Solution: Force a Tool Call on Specific Query Types**

```python
# backend/agent/routing.py

import re

def should_force_tool_call(user_message: str) -> str | None:
    """
    If the user's question clearly maps to a specific tool,
    return the tool call to make — bypassing the LLM's decision.
    This is the safety net for when the 1B model doesn't use tools.
    """
    msg = user_message.lower()

    # District-specific questions → force get_district_status
    for district in ["jagatsinghpur", "kendrapara", "puri", "jajpur", "ganjam",
                     "cuttack", "balasore", "khordha", "bhadrak"]:
        if district in msg:
            if any(w in msg for w in ["status", "situation", "flooding", "how is", "what about"]):
                return f"get_district_status:{district.title()}"

    # Gauge questions → force get_gauge_readings
    if any(w in msg for w in ["gauge", "water level", "river level", "mahanadi", "brahmani"]):
        return "get_gauge_readings:all:all"

    # Alert questions → force get_active_alerts
    if any(w in msg for w in ["alert", "warning", "emergency", "critical"]):
        return "get_active_alerts:3"

    # Asset questions → force get_nearby_assets
    if any(w in msg for w in ["boat", "helicopter", "rescue team", "assets", "deployment"]):
        return "get_nearby_assets:all"

    return None  # Let the LLM decide


async def run_agent_with_fallback(user_message: str) -> dict:
    """Run agent with forced tool call fallback."""

    # First, try the normal agent loop
    result = await run_agent(user_message)

    # If the LLM didn't call any tools (round 1, no tool calls)
    # and the question clearly needs data, force a tool call
    if result["rounds"] == 1 and len(result["tool_calls_made"]) == 0:
        forced = should_force_tool_call(user_message)
        if forced:
            parts = forced.split(":")
            func_name = parts[0]
            func_args = {}

            # Map the forced call to arguments
            if func_name == "get_district_status":
                func_args = {"district_name": parts[1]}
            elif func_name == "get_gauge_readings":
                func_args = {"river_name": parts[1], "status_filter": parts[2]}
            elif func_name == "get_active_alerts":
                func_args = {"min_severity": int(parts[1])}

            # Execute the tool directly
            func = TOOL_REGISTRY[func_name]
            tool_data = await func(**func_args)

            # Now ask LLM to narrate the result
            from llm.client import narrate
            narration = await narrate(tool_data)

            return {
                "response": narration,
                "tool_calls_made": [{"round": 0, "function": func_name,
                                     "arguments": func_args, "result_preview": tool_data[:200],
                                     "forced": True}],
                "rounds": 1,
                "error": None
            }

    return result
```

### Problem 3: Model Gets Stuck in Tool-Calling Loop

The 1B model sometimes keeps calling tools without ever producing a final answer.

**Solution: Already handled by `MAX_TOOL_ROUNDS = 4` in the agent loop.
Additionally, add a "stop and summarize" injection:**

```python
# In the agent loop, after round 3, inject a nudge message
if round_num == MAX_TOOL_ROUNDS - 1:
    messages.append({
        "role": "user",
        "content": "You have gathered enough data. Now provide your final situation summary and recommended action. Do not call any more tools."
    })
```

### Problem 4: Context Window Overflow

After 3-4 tool calls, the conversation history might exceed the 4096 token context.

**Solution: Compress Earlier Tool Results**

```python
# backend/agent/context.py

def compress_messages(messages: list, max_tokens_estimate: int = 3000) -> list:
    """
    Compress message history to fit within context window.
    Keep: system prompt, user query, latest 2 tool results.
    Summarize: older tool results.
    """
    # Rough token estimate: 1 token ≈ 4 characters
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    estimated_tokens = total_chars // 4

    if estimated_tokens < max_tokens_estimate:
        return messages  # fits fine

    # Keep system + user + latest messages, compress middle
    compressed = []
    compressed.append(messages[0])  # system prompt
    compressed.append(messages[1])  # user query

    # Compress old tool results into a single summary
    tool_results = [m for m in messages[2:-4] if m.get("role") == "tool"]
    if tool_results:
        summary_parts = []
        for tr in tool_results:
            # Keep only first 100 chars of each old result
            content = str(tr.get("content", ""))[:100]
            summary_parts.append(f"[{tr.get('tool_name', 'tool')}]: {content}...")

        compressed.append({
            "role": "user",
            "content": "Previous tool results (summarized): " + " | ".join(summary_parts)
        })

    # Keep the last 4 messages intact (latest tool call cycle)
    compressed.extend(messages[-4:])

    return compressed
```

---

## PART 7: FastAPI Integration

### API Endpoint for Agent Queries

```python
# backend/api/agent.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.loop import run_agent_with_fallback

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentQuery(BaseModel):
    message: str
    context: dict | None = None  # optional: pre-loaded context like current district


class AgentResponse(BaseModel):
    response: str
    tool_calls: list
    rounds: int
    error: str | None


@router.post("/query", response_model=AgentResponse)
async def query_agent(query: AgentQuery):
    """
    Send a natural language query to the SahayakMap agent.

    Examples:
    - "What's the situation in Jagatsinghpur?"
    - "Are there any boats available near Kendrapara?"
    - "Is the route from Cuttack to Balasore passable?"
    - "Give me a full situation brief"
    - "Which districts need immediate attention?"
    """
    try:
        result = await run_agent_with_fallback(query.message)
        return AgentResponse(
            response=result["response"],
            tool_calls=result["tool_calls_made"],
            rounds=result["rounds"],
            error=result.get("error")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Pre-built queries for the commander's quick actions
@router.get("/brief")
async def get_situation_brief():
    """Generate a full situation brief using the agent."""
    result = await run_agent_with_fallback(
        "Give me a complete situation brief. Check all gauge stations for danger levels, "
        "find any districts with critical flooding, check if any relief camps are at risk, "
        "and tell me where to deploy rescue assets."
    )
    return result


@router.get("/district/{district_name}")
async def get_district_brief(district_name: str):
    """Get agent-generated brief for a specific district."""
    result = await run_agent_with_fallback(
        f"What's the complete flood situation in {district_name}? "
        f"Check water levels, ground reports, available rescue assets, "
        f"route status, and weather forecast."
    )
    return result
```

---

## PART 8: Frontend Integration — Agent Chat Panel

### React Component for Commander Interaction

```jsx
// frontend/src/components/Panel/AgentChat.jsx

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Bot, User, Wrench } from 'lucide-react';

const QUICK_QUERIES = [
  { label: "Full Brief", query: "Give me a complete situation brief" },
  { label: "Critical Alerts", query: "What are the most critical alerts right now?" },
  { label: "Asset Gaps", query: "Which districts have flooding but no rescue assets?" },
  { label: "Route Check", query: "Are the supply routes from Cuttack to Balasore passable?" },
];

export default function AgentChat({ selectedDistrict }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const sendQuery = async (queryText) => {
    const userMsg = queryText || input;
    if (!userMsg.trim()) return;

    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/agent/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });

      const data = await response.json();

      // Add tool call indicators
      if (data.tool_calls?.length > 0) {
        const toolNames = data.tool_calls.map(t => t.function).join(', ');
        setMessages(prev => [...prev, {
          role: 'tools',
          content: `Queried: ${toolNames} (${data.rounds} rounds)`
        }]);
      }

      // Add agent response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response
      }]);

    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: 'Failed to reach the intelligence engine. Check if the backend is running.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg">
      {/* Header */}
      <div className="p-3 border-b border-gray-700">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Bot className="w-4 h-4 text-blue-400" />
          Intelligence Agent
        </h3>
        <p className="text-gray-400 text-xs mt-1">Ask about any district, route, or asset</p>
      </div>

      {/* Quick Queries */}
      <div className="flex gap-2 p-2 overflow-x-auto border-b border-gray-800">
        {QUICK_QUERIES.map((q, i) => (
          <button
            key={i}
            onClick={() => sendQuery(q.query)}
            disabled={loading}
            className="whitespace-nowrap px-3 py-1 text-xs rounded-full
                       bg-blue-900/50 text-blue-300 hover:bg-blue-800/50
                       disabled:opacity-50 transition-colors"
          >
            {q.label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-gray-500 text-sm text-center mt-8">
            Ask about the flood situation or tap a quick query above
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && <Bot className="w-5 h-5 text-blue-400 mt-1 flex-shrink-0" />}
            {msg.role === 'tools' && <Wrench className="w-4 h-4 text-gray-500 mt-1 flex-shrink-0" />}

            <div className={`rounded-lg px-3 py-2 max-w-[85%] text-sm ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : msg.role === 'tools'
                  ? 'bg-gray-800 text-gray-400 text-xs italic'
                  : msg.role === 'error'
                    ? 'bg-red-900/50 text-red-300'
                    : 'bg-gray-800 text-gray-200'
            }`}>
              {msg.content}
            </div>

            {msg.role === 'user' && <User className="w-5 h-5 text-gray-400 mt-1 flex-shrink-0" />}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            Querying intelligence engine...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-2 border-t border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendQuery()}
            placeholder="Ask about any district, route, or situation..."
            disabled={loading}
            className="flex-1 bg-gray-800 text-white text-sm rounded-lg px-3 py-2
                       placeholder-gray-500 border border-gray-700 focus:border-blue-500
                       focus:outline-none disabled:opacity-50"
          />
          <button
            onClick={() => sendQuery()}
            disabled={loading || !input.trim()}
            className="p-2 bg-blue-600 rounded-lg hover:bg-blue-500
                       disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## PART 9: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      FRONTEND (React)                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Flood Map   │  │  Agent Chat      │  │  Alert Panel     │  │
│  │  (Leaflet)   │  │  Panel           │  │                  │  │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬─────────┘  │
│         │                   │                      │            │
│         └───────────────────┼──────────────────────┘            │
│                             │ POST /api/agent/query             │
└─────────────────────────────┼───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    AGENT LOOP                              │ │
│  │                                                            │ │
│  │  User Query ──▶ Ollama (Llama 3.2:1B)                     │ │
│  │                     │                                      │ │
│  │                     ▼                                      │ │
│  │              ┌─── tool_calls? ───┐                         │ │
│  │              │ YES               │ NO                      │ │
│  │              ▼                   ▼                         │ │
│  │     ┌────────────────┐   Final response                   │ │
│  │     │ SANITIZE args  │      returned                      │ │
│  │     └───────┬────────┘                                    │ │
│  │             ▼                                              │ │
│  │     ┌────────────────┐                                    │ │
│  │     │ EXECUTE tool   │                                    │ │
│  │     └───────┬────────┘                                    │ │
│  │             ▼                                              │ │
│  │     Feed result back to LLM ──▶ loop (max 4 rounds)      │ │
│  │                                                            │ │
│  │  FALLBACKS:                                                │ │
│  │  • Forced tool call if LLM ignores tools                  │ │
│  │  • Context compression if window fills up                 │ │
│  │  • Template response if LLM fails entirely                │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  TOOL FUNCTIONS                             │ │
│  │                                                            │ │
│  │  get_gauge_readings()  ──┐                                 │ │
│  │  get_district_status()  ─┤                                 │ │
│  │  get_nearby_assets()   ──┤      ┌───────────────────┐     │ │
│  │  get_route_status()    ──┼─────▶│    SUPABASE       │     │ │
│  │  get_weather_forecast() ─┤      │    (PostGIS)      │     │ │
│  │  get_relief_camps()    ──┤      └───────────────────┘     │ │
│  │  get_active_alerts()   ──┤                                 │ │
│  │  get_flood_projection() ─┘──▶ Python computation           │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                 DATA INGESTION (APScheduler)               │ │
│  │  CWC Gauges (15min) │ Open-Meteo (30min) │ Synthetic (5m) │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              OLLAMA (localhost:11434)                       │ │
│  │              Model: llama3.2:1b                             │ │
│  │              Fallback: Groq API (cloud)                    │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## PART 10: Complete Example — Agent in Action

### Query: "What's the situation in Jagatsinghpur?"

```
ROUND 1:
  User: "What's the situation in Jagatsinghpur?"
  LLM thinks → calls: get_district_status(district_name="Jagatsinghpur")
  Tool returns: "District: Jagatsinghpur\nPopulation: 1,136,971\n
                 Reports (6h): 34, avg severity: 3.8/5\n
                 Sources: {SOCIAL_MEDIA: 28, CWC_GAUGE: 4, DISTRICT_REPORT: 2}\n
                 Assets: 0 available of 0 total\n
                 Last report: 0.3 hours ago"

ROUND 2:
  LLM sees: high severity, ZERO assets → calls: get_nearby_assets(district_name="Jagatsinghpur", asset_type="BOAT")
  Tool returns: "Assets near Jagatsinghpur (2 found within 50km):
                 - Boat-K1 (BOAT): 42km away, status:AVAILABLE, capacity:12
                 - Boat-K2 (BOAT): 45km away, status:AVAILABLE, capacity:12"

ROUND 3:
  LLM sees: boats in Kendrapara → calls: get_route_status(from_district="Kendrapara", to_district="Jagatsinghpur")
  Tool returns: "Routes from Kendrapara to Jagatsinghpur: 3 segments checked, 1 blocked
                 - NH-5A: OPEN (confidence: 80%)
                 - SH-12 Bridge: SUBMERGED (confidence: 90%)
                 - Devi River Route: OPEN (confidence: 70%)
                 ⚠️ WARNING: 1 route segment is impassable."

ROUND 4 (final — no more tool calls):
  LLM response: "CRITICAL — Jagatsinghpur has severe flooding with 34 reports in the
  last 6 hours (average severity 3.8/5). The district has ZERO rescue boats deployed
  despite a population of over 1.1 million.

  Two boats are available in Kendrapara (42-45km away). The SH-12 bridge is submerged,
  but the Devi River route remains open (70% confidence).

  RECOMMENDED: Immediately redeploy Boat-K1 and Boat-K2 from Kendrapara to
  Jagatsinghpur via the Devi River route. Estimated transit time: 2-3 hours.
  Avoid SH-12 — bridge confirmed submerged."
```

This is the agent autonomously deciding it needs 3 pieces of information,
fetching them in sequence, and synthesizing a coherent response.

---

## PART 11: Groq Cloud Fallback for Tool Calling

Groq also supports tool calling with Llama models. For deployment:

```python
# backend/agent/groq_agent.py

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

async def call_groq_with_tools(messages: list, tools: list) -> dict:
    """Groq uses OpenAI-compatible format for tool calling."""

    # Convert Ollama tool format to OpenAI format (they're nearly identical)
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.2-1b-preview",  # Groq's Llama 3.2 1B
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.1,
        "max_tokens": 512,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(GROQ_URL, json=payload, headers=headers)
        data = resp.json()

    message = data["choices"][0]["message"]

    # Normalize to Ollama format for the agent loop
    return {
        "message": {
            "role": "assistant",
            "content": message.get("content", ""),
            "tool_calls": [
                {
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"])
                                     if isinstance(tc["function"]["arguments"], str)
                                     else tc["function"]["arguments"]
                    }
                }
                for tc in (message.get("tool_calls") or [])
            ] if message.get("tool_calls") else None
        }
    }
```

---

## PART 12: Testing the Tool Calling Setup

### Quick Test Script

```python
# test_agent.py — run this to verify tool calling works

import asyncio
from agent.loop import run_agent_with_fallback

async def main():
    test_queries = [
        "What's the current water level at Naraj?",
        "Are there any boats available near Jagatsinghpur?",
        "Is the route from Cuttack to Balasore passable?",
        "Which districts have the most critical flooding right now?",
        "Give me a full situation brief for the Mahanadi basin.",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print(f"{'='*60}")

        result = await run_agent_with_fallback(query)

        print(f"\nRounds: {result['rounds']}")
        print(f"Tool calls: {len(result['tool_calls_made'])}")
        for tc in result['tool_calls_made']:
            print(f"  → {tc['function']}({tc['arguments']})")
        print(f"\nResponse:\n{result['response']}")
        print(f"\nError: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Expected Behavior Matrix

| Query | Expected Tools Called | Rounds |
|-------|---------------------|--------|
| "Water level at Naraj?" | `get_gauge_readings` | 2 |
| "Situation in Jagatsinghpur?" | `get_district_status` → `get_nearby_assets` | 2-3 |
| "Full situation brief" | `get_gauge_readings` → `get_active_alerts` → `get_nearby_assets` | 3-4 |
| "Route from Cuttack to Balasore?" | `get_route_status` | 2 |
| "Which camps are at risk?" | `get_relief_camps(at_risk_only=true)` | 2 |

### When 1B Model Struggles (and What to Expect)

| Scenario | Likely 1B Behavior | Fallback Kicks In |
|----------|-------------------|-------------------|
| Complex multi-district query | Calls only 1-2 tools, misses some | Forced tool call fills gaps |
| Ambiguous question | Picks wrong tool or no tool | Keyword routing forces correct tool |
| Long tool result | Ignores parts of result | Context compression keeps relevant parts |
| 4th+ round | Stops calling tools, gives partial answer | Max rounds reached, returns partial |

---

## PART 13: Updated File Structure

Add these files to the project structure from the original masterplan:

```
sahayakmap/
├── backend/
│   ├── agent/                    # NEW — agent loop
│   │   ├── __init__.py
│   │   ├── loop.py              # Core agent loop (Part 5)
│   │   ├── sanitize.py          # Argument sanitization (Part 6)
│   │   ├── routing.py           # Forced tool call routing (Part 6)
│   │   ├── context.py           # Context compression (Part 6)
│   │   └── groq_agent.py        # Groq cloud fallback (Part 11)
│   │
│   ├── tools/                    # NEW — tool definitions & implementations
│   │   ├── __init__.py
│   │   ├── definitions.py       # Tool JSON schemas (Part 3)
│   │   └── implementations.py   # Tool functions (Part 4)
│   │
│   ├── api/
│   │   ├── agent.py             # NEW — agent query endpoints (Part 7)
│   │   └── ... (existing)
│   │
│   └── ... (existing)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Panel/
│   │   │   │   ├── AgentChat.jsx  # NEW — chat interface (Part 8)
│   │   │   │   └── ... (existing)
│   │   └── ... (existing)
│   │
│   └── ... (existing)
│
├── test_agent.py                 # NEW — test script (Part 12)
└── ... (existing)
```

---

## PART 14: Build Timeline Integration

Add tool calling to the existing build plan:

**Week 2 (Apr 23-29) — Add after data sources:**
- Day 5: Implement tool definitions + implementations
- Day 6: Build agent loop + sanitization layer
- Day 7: Test with basic queries, tune prompts

**Week 3 (Apr 30 - May 6) — Core integration:**
- Day 1-2: Agent loop integrated with Supabase queries
- Day 3: Forced tool call fallbacks + context compression
- Day 4-5: AgentChat frontend component
- Day 6-7: End-to-end testing with simulation scenario

**Week 4 (May 7-13) — Polish:**
- Groq fallback for deployment
- Quick query buttons tuned for demo
- Demo walkthrough showing agent reasoning

---

## Summary: Why Tool Calling Makes This Project Better

1. **More impressive for capstone** — The evaluators see the LLM autonomously
   deciding what data to fetch, not a hardcoded pipeline.

2. **More flexible** — New questions work without new code. Add a tool, and the
   LLM can use it immediately.

3. **Shows real understanding** — The LLM demonstrates it knows Jagatsinghpur
   has no boats → fetches nearby boats → checks routes. That reasoning chain
   is visible in the UI.

4. **Graceful degradation** — The fallback chain (LLM tools → forced routing →
   template) means the system ALWAYS produces useful output.

5. **Matches the capstone brief** — The brief asks for a system that "reasons
   about what the data means operationally." Tool calling is that reasoning
   made concrete and auditable.

---

*This document extends MASTERPLAN.md and MASTERPLAN_LOCAL_LLM.md.
All three documents together form the complete technical specification
for SahayakMap.*
