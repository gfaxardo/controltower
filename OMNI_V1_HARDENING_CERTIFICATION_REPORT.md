# OMNI-V1 HARDENING CERTIFICATION REPORT

**Date**: 2026-06-08  
**Version**: 1.0  
**Git Hash**: 938c047  
**Branch**: master

---

## 1. EXECUTIVE SUMMARY

Omniview V1 (Evolution) has been audited across 12 hardening dimensions under the OMNI-V1 Hardening framework. The system operates with **WEEK_FACT severe staleness (49 days)**, multiple ungoverned writers per fact table, active legacy routes, and a driver aggregation path that can silently corrupt weekly driver counts.

**Classification: `V1_AT_RISK`**

V1 CAN operate but with significant risk. The week_fact staleness is the primary operational blocker. V2 (Vs Proy) and V2 Shadow are NOT affected by any changes made.

---

## 2. GOVERNANCE STATUS

| Field | Value |
|-------|-------|
| ACTIVE Motor | Control Foundation (REOPENED / P0) |
| ACTIVE Phase | OMNI-P0 — False GO Recovery & Vs Proy Canonicalization |
| READY NEXT | Diagnostic Engine 2A.3 (PAUSED) + CF-H2 Revenue Detail |
| Blocked | Forecast, Suggestion, Decision, Action, AI Copilot, Learning |
| Compatibility | OMNI-V1 Hardening falls under Control Foundation / Serving Governance / Hardening operativo. No conflict with active phase. |

**File references**: `ai_operating_system.md`, `ai_current_phase.md`

---

## 3. BOUNDARY AUDIT V1/V2

### 3.1 V1 (Evolution) Assets

| Asset | Type | Path | Action |
|-------|------|------|--------|
| `BusinessSliceOmniviewMatrix.jsx` | Frontend Shared (dual mode) | `frontend/src/components/` | READ ONLY |
| `BusinessSliceOmniviewMatrixCell.jsx` | Frontend Shared (dual mode) | `frontend/src/components/` | READ ONLY |
| `BusinessSliceOmniviewMatrixTable.jsx` | Frontend Shared (dual mode) | `frontend/src/components/` | READ ONLY |
| `BusinessSliceOmniviewInspector.jsx` | Frontend V1 | `frontend/src/components/` | READ ONLY |
| `omniviewMatrixUtils.js` | Frontend V1 utils | `frontend/src/components/omniview/` | READ ONLY |
| `GET /ops/business-slice/omniview` | Backend V1 endpoint | `backend/app/routers/ops.py:3705` | READ ONLY |
| `GET /ops/business-slice/monthly` | Backend Shared | `backend/app/routers/ops.py:3407` | READ ONLY |
| `GET /ops/business-slice/weekly` | Backend Shared | `backend/app/routers/ops.py:3584` | READ ONLY |
| `GET /ops/business-slice/daily` | Backend Shared | `backend/app/routers/ops.py:3637` | READ ONLY |
| `GET /ops/business-slice/real-freshness` | Backend Shared | `backend/app/routers/ops.py` | READ ONLY |
| `business_slice_omniview_service.py` | Backend V1 | `backend/app/services/` | READ ONLY |
| `business_slice_service.py` | Backend Shared | `backend/app/services/` | READ ONLY |

### 3.2 V2 (Vs Proy) Assets — NOT TOUCHED

| Asset | Status |
|-------|--------|
| `OmniviewProjectionDrill.jsx` | UNTOUCHED |
| `projectionExpectedProgressService.py` | UNTOUCHED |
| `GET /ops/business-slice/omniview-projection` | UNTOUCHED |
| All omniview_v2_* routers/services/repositories | UNTOUCHED |
| V2 Shadow (`pages/omniview-v2-shadow/`) | UNTOUCHED |

### 3.3 Shared Assets

| Asset | Shared By | Changes |
|-------|----------|---------|
| `ops.real_business_slice_day_fact` | V1, V2 | Read only (no schema change) |
| `ops.real_business_slice_week_fact` | V1, V2 | Read only |
| `ops.real_business_slice_month_fact` | V1, V2 | Read only |
| `BusinessSliceOmniviewMatrix.jsx` | V1, V2 (dual mode) | UNTOUCHED |
| `ops.v_real_business_slice_month_serving` | V1, V2 | Read only |
| `/ops/business-slice/data-freshness` | V1, V2 | Read only |

