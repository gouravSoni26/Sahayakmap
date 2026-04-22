# SahayakMap Fix List

**Date:** April 21, 2026
**Status:** Ready for self-fixing
**Total Issues:** 18
**Estimated Time:** 3-4 hours total

---

## 🚨 CRITICAL — Fix First (2 hours)

### 1. Hardcoded CORS Origins
**File:** `backend/config.py` (line 43)
**Problem:** CORS is hardcoded to localhost URLs, will fail in production
**Current Code:**
```python
cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]
```
**Fix:**
```python
cors_origins: List[str] = Field(
    default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
)
```
**Also add to .env.example:**
```
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```
**Test:** Deploy to staging and verify frontend loads without CORS errors

---

### 2. CWC Gauge Data is Synthetic + Synthetic Reports Not Marked
**Files:** `backend/ingestion/cwc_gauge.py` (line 8), `backend/ingestion/synthetic_reports.py`
**Problem:** System uses fake water level data with no clear indication to the user or in the database. Synthetic reports are not architecturally distinguishable from real ones — this will corrupt the fusion engine's confidence scoring.

**Fix Part A — Mark all synthetic records at source:**
```python
# In synthetic_reports.py — add to every synthetic record
record["source_type"] = "SYNTHETIC"
```

**Fix Part B — Frontend DEMO MODE banner:**
Add a banner in the frontend when `SIMULATION_MODE=true` or any data has `source_type = "SYNTHETIC"`:
```jsx
{isSimulationMode && (
  <div className="demo-banner">
    ⚠️ DEMO MODE — Using synthetic data. Not for operational use.
  </div>
)}
```

**Fix Part C — Add TODO comment in cwc_gauge.py:**
```python
# TODO (production): Implement real CWC scraping from https://ffs.india-water.gov.in
# For now, all records generated here are SYNTHETIC — mark them accordingly.
```
**Test:** Verify all synthetic records in `flood_reports` table have `source_type = "SYNTHETIC"`

---

## 🔧 HIGH PRIORITY — Fix Next (1 hour)

### 3. Frontend Vite Config Uses Wrong Env
**File:** `frontend/vite.config.js` (line 10)
**Problem:** Uses `process.env` instead of `import.meta.env` — frontend cannot resolve `VITE_API_BASE_URL`, so every map data call hits the wrong URL. All Week 2 map layers will silently fail.
**Current Code:**
```javascript
target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
```
**Fix:**
```javascript
target: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
```
**Test:** Check network tab — API calls should resolve to the correct backend URL

---

### 4. Bare Exception Handlers (Map Data)
**File:** `backend/api/map_data.py` (line 46)
**Problem:** WKB parsing fails silently, loses location data
**Current Code:**
```python
except Exception:
    pass  # leave record without lat/lng if WKB parse fails; frontend handles gracefully
```
**Fix:**
```python
except Exception as e:
    logger.warning("Failed to parse WKB location for record %s: %s", record.get('id'), e)
    record["lat"] = None
    record["lng"] = None
```

---

### 5. Bare Exception Handlers (Open Meteo)
**File:** `backend/ingestion/open_meteo.py` (line 66)
**Problem:** Forecast insertion fails silently — `logger.debug` is outside the `try` block so it always fires even on failure
**Current Code:**
```python
except Exception as e:
    logger.debug("Inserted %d forecast rows for %s", len(rows), point["name"])
```
**Fix:**
```python
try:
    # ... insert logic ...
    logger.debug("Inserted %d forecast rows for %s", len(rows), point["name"])
except Exception as e:
    logger.error("Failed to insert forecast for %s: %s", point["name"], e)
```

---

### 6. Bare Exception Handlers (OSM Roads)
**File:** `backend/ingestion/osm_roads.py` (line 41)
**Problem:** Road data fetch fails silently — same misplaced `logger.debug` issue as above
**Current Code:**
```python
except Exception as e:
    logger.debug("Fetched %d road segments", len(roads))
```
**Fix:**
```python
try:
    # ... fetch logic ...
    logger.debug("Fetched %d road segments", len(roads))
except Exception as e:
    logger.error("Failed to fetch OSM roads: %s", e)
```

---

### 7. Broad Exception Handlers (Scenarios)
**File:** `backend/api/scenarios.py` (lines 129, 135, 146)
**Problem:** Catches all exceptions, hard to debug
**Current Code:**
```python
except Exception as exc:
    errors.append(f"flood_report insert failed: {exc}")
```
**Fix:**
```python
except (psycopg2.IntegrityError, psycopg2.OperationalError) as exc:
    errors.append(f"flood_report insert failed: {exc}")
except Exception as exc:
    logger.error("Unexpected error inserting flood report: %s", exc)
    errors.append(f"flood_report insert failed: {exc}")
```

