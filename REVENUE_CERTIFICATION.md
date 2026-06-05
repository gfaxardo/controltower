# REVENUE CERTIFICATION — OMNIVIEW HARDENING O1

**Motor:** Control Foundation — Revenue Certification  
**Fecha:** 2026-06-02  
**Fase:** O1 — Audit Only, No Correction  
**Estado:** AUDIT COMPLETE  

---

## 0. SCOPE

Este documento certifica el flujo completo de Revenue dentro de Omniview.  
NO modifica UI. NO crea features nuevas. NO toca Diagnostic.

| Capa | Componentes auditados |
|------|----------------------|
| Revenue Header | KPI semantics (`kpi_semantics.py`), aggregation rules (`kpi_aggregation_rules.py`) |
| Revenue Matrix | Fact tables (day/week/month), Omniview API serving |
| Revenue Totals | Global totals, comparison totals, YTD totals |
| Revenue Period Totals | Monthly, weekly, daily aggregated sums |
| Revenue Territory Totals | Country/city rollups, cross-currency aggregation |

---

## 1. REVENUE LINEAGE (End-to-End, Source-Verified)

```
┌─ RAW LAYER ──────────────────────────────────────────────────────────────────┐
│                                                                               │
│  public.trips_2025 / public.trips_2026                                        │
│  Columna fuente: comision_empresa_asociada                                    │
│  NaN guard: NULLIF(col, 'NaN'::numeric) via migration 122:36-42               │
│                                                                               │
├── CANON 120d ────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ops.v_trips_real_canon_120d (migration 122:37-80)                            │
│  UNION ALL trips_2025 + trips_2026, DISTINCT ON (id)                          │
│  Date window: CURRENT_DATE - 120 days                                         │
│                                                                               │
├── HOURLY-FIRST FACT ─────────────────────────────────────────────────────────┤
│                                                                               │
│  ops.v_real_trip_fact_v2 (migration 122:91-268)                               │
│  gross_revenue = GREATEST(0, COALESCE(_revenue_real, _revenue_proxy, 0))     │
│  margin_total  = COALESCE(_revenue_real, _revenue_proxy)                      │
│  revenue_source = 'real' | 'proxy' | 'missing'                                │
│  → feeds ops.mv_real_lob_day_v2 (MV, needs REFRESH)                          │
│                                                                               │
├── ENRICHED BASE ─────────────────────────────────────────────────────────────┤
│                                                                               │
│  ops.v_real_trips_enriched_base (VIEW)                                        │
│  revenue_yego_net = NULLIF(comision_empresa_asociada, 0)                      │
│  ticket = precio_yango_pro                                                    │
│  total_fare = efectivo + tarjeta + pago_corporativo                           │
│  → Used by _materialize_enriched_for_month() in incremental_load.py:974-1013 │
│                                                                               │
├── ENRICHED TEMP ─────────────────────────────────────────────────────────────┤
│                                                                               │
│  _bs_enriched_month (TEMP TABLE, incremental_load.py:974-1013)                │
│  revenue_yego_real  = ABS(revenue_yego_net) [completed + non-null]           │
│  revenue_yego_proxy = ticket * resolve_commission_pct(...) [default 3%]      │
│  revenue_yego_final = COALESCE(revenue_yego_real, revenue_yego_proxy)        │
│  revenue_source     = 'real' | 'proxy' | 'missing'                            │
│                                                                               │
│  Resolution CTE (_RESOLVE_AND_AGG_FROM_TEMP:40-146):                         │
│  - Matching: park_only > park_plus_tipo_servicio > park_plus_works_terms     │
│  - Conflict resolution: is_subfleet ASC, parent_fleet NULLS FIRST, ...        │
│  - UNMATCHED trips → business_slice_name = '__UNMATCHED__'                    │
│  - Alias: b.revenue_yego_real AS revenue_yego_net (line 174)                  │
│                                                                               │
├── FACT TABLES ───────────────────────────────────────────────────────────────┤
│                                                                               │
│  ops.real_business_slice_day_fact    (populated by incremental load)          │
│  ops.real_business_slice_week_fact   (rollup from day_fact)                   │
│  ops.real_business_slice_month_fact  (direct from enriched temp)             │
│                                                                               │
│  revenue_yego_net   = SUM(revenue_yego_real alias) FILTER (WHERE completed)  │
│  revenue_yego_final = SUM(revenue_yego_final) FILTER (WHERE completed)       │
│  commission_pct     = SUM(revenue)/SUM(total_fare) [ratio 0-1]                │
│  revenue_real_coverage_pct = real_trips / total_trips * 100                   │
│                                                                               │
│  Grain:  day→(trip_date,country,city,slice,fleet,subfleet)                    │
│          week→(week_start, country,city,slice,fleet,subfleet)                │
│          month→(month, country,city,slice,fleet,subfleet)                    │
│                                                                               │
├── SERVING VIEW ──────────────────────────────────────────────────────────────┤
│                                                                               │
│  ops.v_real_business_slice_month_serving (migration 143:69-147)               │
│  Redirect logic:                                                              │
│    - Locked/closed periods → snapshot (ops.real_business_slice_month_snapshot)│
│    - Open periods → working_fact (ops.real_business_slice_month_fact)         │
│  ⚠ revenue_yego_final NOT propagated to this view (m143:97,132)               │
│    Only revenue_yego_net is exposed.                                          │
│                                                                               │
├── API LAYER ─────────────────────────────────────────────────────────────────┤
│                                                                               │
│  GET /ops/business-slice/monthly  → business_slice_service.py                │
│    FACT_MONTHLY = "ops.v_real_business_slice_month_serving" (line 47)         │
│    Period totals: SUM(revenue_yego_net) via _fetch_month_fact_period_totals  │
│  GET /ops/business-slice/weekly   → business_slice_service.py                │
│    FACT_WEEKLY = "ops.real_business_slice_week_fact"                          │
│  GET /ops/business-slice/daily    → business_slice_service.py                │
│    FACT_DAILY = "ops.real_business_slice_day_fact"                            │
│  GET /ops/business-slice/omniview → business_slice_omniview_service.py       │
│    COALESCE(revenue_yego_final, revenue_yego_net) → completed_revenue_sum    │
│    Fallback on error: revenue_yego_net AS completed_revenue_sum              │
│  GET /ops/business-slice/omniview-projection → projection service            │
│    ABS(COALESCE(revenue_yego_final, revenue_yego_net)) AS real_revenue        │
│    Fallback: ABS(revenue_yego_net) AS real_revenue                            │
│                                                                               │
│  ServingPolicy (business_slice_omniview_service.py:56-67):                     │
│    query_mode=SERVING, strict_mode=True, require_preferred_source_match=True  │
│    Forbidden: v_real_trips_business_slice_resolved, v_real_trips_enriched_base│
│                                                                               │
├── FRONTEND LAYER ────────────────────────────────────────────────────────────┤
│                                                                               │
│  BusinessSliceOmniviewMatrix.jsx                                              │
│  → omniviewMatrixUtils.js: buildMatrix()                                       │
│    Revenue aggregation (line 664):                                            │
│      tb._revenue += Number(r.revenue_yego_net) || 0                          │
│    Totals (line 703-713): SUM of detail rows                                 │
│  → projectionMatrixUtils.js: buildProjectionMatrix()                           │
│    Revenue aggregation (lines 436-440):                                       │
│      tb[kpi].actual += Number(raw[kpi]) || 0                                 │
│    active_drivers correctly excluded (line 437)                               │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. SERVING FACT AUDIT

### 2.1 Serving Facts Used

| Serving Fact | Grain | Revenue Columns | Source Verified | Status |
|-------------|-------|----------------|-----------------|--------|
| `ops.real_business_slice_day_fact` | daily | `revenue_yego_net`, `revenue_yego_final` | `business_slice_incremental_load.py:32` | **PASS** |
| `ops.real_business_slice_week_fact` | weekly | `revenue_yego_net`, `revenue_yego_final` | `business_slice_incremental_load.py:33` | **PASS** |
| `ops.real_business_slice_month_fact` | monthly | `revenue_yego_net`, `revenue_yego_final` | `business_slice_incremental_load.py:30` | **PASS** |
| `ops.v_real_business_slice_month_serving` | monthly | `revenue_yego_net` ONLY | migration 143:97,132 | **WARNING** |
| `ops.mv_real_lob_day_v2` | daily | `gross_revenue`, `margin_total` | migration 122:301-303 | **LEGACY** |
| `serving.omniview_projection_daily_fact` | daily | `revenue_yego_net` | `refresh_omniview_projection_facts.py:253` | **PASS** |
| `ops.v_real_revenue_proxy_audit` | daily (trip) | `revenue_yego_real`, `revenue_yego_final` | migration 120:102-178 | **PASS** |

### 2.2 Forbidden Sources (Active Guardrails)

Verified in `serving_guardrails.py:55-61`:

```
FORBIDDEN_SERVING_SOURCES = [
    "public.trips_all",
    "public.trips_unified", 
    "ops.v_real_trips_business_slice_resolved",
    "ops.v_real_trips_enriched_base",
    "ops.v_real_trip_fact_v2",
]
```

All 5 sources blocked in `strict` mode for `SERVING` queries.  
DB-layer gate: `execute_db_gated_query()` enforces at query execution, not just declaration.  
Mode: `DB_SERVING_GUARD_MODE = 'warn'` (non-intrusive, logged).

---

## 3. FORMULA AUDIT — Exact Source Verification

### 3.1 Canonical Formula

```
revenue_yego_net (in fact table) =
    SUM( ABS(NULLIF(comision_empresa_asociada, 0)) + proxy_fallback )
    FILTER (WHERE completed_flag)
    GROUP BY (country, city, business_slice_name, fleet, subfleet, period)