---

## 4. V1 LINEAGE MAP

```
RAW trips (public.trips_2025 / trips_2026 + dim.dim_park + public.drivers)
  │
  ├─ _materialize_enriched_direct()  ── _bs_enriched_month (TEMP)
  │   └─ _RESOLVE_AND_AGG_DAY_FROM_TEMP   → ops.real_business_slice_day_fact     [INSERT ON CONFLICT]
  │   └─ _RESOLVE_AND_AGG_WEEK_FROM_TEMP  → ops.real_business_slice_week_fact    [INSERT]
  │   └─ _RESOLVE_AND_AGG_FROM_TEMP       → ops.real_business_slice_month_fact   [INSERT]
  │
  ├─ driver_day_slice_fact (bridge)
  │   └─ rebuild_day_from_bridge.py       → ops.real_business_slice_day_fact     [DELETE + INSERT]
  │       └─ rebuild_week_from_day_and_bridge.py → ops.real_business_slice_week_fact  [DELETE + INSERT]
  │           └─ rebuild_month_from_day_and_bridge.py → ops.real_business_slice_month_fact  [DELETE + INSERT]
  │
  └─ LEGACY: refresh_business_slice_mvs.py → day_fact, week_fact, month_fact     [DEPRECATED but active]
```

**Frontend → API → Service → SQL chain:**

```
Omniview Matrix (V1 Evolution)
  → api.js: getBusinessSliceOmniview({granularity})
  → GET /ops/business-slice/omniview?grain={daily,weekly,monthly}
  → business_slice_omniview_service.get_business_slice_omniview()
  → SQL: SELECT ... FROM ops.real_business_slice_{day,week,month}_fact
  → Returns: rows + deltas + freshness + subtotals/totals
```

---

## 5. DATA SOURCE AUDIT

### V1 Usage

| Data Source | V1 Uses? | V2 Uses? | Type |
|-------------|----------|----------|------|
| `ops.real_business_slice_day_fact` | YES | YES | Fact table (daily) |
| `ops.real_business_slice_week_fact` | YES | YES | Fact table (weekly) |
| `ops.real_business_slice_month_fact` | YES | YES | Fact table (monthly) |
| `ops.v_real_business_slice_month_serving` | YES | YES | Serving view (monthly only) |
| `ops.real_business_slice_month_snapshot` | Indirect (via serving view) | YES | Snapshot (monthly) |
| `ops.v_real_trips_business_slice_resolved` | NO (FORBIDDEN by ServingPolicy) | NO | Audit only |
| `ops.v_real_trips_enriched_base` | NO (FORBIDDEN by ServingPolicy) | NO | Audit only |
| Raw trip tables | NO | NO | Build only |

### Key Findings
- V1 reads EXCLUSIVELY from fact tables (day_fact, week_fact, month_fact) and the serving view
- ServingPolicy strict mode gates access and forbids raw/semi-raw sources
- `revenue_yego_final` coverage: 95.9% from audited data (acceptable)
- No fallback SQL, no runtime heavy computation, no raw reads in serving path

---

## 6. FRESHNESS AUDIT

| Fact Table | Max Date | Row Count | Expected Freshness | Actual Freshness | Status |
|------------|----------|-----------|-------------------|-----------------|--------|
| `day_fact` | 2026-06-07 | 8,124 | today - 1 day | lag=1 day | **FRESH (OK)** |
| `week_fact` | 2026-04-20 | 24 | last closed ISO week (2026-06-01) | lag=49 days | **STALE (FAIL)** |
| `month_fact` | 2026-06-01 | 261 | last closed month (2026-05-01) | lag=7 days | **FRESH (OK)** |

### Freshness Findings
- **day_fact**: Up to date. Max trip_date = 2026-06-07 (yesterday). ✓
- **week_fact**: Severely behind. Max week_start = 2026-04-20. Expected = 2026-06-01. **49 days lag**. This means V1 will show NO weekly data for the last 7 weeks.
- **month_fact**: Current month (June 2026) present. OK at monthly grain.

