# SahayakMap Code Audit Report

**Date:** April 21, 2026  
**Scope:** Full codebase (backend, frontend, configuration, ingestion)  
**Status:** 🔴 **CRITICAL ISSUES FOUND** — 3 critical, 8 high-priority, 5 medium issues

---

## Executive Summary

The codebase has several **critical** and **high-priority** issues that should be addressed before production deployment:

1. **Hardcoded localhost URLs** in config — breaks production/deployment
2. **Broad Exception handlers** — masks real errors silently
3. **TODO for real CWC implementation** — synthetic data fallback only
4. **Missing input validation** — potential edge cases
5. **Unvalidated environment variables** — could cause runtime failures
6. **Bare `except Exception:` clauses** — poor error visibility

---

## Critical Issues 🔴

### 1. **Hardcoded CORS Origins for localhost** 
**File:** [backend/config.py](backend/config.py#L43)  
**Severity:** CRITICAL  
**Issue:** CORS is hardcoded to localhost URLs:
```python
cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
```
**Impact:** 
- Will fail in production (CORS errors block frontend)
- Should be configurable via environment variable
- Potential security issue if not properly filtered in production

**Fix:** Add environment variable:
```python
cors_origins: List[str] = Field(
    default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
)
```

---

### 2. **Hardcoded Ollama URL**
**File:** [backend/config.py](backend/config.py#L21)  
**Severity:** CRITICAL  
**Issue:**
```python
ollama_base_url: str = "http://localhost:11434"
```
**Impact:**
- Will fail if Ollama is on different host
- Not configurable for Docker/cloud deployments
- Fallback mechanism won't work if this hardcoded URL is unreachable

**Fix:** Should already be configurable, but default is not environment-aware

---

### 3. **TODO: Real CWC Gauge Data Scraping Not Implemented**
**File:** [backend/ingestion/cwc_gauge.py](backend/ingestion/cwc_gauge.py#L8)  
**Severity:** CRITICAL  
**Issue:**
```python
# TODO: Implement real CWC scraping once the dashboard endpoint is identified.
```
**Impact:**
- System currently uses **synthetic water level data**
- NDRF responders will receive fake sensor readings
- Maps show fabricated flood scenarios
- Product is unusable for real emergency response

**Fix:** Implement real CWC dashboard scraping. Current fallback in [cwc_gauge.py](backend/ingestion/cwc_gauge.py#L25+) calls `_synthetic_level()` which generates fake data.

---

## High-Priority Issues 🟠

### 4. **Bare `except Exception:` Without Logging**
**Files:**
- [backend/api/map_data.py:46](backend/api/map_data.py#L46) — WKB parsing fails silently
- [backend/ingestion/open_meteo.py:66](backend/ingestion/open_meteo.py#L66)
- [backend/ingestion/osm_roads.py:41](backend/ingestion/osm_roads.py#L41)

**Severity:** HIGH  
**Example from map_data.py:**
```python
except Exception:
    pass  # leave record without lat/lng if WKB parse fails; frontend handles gracefully
```

**Impact:**
- Silent failures make debugging hard
- No visibility into which records failed parsing
- Frontend doesn't know the difference between "no location" and "parse error"
- Accumulates corrupted records over time

**Fix:** Log the error:
```python
except Exception as e:
    logger.warning("Failed to parse WKB location for station %s: %s", record.get('id'), e)
```

---

### 5. **Overly Broad `except Exception as exc:`**
**Files:**
- [backend/api/scenarios.py:129, 135, 146](backend/api/scenarios.py#L129)
- [backend/api/districts.py:64, 77, 93, 107, 121](backend/api/districts.py#L64)
- [backend/api/health.py:28, 45](backend/api/health.py#L28)
- [backend/intelligence/briefing.py:309](backend/intelligence/briefing.py#L309)

**Severity:** HIGH  
**Example:**
```python
except Exception as exc:
    errors.append(f"flood_report insert failed: {exc}")
```

**Impact:**
- Catches network errors, type errors, database errors all the same way
- Hard to distinguish recoverable from permanent failures
- Makes retry logic and monitoring difficult

**Fix:** Catch specific exceptions:
```python
except (psycopg2.IntegrityError, psycopg2.OperationalError) as exc:
    # handle database-specific issues
except Exception as exc:
    logger.error("Unexpected error inserting flood report: %s", exc)
    raise
```

---

### 6. **Missing Environment Variable Validation**
**File:** [backend/config.py](backend/config.py)  
**Severity:** HIGH  
**Issue:** Required variables (`supabase_url`, `supabase_anon_key`, `supabase_service_key`) have no defaults. If missing, app crashes at startup with unclear error.

**Fields without defaults:**
```python
supabase_url: str                    # ← Will error if missing
supabase_anon_key: str               # ← Will error if missing
supabase_service_key: str            # ← Will error if missing
```

**Impact:**
- Unclear error message if `.env` is missing a required key
- No graceful degradation

**Fix:** Add `.env.example` validation or improve error messages:
```python
if not settings.supabase_url:
    raise ValueError("SUPABASE_URL is required. Check your .env file.")
```

---

### 7. **Bare `pass` Statements with Only Comment Explanations**
**File:** [backend/api/map_data.py:47](backend/api/map_data.py#L47)  
**Severity:** MEDIUM-HIGH  
**Issue:**
```python
pass  # leave record without lat/lng if WKB parse fails; frontend handles gracefully
```

**Impact:**
- Hard to understand the intent without reading the comment
- Comment doesn't explain *why* it's safe to silently drop location data

**Fix:** Replace with explicit logging and document in README:
```python
except Exception as e:
    logger.debug("Location parsing failed for %s, records will have null lat/lng", record.get('id'))
    # Frontend must handle records without location data
```

---

### 8. **Unhandled `asyncio.gather()` Exception in briefing.py**
**File:** [backend/intelligence/briefing.py:309](backend/intelligence/briefing.py#L309)  
**Severity:** HIGH  
**Issue:**
```python
except Exception as e:
    logger.warning("LLM unavailable and llm_fallback_to_templates is disabled")
```

**Context:** This is inside a 5-parallel-query `asyncio.gather()` call. If *any* DB query fails, the entire analysis dict is incomplete.

**Impact:**
- Silently drops failed queries
- Produces incomplete briefings with missing source data
- User doesn't know if the briefing is based on partial data

**Fix:** Log which specific query failed:
```python
try:
    reports = await _fetch_reports(db, since)
except Exception as e:
    logger.error("Failed to fetch flood_reports: %s", e)
    reports = []  # explicit fallback
```

---

### 9. **Bare `pass` in districts.py**
**File:** [backend/api/districts.py:43](backend/api/districts.py#L43)  
**Severity:** MEDIUM  
**Issue:**
```python
pass  # [no comment explaining why]
```
This appears to be a security guard function that does nothing.

**Impact:**
- Unclear if this is intentional or incomplete
- Code review can't verify correctness

**Fix:** Add documentation:
```python
def _guard_district_access(user: None) -> None:
    """Security guard for district endpoints. Currently no auth required."""
    pass
```

---

## Medium-Priority Issues 🟡

### 10. **WKB Parsing May Lose Location Data Silently**
**File:** [backend/api/map_data.py:46-48](backend/api/map_data.py#L46)  
**Severity:** MEDIUM  
**Issue:**
```python
except Exception:
    pass  # leave record without lat/lng if WKB parse fails; frontend handles gracefully
```

**Questions:**
- How many records are failing?
- Which records?
- Is the frontend actually handling null locations gracefully, or are they just not shown?

**Fix:** Add metrics to monitor:
```python
except Exception as e:
    logger.warning("WKB parse failed: %s", e)
    metrics.increment("map_data.wkb_parse_failures")
```

---

### 11. **No Validation on Scenario Data in scenarios.py**
**File:** [backend/api/scenarios.py:120-150](backend/api/scenarios.py#L120)  
**Severity:** MEDIUM  
**Issue:**
```python
for report in step.get("flood_reports", []):
    row = {k: v for k, v in report.items() if k != "_source_type"}
    row["source_id"] = source_id_map[report["_source_type"]]
```

**Impact:**
- If `_source_type` is missing, will crash with KeyError
- No validation that all required fields exist in row
- No type checking on values

**Fix:** Use dataclass validation:
```python
try:
    row["source_id"] = source_id_map[report["_source_type"]]
except KeyError as e:
    raise HTTPException(400, f"Missing required field: {e}")
```

---

### 12. **CORS in Frontend Vite Config Uses process.env**
**File:** [frontend/vite.config.js:10](frontend/vite.config.js#L10)  
**Severity:** MEDIUM  
**Issue:**
```javascript
target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
```

**Impact:**
- `process.env` doesn't exist in Vite; should be `import.meta.env`
- Will silently fall back to localhost in production
- Frontend will make API calls to `http://localhost:8000` even in cloud deployment

**Fix:** Change to:
```javascript
target: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
```

---

### 13. **No Validation of `bbox` Parameter Format**
**File:** [backend/api/map_data.py:60-70](backend/api/map_data.py#L60)  
**Severity:** MEDIUM  
**Issue:**
```python
parts = [float(x) for x in bbox.split(",")]
if len(parts) != 4:
    raise ValueError
```

**Impact:**
- Error message is generic ("bbox must be...")
- `ValueError` without message is poor UX
- No bounds checking on coordinates (could be -500, 500)

**Fix:** Add validation:
```python
try:
    lat1, lng1, lat2, lng2 = [float(x) for x in bbox.split(",")]
    if not (-90 <= lat1, lat2 <= 90) or not (-180 <= lng1, lng2 <= 180):
        raise ValueError("Coordinates out of bounds")
except (ValueError, TypeError) as e:
    raise HTTPException(status_code=422, detail=f"Invalid bbox: {e}")
```

---

### 14. **Synthetic Data in Production Mode**
**File:** [backend/ingestion/synthetic_reports.py](backend/ingestion/synthetic_reports.py)  
**Severity:** MEDIUM  
**Issue:**
The system is hardcoded to generate fake flood reports when `SIMULATION_MODE=true`. But there's no clear indication in the UI that data is synthetic.

**Impact:**
- NDRF responders might not realize they're looking at demo data
- Could cause false alarms if mixed with real data

**Fix:** 
- Always mark synthetic reports with a `source_type = "SIMULATION"`
- Add banner in frontend when simulation mode is active
- Prevent simulation data from being saved to production

---

## Low-Priority Issues (Non-Breaking) 🟢

### 15. **print() Statements in Seed Scripts**
**Files:**
- [backend/seed/routes_bridges.py:49, 68](backend/seed/routes_bridges.py#L49)
- [backend/seed/rescue_assets.py:57, 59](backend/seed/rescue_assets.py#L57)
- [backend/seed/relief_camps.py:74](backend/seed/relief_camps.py#L74)
- [backend/seed/odisha_districts.py:38, 50](backend/seed/odisha_districts.py#L38)
- [backend/seed/gauge_stations.py:99, 118](backend/seed/gauge_stations.py#L99)
- [backend/seed/data_sources.py:65, 67](backend/seed/data_sources.py#L65)

**Severity:** LOW  
**Issue:** Using `print()` instead of logger in production code

**Fix:** Replace with logger:
```python
logger.info(f"Seeded {len(result.data)} routes")
```

---

## Summary Table

| Issue | Severity | Category | File | Line | Fix Time |
|-------|----------|----------|------|------|----------|
| Hardcoded CORS origins | 🔴 CRITICAL | Config | config.py | 43 | 15 min |
| Hardcoded Ollama URL | 🔴 CRITICAL | Config | config.py | 21 | 10 min |
| CWC real data TODO | 🔴 CRITICAL | Feature | cwc_gauge.py | 8 | 2-4 hours |
| Bare except Exception | 🟠 HIGH | Error Handling | map_data.py + 2 more | 46, 66, 41 | 20 min |
| Broad exception handlers | 🟠 HIGH | Error Handling | scenarios.py + 4 more | 129, 135, ... | 30 min |
| Missing env validation | 🟠 HIGH | Config | config.py | — | 15 min |
| Bare pass statements | 🟠 HIGH | Code Quality | map_data.py, districts.py | 47, 43 | 10 min |
| WKB loss metrics | 🟡 MEDIUM | Monitoring | map_data.py | 46 | 20 min |
| No scenario validation | 🟡 MEDIUM | Validation | scenarios.py | 120 | 20 min |
| process.env in Vite | 🟡 MEDIUM | Config | vite.config.js | 10 | 5 min |
| bbox validation | 🟡 MEDIUM | Validation | map_data.py | 60 | 15 min |
| Synthetic data marking | 🟡 MEDIUM | UX | synthetic_reports.py | — | 30 min |
| print() in seeds | 🟢 LOW | Code Quality | seed/*.py | multiple | 10 min |

---

## Recommended Fix Priority

### 🚨 **Must Fix Before MVP (2 hours)**
1. Remove hardcoded CORS/Ollama URLs
2. Add .env validation with clear error messages
3. Implement real CWC scraping (or document that synthetic mode is for demo only)

### 🔧 **Fix This Sprint (1 hour)**
4. Replace bare `except Exception` with specific error handling
5. Add logging to silent failures
6. Fix `process.env` → `import.meta.env` in Vite

### 📝 **Polish Later (30 min)**
7. Replace `print()` with logger in seed scripts
8. Add input validation for bbox and scenario data
9. Add monitoring metrics for data quality issues

---

## Next Steps

1. **Run this audit against PR reviews** — use as a checklist for new code
2. **Set up linting rules** to catch bare `except Exception` patterns
3. **Add integration tests** that verify error paths return proper HTTP errors
4. **Document synthetic data** — add clear UI/API markers for demo vs. real data
5. **Production deployment checklist** — ensure CORS/Ollama/CWC are externally configured

---

## Files Needing Changes

```
backend/
  ├── config.py                    [CRITICAL] CORS, Ollama URLs
  ├── api/
  │   ├── map_data.py            [HIGH] Exception handling, validation
  │   ├── scenarios.py           [HIGH] Exception handling, validation
  │   ├── districts.py           [HIGH] Exception handling, docs
  │   ├── health.py              [HIGH] Exception handling
  │   └── briefing.py            [HIGH] Exception handling
  ├── ingestion/
  │   ├── cwc_gauge.py           [CRITICAL] Real data implementation
  │   ├── open_meteo.py          [HIGH] Exception handling
  │   ├── osm_roads.py           [HIGH] Exception handling
  │   ├── synthetic_reports.py   [MEDIUM] Add synthetic data markers
  │   └── seed/*.py              [LOW] Replace print() with logger
frontend/
  └── vite.config.js              [MEDIUM] process.env → import.meta.env
```

---

**Report Generated:** 2026-04-21  
**Auditor:** GitHub Copilot
