# OV1 LINEAGE MAP — Omniview V1 Source Inventory

**Generated:** 2026-06-06  
**Phase:** Control Foundation — Omniview P0 Recovery (ACTIVE)  
**Scope:** Endpoints, services, queries, MVs, serving facts, fallbacks

---

## 1. ENDPOINT CATALOG

### 1.1 Primary Omniview Serving Endpoints (Router: `ops.py`)

| # | Endpoint | Method | Service | Purpose |
|---|----------|--------|---------|---------|
| 1 | `GET /ops/business-slice/monthly` | GET | `business_slice_service` | Matrix monthly real data |
| 2 | `GET /ops/business-slice/weekly` | GET | `business_slice_service` | Matrix weekly real data |
| 3 | `GET /ops/business-slice/daily` | GET | `business_slice_service` | Matrix daily real data |
| 4 | `GET /ops/business-slice/omniview` | GET | `business_slice_omniview_service` | V1 legacy omniview (comparative MoM/WoW/DoW-7) |
| 5 | `GET /ops/business-slice/omniview-projection` | GET | `projection_expected_progress_service` | Vs Proy projection matrix |
| 6 | `GET /ops/business-slice/omniview-projection/serving-plan-versions` | GET | `projection_expected_progress_service` | Plan versions available in serving |
| 7 | `GET /ops/business-slice/omniview-momentum-drill` | GET | `omniview_momentum_drill_service` | Momentum drill (DoD/WoW/MoM) |
| 8 | `GET /ops/business-slice/real-freshness` | GET | `business_slice_real_freshness_service` | Real data freshness per grain |
| 9 | `GET /ops/omniview/freshness` | GET | `omniview_freshness_governance_service` | Cross-layer freshness governance |
| 10 | `POST /ops/omniview/refresh` | POST | `business_slice_real_refresh_job` | Trigger refresh of day/week/month facts |

### 1.2 Plan vs Real Endpoints

| # | Endpoint | Method | Service | Purpose |
|---|----------|--------|---------|---------|
| 11 | `GET /ops/plan-vs-real/monthly` | GET | `plan_vs_real_service` | Plan vs Real monthly (legacy + canonical) |
| 12 | `GET /ops/plan-vs-real/alerts` | GET | `plan_vs_real_service` | Plan vs Real alerts |
| 13 | `GET /ops/control-loop/plan-vs-real` | GET | `control_loop_plan_vs_real_service` | Control Loop Plan vs Real |

### 1.3 Serving Governance Endpoints

| # | Endpoint | Method | Service | Purpose |
|---|----------|--------|---------|---------|
| 14 | `GET /ops/serving/health` | GET | `serving_governance_service` | Serving registry health |
| 15 | `GET /ops/serving/coverage` | GET | `serving_governance_service` | Serving fact coverage |
| 16 | `GET /ops/serving/failures` | GET | `serving_governance_service` | Refresh failures |
| 17 | `GET /ops/serving/runtime-risks` | GET | `serving_governance_service` | Runtime risk detection |
| 18 | `GET /ops/serving/integrity` | GET | `serving_governance_service` | Aggregate serving integrity |
| 19 | `GET /ops/omniview/weekly-serving-guardrails` | GET | `weekly_serving_guardrails_service` | Weekly fact vs serving reconciliation |

### 1.4 KPI Audit Endpoints

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 20 | `GET /ops/kpi-consistency-audit` | GET | KPI additivity contract validation |
| 21 | `GET /ops/rollup-mismatch-audit` | GET | month_fact vs SUM(day_fact) vs v_resolved |
| 22 | `GET /ops/data-freshness` | GET | Full freshness audit |
| 23 | `GET /ops/data-freshness/global` | GET | Global freshness status |

### 1.5 Other Omniview Endpoints

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 24 | `GET /ops/real/monthly` | GET | Real monthly (legacy + canonical) |
| 25 | `GET /ops/plan/monthly` | GET | Plan monthly |
| 26 | `GET /ops/ownership-serving/monthly` | GET | Ownership-aware Plan vs Real |
| 27 | `GET /ops/business-slice/matrix-operational-trust` | GET | Matrix integrity checks |
| 28 | `GET /ops/business-slice/fact-status` | GET | Fact table row counts per period |
| 29 | `GET /ops/business-slice/coverage` | GET | Business slice coverage |
| 30 | `GET /ops/business-slice/unmatched` | GET | Unmatched trips |
| 31 | `GET /ops/business-slice/conflicts` | GET | Slice conflicts |
| 32 | `GET /ops/universe` | GET | Trips universe |
| 33 | `GET /core/summary/monthly` | GET | Core monthly summary (plan + real) |