### Upstream Status
- Raw trips max: 2026-06-07
- Day fact max: 2026-06-07 (aligned)
- Gap: raw → day = 0 days (excellent)

---

## 7. SNAPSHOT AUDIT

| Snapshot | Source | Max Period | Status | Classification |
|----------|--------|-----------|--------|----------------|
| `ops.real_business_slice_month_snapshot` | `month_fact` | 2026-04-01 | Active snapshot exists | SNAPSHOT_OK |
| `ops.omniview_v2_serving_snapshot` | V2 Shadow facts | N/A | V2 only | SNAPSHOT_OK (V2) |

### Details
- Monthly snapshot max period = 2026-04-01, fact max = 2026-06-01
- Snapshot is NOT ahead of fact base (correct)
- Day/week facts have NO snapshot capability (gap G13 in registry)
- Serving view `v_real_business_slice_month_serving` correctly routes open periods → fact, locked periods → snapshot

---

## 8. WRITER AUDIT

### Writers per Fact Table

| Fact Table | Active Writers | Legacy Writers | Classification |
|------------|---------------|----------------|----------------|
| `day_fact` | 3 (inline, staging, bridge rebuild) | 2 (legacy loaders) + 1 no-op scheduler | **MULTIPLE_WRITERS_DETECTED** |
| `week_fact` | 3 (inline CTE, staging, bridge rebuild) | 4 (resolved view, rollup from day, legacy staging, rebuild from day only) + 1 no-op scheduler | **MULTIPLE_WRITERS_DETECTED** |
| `month_fact` | 3 (inline CTE, staging, bridge rebuild) | 1 (legacy loader) + 1 no-op scheduler | **MULTIPLE_WRITERS_DETECTED** |

### Critical Writer Issues
1. **No active automatic writer**: The scheduled `omniview_business_slice_real_refresh` job is a NO-OP (sets nd=0, nw=0, nm=0). OV2-F.4C deprecates all legacy loaders.
2. **No scheduled OV2 cascade**: `run_ov2_refresh_cascade.py` is MANUAL only.
3. **`refresh_business_slice_mvs.py`** still calls deprecated loaders and can be run accidentally.
4. **`rebuild_week_fact_from_day_fact.py`** is NOT blocked (unlike `refresh_omniview_real_slice.py` which has a safety guard).
5. **Week fact currently has 24 rows only** — suggests the weekly lattice is not being refreshed by any active writer.

### Remediation
- Standardize on OV2 bridge cascade (`run_ov2_refresh_cascade.py`) as the sole canonical writer
- Schedule bridge cascade in APScheduler
- Add safety guard to ALL deprecated write paths
- Block `refresh_business_slice_mvs.py` from writing to fact tables

---

## 9. DRIVER EXACTNESS AUDIT

| Calculation Path | Day | Week | Month | Classification |
|---|---|---|---|---|
| Inline raw trips (`_RESOLVE_AND_AGG_*_FROM_TEMP`) | EXACT `COUNT(DISTINCT)` | EXACT `COUNT(DISTINCT)` | EXACT `COUNT(DISTINCT)` | EXACT |
| Bridge-based (`rebuild_*_from_bridge.py`) | EXACT `COUNT(DISTINCT)` | EXACT `COUNT(DISTINCT)` | EXACT `COUNT(DISTINCT)` | EXACT |
| Rollup from day_fact (`rebuild_week_fact_from_day_fact.py`) | N/A | **BROKEN**: `SUM(daily distinct)` | N/A | **BROKEN** |
| Resolved view (`_WEEK_AGG_FROM_RESOLVED`) | N/A | EXACT per-week DISTINCT | N/A | EXACT |

### Overall Classification: **ACCEPTABLE_WITH_WARNING**

- Primary active path (bridge cascade): EXACT
- Primary legacy path (inline): EXACT
- **Risk**: `rebuild_week_fact_from_day_fact.py` exists and is NOT blocked. If run, it produces INFLATED driver counts at week level (SUM of daily distincts ≠ weekly distinct).

---

## 10. LEGACY ROUTE / PYCACHE RISK

### Active Legacy Routes

