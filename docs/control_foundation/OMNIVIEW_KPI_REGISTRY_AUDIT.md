# Omniview KPI Registry Audit — Control Foundation H1

## Fecha: 2026-05-29
## Scope: Omniview Matrix (Evolution + Vs Proyección)

---

## KPI: trips_completed

| Attribute | Value |
|-----------|-------|
| **Label** | Viajes |
| **Key** | trips_completed |
| **Aggregation Type** | ADDITIVE |
| **Comparable Cross-Grain** | YES |

### Fuente Real

| Grain | Formula | Source Table | Endpoint |
|-------|---------|-------------|----------|
| Daily | `COUNT(*) FILTER (WHERE completed_flag)` grouped by trip_date | `ops.real_business_slice_day_fact` | `getOmniviewProjection()` / `getBusinessSliceDaily()` |
| Weekly | `SUM(d.trips_completed)` — rollup from day_fact | `ops.real_business_slice_week_fact` | `getOmniviewProjection()` / `getBusinessSliceWeekly()` |
| Monthly | `COUNT(*) FILTER (WHERE completed_flag)` — direct from enriched trips | `ops.real_business_slice_month_fact` | `getOmniviewProjection()` / `getBusinessSliceMonthly()` |

### Fuente Plan
- `ops.v_plan_projection_control_loop` → `projected_trips`
- Monthly plan distributed to weeks/days via seasonal curve

### Freshness
- Global: `MAX(trip_date)` from `ops.real_business_slice_day_fact`
- Per-KPI: `MAX(date) WHERE trips_completed > 0`
- Status: **OK** — additive, freshness coincides with trips

### Verdict: **PASS** — Definition consistent across all grains. SUM equivalent to COUNT.

---

## KPI: active_drivers

| Attribute | Value |
|-----------|-------|
| **Label** | Conductores |
| **Key** | active_drivers |
| **Aggregation Type** | SEMI_ADDITIVE (distinct count) |
| **Comparable Cross-Grain** | NO |

### Fuente Real

| Grain | Formula | Source Table | Correctness |
|-------|---------|-------------|-------------|
| Daily | `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)` grouped by trip_date | `ops.real_business_slice_day_fact` | **CORRECT** |
| Weekly | `SUM(COALESCE(d.active_drivers, 0))` — rollup from day_fact | `ops.real_business_slice_week_fact` | **INCORRECT** — SUM of daily distinct counts |
| Monthly | `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)` — direct from enriched trips | `ops.real_business_slice_month_fact` | **CORRECT** |

### Fuente Plan
- `ops.v_plan_projection_control_loop` → `projected_active_drivers`
- Monthly plan distributed to weeks/days via seasonal curve

### Freshness
- Global: depends on `MAX(trip_date)` (trips-based)
- Per-KPI: `MAX(date) WHERE active_drivers > 0` (implemented in hotfix)
- Status: **PARTIAL** — daily and monthly correct. Weekly has SUM proxy bug.

### Weekly Bug Detail
**File**: `backend/app/services/business_slice_incremental_load.py` line 581
```sql
SUM(COALESCE(d.active_drivers, 0))::bigint AS active_drivers
```
Instead of:
```sql
COUNT(DISTINCT d.driver_id) FILTER (WHERE d.completed_flag) AS active_drivers
```
Impact: For a week where N distinct drivers complete trips across 5-7 days, the SUM(daily) overestimates by factor of ~5-7x.

### Verdict: **CONDITIONAL PASS** — Daily and monthly correct. Weekly needs hardening.

---

## KPI: revenue_yego_net

| Attribute | Value |
|-----------|-------|
| **Label** | Revenue |
| **Key** | revenue_yego_net |
| **Aggregation Type** | ADDITIVE |
| **Comparable Cross-Grain** | YES |

### Fuente Real

