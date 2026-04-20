# Reference — API Spec, Enums, Scoring Tables

Read this file only when you need specifics about endpoints, enums, or scoring values.

## API Endpoints (FastAPI)

```
GET  /api/health                    — System status + data source freshness
GET  /api/map/data                  — Fused map data (gauges, reports, assets, routes)
     ?bbox=lat1,lng1,lat2,lng2&hours=6&min_severity=2

GET  /api/gauges                    — All gauge stations with current readings
GET  /api/gauges/{id}/history       — Water level history for a station (24h)

GET  /api/alerts                    — Active alerts, sorted by severity
     ?min_severity=1&district_id=X&unacknowledged_only=true
     &include_expired=false&limit=50&cursor=<generated_at ISO string>
     Response: {alerts, count, next_cursor}
PUT  /api/alerts/{id}/ack           — Acknowledge an alert
     Body: {acknowledged_by?: string}
     Returns 404 if not found | 409 if already acknowledged or race condition

GET  /api/briefing                  — Latest AI-generated situation brief
POST /api/briefing/generate         — Force-generate a new brief

GET  /api/assets                    — All rescue assets with positions
     ?asset_type=BOAT|HELICOPTER|RESCUE_TEAM|SUPPLY_TRUCK
     &status=AVAILABLE|DEPLOYED|IN_TRANSIT|MAINTENANCE
     &district_id=X
     Response: {assets, count}
PUT  /api/assets/{id}/position      — Update asset position (simulation)
     Body: {lat: float, lng: float}
     Returns 404 if not found
PUT  /api/assets/{id}/status        — Update asset status
     Body: {status: AssetStatus enum}
     Returns 404 if not found

GET  /api/districts                 — District overview (signal strength, report counts)
GET  /api/districts/{id}            — District detail with all associated data

GET  /api/routes/status             — Road/bridge status overview
GET  /api/camps                     — Relief camp status + flood risk

POST /api/scenario/load             — Load a simulation scenario (Cyclone Fani replay)
POST /api/scenario/tick             — Advance simulation by N minutes
```

## Domain Enums

```python
DataSourceType: CWC_GAUGE | IMD_WEATHER | SATELLITE | SOCIAL_MEDIA | DISTRICT_REPORT | OSM_ROAD | ASSET_TRACKER
DataSourceStatus: ACTIVE | DEGRADED | OFFLINE
AssetType: BOAT | HELICOPTER | RESCUE_TEAM | SUPPLY_TRUCK
AssetStatus: AVAILABLE | DEPLOYED | IN_TRANSIT | MAINTENANCE
RouteStatus: OPEN | PARTIALLY_BLOCKED | BLOCKED | SUBMERGED | UNKNOWN
CampStatus: ACTIVE | AT_RISK | EVACUATING | CLOSED
AlertType: FLOOD_RISING | BRIDGE_SUBMERGED | CAMP_AT_RISK | ASSET_MISPLACED | ROUTE_BLOCKED | SILENT_DISTRICT | FORECAST_DIVERGENCE
Severity: 1 (INFO) | 2 (ADVISORY) | 3 (WARNING) | 4 (CRITICAL) | 5 (EMERGENCY)
```

## Confidence Scoring Table

| Source Type | Base Confidence | Notes |
|-------------|----------------|-------|
| CWC Gauge | 0.95 | Calibrated instrument |
| IMD Forecast | 0.75 | Decreases with forecast horizon |
| Satellite Imagery | 0.90 | High spatial accuracy, but stale |
| District Report (official) | 0.80 | Verified but delayed |
| Social Media (single) | 0.30 | Unverified |
| Social Media (3+ corroborating) | 0.65 | Cross-verified |
| Social Media (with photo) | 0.50 | Visual evidence |

Corroboration boost: 2 sources +0.15 | 3+ sources +0.25 | Official + social +0.20

## Freshness Half-Life Table

| Data Type | Half-Life |
|-----------|-----------|
| River gauge reading | 30 min |
| Weather forecast (next 3h) | 1 hour |
| Weather forecast (12-24h) | 3 hours |
| Social media report | 2 hours |
| Satellite image | 6 hours |
| Road/bridge status | 4 hours |
| District report | 3 hours |

Visual encoding: full opacity = fresh | 50% opacity = past half-life | dashed border = past 2× half-life | faded + warning icon = source offline

## Severity Color System (Frontend)

| Severity | Color | Hex |
|----------|-------|-----|
| 1 - Normal | green | `#22c55e` |
| 2 - Advisory | yellow | `#eab308` |
| 3 - Warning | orange | `#f97316` |
| 4 - Critical | red | `#ef4444` |
| 5 - Emergency | dark red pulsing | `#7c2d12` |

## API Coding Patterns (established Apr 17)

### 1. Query Builder Pattern for optional filters
```python
@dataclass
class Filter:
    active: bool
    apply: Callable

def build_query(base_query, filters: list[Filter]):
    for f in filters:
        if f.active:
            base_query = f.apply(base_query)
    return base_query
```

### 2. Repository Pattern for DB logic
All database queries for a table belong in a `XxxRepository` class. Endpoints never
touch Supabase directly — they call repository methods.

### 3. Dependency Injection for validation
`get_<entity>_repository()` factory + `get_valid_<entity>()` validator via `Depends()`.

### 4. Always use Enum types for fixed-value fields
Use `str, Enum` — never plain `str` for fields with fixed values.

### 5. Always use UUID type for path parameters
Convert back to str for Supabase: `.eq("id", str(entity_id))`

### 6. Explicit column lists — never select("*") in list endpoints
Define `LIST_COLUMNS` and `UPDATE_COLUMNS` constants at module level.

### 7. DB migration needed before acknowledged_by works
```sql
ALTER TABLE alerts ADD COLUMN acknowledged_by TEXT;
```