---

### 8. Broad Exception Handlers (Districts)
**File:** `backend/api/districts.py` (lines 64, 77, 93, 107, 121)
**Problem:** Catches everything without logging
**Current Code:**
```python
except Exception as exc:
    raise RepositoryError(f"Failed to fetch districts: {exc}") from exc
```
**Fix:**
```python
except Exception as exc:
    logger.error("Database error fetching districts: %s", exc)
    raise RepositoryError(f"Failed to fetch districts: {exc}") from exc
```

---

### 9. Broad Exception Handlers (Health)
**File:** `backend/api/health.py` (lines 28, 45)
**Problem:** Catches everything without logging
**Current Code:**
```python
except Exception as exc:
    raise HTTPException(status_code=503, detail=f"Database unreachable: {exc}")
```
**Fix:**
```python
except Exception as exc:
    logger.error("Health check database error: %s", exc)
    raise HTTPException(status_code=503, detail=f"Database unreachable: {exc}")
```

---

### 10. Broad Exception Handler (Briefing)
**File:** `backend/intelligence/briefing.py` (line 309)
**Problem:** Logger warning is about LLM unavailability but the `except` wraps DB queries — wrong error message for wrong error
**Current Code:**
```python
except Exception as e:
    logger.warning("LLM unavailable and llm_fallback_to_templates is disabled")
```
**Fix:**
```python
try:
    reports, gauges, assets, adjacency, all_districts = await asyncio.gather(...)
    logger.debug("Analysis data fetched successfully")
except Exception as e:
    logger.error("Failed to fetch analysis data: %s", e)
    raise HTTPException(status_code=503, detail="Failed to build analysis")
```

---

### 11. Missing Environment Validation
**File:** `backend/config.py`
**Problem:** No validation if required env vars are missing — app crashes with an unhelpful error at runtime instead of a clear message at startup
**Fix:** Add to `config.py` or `main.py`:
```python
if not settings.supabase_url:
    raise ValueError("SUPABASE_URL is required. Check your .env file.")
if not settings.supabase_anon_key:
    raise ValueError("SUPABASE_ANON_KEY is required. Check your .env file.")
if not settings.supabase_service_key:
    raise ValueError("SUPABASE_SERVICE_KEY is required. Check your .env file.")
if not settings.anthropic_api_key:
    raise ValueError("ANTHROPIC_API_KEY is required. Check your .env file.")
```
**Test:** Temporarily remove each key from `.env` and confirm the correct error message appears

---

### 12. APScheduler Startup Check *(NEW)*
**File:** `backend/main.py` (app startup section)
**Problem:** `apscheduler` is responsible for all periodic data ingestion (Open-Meteo, synthetic reports, OSM roads). If it silently fails to start, the `flood_reports` table stays empty — the entire Week 2 fusion engine has no data to work with. This is nowhere in the codebase currently.
**Fix:** Add a startup health check:
```python
@app.on_event("startup")
async def verify_scheduler():
    jobs = scheduler.get_jobs()
    if not jobs:
        logger.error("APScheduler started with 0 jobs — ingestion pipeline is broken")
        raise RuntimeError("Scheduler has no jobs registered. Check ingestion setup.")
    logger.info("Scheduler started with %d jobs: %s", len(jobs), [j.id for j in jobs])
```
**Test:** On app boot, confirm logs show scheduler job names. Remove one registration temporarily and verify the error fires.

---