| Grain | Formula | Source Table |
|-------|---------|-------------|
| Daily | `SUM(revenue_yego_net) FILTER (WHERE completed_flag)` grouped by trip_date | `ops.real_business_slice_day_fact` |
| Weekly | `SUM(COALESCE(d.revenue_yego_net, 0))` — rollup from day_fact | `ops.real_business_slice_week_fact` |
| Monthly | `SUM(revenue_yego_net) FILTER (WHERE completed_flag)` — direct | `ops.real_business_slice_month_fact` |

### Fuente Plan
- `ops.v_plan_projection_control_loop` → `projected_revenue`
- Monthly plan distributed

### Freshness
- Consistent with trips (additive KPI)
- Status: **OK**

### Verdict: **PASS** — Additive, consistent across grains.

---

## KPI: avg_ticket

| Attribute | Value |
|-----------|-------|
| **Label** | Ticket |
| **Key** | avg_ticket |
| **Aggregation Type** | RATIO (non-additive) |
| **Comparable Cross-Grain** | Formula-only |

### Fuente Real

| Grain | Formula | Source Table |
|-------|---------|-------------|
| Daily | `AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL)` | `ops.real_business_slice_day_fact` |
| Weekly | Weighted average: `SUM(ticket_sum_completed) / SUM(ticket_count_completed)` — rollup from day_fact | `ops.real_business_slice_week_fact` |
| Monthly | `AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL)` — direct | `ops.real_business_slice_month_fact` |

### Fuente Plan
- Not directly projected. Derived as `revenue_plan / trips_plan` if both available.

### Freshness
- Consistent with trips
- Status: **OK**

### Verdict: **PASS** — Ratio recomputed correctly per grain.

---

## KPI: trips_per_driver

| Attribute | Value |
|-----------|-------|
| **Label** | TPD |
| **Key** | trips_per_driver |
| **Aggregation Type** | DERIVED RATIO |
| **Comparable Cross-Grain** | Formula-only |

### Fuente Real

| Grain | Formula | Source Table |
|-------|---------|-------------|
| Daily | `trips_completed / active_drivers` (where drivers > 0) | `ops.real_business_slice_day_fact` |
| Weekly | `SUM(trips_completed) / SUM(active_drivers)` — rollup from day_fact, **inherits weekly SUM proxy** | `ops.real_business_slice_week_fact` |
| Monthly | `trips_completed / active_drivers` — direct, correct denominator | `ops.real_business_slice_month_fact` |

### Weekly Impact
Since weekly `active_drivers` is overestimated (SUM proxy), `trips_per_driver` in weekly grain is **UNDERestimated**. For the same week, TPD ~= real / 5-7x.

### Freshness
- Consistent with parent KPIs
- Status: **INHERITS active_drivers bug** in weekly grain

### Verdict: **CONDITIONAL PASS** — Derived KPI inherits weekly active_drivers bug. Daily and monthly correct.

---

## Summary

| KPI | Daily | Weekly | Monthly | Status |
|-----|-------|--------|---------|--------|
| trips_completed | CORRECT | CORRECT | CORRECT | PASS |
| active_drivers | CORRECT | **SUM PROXY** | CORRECT | CONDITIONAL PASS (weekly hardening needed) |
| revenue_yego_net | CORRECT | CORRECT | CORRECT | PASS |
| avg_ticket | CORRECT | CORRECT | CORRECT | PASS |
| trips_per_driver | CORRECT | **INHERITS AD BUG** | CORRECT | CONDITIONAL PASS |

### Root Cause
`_WEEK_ROLLUP_FROM_DAY_FACT` (@ `business_slice_incremental_load.py:568`) uses:
```sql
SUM(COALESCE(d.active_drivers, 0))::bigint AS active_drivers
```
This SUMs already-computed daily distinct counts instead of computing a correct weekly `COUNT(DISTINCT driver_id)`.

### Affected Systems
- Omniview Evolution weekly view
- Omniview Vs Proyección weekly view
- `serving.omniview_projection_daily_fact` (when grain='weekly')
- Priority scoring / alerting for active_drivers in weekly grain
- Cross-grain comparisons involving weekly active_drivers