| Route | Consumer | Risk |
|-------|----------|------|
| `GET /core/summary/monthly` | MonthlyView.jsx (ORPHAN) | LOW (no active UI) |
| `GET /ops/real/monthly` | MonthlySplitView.jsx | MEDIUM |
| `GET /ops/real-lob/monthly (v1)` | RealLOBView.jsx alongside v2 | HIGH |
| `GET /ops/real-lob/weekly (v1)` | RealLOBView.jsx alongside v2 | HIGH |

### Pycache Status

| Metric | Value |
|--------|-------|
| Total .pyc files | 269 |
| Stale .pyc files | 2 |
| Risk level | **LOW** |

2 stale .pyc files detected. Not critical but should be cleaned.

---

## 11. RUNTIME IDENTITY

### Endpoint: `GET /ops/v1-runtime-identity`

| Field | Value |
|-------|-------|
| git_hash | 938c047 |
| git_branch | master |
| build_time | 2026-06-08T14:29:03.859331+00:00 |
| backend_instance | PC hostname:pid |
| python_version | Python 3.13.x |
| app_start_time | 2026-06-08T14:29:03.859331+00:00 |
| loaded_module_paths | 5 V1-critical modules verified |
| pycache_risk_checked | 269 total, 2 stale |

The health endpoint `GET /health` now includes `runtime_identity` field (additive, non-breaking).

---

## 12. TRUST SENSOR RESULTS

**Endpoint**: `GET /ops/v1-trust-sensor`  
**Overall Status**: **FAIL** (blocking failures detected)

### Check Results

| Code | Severity | Asset | Observed | Blocking |
|------|----------|-------|----------|----------|
| DAY_FACT_STALE | OK | day_fact | max=2026-06-07, lag=1d | No |
| **WEEK_FACT_STALE** | **FAIL** | week_fact | max=2026-04-20, lag=49d | **Yes** |
| MONTH_FACT_STALE | OK | month_fact | max=2026-06-01, lag=7d | No |
| WATERFALL_BROKEN | WARN | day→week→month cascade | week_max behind day_max by >1 week | No |
| MULTIPLE_WRITERS_DETECTED | WARN | day_fact | 4 write paths | No |
| MULTIPLE_WRITERS_DETECTED | WARN | week_fact | 4 write paths (1 BROKEN) | No |
| MULTIPLE_WRITERS_DETECTED | WARN | month_fact | 3 write paths | No |
| LEGACY_ROUTE_ACTIVE | WARN | /core/summary/monthly | Orphan consumer | No |
| LEGACY_ROUTE_ACTIVE | WARN | /ops/real/monthly | Active consumer | No |
| LEGACY_ROUTE_ACTIVE | WARN | /ops/real-lob/monthly (v1) | Active alongside v2 | No |
| LEGACY_ROUTE_ACTIVE | WARN | /ops/real-lob/weekly (v1) | Active alongside v2 | No |
| DRIVER_AGGREGATION_AMBIGUOUS | WARN | week_fact drivers | 1 BROKEN path unblocked | No |
| PYCACHE_RISK | WARN | __pycache__/ | 2/269 stale | No |

---

## 13. WATERFALL VALIDATION

**Endpoint**: `GET /ops/v1-waterfall-validation`  
**Overall Status**: **WATERFALL_WARN**

| Check | Status | Detail |
|-------|--------|--------|
| day_fact_has_data | OK | 8,124 rows, max=2026-06-07 |
| week_fact_has_data | OK | 24 rows, max=2026-04-20 |
| month_fact_has_data | OK | 261 rows, max=2026-06-01 |
| day_to_week_alignment | **WARN** | week_max behind day_max by 48 days |
| day_to_month_alignment | OK | month_max=2026-06-01, day_max=2026-06-07 |
| snapshot_vs_fact_alignment | OK | snapshot ≤ fact max |
| serving_policy_active | WARN | Could not verify ServingPolicy at import time |
| v1_reads_fact_tables_only | OK | No raw reads in serving path |
| monthly_serving_view_exists | OK | 278 rows |
| revenue_without_trips | OK | No revenue rows without trips |
| revenue_yego_final_coverage | OK | 95.9% coverage |