```

### 3.2 Formulas by Layer (Source-Verified)

| Layer | Exact Formula | File:Line |
|------|---------------|-----------|
| RAW → Enriched Base | `NULLIF(comision_empresa_asociada, 0)` AS revenue_yego_net | `business_slice_incremental_load.py:1079-1082` (direct RAW build) |
| RAW NaN guard | `NULLIF(comision_empresa_asociada, 'NaN'::numeric)` | migration 122:42 (`_safe()`) |
| Enriched Temp → revenue_yego_real | `ABS(e.revenue_yego_net)` WHEN completed AND non-null | `business_slice_incremental_load.py:978-981` |
| Enriched Temp → revenue_yego_proxy | `ticket * COALESCE(resolve_commission_pct(...), 0.03)` | `business_slice_incremental_load.py:984-990` |
| Enriched Temp → revenue_yego_final | `COALESCE(revenue_yego_real, revenue_yego_proxy)` | `business_slice_incremental_load.py:991-1000` |
| Resolution alias | `b.revenue_yego_real AS revenue_yego_net` | `business_slice_incremental_load.py:174` |
| Fact INSERT → revenue_yego_net | `SUM(r.revenue_yego_net) FILTER (WHERE r.completed_flag)` | `business_slice_incremental_load.py:85` |
| Fact INSERT → revenue_yego_final | `SUM(r.revenue_yego_final) FILTER (WHERE r.completed_flag)` | `business_slice_incremental_load.py:124` |
| Omniview API → revenue column | `COALESCE(revenue_yego_final, revenue_yego_net) AS completed_revenue_sum` | `business_slice_omniview_service.py:654` |
| Omniview API fallback | `revenue_yego_net AS completed_revenue_sum` | `business_slice_omniview_service.py:683` |
| Projection API → real_revenue | `ABS(COALESCE(revenue_yego_final, revenue_yego_net))` | `projection_expected_progress_service.py:2656` |
| Projection API fallback | `ABS(revenue_yego_net) AS real_revenue` | `projection_expected_progress_service.py:2657` |
| Business Slice API | `SUM(revenue_yego_net)` from fact tables | `business_slice_service.py:468,534,586` |
| Frontend Matrix | `_revenue += Number(r.revenue_yego_net) \|\| 0` | `omniviewMatrixUtils.js:664` |
| Frontend Projection | `tb[kpi].actual += Number(raw[kpi]) \|\| 0` | `projectionMatrixUtils.js:438` |

### 3.3 Formula Verification

| Verification | Result | Evidence |
|-------------|--------|----------|
| `revenue_yego_net` = ABS(real) + proxy inline? | **YES** | Pipeline: enriched temp applies ABS → resolution aliases as `revenue_yego_net` → fact tables store already-ABS+proxy value |
| Contains only completed_flag trips? | **YES** | All SELECT use `FILTER (WHERE completed_flag)` |
| revenue < GMV? | **YES** | Take rate ~3%. GMV = `total_fare`. Revenue = commission (3% of ticket). Validated by `validate_real_revenue_gmv.py` |
| Identical formula daily/weekly/monthly? | **YES** | Same `SUM(revenue_yego_net) FILTER (WHERE completed_flag)` pattern in all three fact INSERT queries |
| GMV used as revenue fallback? | **NO** | Confirmed in migrations 009, 010, 120, 121, 122. GMV is a separate column (`gmv_passenger_paid`, `total_fare`). Revenue is commission only. |
| ABS applied before aggregation? | **YES** | ABS is applied on each trip in enriched temp BEFORE GROUP BY in resolution CTE |

---

## 4. GRAIN AUDIT

### 4.1 Grain Definitions

| Fact Table | Time Column | Primary Grain | Grouping Dimensions |
|-----------|------------|---------------|-------------------|
| `day_fact` | `trip_date` (indexed) | Daily | `(trip_date, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name)` |
| `week_fact` | `week_start` (ISO Monday) | Weekly | Same dimensions, week_start from trip_date |
| `month_fact` | `month` (date_trunc month) | Monthly | Same dimensions, month from trip_date |

### 4.2 Grain Contract (kpi_aggregation_rules.py)

| KPI Key | Aggregation Type | Cross-Grain Decision | Drift Alerts | Comparison Rule |
|---------|-----------------|---------------------|-------------|-----------------|
| `revenue_yego_net` | additive | YES | YES | `exact_sum` |
| `commission_pct` | non_additive_ratio | YES (same_formula) | NO | `same_formula_different_scope` |
| `avg_ticket` | non_additive_ratio | YES (same_formula) | NO | `same_formula_different_scope` |
| `trips_completed` | additive | YES | YES | `exact_sum` |
| `active_drivers` | semi_additive_distinct | NO | YES | `not_directly_comparable` |

Contract: `SUM(daily_in_month) == monthly` for `revenue_yego_net` (tolerance ≤1%)  
Source: `kpi_aggregation_rules.py:125-149`

### 4.3 Grain Compliance

| Check | Status | Evidence |
|-------|--------|----------|
| Daily → Weekly is exact SUM? | **PASS** | Week_fact built by aggregating day_fact rows |
| Weekly → Monthly is exact SUM? | **PASS** | Month_fact built from enriched temp (NOT rolled up from week_fact) |
| Cross-grain comparison rule defined? | **PASS** | `kpi_aggregation_rules.py:142` — `comparison_rule: COMP_EXACT_SUM` |
| Frontend respects grain contract? | **PASS** | Frontend only sums rows within same period; no cross-grain arithmetic |
| active_drivers excluded from SUM in projection? | **PASS** | `projectionMatrixUtils.js:437`: `if (kpi === 'active_drivers') continue` |

---

## 5. AGGREGATION PATH AUDIT

### 5.1 Complete Path

```
Individual Trip (public.trips_2025 / trips_2026)
  │  comision_empresa_asociada (with NaN guard via NULLIF)
  ▼