---

## 2. CORE SERVING FACT TABLES (V1 Canonical)

### 2.1 Business Slice Fact Layer

| Object | Schema | Type | Grain | Key Columns |
|--------|--------|------|-------|-------------|
| `ops.real_business_slice_day_fact` | ops | Table | day | trip_date, country, city, business_slice_name, trips_completed, revenue_yego_net, revenue_yego_final, active_drivers, avg_ticket, commission_pct, trips_per_driver, cancel_rate_pct |
| `ops.real_business_slice_week_fact` | ops | Table | week (ISO) | week_start, same columns |
| `ops.real_business_slice_month_fact` | ops | Table | month | month, loaded_at, same columns |
| `ops.real_business_slice_hour_fact` | ops | Table | hour | hour_start, same columns |
| `ops.v_real_business_slice_month_serving` | ops | View | month | Serving view: routes snapshot if locked, working fact if open |
| `ops.real_business_slice_month_snapshot` | ops | Table | month | Frozen snapshot for locked periods |

### 2.2 Projection Serving Facts

| Object | Schema | Type | Grain | Key Columns |
|--------|--------|------|-------|-------------|
| `serving.omniview_projection_daily_fact` | serving | Table | daily, weekly, monthly | plan_version, grain, trips_completed, revenue_yego_final, active_drivers, generated_at |

---

## 3. MATERIALIZED VIEWS (V1 Dependencies)

### 3.1 Plan vs Real MVs

| MV | Source | Refresh | Status |
|----|--------|---------|--------|
| `ops.mv_plan_vs_real_monthly_fact` | Plan + Real tables | `refresh_plan_vs_real_monthly_materialized_views()` | **LEGACY** — active but has canonical replacement |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | Plan + `v_trips_real_canon` | Same function | **CANONICAL** |
| `ops.mv_real_trips_monthly` | `ops.v_real_trips_canon` | `refresh_real_trips_monthly()` | **LEGACY** |
| `ops.mv_real_monthly_canonical_hist` | `ops.v_trips_real_canon` | `refresh_real_monthly_canonical_hist.py` | **CANONICAL HIST** |

### 3.2 Real LOB MVs

| MV | Source | Refresh |
|----|--------|---------|
| `ops.mv_real_lob_hour_v2` | `ops.v_trip_fact_v2` | Hourly-first chain |
| `ops.mv_real_lob_day_v2` | `ops.mv_real_lob_hour_v2` | Hourly-first chain |
| `ops.mv_real_lob_week_v3` | `ops.mv_real_lob_day_v2` | Hourly-first chain |
| `ops.mv_real_lob_month_v3` | Weekly/hour rollup | Hourly-first chain |

### 3.3 Other MVs

| MV | Purpose | Refresh Status |
|----|---------|----------------|
| `ops.mv_ownership_serving_fact` | Ownership-aware Plan vs Real | `refresh_ownership_serving_fact()` |
| `ops.mv_driver_lifecycle_base` | 1 row/driver (activation, lifetime) | DROP+CASCADE build (QUARANTINE) |
| `ops.mv_supply_weekly` | Weekly supply | **NOT REFRESHED** (stale, replaced by views) |
| `ops.mv_supply_monthly` | Monthly supply | **NOT REFRESHED** (stale) |

---

## 4. REVENUE COLUMN RESOLUTION

All V1 fact tables use:

```sql
COALESCE(revenue_yego_final, revenue_yego_net) AS completed_revenue_sum
```

- `revenue_yego_final`: canonical revenue (preferred)
- `revenue_yego_net`: fallback when `_final` is NULL

**Risk:** If `revenue_yego_final` is not populated, the system silently falls back to `revenue_yego_net` without alerting. No visual differentiation between the two sources.

---

## 5. RUNTIME FALLBACK CHAINS (V1)

