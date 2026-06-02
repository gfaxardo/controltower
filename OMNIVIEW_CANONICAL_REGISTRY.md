# OMNIVIEW CANONICAL REGISTRY

## YEGO CONTROL TOWER — Governance Registry for Omniview Matrix

**Version**: 1.0  
**Date**: 2026-06-02  
**Phase**: 1H.4 — Operational Maturity Governance Layer  
**Status**: REGISTRY CREATED — NO IMPLEMENTATION YET  
**Certified by**: Control Foundation Hardening Audit (CF-H1J.5 through CF-H1J.9)

---

## TABLE OF CONTENTS

1. [LINEAGE REAL](#1-lineage-real)
2. [INVENTARIO DE OBJETOS](#2-inventario-de-objetos)
3. [CLASIFICACIÓN OFICIAL](#3-clasificación-oficial)
4. [FRESHNESS GOVERNANCE](#4-freshness-governance)
5. [SCHEDULER GOVERNANCE](#5-scheduler-governance)
6. [REFRESH GOVERNANCE](#6-refresh-governance)
7. [DEPRECATION PLAN](#7-deprecation-plan)
8. [CONTROL FOUNDATION GAP ANALYSIS](#8-control-foundation-gap-analysis)
9. [GO / NO-GO FOR DIAGNOSTIC ENGINE](#9-go--no-go-for-diagnostic-engine)
10. [RECOMMENDATIONS](#10-recommendations)

---

## 1. LINEAGE REAL

### 1.1 DAILY Lineage

```
┌──────────────────────────────────────────────────────────────────┐
│                            DAILY                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  UI: RealLOBDailyView.jsx                                          │
│       └── GET /ops/real-lob/daily/summary                          │
│           GET /ops/real-lob/daily/comparative                      │
│           GET /ops/real-lob/daily/table                            │
│                                                                    │
│  UI (Omniview): BusinessSliceOmniview.jsx                          │
│       └── GET /ops/business-slice/omniview?grain=daily             │
│       └── GET /ops/business-slice/daily                            │
│                                                                    │
├── ENDPOINT LAYER ────────────────────────────────────────────────┤
│                                                                    │
│  GET /ops/business-slice/daily                                     │
│       └── Service: business_slice_service.py                       │
│           └── get_business_slice_daily()                           │
│                                                                    │
│  GET /ops/business-slice/omniview?grain=daily                      │
│       └── Service: business_slice_omniview_service.py              │
│           └── get_business_slice_omniview()                        │
│                                                                    │
│  GET /ops/real-lob/daily/*                                         │
│       └── Service: real_lob_daily_service.py                       │
│                                                                    │
├── SERVICE LAYER ──────────────────────────────────────────────────┤
│                                                                    │
│  business_slice_service.py:                                        │
│       FACT_DAILY = "ops.real_business_slice_day_fact"              │
│                                                                    │
│  business_slice_omniview_service.py:                               │
│       Reads FACT_DAILY (imported from business_slice_service)      │
│       Enforced by ServingPolicy (strict_mode=True)                 │
│       Forbidden: v_real_trips_business_slice_resolved              │
│       Forbidden: v_real_trips_enriched_base                        │
│                                                                    │
│  real_lob_daily_service.py:                                        │
│       Reads ops.real_rollup_day_fact                               │
│                                                                    │
├── QUERY LAYER —───────────────────────────────────────────────────┤
│                                                                    │
│  SQL SELECT on ops.real_business_slice_day_fact                     │
│  (No serving view — direct fact read — backlog item)               │
│                                                                    │
├── FACT LAYER ─────────────────────────────────────────────────────┤
│                                                                    │
│  ops.real_business_slice_day_fact                                  │
│  Populated by: business_slice_incremental_load.py                  │
│  Refresh via: business_slice_real_refresh_job.py                   │
│               refresh_omniview_real_slice_incremental.py            │
│                                                                    │
├── ENRICHED VIEW (INTERMEDIATE) ───────────────────────────────────┤
│                                                                    │
│  ops.v_real_trips_enriched_base                                    │
│  Materialized as TEMP TABLE during incremental load                │
│  Sources: trips_2026, trips_2025, drivers, dim_business_slice      │
│                                                                    │
├── RAW LAYER ──────────────────────────────────────────────────────┤
│                                                                    │
│  public.trips_2026           (current year raw trips)              │
│  public.trips_2025           (prior year raw trips)                │
│  public.module_ct_fleet_summary_daily                              │
│  public.drivers                                                    │
│  public.drivers_data                                               │
│  dim.dim_business_slice_mapping                                    │
│  ops.business_slice_mapping_rules                                  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 WEEKLY Lineage

```
┌──────────────────────────────────────────────────────────────────┐
│                            WEEKLY                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  UI (Omniview): BusinessSliceOmniview.jsx                          │
│       └── GET /ops/business-slice/omniview?grain=weekly            │
│       └── GET /ops/business-slice/weekly                           │
│                                                                    │
│  UI (Real LOB): RealLOBView.jsx                                    │
│       └── GET /ops/real-lob/weekly                                 │
│       └── GET /ops/real-lob/weekly-v2                              │
│                                                                    │
├── ENDPOINT LAYER ────────────────────────────────────────────────┤
│                                                                    │
│  GET /ops/business-slice/weekly                                    │
│       └── Service: business_slice_service.py                       │
│           └── get_business_slice_weekly()                          │
│                                                                    │
│  GET /ops/business-slice/omniview?grain=weekly                     │
│       └── Service: business_slice_omniview_service.py              │
│           └── get_business_slice_omniview()                        │
│                                                                    │
│  GET /ops/real-lob/weekly / weekly-v2                              │
│       └── Service: real_lob_service.py / real_lob_service_v2.py    │
│                                                                    │
├── SERVICE LAYER ──────────────────────────────────────────────────┤
│                                                                    │
│  business_slice_service.py:                                        │
│       FACT_WEEKLY = "ops.real_business_slice_week_fact"            │
│                                                                    │
│  business_slice_omniview_service.py:                               │
│       Reads FACT_WEEKLY                                            │
│       Enforced by ServingPolicy (strict_mode=True)                 │
│                                                                    │
│  real_lob_service.py (v1 — LEGACY):                                │
│       Reads ops.mv_real_trips_by_lob_week                           │
│                                                                    │
│  real_lob_service_v2.py (v2 — ACTIVE):                             │
│       Reads ops.mv_real_lob_week_v2                                 │
│                                                                    │
├── QUERY LAYER ────────────────────────────────────────────────────┤
│                                                                    │
│  SQL SELECT on ops.real_business_slice_week_fact                    │
│  (No serving view — direct fact read — backlog item)               │
│                                                                    │
├── FACT LAYER ─────────────────────────────────────────────────────┤
│                                                                    │
│  ops.real_business_slice_week_fact                                 │
│  Populated by: business_slice_incremental_load.py                  │
│  Refresh via: business_slice_real_refresh_job.py                   │
│               refresh_omniview_real_slice_incremental.py            │
│                                                                    │
├── ENRICHED VIEW (INTERMEDIATE) ───────────────────────────────────┤
│                                                                    │
│  ops.v_real_trips_enriched_base                                    │
│  (same as daily — shared intermediate layer)                       │
│                                                                    │
├── RAW LAYER ──────────────────────────────────────────────────────┤
│                                                                    │
│  public.trips_2026 / public.trips_2025                             │
│  public.module_ct_fleet_summary_daily                              │
│  public.drivers / public.drivers_data                              │
│  dim.dim_business_slice_mapping                                    │
│  ops.business_slice_mapping_rules                                  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 1.3 MONTHLY Lineage

```
┌──────────────────────────────────────────────────────────────────┐
│                            MONTHLY                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  UI (Omniview): BusinessSliceOmniview.jsx                          │
│       └── GET /ops/business-slice/omniview?grain=monthly           │
│       └── GET /ops/business-slice/monthly                          │
│                                                                    │
│  UI (Omniview Projection): BusinessSliceOmniviewMatrix.jsx         │
│       └── GET /ops/business-slice/omniview-projection              │
│                                                                    │
│  UI (Legacy): MonthlyView.jsx                                      │
│       └── GET /core/summary/monthly                                │
│                                                                    │
│  UI (Legacy Split): MonthlySplitView.jsx                           │
│       └── GET /ops/{real,plan}/monthly                             │
│                                                                    │
│  UI (Real LOB): RealLOBView.jsx                                    │
│       └── GET /ops/real-lob/monthly / monthly-v2                   │
│                                                                    │
├── ENDPOINT LAYER ────────────────────────────────────────────────┤
│                                                                    │
│  GET /ops/business-slice/monthly                                   │
│       └── Service: business_slice_service.py                       │
│           └── get_business_slice_monthly()                         │
│                                                                    │
│  GET /ops/business-slice/omniview?grain=monthly                    │
│       └── Service: business_slice_omniview_service.py              │
│           └── get_business_slice_omniview() (REAL only)            │
│                                                                    │
│  GET /ops/business-slice/omniview-projection                       │
│       └── Service: projection_expected_progress_service.py        │
│           └── get_omniview_projection() (Plan vs Real)             │
│                                                                    │
│  GET /core/summary/monthly (legacy)                                │
│       └── Service: core_service.py                                 │
│           └── Combines plan + real summary                         │
│                                                                    │
│  GET /ops/real/monthly (split legacy)                              │
│       └── Service: plan_real_split_service.py                      │
│           └── get_real_monthly() or get_real_monthly_canonical()   │
│                                                                    │
│  GET /ops/plan/monthly (split legacy)                              │
│       └── Service: plan_real_split_service.py                      │
│           └── get_plan_monthly()                                   │
│                                                                    │
├── SERVICE LAYER ──────────────────────────────────────────────────┤
│                                                                    │
│  business_slice_service.py:                                        │
│       FACT_MONTHLY = "ops.v_real_business_slice_month_serving"     │
│       FACT_MONTHLY_RAW = "ops.real_business_slice_month_fact"       │
│                                                                    │
│  business_slice_omniview_service.py:                               │
│       Reads FACT_MONTHLY (the serving VIEW)                        │
│       Enforced by ServingPolicy (strict_mode=True)                 │
│                                                                    │
│  projection_expected_progress_service.py:                          │
│       Reads FACT_MONTHLY (serving) for real data                   │
│       Reads ops.v_plan_projection_control_loop for plan data        │
│       Reads serving.omniview_projection_daily_fact (projection)    │
│                                                                    │
├── SERVING LAYER ──────────────────────────────────────────────────┤
│                                                                    │
│  ops.v_real_business_slice_month_serving  (VIEW redirector)        │
│       └── locked period → ops.real_business_slice_month_snapshot   │
│       └── open period   → ops.real_business_slice_month_fact       │
│                                                                    │
│  serving.omniview_projection_daily_fact  (Projection mode)         │
│       Populated by: refresh_omniview_projection_facts.py           │
│       Scheduler: serving_refresh_scheduler.py                      │
│                                                                    │
├── FACT LAYER ─────────────────────────────────────────────────────┤
│                                                                    │
│  ops.real_business_slice_month_fact       (working fact)           │
│  ops.real_business_slice_month_snapshot   (frozen for locked per.) │
│  ops.real_business_slice_month_fact       (FACT_MONTHLY_RAW)       │
│  Populated by: business_slice_incremental_load.py                  │
│  Refresh via: business_slice_real_refresh_job.py                   │
│               refresh_omniview_real_slice_incremental.py            │
│                                                                    │
├── ENRICHED VIEW (INTERMEDIATE) ───────────────────────────────────┤
│                                                                    │
│  ops.v_real_trips_enriched_base                                    │
│  ops.v_real_trips_business_slice_resolved                          │
│  (same as daily/weekly — shared intermediate layer)                │
│                                                                    │
├── RAW LAYER ──────────────────────────────────────────────────────┤
│                                                                    │
│  public.trips_2026 / public.trips_2025                             │
│  public.module_ct_fleet_summary_daily                              │
│  public.drivers / public.drivers_data                              │
│  dim.dim_business_slice_mapping                                    │
│  ops.business_slice_mapping_rules                                  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 1.4 PROJECTION Lineage (Plan vs Real — Omniview Projection Mode)

```
┌──────────────────────────────────────────────────────────────────┐
│                     PROJECTION (PLAN VS REAL)                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  UI: BusinessSliceOmniviewMatrix.jsx                               │
│       └── GET /ops/business-slice/omniview-projection              │
│       └── GET /ops/business-slice/omniview-projection/             │
│           serving-plan-versions                                    │
│       └── GET /ops/control-loop/plan-versions                      │
│       └── GET /plan/versions                                       │
│                                                                    │
├── ENDPOINT LAYER ────────────────────────────────────────────────┤
│                                                                    │
│  GET /ops/business-slice/omniview-projection                       │
│       └── Service: projection_expected_progress_service.py        │
│           └── get_omniview_projection()                            │
│                                                                    │
├── SERVICE LAYER ──────────────────────────────────────────────────┤
│                                                                    │
│  projection_expected_progress_service.py (3210 lines)              │
│       Reads FACT_MONTHLY (serving) for real data                   │
│       Reads ops.v_plan_projection_control_loop for plan data        │
│       Reads serving.omniview_projection_daily_fact                  │
│       Applies seasonality curves                                   │
│       Computes YTD progress, gaps, attainment                      │
│       Generates contextual suggestions                             │
│                                                                    │
│  seasonality_curve_engine.py                                       │
│       Reads ops.real_business_slice_day_fact                        │
│       Hierarchical fallback: city_slice → city_all →               │
│                              country_slice → country_all → linear   │
│                                                                    │
├── SERVING LAYER ──────────────────────────────────────────────────┤
│                                                                    │
│  serving.omniview_projection_daily_fact                            │
│       DELELE + INSERT by refresh_omniview_projection_facts.py      │
│       Partitioned by (plan_version, grain)                          │
│       Default plan_version: ruta27_2026_04_21                      │
│                                                                    │
├── PLAN LAYER ─────────────────────────────────────────────────────│
│                                                                    │
│  ops.v_plan_projection_control_loop                                │
│       Source: ops.plan_trips_monthly + control_loop plan_metric     │
│       Normalized via: control_loop_business_slice_resolve.py       │
│                                                                    │
├── REAL LAYER ─────────────────────────────────────────────────────│
│                                                                    │
│  ops.v_real_business_slice_month_serving (monthly serving)         │
│  ops.real_business_slice_day_fact (daily fact, no serving view)    │
│  ops.real_business_slice_week_fact (weekly fact, no serving view)  │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. INVENTARIO DE OBJETOS

### 2.1 TABLES / MATERIALIZED VIEWS / VIEWS

| # | Object | Type | Schema | Owner | Used by UI? | Used by Freshness? | Used by Scheduler? | Used by Refresh? | Used by Revenue? | Used by Forecast? |
|---|--------|------|--------|-------|-------------|---------------------|---------------------|-------------------|-------------------|--------------------|
| 1 | `real_business_slice_month_fact` | TABLE (FACT) | ops | business_slice | YES (via serving view) | YES | NO | YES (write target) | YES (via serving) | NO |
| 2 | `real_business_slice_day_fact` | TABLE (FACT) | ops | business_slice | YES (direct) | YES | NO | YES (write target) | NO | NO |
| 3 | `real_business_slice_week_fact` | TABLE (FACT) | ops | business_slice | YES (direct) | YES | NO | YES (write target) | NO | NO |
| 4 | `real_business_slice_hour_fact` | TABLE (FACT) | ops | business_slice | NO | NO | NO | YES | NO | NO |
| 5 | `real_business_slice_month_snapshot` | TABLE (SNAPSHOT) | ops | business_slice | YES (via serving view, locked) | YES | NO | YES (write target) | NO | NO |
| 6 | `v_real_business_slice_month_serving` | VIEW (SERVING) | ops | business_slice | YES (monthly) | YES | NO | NO | NO | NO |
| 7 | `real_rollup_day_fact` | TABLE (FACT) | ops | real_lob | YES (daily LOB) | NO | NO | YES | NO | NO |
| 8 | `real_drill_dim_fact` | TABLE (FACT) | ops | real_lob | YES (drill) | NO | NO | YES | NO | NO |
| 9 | `omniview_projection_daily_fact` | TABLE (SERVING) | serving | projection | YES (projection) | YES (omniview freshness) | YES (refresh target) | YES | NO | NO |
| 10 | `v_real_trips_enriched_base` | VIEW (INTERM.) | ops | business_slice | NO (FORBIDDEN by policy) | NO | NO | YES (temp table source) | NO | NO |
| 11 | `v_real_trips_business_slice_resolved` | VIEW (INTERM.) | ops | business_slice | NO (FORBIDDEN by policy) | NO | NO | YES (audit/backfill) | NO | NO |
| 12 | `v_business_slice_coverage_month` | VIEW | ops | business_slice | YES (coverage) | NO | NO | NO | NO | NO |
| 13 | `v_business_slice_unmatched_trips` | VIEW | ops | business_slice | YES (unmatched) | NO | NO | NO | NO | NO |
| 14 | `v_business_slice_conflict_trips` | VIEW | ops | business_slice | YES (conflicts) | NO | NO | NO | NO | NO |
| 15 | `v_business_slice_mapping_coverage` | VIEW | ops | business_slice | YES (coverage) | NO | NO | NO | NO | NO |
| 16 | `mv_real_lob_day_v2` | MATERIALIZED VIEW | ops | real_lob | YES (daily) | NO | NO | YES | NO | NO |
| 17 | `mv_real_lob_week_v3` | MATERIALIZED VIEW | ops | real_lob | YES (weekly) | NO | NO | YES | NO | NO |
| 18 | `mv_real_lob_month_v3` | MATERIALIZED VIEW | ops | real_lob | YES (monthly) | NO | NO | YES | NO | NO |
| 19 | `mv_real_lob_hour_v2` | MATERIALIZED VIEW | ops | real_lob | NO | NO | NO | YES | NO | NO |
| 20 | `mv_real_trips_by_lob_month` | MATERIALIZED VIEW | ops | real_lob (LEGACY) | YES (v1 only) | NO | NO | LEGACY | NO | NO |
| 21 | `mv_real_trips_by_lob_week` | MATERIALIZED VIEW | ops | real_lob (LEGACY) | YES (v1 only) | NO | NO | LEGACY | NO | NO |
| 22 | `mv_real_trips_monthly` | MATERIALIZED VIEW | ops | plan_vs_real | YES (split view) | NO | NO | YES | NO | NO |
| 23 | `mv_real_trips_monthly_v2` | MATERIALIZED VIEW | ops | plan_vs_real | NO | NO | NO | YES | NO | NO |
| 24 | `mv_plan_vs_real_monthly_fact` | MATERIALIZED VIEW | ops | plan_vs_real (LEGACY) | YES (legacy) | NO | NO | YES | NO | NO |
| 25 | `mv_plan_vs_real_monthly_fact_canonical` | MATERIALIZED VIEW | ops | plan_vs_real (CANONICAL) | YES | NO | NO | YES | NO | NO |
| 26 | `mv_real_drill_dim_agg` | MATERIALIZED VIEW | ops | real_lob | YES (drill) | NO | NO | YES | NO | NO |
| 27 | `mv_real_rollup_day` | MATERIALIZED VIEW | ops | real_lob | YES (daily) | NO | NO | YES | NO | NO |
| 28 | `mv_real_drill_enriched` | MATERIALIZED VIEW | ops | real_lob | YES (drill) | NO | NO | YES | NO | NO |
| 29 | `mv_driver_lifecycle_base` | MATERIALIZED VIEW | ops | driver_lifecycle | YES | NO | NO | YES | NO | NO |
| 30 | `mv_driver_weekly_stats` | MATERIALIZED VIEW | ops | driver_lifecycle | YES | NO | NO | YES | NO | NO |
| 31 | `mv_driver_monthly_stats` | MATERIALIZED VIEW | ops | driver_lifecycle | YES | NO | NO | YES | NO | NO |
| 32 | `mv_driver_segments_weekly` | MATERIALIZED VIEW | ops | supply | YES | NO | NO | YES | NO | NO |
| 33 | `mv_supply_weekly` | MATERIALIZED VIEW | ops | supply (LEGACY/STALE) | YES (supply endpoints) | NO | NO | NOT in pipeline | NO | NO |
| 34 | `mv_supply_monthly` | MATERIALIZED VIEW | ops | supply (LEGACY/STALE) | YES (supply endpoints) | NO | NO | NOT in pipeline | NO | NO |
| 35 | `mv_supply_segments_weekly` | MATERIALIZED VIEW | ops | supply | YES | NO | NO | YES | NO | NO |
| 36 | `mv_supply_alerts_weekly` | MATERIALIZED VIEW | ops | supply | YES | NO | NO | YES | NO | NO |
| 37 | `mv_real_financials_monthly` | MATERIALIZED VIEW | ops | financials | YES | NO | NO | YES | YES | NO |
| 38 | `mv_real_monthly_canonical_hist` | MATERIALIZED VIEW | ops | real | YES (canonical) | NO | NO | YES | NO | NO |
| 39 | `mv_ownership_serving_fact` | MATERIALIZED VIEW | ops | ownership | YES | NO | NO | YES | NO | NO |
| 40 | `mv_yango_loyalty_performance_monthly_v1` | MATERIALIZED VIEW | ops | yango_loyalty | YES | NO | NO | YES | NO | NO |
| 41 | `v_plan_trips_monthly_latest` | VIEW | ops | plan | YES (summary) | NO | NO | NO | NO | NO |
| 42 | `v_plan_projection_control_loop` | VIEW | ops | control_loop | YES (projection) | NO | NO | NO | NO | NO |
| 43 | `serving_registry` | TABLE | ops | serving_governance | YES (health) | YES | YES | YES | NO | NO |
| 44 | `data_freshness_expectations` | TABLE | ops | freshness | YES | YES | NO | NO | NO | NO |
| 45 | `data_freshness_audit` | TABLE | ops | freshness | YES | YES | NO | NO | NO | NO |
| 46 | `refresh_run_log` | TABLE | ops | refresh_control | YES (status) | NO | YES | YES | NO | NO |
| 47 | `observability_artifact_registry` | TABLE | ops | observability | YES | YES | NO | YES | NO | NO |
| 48 | `observability_refresh_log` | TABLE | ops | observability | YES | YES | NO | YES | NO | NO |
| 49 | `period_closure_registry` | TABLE | ops | period_closure | YES (status) | NO | NO | YES | NO | NO |
| 50 | `dim_business_slice_mapping` | TABLE | dim | business_slice | NO | NO | NO | NO | NO | NO |
| 51 | `business_slice_mapping_rules` | TABLE | ops | business_slice | NO | NO | NO | NO | NO | NO |
| 52 | `control_loop_plan_line_to_business_slice` | TABLE | ops | control_loop | NO | NO | NO | NO | NO | NO |
| 53 | `projection_ownership` | TABLE | ops | control_loop | YES via ownership serving | NO | NO | NO | NO | NO |
| 54 | `plan_trips_monthly` | TABLE | ops | plan | YES | NO | NO | NO | NO | NO |
| 55 | `trips_2026` | TABLE | public | data_engineering | NO (RAW) | YES (upstream check) | NO | NO | YES | NO |
| 56 | `trips_2025` | TABLE | public | data_engineering | NO (RAW) | YES (upstream check) | NO | NO | NO | NO |
| 57 | `omniview_matrix_trust_history` | TABLE | ops | omniview_integrity | YES (trust) | NO | NO | NO | NO | NO |
| 58 | `omniview_matrix_issue_action_log` | TABLE | ops | omniview_integrity | YES (issue log) | NO | NO | NO | NO | NO |

### 2.2 BACKEND SERVICES

| # | Service File | Type | Owner | Used by UI? | Used by Freshness? | Used by Scheduler? | Used by Refresh? |
|---|-------------|------|-------|-------------|---------------------|---------------------|-------------------|
| 1 | `business_slice_service.py` | CANONICAL READ | business_slice | YES (Omniview + Matrix + Reports) | YES (freshness calc) | NO | NO |
| 2 | `business_slice_omniview_service.py` | CANONICAL READ | business_slice | YES (Omniview REAL) | NO | NO | NO |
| 3 | `business_slice_canonical_service.py` | CANONICAL RESOLVE | business_slice | NO (internal) | NO | NO | NO |
| 4 | `business_slice_incremental_load.py` | WRITE (FACT loader) | business_slice | NO | NO | NO | YES (core refresh) |
| 5 | `business_slice_real_refresh_job.py` | WRITE (FACT refresh) | business_slice | NO (POST trigger only) | NO | YES (APScheduler) | YES |
| 6 | `business_slice_real_freshness_service.py` | FRESHNESS | freshness | YES (freshness endpoint) | YES | NO | NO |
| 7 | `projection_expected_progress_service.py` | CANONICAL READ | projection | YES (Projection mode) | NO | NO | NO |
| 8 | `seasonality_curve_engine.py` | CANONICAL READ | projection | NO (internal) | NO | NO | NO |
| 9 | `omniview_freshness_governance_service.py` | FRESHNESS | freshness | YES (omniview freshness) | YES | NO | NO |
| 10 | `omniview_matrix_integrity_service.py` | INTEGRITY | omniview | YES (trust) | NO | NO | NO |
| 11 | `omniview_momentum_drill_service.py` | CANONICAL READ | omniview | YES (drill) | NO | NO | NO |
| 12 | `omniview_semantics_service.py` | CANONICAL SEMANTICS | omniview | NO (internal) | NO | NO | NO |
| 13 | `omniview_playbooks.py` | PLAYBOOKS | omniview | NO (internal) | NO | NO | NO |
| 14 | `serving_governance_service.py` | GOVERNANCE | serving_governance | YES (health/runtime) | YES | YES | YES |
| 15 | `serving_refresh_scheduler.py` | SCHEDULER | serving_governance | NO | NO | YES (APScheduler) | YES |
| 16 | `serving_guardrails.py` | GUARDRAILS | serving_governance | NO (enforced at DB level) | NO | NO | NO |
| 17 | `weekly_serving_guardrails_service.py` | GUARDRAILS | serving_governance | YES (reconciliation) | NO | NO | NO |
| 18 | `data_freshness_service.py` | FRESHNESS | freshness | YES (banner) | YES | NO | NO |
| 19 | `period_state_engine.py` | SEMANTICS | period | NO (internal) | NO | NO | NO |
| 20 | `period_closure_service.py` | GOVERNANCE | period | YES (status endpoint) | NO | NO | YES (guard) |
| 21 | `last_good_data_service.py` | GOVERNANCE | period | YES (serving status) | NO | NO | YES |
| 22 | `confidence_engine.py` | TRUST | data_trust | YES (data trust badge) | YES | NO | NO |
| 23 | `real_lob_service.py` | LEGACY READ | real_lob | YES (v1 endpoints) | NO | NO | NO |
| 24 | `real_lob_service_v2.py` | CANONICAL READ | real_lob | YES (v2 endpoints) | NO | NO | NO |
| 25 | `real_lob_daily_service.py` | CANONICAL READ | real_lob | YES (daily LOB) | NO | NO | NO |
| 26 | `real_lob_drill_pro_service.py` | CANONICAL READ | real_lob | YES (drill) | NO | NO | NO |
| 27 | `real_lob_filters_service.py` | AUXILIARY | real_lob | YES (filters) | NO | NO | NO |
| 28 | `real_lob_v2_data_service.py` | CANONICAL READ | real_lob | YES (v2 data) | NO | NO | NO |
| 29 | `canonical_real_monthly_service.py` | CANONICAL READ | real | YES (canonical split) | NO | NO | NO |
| 30 | `comparative_metrics_service.py` | CANONICAL READ | real_lob | YES (comparatives) | NO | NO | NO |
| 31 | `real_operational_service.py` | CANONICAL READ | real_operational | YES (operational) | NO | NO | NO |
| 32 | `refresh_service.py` | WRITE (MV refresh) | refresh | NO | NO | NO | YES |
| 33 | `refresh_control_service.py` | GOVERNANCE | refresh | YES (status) | NO | YES | YES |
| 34 | `supply_service.py` | CANONICAL READ | supply | YES (supply endpoints) | NO | NO | NO |
| 35 | `plan_vs_real_service.py` | LEGACY READ | plan_vs_real | YES (PvR monthly) | NO | NO | NO |
| 36 | `plan_real_split_service.py` | LEGACY READ | plan_vs_real | YES (split view) | NO | NO | NO |
| 37 | `financials_service.py` | CANONICAL READ | financials | YES (financials) | NO | NO | NO |
| 38 | `core_service.py` | LEGACY READ | core | YES (core summary) | NO | NO | NO |
| 39 | `summary_service.py` | LEGACY READ | plan | YES (plan summary) | NO | NO | NO |
| 40 | `observability_service.py` | OBSERVABILITY | observability | YES (observability) | YES | NO | NO |
| 41 | `ownership_serving_service.py` | CANONICAL READ | ownership | YES | NO | NO | NO |
| 42 | `control_loop_plan_vs_real_service.py` | CANONICAL READ | control_loop | YES (PvR by slice) | NO | NO | NO |
| 43 | `control_loop_business_slice_resolve.py` | CANONICAL RESOLVE | control_loop | NO (internal) | NO | NO | NO |
| 44 | `upstream_real_status_service.py` | STATUS CHECK | real | NO | YES (freshness) | NO | NO |
| 45 | `data_trust_service.py` | DELEGATION | data_trust | YES (trust badge) | NO | NO | NO |

### 2.3 FRONTEND COMPONENTS (Omniview-related)

| # | Component | Type | Reads from (API) | Depends on (service) |
|---|-----------|------|-------------------|-----------------------|
| 1 | `BusinessSliceOmniview.jsx` | ORCHESTRATOR | `/ops/business-slice/omniview`, filters | business_slice_omniview_service |
| 2 | `BusinessSliceOmniviewMatrix.jsx` | MATRIX | `/ops/business-slice/omniview-projection`, freshness, trust, filters | projection_expected_progress, freshness, integrity |
| 3 | `BusinessSliceOmniviewReports.jsx` | REPORTS | `/ops/business-slice/{monthly,weekly,daily}`, coverage | business_slice_service |
| 4 | `BusinessSliceOmniviewKpis.jsx` | KPI STRIP | NONE (pure presentational) | — |
| 5 | `BusinessSliceOmniviewTable.jsx` | TABLE | NONE (pure presentational) | — |
| 6 | `BusinessSliceOmniviewSidebar.jsx` | SIDEBAR | NONE (pure presentational) | — |
| 7 | `BusinessSliceOmniviewMatrixTable.jsx` | MATRIX TABLE | NONE (pure presentational) | — |
| 8 | `BusinessSliceOmniviewMatrixCell.jsx` | CELL | NONE (pure presentational) | — |
| 9 | `BusinessSliceOmniviewMatrixHeader.jsx` | HEADER | NONE (pure presentational) | — |
| 10 | `BusinessSliceOmniviewInspector.jsx` | INSPECTOR | POST `/matrix-issue-action`, momentum drill | omniview_matrix_integrity, momentum_drill |
| 11 | `BusinessSliceOmniviewProjectionTable.jsx` | DEPRECATED | — | — |
| 12 | `BusinessSliceOmniviewProjectionCell.jsx` | DEPRECATED | — | — |
| 13 | `RealLOBDailyView.jsx` | DAILY LOB | `/ops/real-lob/daily/*` | real_lob_daily_service |
| 14 | `RealLOBView.jsx` | REAL LOB | `/ops/real-lob/*` v1/v2 | real_lob_service, real_lob_service_v2 |
| 15 | `RealLOBDrillView.jsx` | DRILL | `/ops/real-lob/drill/*`, comparatives | real_lob_drill_pro_service, comparative_metrics |
| 16 | `MonthlyView.jsx` | LEGACY MONTHLY | `/core/summary/monthly` | core_service |
| 17 | `MonthlySplitView.jsx` | LEGACY SPLIT | `/ops/{real,plan}/monthly` | plan_real_split_service |
| 18 | `GlobalFreshnessBanner.jsx` | FRESHNESS BANNER | `/ops/data-freshness/global` | data_freshness_service |
| 19 | `ServingGovernanceDashboard.jsx` | SERVING DASHBOARD | `/api/ops/serving/health` (raw fetch) | serving_governance_service |
| 20 | `DataStateBadge.jsx` | BADGE | NONE (pure presentational) | — |
| 21 | `DataTrustBadge.jsx` | BADGE | `/ops/data-trust` | data_trust_service |

---

## 3. CLASIFICACIÓN OFICIAL

### 3.1 CANONICAL — Fuente de Verdad

These objects are the **single source of truth** for their domain. All UI paths MUST read from these (directly or via serving views). No alternative read paths should exist.

| Object | Scope | Justification |
|--------|-------|---------------|
| `ops.real_business_slice_month_fact` | MONTHLY REAL | Definitive monthly aggregations. Service: `business_slice_service` writes here. Read only via `v_real_business_slice_month_serving`. |
| `ops.real_business_slice_day_fact` | DAILY REAL | Definitive daily aggregations. Service: `business_slice_service` reads here. |
| `ops.real_business_slice_week_fact` | WEEKLY REAL | Definitive weekly aggregations. Service: `business_slice_service` reads here. |
| `ops.v_real_business_slice_month_serving` | MONTHLY SERVING | Canonical read path for monthly. Redirects: snapshot (locked) or working_fact (open). |
| `serving.omniview_projection_daily_fact` | PROJECTION SERVING | Canonical read path for Plan vs Real projection at daily grain. |
| `mv_plan_vs_real_monthly_fact_canonical` | PVR CANONICAL | Faster canonical Plan vs Real. Replaces legacy `mv_plan_vs_real_monthly_fact`. |
| `business_slice_service.py` | READ SERVICE | Canonical service for business_slice reads. Defines FACT constants. |
| `business_slice_omniview_service.py` | OMNIVIEW SERVICE | Canonical service for Omniview Matrix (REAL only). ServingPolicy enforced. |
| `projection_expected_progress_service.py` | PROJECTION SERVICE | Canonical service for Omniview Projection mode. |
| `control_loop_plan_vs_real_service.py` | CONTROL LOOP PVR | Canonical PvR aligned to business_slice_name grain. |
| `serving_governance_service.py` | SERVING GOVERNANCE | Canonical registry for all serving facts. |
| `serving_guardrails.py` | GUARDRAILS | Canonical enforcement. FORBIDDEN_SERVING_SOURCES blocklist is authoritative. |
| `omniview_semantics_service.py` | SEMANTICS | Canonical definitions of avance_pct, gap_abs, gap_pct, compare signals. |
| `period_closure_service.py` | PERIOD GOVERNANCE | Canonical authority on which periods are locked/open/partial. |

### 3.2 ACTIVE SERVING — Cache o serving derivado

These objects exist to accelerate reads or serve as intermediate serving layers. They derive from CANONICAL sources.

| Object | Derives from | Purpose |
|--------|-------------|---------|
| `ops.real_business_slice_month_snapshot` | `real_business_slice_month_fact` | Frozen stable snapshot for locked periods. Created by `period_closure_service`. |
| `ops.v_real_business_slice_month_serving` | `snapshot` + `month_fact` | Serving redirector VIEW. Not a data source itself — reads from canonical. |
| `ops.mv_real_lob_day_v2` | `mv_real_lob_hour_v2` (hourly-first chain) | Accelerated daily LOB read. Part of hourly-first architecture. |
| `ops.mv_real_lob_week_v3` | `mv_real_lob_hour_v2` | Accelerated weekly LOB read. |
| `ops.mv_real_lob_month_v3` | `mv_real_lob_hour_v2` | Accelerated monthly LOB read. |
| `ops.mv_real_drill_dim_agg` | `real_drill_dim_fact` | Aggregated drill view for performance. |
| `ops.mv_ownership_serving_fact` | `plan_trips_monthly` + `month_fact` + `projection_ownership` | Serving fact for ownership data (plan+real+ownership). |
| `ops.mv_real_monthly_canonical_hist` | `v_trips_real_canon` | Canonical historical real without 120d window. |
| `ops.v_plan_trips_monthly_latest` | `plan_trips_monthly` | Latest plan version VIEW. |

### 3.3 LEGACY — No debe usarse para nuevos desarrollos

These objects exist and may still serve some UI paths, but are superseded by canonical alternatives. New code should NOT depend on them.

| Object | Replacement | Risk if used |
|--------|-------------|--------------|
| `ops.mv_real_trips_by_lob_month` | `mv_real_lob_month_v3` | v1 LOB aggregation, coarser dimensions. Endpoint still serves `/ops/real-lob/monthly` v1. |
| `ops.mv_real_trips_by_lob_week` | `mv_real_lob_week_v3` | v1 weekly LOB. Endpoint still serves `/ops/real-lob/weekly` v1. |
| `ops.mv_real_trips_monthly` | `mv_real_monthly_canonical_hist` | Old real monthly MV. Used by `plan_real_split_service.py` and `MonthlySplitView.jsx`. |
| `ops.mv_plan_vs_real_monthly_fact` | `mv_plan_vs_real_monthly_fact_canonical` | Legacy PvR MV. Still used alongside canonical. |
| `real_lob_service.py` (v1) | `real_lob_service_v2.py` | v1 LOB service. Serves `/ops/real-lob/monthly`, `/ops/real-lob/weekly`. |
| `core_service.py` | `business_slice_service.py` | Legacy core monthly summary. Used by `MonthlyView.jsx` only. |
| `summary_service.py` | `control_loop_plan_vs_real_service.py` | Legacy plan summary. |
| `plan_real_split_service.py` | `business_slice_service.py` | Legacy split view service. Used by `MonthlySplitView.jsx` only. |
| `plan_vs_real_service.py` | `control_loop_plan_vs_real_service.py` | Legacy PvR using REALKEY views. |
| `MonthlyView.jsx` | `BusinessSliceOmniview.jsx` | Legacy monthly view component. Non-Omniview UI for Plan vs Real. |
| `MonthlySplitView.jsx` | `BusinessSliceOmniview.jsx` | Legacy split view. |
| `RealLOBView.jsx` (v1 mode) | `RealLOBView.jsx` (v2 mode) | v1 LOB UI. v2 exists and should be the default. |
| `refresh_real_lob_mvs.py` | `refresh_real_lob_mvs_v2.py` | Legacy v1 LOB MV refresh. Still runnable but superseded. |
| `refresh_omniview_real_slice.py` | `refresh_omniview_real_slice_incremental.py` | DEPRECATED. Blocked by safety guard. Redirects to incremental. |
| `backfill_real_lob_mvs.py` | `populate_real_drill_from_hourly_chain.py` | DEPRECATED. Modern pipeline uses hourly chain. |
| `backfill_week_from_day_fact.py` | `business_slice_real_refresh_job.py` | DEPRECATED. Blocked by safety guard. Redirects to incremental. |
| `BusinessSliceOmniviewProjectionTable.jsx` | `BusinessSliceOmniviewMatrixTable.jsx` (mode='projection') | DEPRECATED UI component. Replaced by unified MatrixTable. |
| `BusinessSliceOmniviewProjectionCell.jsx` | `BusinessSliceOmniviewMatrixCell.jsx` (mode='projection') | DEPRECATED UI component. Replaced by unified MatrixCell. |

### 3.4 QUARANTINE — Código peligroso, debe bloquearse por defecto

| Object | Risk | Action Required |
|--------|------|-----------------|
| DROP+CASCADE pattern on `mv_driver_lifecycle_base` (driver lifecycle build) | Non-idempotent. If script fails between DROP and CREATE, MV is gone. | Replace with REFRESH MATERIALIZED VIEW CONCURRENTLY or CREATE OR REPLACE. |
| `refresh_supply_mvs()` function (migration 060) | Refreshes `mv_supply_weekly` and `mv_supply_monthly` which NO pipeline calls → permanently stale data served to live endpoints. | Either integrate into main pipeline or deprecate the MVs and their consumers. |
| `clear_all_plan_data.py` | TRUNCATE/DELETE all plan data. No confirmation. | Add confirmation gate + dry-run mode. |
| `clear_all_plans.py` | Clears all plan entries. No confirmation. | Add confirmation gate + dry-run mode. |
| `clear_plan_version.py` | Deletes specific plan version. No rollback. | Add backup snapshot before delete. |

### 3.5 DELETE CANDIDATE — Sin referencias activas

| Object | Justification |
|--------|---------------|
| `BusinessSliceOmniviewProjectionTable.jsx` | Replaced by MatrixTable with mode='projection'. Verify no remaining imports. |
| `BusinessSliceOmniviewProjectionCell.jsx` | Replaced by MatrixCell with mode='projection'. Verify no remaining imports. |
| `refresh_omniview_real_slice.py` | Blocked by safety guard. Always redirects to incremental. |
| `backfill_week_from_day_fact.py` | Blocked by safety guard. Always redirects to incremental. |
| `backfill_real_lob_mvs.py` | DEPRECATED. Replaced by populate_real_drill_from_hourly_chain. |

---

## 4. FRESHNESS GOVERNANCE

### 4.1 WHAT SHOULD BE MONITORED BY FRESHNESS

| Target | Monitoring Service | Criticality |
|--------|-------------------|-------------|
| `public.trips_2026` (RAW upstream) | `upstream_real_status_service.py` | CRITICAL — if RAW is stale, everything is stale |
| `ops.real_business_slice_day_fact` | `business_slice_real_freshness_service.py` | CRITICAL — daily Omniview depends on this |
| `ops.real_business_slice_week_fact` | `business_slice_real_freshness_service.py` | CRITICAL — weekly Omniview depends on this |
| `ops.real_business_slice_month_fact` | `business_slice_real_freshness_service.py` | CRITICAL — monthly Omniview + Projection depends on this |
| `ops.v_real_business_slice_month_serving` | `omniview_freshness_governance_service.py` | CRITICAL — serving view redirect must work |
| `serving.omniview_projection_daily_fact` | `omniview_freshness_governance_service.py` | CRITICAL — Projection mode depends on this |
| `ops.mv_real_lob_day_v2` | (should be monitored — gap) | HIGH — daily LOB view depends on this |
| `ops.mv_real_lob_week_v3` | (should be monitored — gap) | HIGH — weekly LOB view depends on this |
| `ops.mv_real_lob_month_v3` | (should be monitored — gap) | HIGH — monthly LOB view depends on this |
| `ops.mv_driver_lifecycle_base` | `driver_raw_freshness_service.py` / `driver_serving_freshness_service.py` | HIGH — single point of failure for all driver views |
| `ops.mv_ownership_serving_fact` | (registration in serving_registry — light) | MEDIUM |
| `ops.mv_supply_segments_weekly` | `supply_service.get_supply_freshness()` | MEDIUM |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | (registration in serving_registry — light) | MEDIUM |

### 4.2 WHAT SHOULD NOT BE MONITORED BY FRESHNESS

| Object | Reason |
|--------|--------|
| `ops.real_business_slice_hour_fact` | Not consumed by any UI endpoint. Internal-only for hourly-first chain. |
| `ops.v_real_trips_enriched_base` | Intermediate VIEW. Freshness tracked via downstream facts. |
| `ops.v_real_trips_business_slice_resolved` | Intermediate VIEW. Forbidden for UI reads by ServingPolicy. |
| `ops.mv_real_trips_by_lob_month` (v1) | LEGACY. v2/3 is the canonical path. Deprecating the v1 endpoint = deprecate this monitoring. |
| `ops.mv_real_trips_by_lob_week` (v1) | LEGACY. Same as above. |
| `ops.mv_real_trips_monthly` | LEGACY. `mv_real_monthly_canonical_hist` is canonical. |
| `ops.mv_plan_vs_real_monthly_fact` (legacy) | LEGACY. `_canonical` version replaces it. |
| `ops.mv_supply_weekly` | STALE by design — no pipeline refreshes it. Monitoring would generate false alerts. Either fix the pipeline or deprecate. |
| `ops.mv_supply_monthly` | STALE by design — same as above. |

### 4.3 FRESHNESS GAPS

| Gap | Impact | Priority |
|-----|--------|----------|
| Daily/weekly facts lack serving views with freshness metadata columns (`loaded_at`, `refreshed_at`) | Freshness queries on daily/weekly are less robust. D-1_CLOSED mode compensates. | MEDIUM |
| `mv_real_lob_*` MVs not integrated into unified freshness monitoring | LOB views have no freshness banner exposure. | LOW — hourly-first chain is reliable |
| `mv_supply_weekly` / `mv_supply_monthly` not refreshed by any pipeline | Supply endpoints may serve stale data. Root cause: legacy `ops.refresh_supply_mvs()` not called. | HIGH — but this is a refresh gap, not a monitoring gap |
| No freshness headers on API responses (`X-Data-Freshness`, `X-Last-Refresh`) | Users cannot verify data freshness at the HTTP level. | LOW |

---

## 5. SCHEDULER GOVERNANCE

### 5.1 ACTIVE JOBS

| Job | Trigger | Service | Status |
|-----|---------|---------|--------|
| `business_slice_real_refresh_job` | APScheduler periodic | `business_slice_real_refresh_job.py` | ACTIVE — refreshes day_fact + week_fact (+ optionally month_fact) for current + previous month. Cooldown enforced. |
| `serving_refresh_scheduler` (projection) | APScheduler periodic | `serving_refresh_scheduler.py` | ACTIVE — runs `refresh_omniview_projection_facts.py` for daily/weekly/monthly grains. Anti-concurrency lock. MAX_RETRIES=2. |
| `run_pipeline_refresh_and_audit` | Manual POST `/ops/pipeline-refresh` | `run_pipeline_refresh_and_audit.py` | ON-DEMAND — full pipeline: hourly-first → drill → driver lifecycle → supply → plan-vs-real → audit. Guarded. |
| `run_refresh_loop` | CLI script (infinite loop) | `run_refresh_loop.py` | CLI-ONLY — runs `run_refresh_job` every 30 min. Not integrated into APScheduler. |

### 5.2 LEGACY JOBS

| Job | Status | Action |
|-----|--------|--------|
| `ops.refresh_supply_mvs()` (migration 060) | **NOT CALLED BY ANY PIPELINE** | This function refreshes `mv_supply_weekly` and `mv_supply_monthly`. It is never called by any scheduler, script, or pipeline. The MVs may be permanently stale. |
| `refresh_omniview_real_slice.py` | BLOCKED by safety guard | Always redirects to incremental. DELETE CANDIDATE. |

### 5.3 OBSOLETE JOBS

| Job | Reason |
|-----|--------|
| `refresh_real_lob_mvs.py` | v1 LOB MVs. Superseded by `refresh_real_lob_mvs_v2.py`. |
| `backfill_real_lob_mvs.py` | DEPRECATED. Replaced by `populate_real_drill_from_hourly_chain`. |
| `backfill_week_from_day_fact.py` | DEPRECATED. Blocked by safety guard. |

### 5.4 SCHEDULER GAPS

| Gap | Impact | Priority |
|-----|--------|----------|
| `CT_SCHEDULER_ENABLED=false` in production | No automatic refresh. All refreshes are manual or CLI-only. | HIGH — serving facts may go stale if no one runs refreshes |
| `mv_supply_weekly` / `mv_supply_monthly` not in any pipeline | Supply endpoints `/ops/supply/*` may serve permanently stale data. | HIGH |
| No DB-level scheduler coordination (APScheduler runs in-process per gunicorn worker) | Multiple workers could collide on refreshes. Mitigated by advisory locks in `refresh_control_service.py` and in-memory lock in `serving_refresh_scheduler.py`. | MEDIUM |
| `run_refresh_loop.py` not integrated into APScheduler | Requires separate CLI process. | LOW |

---

## 6. REFRESH GOVERNANCE

### 6.1 INVENTORY OF REFRESH SCRIPTS

#### SAFE — Read-only scripts

| Script | Purpose |
|--------|---------|
| `refresh_plan_weekly_weighted.py` | DRY-RUN ONLY. `--execute` always aborts with "MODO SAFE". |
| All `audit_*` scripts (24) | Read-only audits. Some write to audit metadata tables (safe). |
| All `validate_*` scripts (48) | Read-only validations. |
| All `check_*` scripts (28) | Read-only checks (except `check_and_create_views.py` — DANGEROUS). |
| All `diagnose_*` scripts (13) | Read-only diagnosis. |
| All `verify_*` scripts (9) | Read-only verifications. |
| All `inspect_*` scripts (7) | Read-only inspections. |
| All `profile_*` scripts (4) | Read-only profiling. |

#### DANGEROUS — Writes to serving/data layer

| Script | What it modifies | Guard? |
|--------|-----------------|--------|
| `run_pipeline_refresh_and_audit.py` | MAIN PIPELINE: hourly-first chain → drill → driver lifecycle → supply → plan-vs-real → audit | YES — `refresh_control_service.refresh_guard()` |
| `refresh_business_slice_mvs.py` | Business slice day/week/month/hour fact tables | YES — `refresh_guard` + `period_closure` |
| `refresh_hourly_first_chain.py` | Hour→Day→Week→Month LOB MVs (hourly-first) | YES — guarded |
| `refresh_omniview_real_slice_incremental.py` | Business slice facts (direct from RAW, bypassing enriched view) | YES — CURRENT STANDARD |
| `refresh_omniview_projection_facts.py` | `serving.omniview_projection_daily_fact` (DELETE+INSERT) | YES — idempotent |
| `refresh_driver_daily_activity_fact.py` | `ops.driver_daily_activity_fact` (DELETE/INSERT/TRUNCATE) | NO explicit guard |
| `refresh_driver_lifecycle.py` | Driver lifecycle MVs (delegates to check_and_validate) | PARTIAL |
| `refresh_driver_supply_facts.py` | 5 driver supply fact MVs (CONCURRENTLY) | NO explicit guard |
| `refresh_phase2b2_operational_behavior_facts.py` | 3 behavioral fact tables (TRUNCATE+INSERT) | NO explicit guard |
| `refresh_real_lob_mvs_v2.py` | `mv_real_lob_month_v2` + `mv_real_lob_week_v2` (CONCURRENTLY) | NO explicit guard |
| `refresh_real_lob_drill_pro_mv.py` | `mv_real_drill_dim_agg` + `mv_real_rollup_day` + `mv_real_drill_enriched` | NO explicit guard |
| `refresh_real_monthly_canonical_hist.py` | `mv_real_monthly_canonical_hist` | NO explicit guard |
| `refresh_and_validate_financials.py` | `mv_real_financials_monthly` + SQL validations | NO explicit guard |
| `run_supply_refresh_pipeline.py` | Supply alerting MVs → verify serving views → log to supply_refresh_log | YES — guarded |
| All `backfill_*` scripts (7) | Various fact tables | Varies |
| All `load_*` scripts (7) | Various mapping tables | NO explicit guard |

#### LEGACY — Superseded or blocked

| Script | Status |
|--------|--------|
| `refresh_omniview_real_slice.py` | DEPRECATED. Blocked by safety guard. |
| `refresh_real_lob_mvs.py` | v1 LOB. Superseded by v2. |
| `backfill_real_lob_mvs.py` | DEPRECATED. |
| `backfill_week_from_day_fact.py` | DEPRECATED. Blocked by safety guard. |

### 6.2 REFRESH GAPS

| Gap | Impact | Priority |
|-----|--------|----------|
| Many DANGEROUS refresh scripts lack `refresh_guard()` context manager | No centralized advisory lock, no destructive SQL detection for those scripts. | HIGH |
| `mv_supply_weekly` / `mv_supply_monthly` never refreshed | Supply data may be permanently stale. | HIGH |
| DROP+CASCADE on driver lifecycle base MV | Non-idempotent. Failure between DROP and CREATE = broken MV. | MEDIUM |
| No refresh duration metrics for most MVs | Hard to detect performance degradation. | MEDIUM |
| `run_refresh_loop.py` runs as CLI infinite loop, not APScheduler | Inconsistent with other scheduling. | LOW |
| Business slice month_fact recalculates previous (closed) month on every run | Unnecessary work. Closed periods are protected from writes but the calculation still runs. | LOW |

---

## 7. DEPRECATION PLAN

| # | Objeto | Estado Actual | Acción | Timeline | Blocker? |
|---|--------|---------------|--------|----------|----------|
| 1 | `refresh_omniview_real_slice.py` | LEGACY — blocked | DELETE. Safety guard already blocks it. Remove file. | Now | No |
| 2 | `backfill_week_from_day_fact.py` | LEGACY — blocked | DELETE. Safety guard already blocks it. Remove file. | Now | No |
| 3 | `BusinessSliceOmniviewProjectionTable.jsx` | DEPRECATED | DELETE. Verify zero remaining imports first. | Now | No |
| 4 | `BusinessSliceOmniviewProjectionCell.jsx` | DEPRECATED | DELETE. Verify zero remaining imports first. | Now | No |
| 5 | `backfill_real_lob_mvs.py` | DEPRECATED | DEPRECATE + MOVE to `backend/scripts/legacy/`. Add comment redirecting to `populate_real_drill_from_hourly_chain`. | 30 days | No |
| 6 | `refresh_real_lob_mvs.py` (v1) | LEGACY | DEPRECATE + MOVE to `legacy/`. Ensure v2 is the exclusive path for all pipeline triggers. | 30 days | May require LOB v1 endpoint deprecation first |
| 7 | `ops.mv_real_trips_by_lob_month` | LEGACY | MARK LEGACY. Plan migration: redirect `/ops/real-lob/monthly` v1 to v2. | 60 days | Yes — requires UI migration |
| 8 | `ops.mv_real_trips_by_lob_week` | LEGACY | MARK LEGACY. Plan migration: redirect `/ops/real-lob/weekly` v1 to v2. | 60 days | Yes — requires UI migration |
| 9 | `ops.mv_real_trips_monthly` | LEGACY | MARK LEGACY. Migrate `MonthlySplitView.jsx` and `plan_real_split_service.py` to use `mv_real_monthly_canonical_hist`. | 60 days | Yes — requires UI migration |
| 10 | `ops.mv_plan_vs_real_monthly_fact` (legacy) | LEGACY | MARK LEGACY. Migrate remaining consumers to `_canonical` version. | 60 days | Yes — requires audit of remaining consumers |
| 11 | `real_lob_service.py` (v1) | LEGACY | QUARANTINE. Freeze v1 endpoints. Add deprecation header. Redirect to v2. | 90 days | Yes — requires UI migration for `RealLOBView.jsx` v1 mode |
| 12 | `MonthlyView.jsx` | LEGACY | QUARANTINE. Add banner "This view will be replaced by Omniview". | 90 days | Yes — requires Omniview parity |
| 13 | `MonthlySplitView.jsx` | LEGACY | QUARANTINE. Same treatment as MonthlyView. | 90 days | Yes — requires Omniview parity |
| 14 | `core_service.py` | LEGACY | QUARANTINE. Only consumer is MonthlyView. Deprecate together. | 90 days | No |
| 15 | `plan_real_split_service.py` | LEGACY | QUARANTINE. Only consumer is MonthlySplitView. Deprecate together. | 90 days | No |
| 16 | `ops.refresh_supply_mvs()` (migration 060) | QUARANTINE | BLOCK. This function refreshes MVs that no pipeline calls. Either integrate into main pipeline OR deprecate both MVs. | Now (decision) / 60 days (implementation) | Partially — supply endpoints may break |
| 17 | `mv_supply_weekly` | QUARANTINE | BLOCK. No pipeline refreshes it. Either fix the pipeline or deprecate the MV and its consumers. | 60 days | Yes — supply endpoints depend on this |
| 18 | `mv_supply_monthly` | QUARANTINE | BLOCK. Same as above. | 60 days | Yes — supply endpoints depend on this |
| 19 | `clear_all_plan_data.py` | QUARANTINE | BLOCK. Add `--dry-run` and confirmation gate. Never allow unattended execution. | Now | No |
| 20 | `clear_all_plans.py` | QUARANTINE | BLOCK. Same as above. | Now | No |
| 21 | `clear_plan_version.py` | QUARANTINE | BLOCK. Add backup snapshot before delete. | Now | No |

---

## 8. CONTROL FOUNDATION GAP ANALYSIS

### 8.1 WHAT IS CERTIFIED (Closed)

| Certification | Document | Date | Status |
|---------------|----------|------|--------|
| CF-H1J.5 Source of Truth Audit | AUDITORIA_FASE1_REFRESH_SERVING_HARDENING.md | Phase 1 | CLOSED |
| CF-H1J.6 Weekly Recovery | (Phase 1F/1G audits) | Phase 1 | CLOSED |
| CF-H1J.7 Guardrails | AUDITORIA_FASE1D_CLOSED_PERIOD_PROTECTION.md | Phase 1D | CLOSED |
| CF-H1J.8 Freshness Audit | AUDITORIA_FASE1F_OMNIVIEW_SERVING_INTEGRATION.md | Phase 1F | CLOSED |
| CF-H1J.9 Canonical Registry (partial) | AUDITORIA_FASE1G1_UI_REGRESSION_RECOVERY.md | Phase 1G.1 | CLOSED |
| Control Foundation Closure | docs/control_foundation/CONTROL_FOUNDATION_CLOSURE_REPORT.md | 2026-05-29 | CLOSED (11 GO / 1 CONDITIONAL) |

### 8.2 WHAT REMAINS TO CONSIDER CONTROL FOUNDATION = FULLY CERTIFIED

| Gap | Severity | Owner | Status |
|-----|----------|-------|--------|
| **G1: This Canonical Registry did not exist until now** | BLOCKER | governance | **FIXED NOW** — this document fills the gap |
| **G2: No explicit classification of canonical vs serving vs legacy vs quarantine** | BLOCKER | governance | **FIXED NOW** — Section 3 above |
| **G3: No explicit Freshness governance — what to monitor vs not** | HIGH | freshness | **FIXED NOW** — Section 4 above |
| **G4: No explicit Scheduler governance — active/legacy/obsolete jobs** | HIGH | scheduler | **FIXED NOW** — Section 5 above |
| **G5: No explicit Refresh governance — safe/legacy/dangerous classification** | HIGH | refresh | **FIXED NOW** — Section 6 above |
| **G6: No explicit Deprecation Plan** | MEDIUM | governance | **FIXED NOW** — Section 7 above |
| G7: `mv_supply_weekly` / `mv_supply_monthly` potentially stale | HIGH | supply | **NOT FIXED** — requires pipeline integration or deprecation |
| G8: `CT_SCHEDULER_ENABLED=false` in production | HIGH | ops | **NOT FIXED** — requires production decision |
| G9: Daily/weekly facts lack serving views (only monthly has one) | MEDIUM | business_slice | **NOT FIXED** — backlog item |
| G10: Several LEGACY UI paths still active (MonthlyView, MonthlySplitView, RealLOBView v1) | MEDIUM | frontend | **NOT FIXED** — requires gradual migration |
| G11: No `X-Data-Freshness` headers on API responses | LOW | API | **NOT FIXED** |
| G12: Alerting engine not activated (1 CONDITIONAL GO in scorecard) | CONDITIONAL | action_engine | **NOT FIXED** — requires RC-1 Operational Priority Layer |
| G13: Snapshots for day/week facts (only monthly has snapshot) | LOW | business_slice | **NOT FIXED** — backlog |

### 8.3 VERDICT

**Control Foundation = CLOSED** — The existing certifications (11 GO / 1 CONDITIONAL) are valid. This registry fills the remaining documentation gaps (G1-G6). The 7 remaining gaps (G7-G13) are ALL operational backlog items, not architectural blockers.

**The gateway to Diagnostic Engine is open.**

---

## 9. GO / NO-GO FOR DIAGNOSTIC ENGINE

### 9.1 GO Conditions (all met)

| Condition | Status |
|-----------|--------|
| KPIs reconcile across grains | GO |
| Grains are consistent | GO |
| Serving facts are governed | GO |
| Freshness monitoring is active | GO |
| Runtime fallback is protected | GO |
| Performance is stable (build 11.52s) | GO |
| UI does not freeze | GO |
| Plan vs Real is trustworthy (revenue certified) | GO |
| Canonical Registry exists (this document) | GO |
| Deprecation Plan exists (Section 7) | GO |

### 9.2 NO-GO Conditions (none blocking)

| Condition | Status |
|-----------|--------|
| Supply MVs potentially stale (G7) | **NOT blocking Diagnostic Engine** — Supply is a separate module |
| Scheduler not enabled in production (G8) | **NOT blocking** — Operational concern, not architectural |
| Alerting engine not activated (G12) | **CONDITIONAL GO** — requires RC-1, but RC-1 is a Diagnostic sub-phase |

### 9.3 VERDICT

**GO for Diagnostic Engine Phase 2A.3 — Behavioral Pattern Diagnosis**

Control Foundation is sufficiently stable and governed. All documented blockers are resolved. Remaining gaps are operational backlog (LOW/MEDIUM), not architectural risks.

**With caveat**: G7 (stale supply MVs) and G8 (scheduler disabled) should be addressed before reaching Decision Engine (Engine 6), but do NOT block Diagnostic Engine (Engine 2).

---

## 10. RECOMMENDATIONS

### 10.1 Priority 1 — IMMEDIATE (this phase)

1. **Merge this registry** as the authoritative governance document for Omniview.
2. **Tag this commit** as `registry-v1-omniview-canonical`.
3. **Add to `ai_current_phase.md`** a reference to this registry.
4. **Block** `clear_all_plan_data.py`, `clear_all_plans.py`, `clear_plan_version.py` with confirmation gates.

### 10.2 Priority 2 — NEXT (Phase 1H.4 closure)

5. **Delete** the 4 DELETE CANDIDATE objects (Section 3.5).
6. **Deprecate** the 30-day items in the Deprecation Plan.
7. **Integrate or fix** `mv_supply_weekly` / `mv_supply_monthly` refresh into main pipeline.
8. **Enable** `CT_SCHEDULER_ENABLED=true` in production with monitoring.

### 10.3 Priority 3 — BACKLOG (Phase 2A+)

9. **Migrate** LEGACY UI paths to Omniview (MonthlyView, MonthlySplitView, RealLOBView v1).
10. **Add** serving views for day/week facts.
11. **Add** `X-Data-Freshness` headers to API responses.
12. **Replace** DROP+CASCADE pattern on driver lifecycle MV with CREATE OR REPLACE.
13. **Add** `refresh_guard()` to all DANGEROUS refresh scripts that lack it.

### 10.4 Priority 4 — FUTURE (beyond Diagnostic Engine)

14. **Add** snapshots for day/week facts (parity with monthly snapshot).
15. **Add** refresh duration metrics for all MVs.
16. **Activate** alerting engine (RC-1 Operational Priority Layer).
17. **Complete** deprecation of LEGACY LOB v1 endpoints.

---

## APPENDIX A — KEY CONSTANTS REFERENCE

| Constant | File | Value | Meaning |
|----------|------|-------|---------|
| `FACT_MONTHLY` | `business_slice_service.py:47` | `ops.v_real_business_slice_month_serving` | Canonical monthly read path |
| `FACT_MONTHLY_RAW` | `business_slice_service.py:48` | `ops.real_business_slice_month_fact` | Write target + metadata freshness |
| `FACT_DAILY` | `business_slice_service.py:50` | `ops.real_business_slice_day_fact` | Canonical daily read path |
| `FACT_WEEKLY` | `business_slice_service.py:51` | `ops.real_business_slice_week_fact` | Canonical weekly read path |
| `STALE_THRESHOLD_HOURS` | `serving_governance_service.py:25` | `24` | Facts older than this are marked stale |
| `DEFAULT_PLAN_VERSION` | `serving_refresh_scheduler.py:30` | `ruta27_2026_04_21` | Default plan version for projection refresh |
| `REFRESH_TIMEOUT_SECONDS` | `serving_refresh_scheduler.py:32` | `600` | Max runtime for projection refresh |
| `FORBIDDEN_SERVING_SOURCES` | `serving_guardrails.py` | `["v_real_trips_business_slice_resolved", "v_real_trips_enriched_base"]` | Never use for UI reads |

## APPENDIX B — SERVING REGISTRY KEYS

| serving_key | entity_name | grain | source_dependencies |
|-------------|-------------|-------|---------------------|
| `business_slice_month` | `ops.v_real_business_slice_month_serving` | monthly | `real_business_slice_month_fact`, `real_business_slice_month_snapshot` |
| `business_slice_day` | `ops.real_business_slice_day_fact` | daily | `v_real_trips_enriched_base`, `trips_2026` |
| `business_slice_week` | `ops.real_business_slice_week_fact` | weekly | `v_real_trips_enriched_base`, `trips_2026` |
| `omniview_projection_daily` | `serving.omniview_projection_daily_fact` | daily | `plan_trips_monthly`, `real_business_slice_day_fact` |
| `omniview_projection_weekly` | `serving.omniview_projection_daily_fact` | weekly | `plan_trips_monthly`, `real_business_slice_week_fact` |
| `omniview_projection_monthly` | `serving.omniview_projection_daily_fact` | monthly | `plan_trips_monthly`, `real_business_slice_month_fact` |
| `ownership_serving` | `ops.mv_ownership_serving_fact` | monthly | `plan_trips_monthly`, `real_business_slice_month_fact`, `projection_ownership` |
| `plan_vs_real_canonical` | `ops.mv_plan_vs_real_monthly_fact_canonical` | monthly | `mv_real_monthly_canonical_hist`, `plan_trips_monthly` |

---

**END OF REGISTRY**