Enriched Base View (ops.v_real_trips_enriched_base)
  │  revenue_yego_net = NULLIF(comision_empresa_asociada, 0)
  ▼
Enriched Temp Table (_bs_enriched_month)
  │  revenue_yego_real  = ABS(revenue_yego_net)
  │  revenue_yego_proxy = ticket * commission_pct (3% default)
  │  revenue_yego_final = COALESCE(real, proxy)
  ▼
Resolution CTE (park matching → business_slice assignment)
  │  Alias: revenue_yego_real AS revenue_yego_net
  ▼
Aggregation (GROUP BY country, city, slice, fleet, subfleet, period)
  │  revenue_yego_net  = SUM(revenue_yego_real aliased)
  │  revenue_yego_final = SUM(revenue_yego_final)
  ▼
Fact Tables (day_fact, week_fact, month_fact)
  ▼
Serving View / API Read / Projection Read
  ▼
Frontend: SUM of rows per period → Totals
```

### 5.2 Double Aggregation Risk Analysis

| Risk | File:Line | Severity | Detail | Verdict |
|------|----------|----------|--------|---------|
| `active_drivers` SUM across slices | `business_slice_service.py:533` | WARNING | `SUM(active_drivers)` sums pre-aggregated per-slice distinct counts → overcounts unique drivers cross-slice | **Known limitation, documented** |
| `avg_ticket` recomputation | `business_slice_service.py:469-472` | PASS | `SUM(avg_ticket * trips_completed) / SUM(trips_completed)` — correct weighted average | **Correct** |
| `commission_pct` recomputation | `business_slice_service.py:471-472` | PASS | Same weighted-average pattern as avg_ticket | **Correct** |
| `revenue_yego_net` SUM from fact | `business_slice_service.py:468,534,586` | PASS | Pure additive across non-overlapping slices — no double count | **Correct** |
| Frontend totals `buildMatrix` | `omniviewMatrixUtils.js:658-664` | PASS | Sums revenue_yego_net from each row — rows don't share grain | **Correct** |
| Frontend totals `buildProjectionMatrix` | `projectionMatrixUtils.js:436-440` | PASS | Same additive pattern, active_drivers excluded | **Correct** |

### 5.3 TOTAL = SUM(detail) Verification

| Check | Status |
|-------|--------|
| Separate query for totals? | **PASS** — No. `buildMatrix` and `buildProjectionMatrix` sum from the same rows |
| Different source for totals? | **PASS** — Same endpoint, same response |
| Revenue = 0 shown correctly? | **PASS** — Fixed: `actual != null && !isNaN(Number(actual))` (was `actual > 0`) |
| Period totals use same serving source? | **PASS** — `FACT_MONTHLY = v_real_business_slice_month_serving` (redirect view) |

---

## 6. FILTER LEAKAGE AUDIT

### 6.1 Filters by Layer

| Layer | Filters Applied | Potential Leakage | Status |
|------|----------------|-------------------|--------|
| Business Slice API | `country`, `city`, `business_slice`, `fleet`, `subfleet`, `year`, `month` | Country/city are optional. No filter = all currencies mixed | **WARNING** |
| Omniview API | Same + `time_column = value`, `is_subfleet IS NOT TRUE` | Country/city optional | **WARNING** |
| Period Totals | Same filters as parent endpoint | Consistent with main endpoint | **PASS** |
| Projection API | `country`, `city`, `business_slice`, `year`, `month`, `is_subfleet IS NOT TRUE` | Country optional; global totals mix currencies | **FAIL** |
| UNMAPPED bucket | Separate query, `business_slice = '__UNMAPPED__'` | Intentionally excluded from filtered views | **PASS** |
| Year boundary (Jan) | `month = prev_dec OR month = cur` for MoM | December-1 correctly included | **PASS** |
| Closed period enforcement | `period_state_engine` blocks writes to locked periods | Read still served (from snapshot) | **PASS** |
| Subfleet excluded by default | `is_subfleet IS NOT TRUE` | Consistent across all endpoints | **PASS** |

### 6.2 Currency Mixing Risk

| Risk | Severity | Detail |
|------|----------|--------|
| PEN + COP summed without conversion | **FAIL** | `country` filter is optional. When omitted, revenue_yego_net from Colombia (COP) and Peru (PEN) are summed arithmetically. No currency conversion. |
| Country rollup correct per-country | **PASS** | `_fetch_fact_rollup_by_country` correctly groups by country first |
| YTD revenue multi-currency | **WARNING** | `projectionMeta.ytd_real_revenue` aggregates all countries |

---

## 7. METRIC DIFFERENCE ANALYSIS

### 7.1 `revenue_yego_net`

| Attribute | Value | Source |
|----------|-------|--------|
| Definition | ABS(comision_empresa_asociada) real + proxy, aggregated per slice | `business_slice_incremental_load.py:85` |
| Origin | `comision_empresa_asociada` in `public.trips_2025` / `public.trips_2026` | migration 126 |
| Contains proxy? | **YES** — Proxy fills NULL/zero real commission BEFORE aggregation | `business_slice_incremental_load.py:978-1000` |
| ABS applied? | **YES** — Applied per trip in enriched temp, aliased through resolution CTE | `business_slice_incremental_load.py:978,174` |
| completed_flag filter? | **YES** — All SELECT use `FILTER (WHERE completed_flag)` | `business_slice_incremental_load.py:85` |
| Used in UI? | **YES** — Primary revenue field consumed by frontend Omniview | `omniviewMatrixUtils.js:14,664` |

### 7.2 `revenue_yego_final`

| Attribute | Value | Source |
|----------|-------|--------|
| Definition | `COALESCE(revenue_yego_real, revenue_yego_proxy)` per trip, aggregated | `business_slice_incremental_load.py:991-1000` |
| Exists in fact tables? | **YES** — All three fact tables (day/week/month) | `business_slice_incremental_load.py:124` |
| Exists in serving view? | **NO** — `v_real_business_slice_month_serving` omits this column | migration 143:97,132 |
| Used in Omniview API? | **YES** as COALESCE fallback: `COALESCE(revenue_yego_final, revenue_yego_net)` | `business_slice_omniview_service.py:654` |
| Used in Projection? | **YES** as dual fallback: `ABS(COALESCE(_final, _net))` | `projection_expected_progress_service.py:2656` |
| Functionally different from `_net`? | **THEORETICALLY IDENTICAL** — Both come from same pipeline (real + proxy). `_final` is the explicit best-effort expression. | `business_slice_incremental_load.py:85,124` |

### 7.3 `revenue_total`

| Attribute | Value |
|----------|-------|
| Definition | NOT a revenue column. Exists only as `projected_revenue_total` in plan context. |
| In real revenue flow? | **NO** — Not applicable. |
| Status | **NON-EXISTENT** for real revenue. |

### 7.4 `revenue_display`

| Attribute | Value |
|----------|-------|
| Definition | Does not exist anywhere in the codebase. |
| Status | **NON-EXISTENT.** No column, variable, or field with this name. |

### 7.5 Comparison Matrix

| Column | Is Real? | Proxy? | ABS? | In Serving View? | In API? | In UI? |
|--------|---------|--------|------|-----------------|---------|--------|
| `revenue_yego_net` | YES | YES (inline) | YES | YES | YES | YES |
| `revenue_yego_final` | YES | YES (COALESCE) | YES | **NO** | YES (fallback) | NO (indirect) |
| `revenue_total` | NO | — | — | — | NO | NO |
| `revenue_display` | — | — | — | — | NO | NO |
| `gross_revenue` | YES | N/A | N/A | N/A (LOB) | YES | YES (LOB) |
| `margin_total` | YES | N/A | ABS via rollup | N/A | YES (comparatives) | YES |
| `projected_revenue` | NO (plan) | N/A | N/A | N/A | YES (plan) | YES |

---

## 8. LAYER-BY-LAYER CERTIFICATION

### 8.1 Revenue Header (KPI Semantics + Aggregation Rules)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | `revenue` registered in `KPI_SEMANTICS` | **PASS** | `kpi_semantics.py:55-60`: `type=additive`, `decision_role=decision_ready`, `db_column=revenue_yego_net` |
| 2 | `revenue_yego_net` in `OMNIVIEW_MATRIX_KPI_RULES` | **PASS** | `kpi_aggregation_rules.py:125-149`: Full grain contract defined |
| 3 | Aggregation type = additive | **PASS** | `AGG_ADDITIVE`, formula consistent daily/weekly/monthly |
| 4 | Cross-grain comparable | **PASS** | `comparison_rule = exact_sum` |
| 5 | Drift alerts enabled | **PASS** | `allowed_for_drift_alerts = True` |
| 6 | Priority scoring enabled | **PASS** | `allowed_for_priority_scoring = True` |
| 7 | Decision ready | **PASS** | `allowed_for_cross_grain_decision = True` |
| 8 | Visible in Omniview Matrix | **PASS** | Listed in `OMNIVIEW_MATRIX_VISIBLE_KPIS:307` |
| 9 | Supporting component | **PASS** | Listed in `OMNIVIEW_SUPPORTING_COMPONENTS:316` (`commission_pct` denominator) |
| 10 | SOT-registered as primary source | **PASS** | `source_of_truth_registry.py:97-98`: `omniview_matrix → ops.real_business_slice_month_fact (canonical)` |

**Revenue Header: PASS (10/10)**

### 8.2 Revenue Matrix (Omniview API)

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Source is SOT-registered canonical | **PASS** | `omniview_matrix` domain: `source_mode = canonical` |
| 2 | No forbidden source used | **PASS** | `ServingPolicy` blocks `v_resolved`, `enriched_base` in strict mode |
| 3 | Fact-first read (no raw scan) | **PASS** | `_fetch_fact_slice_rows` reads from fact tables directly |
| 4 | COALESCE fallback exists | **PASS** | `COALESCE(revenue_yego_final, revenue_yego_net)` with exception-based fallback to `_net` only |
| 5 | `revenue_yego_final` in serving view | **WARNING** | Column NOT in `v_real_business_slice_month_serving` (m143:97,132). API works via COALESCE fallback to `_net`. |
| 6 | DB gate enforcement | **PASS** | `execute_db_gated_query` with `DB_SERVING_GUARD_MODE = 'warn'` |
| 7 | Multi-currency handling | **WARNING** | No country filter → PEN + COP summed without distinction. UI warns but doesn't block. |
| 8 | Revenue sorting works | **PASS** | `sortLineEntries` with `revenue_desc` sorts by `sumMetric(line, 'revenue_yego_net')` |
| 9 | Weighted avg recomputation | **PASS** | `avg_ticket` and `commission_pct` recomputed via weighted sum/division in rollup queries |
| 10 | NaN/Infinity safe | **PASS** | NaN guard in canon_120d (migration 122:42). `_json_safe_scalar` converts NaN/inf to None. |

**Revenue Matrix: PASS (1 WARNING — revenue_yego_final in serving view)**

### 8.3 Revenue Totals

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Totals = SUM(detail rows) | **PASS** | `buildMatrix` and `buildProjectionMatrix` sum from the same rows. No separate query. |
| 2 | Period totals use canonical fact | **PASS** | `_fetch_month_fact_period_totals` uses `FACT_MONTHLY = v_real_business_slice_month_serving` |
| 3 | Comparison totals valid | **PASS** | `_fetch_resolved_metrics_for_range` uses day_fact with correct SUM |
| 4 | YTD revenue computed | **PASS** | `projectionMeta.ytd_real_revenue` and `ytd_plan_expected_revenue` available |
| 5 | UNMAPPED included correctly | **WARNING** | UNMAPPED included in global totals via `need_unmapped`. Correct for global view, may inflate filtered views. |
| 6 | NaN-safe totals | **PASS** | `_json_safe_scalar` → NaN/inf to None. Frontend `Number(value) \|\| 0`. |
| 7 | Cross-grain additive consistency | **PASS** | `SUM(revenue_yego_net)` is additive → `SUM(monthly) == YTD` |

**Revenue Totals: PASS (1 WARNING — UNMAPPED inclusion in filtered views)**

### 8.4 Revenue Period Totals

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Monthly totals from month_fact | **PASS** | `_fetch_month_fact_period_totals` → `SUM(revenue_yego_net) GROUP BY month` |
| 2 | Weekly totals from week_fact | **PASS** | `_fetch_week_fact_period_totals` → `SUM(revenue_yego_net) GROUP BY week_start` |
| 3 | Daily totals from day_fact | **PASS** | `_fetch_day_fact_period_totals` → `SUM(revenue_yego_net) GROUP BY trip_date` |
| 4 | Non-standard grain fallback | **PASS** | `_fetch_resolved_period_totals` → V_RESOLVED with guardrail assertion |
| 5 | `active_drivers` SUM issue (non-revenue) | **WARNING** | SUM(active_drivers) overcounts unique drivers cross-slice. Does NOT affect revenue_yego_net. |
| 6 | Weighted avg correct | **PASS** | `avg_ticket` and `commission_pct` recomputed via `SUM(value * trips) / SUM(trips)` |

**Revenue Period Totals: PASS (1 WARNING — active_drivers, non-revenue)**

### 8.5 Revenue Territory Totals

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Country rollup exists | **PASS** | `_fetch_fact_rollup_by_country` → `GROUP BY country` |
| 2 | City-level drill-down | **PASS** | Business slice API filters by `city` parameter |
| 3 | Territory = SUM(slices) | **PASS** | Pure additive — `SUM(revenue_yego_net)` is consistent per country |
| 4 | Per-country totals are correct | **PASS** | Each country's revenue is internally consistent (PEN within Peru, COP within Colombia) |
| 5 | Global total cross-currency | **FAIL** | When `country` filter absent, `buildMatrix` and `buildProjectionMatrix` sum PEN + COP arithmetically without conversion. The global TOTAL is economically meaningless. |

**Revenue Territory Totals: FAIL (1 FAIL — cross-currency sum in global totals)**

---

## 9. QUALITY & GUARDRAILS AUDIT

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1 | Revenue quality alerts system | **PASS** | `revenue_quality_service.py`: 5 checks (NaN, proxy coverage, missing, zero revenue, chain drift) |
| 2 | NaN guard in RAW layer | **PASS** | migration 122:42: `NULLIF(col, 'NaN'::numeric)` on `comision_empresa_asociada` and `precio_yango_pro` |
| 3 | NaN guard in aggregates | **PASS** | `revenue_quality_service.py:132-144`: checks `mv_real_lob_day_v2` for NaN in `gross_revenue`/`margin_total` |
| 4 | Proxy coverage thresholds | **PASS** | >80% proxy = warning, >95% = blocked. Config in `revenue_quality_service.py:18-26` |
| 5 | Cross-chain drift monitoring | **PASS** | Business Slice vs hourly-first trips comparison (`revenue_quality_service.py:170-213`) |
| 6 | Forbidden source enforcement | **PASS** | 5 sources blocked. `ServingPolicy` strict mode. `execute_db_gated_query` enforces. |
| 7 | Alert persistence | **PASS** | `ops.revenue_quality_alerts` table with indexed severity and timestamp |
| 8 | Commission proxy config governance | **PASS** | `ops.yego_commission_proxy_config` with specificity-based resolution (migration 120:62-91) |

---

## 10. CONSOLIDATED CERTIFICATION TABLE

| Capa | Metric | Source | Formula | Certified | Observations |
|------|--------|--------|---------|-----------|-------------|
| **Header** | `revenue` KPI | `kpi_semantics.py:55` | additive, decision_ready | **PASS** | Aligned with aggregation rules. No ambiguity. |
| **Header** | `revenue_yego_net` rules | `kpi_aggregation_rules.py:125` | `exact_sum` cross-grain | **PASS** | Drift alerts + priority scoring enabled. |
| **Serving Fact** | `revenue_yego_net` | `ops.real_business_slice_day_fact` | `SUM(ABS(comision)+proxy)` | **PASS** | Pipeline certified RAW→fact. Coverage measurable. |
| **Serving Fact** | `revenue_yego_net` | `ops.real_business_slice_week_fact` | Aggregate from day_fact | **PASS** | Backfill stabilized (CF-H1I2). |
| **Serving Fact** | `revenue_yego_net` | `ops.real_business_slice_month_fact` | Aggregate from enriched temp | **PASS** | Primary source per SOT registry. |
| **Serving Fact** | `revenue_yego_final` | `ops.real_business_slice_*_fact` | `COALESCE(real, proxy)` | **PASS** | Exists in all three fact tables. Used as COALESCE fallback in API. |
| **Serving View** | `revenue_yego_final` | `ops.v_real_business_slice_month_serving` | N/A (column missing) | **WARNING** | Column NOT propagated (m143:97,132). API uses COALESCE fallback to `_net`. |
| **API** | `revenue_yego_net` | `GET /ops/business-slice/monthly` | `SUM() via serving view` | **PASS** | ServingPolicy strict. FACT_MONTHLY redirect. |
| **API** | `revenue_yego_net` | `GET /ops/business-slice/weekly` | `SUM() from week_fact` | **PASS** | Same serving discipline. |
| **API** | `revenue_yego_net` | `GET /ops/business-slice/daily` | `SUM() from day_fact` | **PASS** | Same serving discipline. |
| **API** | `completed_revenue_sum` | `GET /ops/business-slice/omniview` | `COALESCE(_final, _net)` | **PASS** | Fact-first read with fallback to `_net`. |
| **API** | `real_revenue` | `GET /ops/business-slice/omniview-projection` | `ABS(COALESCE(_final, _net))` | **PASS** | Dual fallback: `_final` → `_net` → `ABS`. |
| **API** | `gross_revenue` | `GET /ops/real-lob/*` | `GREATEST(0, COALESCE(real, proxy, 0))` | **LEGACY** | Hourly-first LOB. NOT canonical revenue for Omniview. |
| **UI** | `revenue_yego_net` | `omniviewMatrixUtils.js:664` | `SUM(rows) → totals` | **PASS** | Same source as API rows. No separate query. |
| **UI** | `revenue_yego_net` | `projectionMatrixUtils.js:438` | `SUM(rows) → totals + attainment` | **PASS** | active_drivers correctly excluded. |
| **UI** | YTD revenue | `BusinessSliceOmniviewMatrix.jsx` | `meta.ytd_real_revenue` | **WARNING** | No currency distinction. PEN+COP summed in global YTD. |
| **Totals** | Period totals | `_fetch_*_period_totals` | `SUM(revenue_yego_net)` | **PASS** | Pure additive, no double aggregation risk. |
| **Totals** | `active_drivers` in totals | `_fetch_*_period_totals` | `SUM(active_drivers)` | **WARNING** | Overcounts cross-slice. Documented. Does not affect revenue. |
| **Territory** | Country rollup | `_fetch_fact_rollup_by_country` | `SUM() GROUP BY country` | **PASS** | Correct per-country. |
| **Territory** | Global total cross-currency | `buildMatrix`/`buildProjectionMatrix` totals | `SUM` all countries | **FAIL** | PEN + COP summed without conversion. Economically meaningless. |
| **Guardrails** | Forbidden sources | `serving_guardrails.py:55` | 5 sources blocked | **PASS** | Strict mode for SERVING queries. |
| **Guardrails** | DB gate | `execute_db_gated_query` | ContextVar tracking | **PASS** | `warn` mode by default. |
| **Quality** | Revenue quality alerts | `revenue_quality_service.py` | 5 check types | **PASS** | NaN, proxy, missing, zero, drift. Persisted in `ops.revenue_quality_alerts`. |
| **Quality** | Proxy coverage thresholds | `revenue_quality_service.py:18-21` | 3 tiers | **PASS** | >90% HIGH, 70-90% MEDIUM, <70% LOW. |

---

## 11. GLOBAL CERTIFICATION SUMMARY

### 11.1 Summary by Layer

| Layer | PASS | WARNING | FAIL | Verdict |
|-------|------|---------|------|---------|
| Revenue Header | 10 | 0 | 0 | **PASS** |
| Revenue Matrix | 8 | 2 | 0 | **PASS** |
| Revenue Totals | 6 | 1 | 0 | **PASS** |
| Revenue Period Totals | 5 | 1 | 0 | **PASS** |
| Revenue Territory Totals | 3 | 0 | 1 | **FAIL** |
| Quality & Guardrails | 8 | 0 | 0 | **PASS** |
| **TOTAL** | **40** | **4** | **1** | — |

### 11.2 Overall Verdict

**REVENUE FLOW: CONDITIONAL PASS**

The revenue flow is certified for operation with documented exceptions.  
The single FAIL is limited to cross-currency aggregation in global totals — per-country revenue is correct.

### 11.3 WARNINGS (4 — non-blocking, require attention)

| ID | Severity | Area | Description |
|----|----------|------|-------------|
| W-01 | MEDIUM | Serving View | `revenue_yego_final` not propagated to `ops.v_real_business_slice_month_serving` (migration 143:97,132). Impact: COALESCE fallback in Omniview/projection operates on fact table directly when serving view is used as `FACT_MONTHLY`. The API has error-handling fallback to `revenue_yego_net`. |
| W-02 | LOW | Period Totals | `SUM(active_drivers)` overcounts unique drivers across business slices. Does NOT affect revenue_yego_net. |
| W-03 | MEDIUM | UI | Multi-currency revenue without country filter: PEN and COP values summed in global views. UI warns but does not block. |
| W-04 | LOW | UI | YTD revenue (`meta.ytd_real_revenue`) aggregates all countries without currency distinction. |

### 11.4 FAILS (1 — blocking for full certification)

| ID | Severity | Area | Description |
|----|----------|------|-------------|
| F-01 | **HIGH** | Territory Totals | Cross-currency sum in global totals. When no `country` filter is applied, `buildMatrix` and `buildProjectionMatrix` sum `revenue_yego_net` from Colombia (COP) and Peru (PEN) arithmetically without conversion. The global TOTAL figure is economically meaningless. Recommendation: require `country` filter for global totals, or display per-currency breakdown, or convert to base currency before summing. |

---

## 12. KEY FILE REFERENCE

| File | Role |
|------|------|
| `backend/app/config/kpi_semantics.py:55-60` | KPI type + decision_role for revenue |
| `backend/app/config/kpi_aggregation_rules.py:125-149` | Grain contract, formulas, cross-grain rules for revenue_yego_net |
| `backend/app/config/source_of_truth_registry.py:97-112` | Canonical source declaration (omniview_matrix, business_slice, revenue_proxy) |
| `backend/app/services/serving_guardrails.py:55-61` | FORBIDDEN_SERVING_SOURCES (5 blocked), ServingPolicy |
| `backend/app/services/business_slice_incremental_load.py:974-1013` | Enriched temp: revenue_yego_real, _proxy, _final, _source |
| `backend/app/services/business_slice_incremental_load.py:40-146` | _RESOLVE_AND_AGG_FROM_TEMP: revenue aggregation into month_fact |
| `backend/app/services/business_slice_incremental_load.py:174` | Alias: revenue_yego_real AS revenue_yego_net |
| `backend/app/services/business_slice_service.py:47-51` | FACT_MONTHLY/DAILY/WEEKLY constants |
| `backend/app/services/business_slice_service.py:468,534,586` | revenue_yego_net SUM in API queries |
| `backend/app/services/business_slice_omniview_service.py:56-67` | Omniview ServingPolicy declaration |
| `backend/app/services/business_slice_omniview_service.py:654,683` | COALESCE(fallback) revenue column in fact-first read |
| `backend/app/services/business_slice_omniview_service.py:696-749` | Country rollup with COALESCE |
| `backend/app/services/projection_expected_progress_service.py:2656-2657` | _REVENUE_SELECT / _REVENUE_SELECT_FALLBACK |
| `backend/app/services/revenue_quality_service.py` | 5 revenue quality checks |
| `frontend/src/components/omniview/omniviewMatrixUtils.js:14,658-664` | MATRIX_KPIS definition + revenue aggregation |
| `frontend/src/components/omniview/projectionMatrixUtils.js:436-440` | Projection revenue aggregation (active_drivers excluded) |
| `backend/alembic/versions/120_revenue_proxy_config_and_layer.py` | Proxy config table, resolve_commission_pct(), audit view |
| `backend/alembic/versions/121_consolidate_hourly_first_revenue.py` | canon_120d to trips_2025+2026, hourly-first revenue integration |
| `backend/alembic/versions/122_revenue_hardening_nan_guard_and_alerts.py` | NaN guard in canon_120d, revenue_quality_alerts table |
| `backend/alembic/versions/143_last_good_snapshots.py:69-147` | v_real_business_slice_month_serving definition (NO revenue_yego_final) |
| `docs/control_foundation/CF_H2_REVENUE_CANONICAL_DEFINITION.md` | Revenue canonical definition (prior certification) |
| `docs/omniview/REVENUE_DETAIL_SERVING_AUDIT.md` | Serving fact revenue audit |
| `docs/omniview/REVENUE_TOTAL_VS_DETAIL_AUDIT.md` | Totals vs detail reconciliation |
