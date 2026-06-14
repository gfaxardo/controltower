# OMNIVIEW V2 — CANONICAL DOCUMENTATION

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** FIRST DRAFT — Evidence-based from live repo audit
**Engine:** Control Foundation (#1)

---

## 1. OVERVIEW

Omniview is the canonical operational view for YEGO Control Tower. It provides a matrix-based visualization of operational KPIs across business slices and time grains.

**Active versions:**
- Omniview V1 (Business Slice) — Production, canonical
- Omniview V2 (Source-agnostic) — Parallel, under development

**Key principle:** Omniview is REAL ONLY. Plan vs Real comparison has its own separate view (`/ops/business-slice/omniview-projection`).

---

## 2. CANONICAL DATA SOURCES

### 2.1 Fact Tables (Source of Truth)

| Table | Grain | Read Path |
|-------|-------|-----------|
| `ops.real_business_slice_day_fact` | daily | Direct read by `business_slice_service.py` |
| `ops.real_business_slice_week_fact` | weekly | Direct read by `business_slice_service.py` |
| `ops.real_business_slice_month_fact` | monthly | Via `v_real_business_slice_month_serving` |
| `ops.real_business_slice_hour_fact` | hourly | Internal only (not served to UI) |

### 2.2 Serving View (Monthly Only)

```
ops.v_real_business_slice_month_serving
    ├── locked period  → ops.real_business_slice_month_snapshot
    └── open period    → ops.real_business_slice_month_fact
```

### 2.3 FORBIDDEN Sources

These MUST NOT be used for UI reads (enforced by `serving_guardrails.py`):
- `ops.v_real_trips_enriched_base` — Intermediate view
- `ops.v_real_trips_business_slice_resolved` — Intermediate view

---

## 3. CANONICAL KPIs

| KPI | Aggregation Type | Data Source |
|-----|-----------------|-------------|
| `trips_completed` | ADDITIVE (SUM) | `completed_orders` from fact |
| `trips_cancelled` | ADDITIVE (SUM) | `cancelled_orders` from fact |
| `active_drivers` | SEMI_ADDITIVE (COUNT DISTINCT) | `active_drivers` from fact |
| `avg_ticket` | RATIO (AVG weighted) | Computed from revenue/trips |
| `revenue_yego_net` | ADDITIVE (SUM) | `revenue_yego_final` from fact |
| `commission_pct` | RATIO | Computed from totals |
| `cancel_rate_pct` | RATIO | Computed from totals |
| `trips_per_driver` | DERIVED_RATIO | trips_completed / active_drivers |

---

## 4. SERVICE ARCHITECTURE

### 4.1 Canonical Read Services

| Service | File | Responsibility |
|---------|------|----------------|
| `business_slice_service.py` | `backend/app/services/` | Defines FACT constants, read methods for all grains |
| `business_slice_omniview_service.py` | `backend/app/services/` | Omniview-specific queries with ServingPolicy enforcement |
| `business_slice_canonical_service.py` | `backend/app/services/` | Normalization and aggregation of business slices |
| `omniview_semantics_service.py` | `backend/app/services/` | Canonical definitions of avance_pct, gap, compare signals |
| `omniview_matrix_integrity_service.py` | `backend/app/services/` | Matrix integrity checks (trip loss, B2B, LOB mapping, duplicates) |
| `omniview_momentum_drill_service.py` | `backend/app/services/` | Drill-down into specific cell data |
| `omniview_freshness_governance_service.py` | `backend/app/services/` | Per-fact freshness monitoring |

### 4.2 Key Constants

| Constant | Value | File |
|----------|-------|------|
| `FACT_MONTHLY` | `ops.v_real_business_slice_month_serving` | `business_slice_service.py:47` |
| `FACT_MONTHLY_RAW` | `ops.real_business_slice_month_fact` | `business_slice_service.py:48` |
| `FACT_DAILY` | `ops.real_business_slice_day_fact` | `business_slice_service.py:50` |
| `FACT_WEEKLY` | `ops.real_business_slice_week_fact` | `business_slice_service.py:51` |
| `STALE_THRESHOLD_HOURS` | `24` | `serving_governance_service.py:25` |
| `DEFAULT_PLAN_VERSION` | `ruta27_2026_04_21` | `serving_refresh_scheduler.py:30` |
| `FORBIDDEN_SERVING_SOURCES` | `["v_real_trips_business_slice_resolved", "v_real_trips_enriched_base"]` | `serving_guardrails.py` |

---

## 5. ENDPOINTS

### 5.1 Omniview V1 (Business Slice)

| Method | Endpoint | Grain | Service |
|--------|----------|-------|---------|
| GET | `/ops/business-slice/monthly` | monthly | `business_slice_service.py` |
| GET | `/ops/business-slice/weekly` | weekly | `business_slice_service.py` |
| GET | `/ops/business-slice/daily` | daily | `business_slice_service.py` |
| GET | `/ops/business-slice/omniview` | any | `business_slice_omniview_service.py` |
| GET | `/ops/business-slice/filters` | metadata | `real_lob_filters_service.py` |
| GET | `/ops/business-slice/coverage` | coverage | (DB query) |
| GET | `/ops/business-slice/coverage-summary` | summary | (DB query) |
| GET | `/ops/business-slice/real-freshness` | freshness | `business_slice_real_freshness_service.py` |
| GET | `/ops/business-slice/fact-status` | status | (DB query) |
| GET | `/ops/business-slice/matrix-operational-trust` | trust | `omniview_matrix_integrity_service.py` |
| POST | `/ops/business-slice/matrix-issue-action` | action | `omniview_matrix_integrity_service.py` |
| GET | `/ops/business-slice/omniview-projection` | projection | `projection_expected_progress_service.py` |
| GET | `/ops/business-slice/omniview-projection/serving-plan-versions` | metadata | `projection_expected_progress_service.py` |
| GET | `/ops/business-slice/momentum-drill` | drill | `omniview_momentum_drill_service.py` |

### 5.2 Omniview V2 (Source-agnostic)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ops/omniview-v2/sources` | List registered sources |
| GET | `/ops/omniview-v2/summary` | KPIs from a single source |
| GET | `/ops/omniview-v2/health` | Health check for all sources |
| GET | `/ops/omniview-v2/compare` | Side-by-side source comparison |
| GET | `/ops/omniview-v2/matrix` | Matrix response |
| GET | `/ops/omniview-v2/snapshots/serving` | Served payload |
| GET | `/ops/omniview-v2/plan-real/monthly` | Plan Real side-by-side matrix |
| GET | `/ops/omniview-v2/plan-versions` | Plan version list |
| GET | `/ops/omniview-v2/usage-metrics` | Usage metrics |
| POST | `/ops/omniview-v2/session` | Record session |

---

## 6. FRONTEND COMPONENTS

### 6.1 Omniview V1 Components (Production)

| Component | File | Role |
|-----------|------|------|
| `BusinessSliceOmniview.jsx` | `frontend/src/components/` | Main orchestrator — state, filters, data fetching |
| `BusinessSliceOmniviewMatrix.jsx` | `frontend/src/components/` | Matrix view (grid of cells) |
| `BusinessSliceOmniviewMatrixTable.jsx` | `frontend/src/components/` | Unified table for Real/Projection/Comparison |
| `BusinessSliceOmniviewMatrixCell.jsx` | `frontend/src/components/` | Individual cell renderer |
| `BusinessSliceOmniviewMatrixHeader.jsx` | `frontend/src/components/` | Matrix header |
| `BusinessSliceOmniviewKpis.jsx` | `frontend/src/components/` | KPI strip (pure presentational) |
| `BusinessSliceOmniviewTable.jsx` | `frontend/src/components/` | Table view (pure presentational) |
| `BusinessSliceOmniviewSidebar.jsx` | `frontend/src/components/` | Sidebar (pure presentational) |
| `BusinessSliceOmniviewInspector.jsx` | `frontend/src/components/` | Cell inspector (POST matrix-issue-action) |
| `BusinessSliceOmniviewReports.jsx` | `frontend/src/components/` | Reports view |
| `OmniviewPriorityPanel.jsx` | `frontend/src/components/` | Priority panel |
| `OmniviewProjectionDrill.jsx` | `frontend/src/components/` | Projection drill-down |
| `OmniviewTopDeviations.jsx` | `frontend/src/components/` | Top deviations panel |
| `OmniviewErrorBoundary.jsx` | `frontend/src/components/` | Error boundary |

### 6.2 Deprecated Components

| Component | Replacement |
|-----------|-------------|
| `BusinessSliceOmniviewProjectionTable.jsx` | `BusinessSliceOmniviewMatrixTable.jsx` (mode='projection') |
| `BusinessSliceOmniviewProjectionCell.jsx` | `BusinessSliceOmniviewMatrixCell.jsx` (mode='projection') |

---

## 7. REFRESH PIPELINE (UPDATED: OV2-CERTIFIED v1.9.0)

### 7.1 Canonical Cascade Chain

The ONLY canonical refresh path for Omniview V2 facts is the bridge cascade:

```
public.trips_2026
    │
    ├──► build_driver_bridge_direct.py (UPSERT)
    │       └──► ops.driver_day_slice_fact  (DRIVER BRIDGE)
    │
    ├──► rebuild_day_from_bridge.py (staging swap: DELETE + INSERT)
    │       └──► ops.real_business_slice_day_fact  (DAY FACT)
    │
    ├──► rebuild_week_from_day_and_bridge.py (staging swap)
    │       └──► ops.real_business_slice_week_fact  (WEEK FACT)
    │
    └──► rebuild_month_from_day_and_bridge.py (staging swap)
            └──► ops.real_business_slice_month_fact  (MONTH FACT)
```

### 7.2 Canonical Orchestrator

| Path | Service/CLI | Trigger |
|------|------------|---------|
| Scheduler | `omniview_cascade_service.py` → `omniview_cascade_refresh` (APScheduler) | Cron daily |
| Manual CLI | `python -m scripts.run_ov2_refresh_cascade --confirm` | Manual approved |

### 7.3 Freshness Governance

Registered in `ops.serving_registry` (migration 221, Phase D.1). Updated by cascade (Phase D.2A). Traceability via `ops.serving_refresh_log` (Phase D.2B).

| Serving Key | Table | Grain |
|-------------|-------|-------|
| `omniview_v2_driver_bridge` | `ops.driver_day_slice_fact` | daily |
| `omniview_v2_real_business_slice_day_fact` | `ops.real_business_slice_day_fact` | daily |
| `omniview_v2_real_business_slice_week_fact` | `ops.real_business_slice_week_fact` | weekly |
| `omniview_v2_real_business_slice_month_fact` | `ops.real_business_slice_month_fact` | monthly |

### 7.4 Blocked / Deprecated Paths (DO NOT USE)

| Path | Status | Reason |
|------|--------|--------|
| `business_slice_real_refresh_job.py` | **BLOCKED** (C.1) | Auto-scheduler fallback removed. Endpoints fail-closed (C.2). |
| `business_slice_incremental_load.py` (writer paths) | **DEPRECATED** (B.1/C.1) | Superseded by bridge cascade. Writer functions marked DEPRECATED. |
| `backfill_runner.py` (writer paths) | **GUARDED** (C.2) | Requires cascade lock + double override. Fail-closed by default. |
| `refresh_business_slice_mvs.py` | **DEPRECATED** (E) | Use canonical cascade. Deprecation banner added. |
| `build_driver_day_slice_fact.py` | **BLOCKED** (B.1) | Renamed to `.legacy.disabled`. Superseded by `build_driver_bridge_direct.py`. |
| `rebuild_week_fact_from_day_fact.py` | **BLOCKED** (B.1) | Renamed to `.legacy.broken`. SUM(DISTINCT) bug. |
| All `.legacy.disabled`/`.legacy.broken` scripts | **BLOCKED** (B.1) | CLI-only scripts renamed. |

### 7.5 Projection Refresh (Separate Concern)

Projection refresh (`serving.omniview_projection_daily_fact`) is a separate pipeline unrelated to Omniview V2 fact governance. Uses `refresh_omniview_projection_facts.py` via APScheduler. Reads from Omniview V2 facts as source data.
    │
    ├──► DELETE+INSERT serving.omniview_projection_daily_fact
    │       partitioned by (plan_version, grain)
    │
    ├──► Sources: ops.v_plan_projection_control_loop (plan)
    │             ops.v_real_business_slice_month_serving (real)
    │             ops.real_business_slice_day_fact (day real)
    │             ops.real_business_slice_week_fact (week real)
```

---

## 8. PROJECTION MODE (Plan vs Real)

### 8.1 Service

`projection_expected_progress_service.py` (3210 lines):
- Reads canonical real data from FACT tables
- Reads plan data from `ops.v_plan_projection_control_loop`
- Applies seasonality curves via `seasonality_curve_engine.py`
- Computes YTD progress, gaps, attainment
- Generates contextual suggestions (prototype — NOT Suggestion Engine)

### 8.2 Seasonality Curves

`seasonality_curve_engine.py`:
- Reads `ops.real_business_slice_day_fact`
- Hierarchical fallback: `city_slice → city_all → country_slice → country_all → linear`

---

## 9. KNOWN GAPS

| Gap | Status | Priority |
|-----|--------|----------|
| Daily/weekly facts lack serving views (only monthly has one) | OPEN | MEDIUM |
| No freshness headers on API responses (`X-Data-Freshness`) | OPEN | LOW |
| Snapshots only exist for month fact (not day/week) | OPEN | LOW |
| Per-KPI freshness in Evolution mode not implemented | OPEN | MEDIUM |
| Alerting engine not activated (CONDITIONAL GO) | OPEN | CONDITIONAL |

---

## 10. CERTIFICATION STATUS

| Certification | Document | Status |
|---------------|----------|--------|
| Control Foundation Closure | `CONTROL_FOUNDATION_CLOSURE_REPORT.md` | CLOSED (11 GO / 1 CONDITIONAL) |
| CF-H1: Revenue Certification | `CF_H1_FINAL_CERTIFICATION.md` | CLOSED |
| CF-H1 Operational Closure | `CF_H1_OPERATIONAL_CLOSURE.md` | CLOSED |
| Phase 1G.2 Closure | `CIERRE_FASE1G2_CONTROL_FOUNDATION_CLOSURE.md` | CLOSED |
| OMNI-P0 Recovery | `ai_current_phase.md` | ACTIVE (REOPENED) |

---

## 11. CROSS-REFERENCES

- [SYSTEM_MAP.md](SYSTEM_MAP.md) — Full system map
- [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — Known constraints
- [OMNIVIEW_CANONICAL_REGISTRY.md](../../OMNIVIEW_CANONICAL_REGISTRY.md) — Full object inventory
- [OMNIVIEW_EXPORT_CONTRACT.md](OMNIVIEW_EXPORT_CONTRACT.md) — Export contract
- [ENGINE_BOUNDARIES.md](ENGINE_BOUNDARIES.md) — Engine boundaries
- [CONTROL_FOUNDATION_LIVING_ARCHITECTURE.md](../control_foundation/CONTROL_FOUNDATION_LIVING_ARCHITECTURE.md) — Living architecture

---

## 12. OPERATIONAL CERTIFICATION STATUS (OV2-VC6A)

**Certified:** 2026-06-14 | **Commit:** `3b03e35` | **Decision:** OPERATIONAL GO

| Area | Status |
|------|--------|
| Visual Cockpit | CERTIFIED |
| KPI Cards (4 KPIs + deltas) | CERTIFIED |
| Trend Layer (ECharts + comparable periods) | CERTIFIED |
| Plan vs Real (attainment bars, guarded) | CERTIFIED WITH SAFEGUARDS |
| Slice Breakdown (ranking + contribution) | CERTIFIED |
| Matrix Detail / Drill | CERTIFIED |
| Monthly Real Data | CERTIFIED |
| Park Attribution | CERTIFIED |
| Export CSV | CERTIFIED |
| V1 Fallback | PRESERVED |
| Shadow Fallback | PRESERVED |
| Diagnostic Engine | READY NEXT (gated) |
| Forecast/Suggestion/Decision/Action/AI | BLOCKED |

Reference: `docs/architecture/OMNIVIEW_V2_OMNI_P0_CLOSURE_REPORT.md`

---

*Generated from live repo audit. Evidence sources: `OMNIVIEW_CANONICAL_REGISTRY.md`, `business_slice_service.py`, `business_slice_omniview_service.py`, `projection_expected_progress_service.py`, `CONTROL_FOUNDATION_LIVING_ARCHITECTURE.md`, `backend/app/routers/ops.py`, `frontend/src/components/BusinessSliceOmniview*.jsx`.*