### Architecture Validation
- RAW → day_fact → ✓ (fresh, 1 day lag)
- day_fact → week_fact → ✗ (48 days behind)
- day_fact → month_fact → ✓ (aligned with June)
- month_fact → snapshot → ✓ (not ahead)
- Serving → UI → ✓ (ServingPolicy gated, fact tables only)
- Revenue → ✓ (95.9% final coverage, no phantom revenue)

---

## 14. V1 RISKS

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | **Week_fact 49 days stale** — V1 weekly view shows no data for last 7 weeks | **CRITICAL** | Execute `run_ov2_refresh_cascade.py` immediately |
| 2 | Multiple ungoverned writers — manual execution of wrong script corrupts data | **HIGH** | Add safety guards, standardize bridge cascade |
| 3 | `rebuild_week_fact_from_day_fact.py` unblocked — can silently inflate driver counts | **HIGH** | Add `--allow-legacy-weekly-dangerous` guard |
| 4 | No automatic scheduler writing to fact tables | **HIGH** | Schedule `run_ov2_refresh_cascade.py` in APScheduler |
| 5 | Legacy routes active with active consumers | MEDIUM | Migration plan for MonthlySplitView, RealLOBView |
| 6 | 2 stale .pyc files | LOW | Clean and restart |

---

## 15. V2 RISKS

| # | Risk | Severity |
|---|------|----------|
| 1 | V1 and V2 share fact tables — if week_fact is stale, V2 weekly view also affected | **HIGH** |
| 2 | V2 projection serving facts (`serving.omniview_projection_daily_fact`) depend on fresh day_fact | MEDIUM |
| 3 | V2 Shadow has independent snapshot layer, less affected by fact staleness | LOW |

**V2 Is Not Directly Affected By This Hardening Effort.** No V2 code, contracts, or routes were modified.

---

## 16. SHARED ASSETS

| Asset | V1 Impact | V2 Impact | Risk |
|-------|-----------|-----------|------|
| `day_fact` | Reads for daily data | Reads for plan-vs-real baseline | Shared freshness OK currently |
| `week_fact` | Reads for weekly data | Reads for weekly aggregation | **BOTH broken (49d stale)** |
| `month_fact` | Reads for monthly data | Reads for monthly totals | Shared freshness OK |
| `business_slice_service.py` | Canonical read (V1) | Canonical read (V2) | No changes, shared OK |
| `BusinessSliceOmniviewMatrix.jsx` | Evolution mode | Projection mode | No changes, shared OK |
| `/health` endpoint | Used by V1 monitoring | Used by V2 monitoring | **Enhanced** with runtime_identity (additive, non-breaking) |

---

## 17. MINIMUM BACKLOG

| Item | Priority | Effort |
|------|----------|--------|
| Execute `run_ov2_refresh_cascade.py` to refresh week_fact | P0 - NOW | 5 min CLI |
| Schedule bridge cascade in APScheduler (hourly/daily) | P0 | 2 hrs |
| Add safety guard to `rebuild_week_fact_from_day_fact.py` | P1 | 30 min |
| Block `refresh_business_slice_mvs.py` fact writes | P1 | 1 hr |
| Migrate MonthlySplitView from `/ops/real/monthly` to canonical | P2 | 4 hrs |
| Migrate RealLOBView from v1 to v2 exclusively | P2 | 3 hrs |
| Schedule day/week snapshot creation (gap G13) | P2 | 1 day |
| Clean stale .pyc files | P3 | 5 min |

---

## 18. FINAL CLASSIFICATION

### `V1_AT_RISK`

**Rationale:**

| Criterion | Status |
|-----------|--------|
| day/week/month fresh | **NO** — week_fact 49 days stale |
| snapshots gobernados | PARTIAL — monthly only, no day/week snapshots |
| single writer confirmado | **NO** — 3-4 writers per fact table |
| no legacy route peligrosa | **NO** — 4 active legacy routes with active consumers |
| runtime identity visible | **YES** — new endpoint + health enhancement |
| drivers exactos o warning aceptable | WARNING ACCEPTABLE — exact paths exist, BROKEN path unblocked |
| waterfall OK | **NO** — WATERFALL_WARN (week behind day by 48d) |
| Trust Sensor OK/WARN no bloqueante | **NO** — FAIL with blocking WEEK_FACT_STALE |
| V2 no afectado | **YES** — no V2 assets touched |