### 5.1 Projection Service

```
1. serving.omniview_projection_daily_fact  (fact-first, pre-computed)
   └── NOT found:
2. Empty + remediation message (from API, no runtime fallback)
   └── Only if _allow_runtime_fallback=True (scripts):
       3a. ops.v_plan_projection_control_loop (primary plan)
       3b. ops.plan_trips_monthly (secondary plan)
       + ops.real_business_slice_{month/week/day}_fact (real)
```

### 5.2 Plan vs Real Service

```
1. ops.mv_plan_vs_real_monthly_fact[_canonical] (MV)
   └── MV missing/stale:
2. ops.v_plan_vs_real_realkey_final[_canonical] (View fallback)
```

### 5.3 Business Slice Monthly

```
1. ops.v_real_business_slice_month_serving (Serving view)
   └── unmapped bucket:
2. ops.v_real_trips_business_slice_resolved (FORBIDDEN for serving)
```

---

## 6. FORBIDDEN SERVING SOURCES

```python
FORBIDDEN_SERVING_SOURCES = {
    "public.trips_all",
    "public.trips_unified",
    "ops.v_real_trips_business_slice_resolved",
    "ops.v_real_trips_enriched_base",
    "ops.v_real_trip_fact_v2",
}
```

These are explicitly blocked by `serving_guardrails.py` `ServingPolicy` in strict mode.

---

## 7. KPI → SOURCE MATRIX (V1)

| KPI | Endpoint | Source Table | Column |
|-----|----------|-------------|--------|
| **trips** | `/ops/business-slice/monthly` | `ops.real_business_slice_month_fact` | `trips_completed` |
| **trips** | `/ops/business-slice/weekly` | `ops.real_business_slice_week_fact` | `trips_completed` |
| **trips** | `/ops/business-slice/daily` | `ops.real_business_slice_day_fact` | `trips_completed` |
| **revenue** | `/ops/business-slice/monthly` | `ops.real_business_slice_month_fact` | `COALESCE(revenue_yego_final, revenue_yego_net)` |
| **revenue** | `/ops/business-slice/omniview-projection` | `serving.omniview_projection_daily_fact` | `revenue_yego_final` |
| **drivers** | `/ops/business-slice/monthly` | `ops.real_business_slice_month_fact` | `active_drivers` |
| **ticket** | `/ops/business-slice/monthly` | `ops.real_business_slice_month_fact` | `avg_ticket` |
| **TPD** | Computed frontend | `trips_completed / active_drivers` | Computed |
| **Plan vs Real** | `/ops/plan-vs-real/monthly` | `ops.mv_plan_vs_real_monthly_fact[_canonical]` | trips_plan, trips_real, revenue_plan, revenue_real |
| **Plan vs Real** | `/ops/control-loop/plan-vs-real` | `ops.real_business_slice_month_fact` + `ops.v_plan_projection_control_loop` | Same |

---

## 8. REFRESH ORCHESTRATION (V1)

| Job | Schedule | Target |
|-----|----------|--------|
| `omniview_business_slice_real_refresh` | Configured hour | `real_business_slice_{day/week/month}_fact` |
| `serving_fact_daily_refresh` | Daily 05:00 UTC | `serving.omniview_projection_daily_fact` (all grains) |
| `omniview_real_data_watchdog` | Every N minutes | Data freshness validation |

---

## 9. KNOWN V1 ARCHITECTURAL RISKS

| Risk | Severity | Detail |
|------|----------|--------|
| Revenue COALESCE silent fallback | **HIGH** | `revenue_yego_final → revenue_yego_net` without alert |
| MV stale without detection | **MEDIUM** | `mv_supply_weekly/monthly` never refreshed |
| Dual Plan vs Real source | **MEDIUM** | Legacy `_fact` vs canonical `_fact_canonical` coexist |
| DROP+CASCADE on driver MVs | **HIGH** | Non-idempotent build can leave empty MVs |
| Frontend recomputes KPIs | **MEDIUM** | cancel_rate_pct, trips_per_driver recalculated client-side |
| Runtime fallback gated only by Python flag | **MEDIUM** | `_allow_runtime_fallback` not auditable at DB level |
| `v_resolved` still queryable | **LOW** | Forbidden source reachable if guard bypassed |