### 13. Bare Pass Statement (Map Data)
**File:** `backend/api/map_data.py` (line 47)
**Problem:** Intent is unclear — does the code know it's setting lat/lng to None, or is it just forgetting?
**Current Code:**
```python
pass  # leave record without lat/lng if WKB parse fails; frontend handles gracefully
```
**Fix:** (Covered in Issue #4 — replace pass with explicit None assignment)
```python
record["lat"] = None
record["lng"] = None
```

---

### 14. Bare Pass Statement (Districts)
**File:** `backend/api/districts.py` (line 43)
**Problem:** Security guard stub has no documentation
**Current Code:**
```python
def _guard_district_access(user: None) -> None:
    pass
```
**Fix:**
```python
def _guard_district_access(user: None) -> None:
    """Security guard for district endpoints. Currently no auth required.
    TODO (Week 3+): Add token validation when auth is implemented."""
    pass
```

---

## 🟡 MEDIUM PRIORITY — Fix Later (30 min)

### 15. Bbox Parameter Validation
**File:** `backend/api/map_data.py` (lines 60-70)
**Problem:** No bounds checking on coordinates — invalid bbox silently returns wrong data
**Current Code:**
```python
parts = [float(x) for x in bbox.split(",")]
if len(parts) != 4:
    raise ValueError
```
**Fix:**
```python
try:
    lat1, lng1, lat2, lng2 = [float(x) for x in bbox.split(",")]
    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("Latitude out of bounds")
    if not (-180 <= lng1 <= 180 and -180 <= lng2 <= 180):
        raise ValueError("Longitude out of bounds")
except (ValueError, TypeError) as e:
    raise HTTPException(status_code=422, detail=f"Invalid bbox: {e}")
```

---

### 16. Scenario Data Validation
**File:** `backend/api/scenarios.py` (line 120+)
**Problem:** No validation of scenario data structure — `KeyError` on bad `_source_type` gives a 500 instead of a 400
**Current Code:**
```python
row["source_id"] = source_id_map[report["_source_type"]]
```
**Fix:**
```python
try:
    source_type = report["_source_type"]
    row["source_id"] = source_id_map[source_type]
except KeyError as e:
    raise HTTPException(status_code=400, detail=f"Invalid source_type: {e}")
```

---

## 🟢 LOW PRIORITY — Optional (15 min)

### 17. Replace Print with Logger (Seed Scripts)
**Files:** `backend/seed/*.py` (multiple lines)
**Problem:** Uses `print()` instead of logger — inconsistent with rest of codebase
**Current Code:**
```python
print(f"Seeded {len(result.data)} routes")
```
**Fix:**
```python
logger.info("Seeded %d routes", len(result.data))
```

---

### 18. Ollama URL Configuration
**File:** `backend/config.py` (line 21)
**Problem:** Ollama URL is hardcoded
**Note:** Per masterplan, Ollama is a fallback for offline/degraded mode only — Claude API is the primary intelligence layer. This is LOW priority; do not spend time on it until Week 3+ when the intelligence layer is being built.
**Current Code:**
```python
ollama_base_url: str = "http://localhost:11434"
```
**Fix (when needed):**
```python
ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
```

---

## 📋 Fix Checklist

- [ ] **#1** Hardcoded CORS Origins
- [ ] **#2** CWC Synthetic Data + Mark All Synthetic Records
- [ ] **#3** Vite Config Wrong Env Variable *(upgraded to HIGH)*
- [ ] **#4** Bare Exception — Map Data
- [ ] **#5** Bare Exception — Open Meteo
- [ ] **#6** Bare Exception — OSM Roads
- [ ] **#7** Broad Exception — Scenarios
- [ ] **#8** Broad Exception — Districts
- [ ] **#9** Broad Exception — Health
- [ ] **#10** Wrong Exception Message — Briefing
- [ ] **#11** Missing Env Validation (incl. ANTHROPIC_API_KEY)
- [ ] **#12** APScheduler Startup Check *(new)*
- [ ] **#13** Bare Pass — Map Data (covered in #4)
- [ ] **#14** Bare Pass — Districts
- [ ] **#15** Bbox Validation
- [ ] **#16** Scenario Data Validation
- [ ] **#17** Print → Logger in Seed Scripts
- [ ] **#18** Ollama URL *(do in Week 3, not now)*

---

## 🧪 Testing After Fixes

1. **Env Validation:** Remove each key from `.env` one at a time — confirm clear error messages
2. **CORS:** Test frontend against backend with CORS_ORIGINS set correctly
3. **Vite Env:** Check browser network tab — API calls should hit correct backend URL
4. **Scheduler:** Check startup logs — should list all registered job IDs
5. **Synthetic Data:** Query `flood_reports` table — all synthetic rows must have `source_type = "SYNTHETIC"`
6. **Error Handling:** Trigger each error path and verify logs show proper messages

---

## 📝 Changes from Previous Version

| # | Change | Reason |
|---|--------|--------|
| Issue #2 | Merged original #3 + #17 into one issue | Same root fix — mark synthetic data at source |
| Issue #3 | **Upgraded from MEDIUM → HIGH** | Breaks all frontend API calls — Week 2 blocker |
| Issue #11 | Added `ANTHROPIC_API_KEY` validation | Required for Week 3 intelligence layer |
| Issue #12 | **New issue added** | APScheduler failure = empty `flood_reports` = fusion engine has no data |
| Issue #18 | **Downgraded from CRITICAL → LOW** | Ollama is a fallback only per masterplan; Claude API is primary |
| Total count | Fixed from 16 → 18 | Accurate count |

---

*This document is the execution plan for resolving Week 1 technical debt before building Week 2 features.*