**Does NOT qualify for V1_CERTIFIED** because:
- week_fact is severely stale (FAIL, blocking)
- multiple writers are ungoverned
- legacy routes are active
- waterfall shows WARN-level misalignment

**Does NOT qualify for V1_PARTIAL** because:
- The blocking WEEK_FACT_STALE signal prevents reliable weekly operations
- The lack of any automated writer means the system depends on manual intervention for basic freshness

---

## 19. GO / NO-GO

### **NO-GO for Certified Operation**

V1 CAN operate in a degraded capacity (daily and monthly views work). Weekly view is effectively non-functional due to 49-day staleness. The system lacks automatic refresh and has ungoverned multiple writers.

### Immediate Remediation Required for GO:
1. Execute bridge cascade refresh for week_fact
2. Schedule automatic refresh in APScheduler
3. Add safety guards to all deprecated write paths

---

## 20. QA RESULTS

### Backend Import Check

| Module | Result |
|--------|--------|
| `omniview_v1_trust_sensor.py` | ✓ Import OK |
| `omniview_v1_runtime_identity.py` | ✓ Import OK |
| `omniview_v1_waterfall_validation.py` | ✓ Import OK |
| `health.py` (updated) | ✓ Import OK |
| `ops.py` (updated) | ✓ Import OK |

### Trust Sensor Evidence

```
Trust Sensor → FAIL
  OK: 2  |  WARN: 10  |  FAIL: 1  |  BLOCKED: True
  BLOCKING: WEEK_FACT_STALE (max=2026-04-20, expected=2026-06-01, lag=49d)
```

### Waterfall Validation Evidence

```
Waterfall → WATERFALL_WARN
  day_fact: 8,124 rows, max=2026-06-07
  week_fact: 24 rows, max=2026-04-20 (48d behind)
  month_fact: 261 rows, max=2026-06-01
  day→week: WARN | day→month: OK | revenue: 95.9% coverage
```

### Runtime Identity Evidence

```
git_hash: 938c047
git_branch: master
python_version: Python 3.13.9
loaded_modules: 5/5 V1 modules verified
pycache: 269 total, 2 stale
```

### Freshness Queries (Live)

```
SELECT MAX(trip_date), COUNT(*) FROM ops.real_business_slice_day_fact
→ 2026-06-07, 8,124 rows

SELECT MAX(week_start), COUNT(*) FROM ops.real_business_slice_week_fact
→ 2026-04-20, 24 rows

SELECT MAX(month), COUNT(*) FROM ops.real_business_slice_month_fact
→ 2026-06-01, 261 rows
```

### Health Endpoint (Live)

```
GET /health → 200 OK
  status: ok
  db_connection: ok
  runtime_identity: {git_hash, git_branch, build_time, ...}
  scheduler_status: active
```

---

## 21. FILES CREATED/MODIFIED

### Created
| File | Purpose |
|------|---------|
| `backend/app/services/omniview_v1_trust_sensor.py` | V1 Trust Sensor service (549 lines) |
| `backend/app/services/omniview_v1_runtime_identity.py` | Runtime Identity service (120 lines) |
| `backend/app/services/omniview_v1_waterfall_validation.py` | Waterfall Validation service (219 lines) |
| `OMNI_V1_HARDENING_CERTIFICATION_REPORT.md` | This report |

### Modified
| File | Change | Impact V1 | Impact V2 |
|------|--------|-----------|-----------|
| `backend/app/routers/health.py` | Added `runtime_identity` field (additive) | None (new field) | None (new field) |
| `backend/app/routers/ops.py` | Added 3 new V1 hardening endpoints | New endpoints only | None (separate routes) |

### Assets NOT Touched
- All V2 (Vs Proy) frontend/backend/service/router files
- All V2 Shadow files
- All shared fact tables (read only, no schema changes)
- All shared frontend Matrix components
- No UX changes
- No layout changes
- No navigation changes
- No Forecast/Suggestion/Decision/Action/AI Copilot introduced

---

**END OF REPORT**

_Generated by OMNI-V1 Hardening framework at 2026-06-08. Git: 938c047. Classification: V1_AT_RISK._
