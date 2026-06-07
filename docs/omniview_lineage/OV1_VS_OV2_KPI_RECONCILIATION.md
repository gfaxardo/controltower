# OV1 VS OV2 KPI RECONCILIATION — Pruebas de Consistencia

**Generated:** 2026-06-06  
**Phase:** Control Foundation — Omniview P0 Recovery (ACTIVE)  
**Method:** Static code analysis comparison (no live DB access)  
**Note:** Live reconciliation requires executing queries against the actual database. This report documents the reconciliation framework and classification methodology.

---

## 1. RECONCILIATION FRAMEWORK

### 1.1 Classification Taxonomy

| Classification | Meaning | Action Required |
|----------------|---------|-----------------|
| `SAME_SOURCE_SAME_VALUE` | Both read same table/column, should produce identical values | Verify with live query |
| `SAME_SOURCE_DIFFERENT_VALUE` | Same table, different column or aggregation — values may differ | Explain and document difference |
| `DIFFERENT_SOURCE_SAME_VALUE` | Different sources converge to same value | Verify convergence |
| `DIFFERENT_SOURCE_DIFFERENT_VALUE` | Different sources produce different values | Investigate which is authoritative |
| `V2_INHERITS_V1_RISK` | V2 dependency chain includes V1 defect-prone assets | Remediate upstream first |
| `V2_ISOLATED_FROM_V1` | V2 reads from independent source, no V1 risk | Safe to proceed |

### 1.2 Data Sources Compared

| Source Label | Description |
|-------------|-------------|
| **V1 endpoint** | Value served by `GET /ops/business-slice/{monthly|weekly|daily}` |
| **V2 endpoint** | Value served by `GET /ops/omniview-v2/matrix?source_system=CT_TRIPS_2026` |
| **Serving fact direct** | Value read directly from `ops.real_business_slice_{grain}_fact` |
| **MV direct** | Value read from `ops.mv_plan_vs_real_monthly_fact[_canonical]` (Plan vs Real only) |
| **Raw/fact table direct** | Value from `public.trips_2026` (when viable, for comparison) |

---

## 2. KPI RECONCILIATION BY METRIC

### 2.1 TRIPS (trips_completed)

#### Source Chain Analysis

```
V1: GET /ops/business-slice/monthly
  → business_slice_service.get_business_slice_monthly()
    → SELECT trips_completed FROM ops.v_real_business_slice_month_serving
      → ops.real_business_slice_month_fact (or snapshot if locked)

V2: GET /ops/omniview-v2/matrix?source_system=CT_TRIPS_2026&grain=month
  → omniview_v2_matrix_repository.get_ct_matrix_data()
    → SELECT SUM(trips_completed) FROM ops.real_business_slice_month_fact
      GROUP BY month, business_slice_name

Serving fact direct:
  → SELECT SUM(trips_completed) FROM ops.real_business_slice_month_fact
    WHERE month = ?
```

**Classification:** `SAME_SOURCE_SAME_VALUE`

Both V1 and V2 read `trips_completed` from `ops.real_business_slice_month_fact`. Values should be identical barring:
- V1 uses `v_real_business_slice_month_serving` (view that routes to snapshot or working fact)
- V2 queries the fact table directly
- For locked months, V1 may read from `real_business_slice_month_snapshot`, V2 from working fact

**Reconciliation SQL (to execute against DB):**

```sql
-- Compare trips between V1 and V2 source for a given month
SELECT
    'V1_source' as source,
    month,
    SUM(trips_completed) as total_trips
FROM ops.v_real_business_slice_month_serving
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'
GROUP BY month

UNION ALL

SELECT
    'V2_source' as source,
    month,
    SUM(trips_completed) as total_trips
FROM ops.real_business_slice_month_fact
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'
GROUP BY month;
```

---

### 2.2 REVENUE

#### Source Chain Analysis (CRITICAL DIFFERENCE DETECTED)

```
V1: GET /ops/business-slice/monthly
  → SELECT COALESCE(revenue_yego_final, revenue_yego_net) AS completed_revenue_sum
    FROM ops.v_real_business_slice_month_serving

V2: GET /ops/omniview-v2/matrix?source_system=CT_TRIPS_2026
  → SELECT SUM(revenue_yego_final)
    FROM ops.real_business_slice_month_fact
    GROUP BY month, business_slice_name

Serving fact direct:
  → SELECT SUM(revenue_yego_final), SUM(revenue_yego_net)
    FROM ops.real_business_slice_month_fact WHERE month = ?
```

**Classification:** `SAME_SOURCE_DIFFERENT_VALUE`

**Critical difference:** V1 uses `COALESCE(revenue_yego_final, revenue_yego_net)`, V2 uses `revenue_yego_final` directly.

**When values will differ:**
- Periods where `revenue_yego_final IS NULL` but `revenue_yego_net` has a value
- V1 will show `revenue_yego_net` value (silent fallback)
- V2 will show NULL or 0

**Risk:** If `revenue_yego_final` is not fully populated, V2 appears to have "missing revenue" where V1 shows data. This is architecturally better (no silent fallback) but operationally visible.

**Reconciliation SQL:**

```sql
-- Detect revenue gaps between V1 and V2
SELECT
    month,
    country,
    city,
    business_slice_name,
    SUM(COALESCE(revenue_yego_final, revenue_yego_net)) as v1_revenue,
    SUM(revenue_yego_final) as v2_revenue,
    SUM(revenue_yego_final) - SUM(COALESCE(revenue_yego_final, revenue_yego_net)) as delta,
    COUNT(*) FILTER (WHERE revenue_yego_final IS NULL AND revenue_yego_net IS NOT NULL) as rows_with_final_null,
    CASE
        WHEN SUM(COALESCE(revenue_yego_final, revenue_yego_net)) = SUM(revenue_yego_final) THEN 'SAME'
        WHEN SUM(revenue_yego_final) IS NULL THEN 'V2_NULL'
        ELSE 'DIFFERENT'
    END as match_status
FROM ops.real_business_slice_month_fact
WHERE country = 'peru' AND city = 'lima'
  AND month >= '2026-01-01'
GROUP BY month, country, city, business_slice_name
HAVING SUM(COALESCE(revenue_yego_final, revenue_yego_net)) != SUM(revenue_yego_final)
   OR SUM(revenue_yego_final) IS NULL
ORDER BY month;
```

---

### 2.3 DRIVERS (active_drivers)

#### Source Chain Analysis

```
V1: ops.real_business_slice_month_fact.active_drivers
V2: ops.real_business_slice_month_fact.active_drivers (SUM)
```

**Classification:** `SAME_SOURCE_SAME_VALUE`

Same table, same column. Values should be identical.

**Note on KPI contract:** `active_drivers` is classified as SEMI_ADDITIVE (not summable across grains). V1 and V2 both sum it at the query level, which is the same behavior (correct within the same grain, incorrect across grains).

**Reconciliation SQL:**

```sql
SELECT
    month,
    SUM(active_drivers) as total_active_drivers
FROM ops.real_business_slice_month_fact
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'
GROUP BY month;
```

---

### 2.4 TICKET (avg_ticket)

#### Source Chain Analysis

```
V1: ops.real_business_slice_month_fact.avg_ticket (pre-computed in fact table)
V2: ops.real_business_slice_month_fact.avg_ticket (AVG aggregation)
```

**Classification:** `SAME_SOURCE_SAME_VALUE`

Both read `avg_ticket` from the same fact table. The aggregation method differs (V1 uses `AVG(avg_ticket)`, V2 also uses `AVG(avg_ticket)`) but since `avg_ticket` is already an average per row, the result is identical within a grain.

**Reconciliation SQL:**

```sql
SELECT
    month,
    AVG(avg_ticket) as avg_ticket
FROM ops.real_business_slice_month_fact
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'
  AND avg_ticket IS NOT NULL
GROUP BY month;
```

---

### 2.5 TPD (trips_per_driver)

#### Source Chain Analysis

```
V1 (backend): trips_per_driver column from fact table OR computed trips/drivers
V1 (frontend): Computed as trips_completed / active_drivers (when backend doesn't provide)
V2: trips_per_driver column from fact table (AVG aggregation), or computed orders/drivers
```

**Classification:** `SAME_SOURCE_SAME_VALUE`

Both ultimately derive from the same fact table columns. Minor differences possible due to:
- V1 frontend division vs V2 backend division (floating point precision)
- V1 may use per-row `trips_per_driver`, V2 aggregates with AVG

---

### 2.6 PLAN VS REAL

#### Source Chain Analysis

```
V1: GET /ops/plan-vs-real/monthly
  → ops.mv_plan_vs_real_monthly_fact (LEGACY) or _canonical
  → Fallback: ops.v_plan_vs_real_realkey_final

V1: GET /ops/control-loop/plan-vs-real
  → ops.real_business_slice_month_fact + ops.v_plan_projection_control_loop

V2: GET /ops/omniview-v2/shell
  → Shell section "plan_vs_real" — only checks if plan data is available
  → Does NOT compute actual Plan vs Real values
```

**Classification:** `DIFFERENT_SOURCE_DIFFERENT_VALUE` (V2 doesn't compute)

V2 does not have a Plan vs Real computation. The shell `plan_vs_real` section only reports readiness (plan_available=true/false, plan_periods list). This is a feature gap, not a bug.

**V2 classification for Plan vs Real:** `V2_ISOLATED_FROM_V1` for calculation bugs (V2 doesn't calculate), but `V2_INHERITS_V1_RISK` for underlying data (plan data would come from same tables if V2 added the feature).

---

## 3. CLASSIFICATION SUMMARY TABLE

| KPI | V1 Source | V2 Source | Classification | Notes |
|-----|-----------|-----------|----------------|-------|
| **trips** (monthly) | `real_business_slice_month_fact.trips_completed` via serving view | Same table, direct query | `SAME_SOURCE_SAME_VALUE` | V1 uses view (snapshot routing), V2 uses direct table |
| **trips** (weekly) | `real_business_slice_week_fact.trips_completed` | Same table | `SAME_SOURCE_SAME_VALUE` | |
| **trips** (daily) | `real_business_slice_day_fact.trips_completed` | Same table | `SAME_SOURCE_SAME_VALUE` | |
| **revenue** (monthly) | `COALESCE(revenue_yego_final, revenue_yego_net)` | `revenue_yego_final` only | `SAME_SOURCE_DIFFERENT_VALUE` | V2 is stricter — exposes NULL where V1 falls back silently |
| **revenue** (projection) | `serving.omniview_projection_daily_fact.revenue_yego_final` | `real_business_slice_*_fact.revenue_yego_final` (matrix endpoint) | `DIFFERENT_SOURCE_SAME_VALUE` | Different intermediate but same underlying field |
| **drivers** (monthly) | `real_business_slice_month_fact.active_drivers` | Same table | `SAME_SOURCE_SAME_VALUE` | |
| **ticket** (monthly) | `real_business_slice_month_fact.avg_ticket` | Same table | `SAME_SOURCE_SAME_VALUE` | |
| **TPD** | Computed/column from fact table | Column from fact table | `SAME_SOURCE_SAME_VALUE` | |
| **Plan vs Real** | `mv_plan_vs_real_monthly_fact[_canonical]` or control loop | No equivalent (readiness only) | `V2_INHERITS_V1_RISK` (data) + `DIFFERENT_SOURCE_DIFFERENT_VALUE` (computation) | V2 doesn't compute Plan vs Real |
| **commission_pct** | Fact table column | Fact table column | `SAME_SOURCE_SAME_VALUE` | |
| **cancel_rate_pct** | Fact table column | Fact table column | `SAME_SOURCE_SAME_VALUE` | |

---

## 4. DEPENDENCY CHAIN CLASSIFICATION

| Asset | V1 Uses | V2 Uses | V2 Inherits V1 Risk? | Classification |
|-------|---------|---------|---------------------|----------------|
| `ops.real_business_slice_day_fact` | Si | Si (CT) | **SI** | `V2_INHERITS_V1_RISK` |
| `ops.real_business_slice_week_fact` | Si | Si (CT) | **SI** | `V2_INHERITS_V1_RISK` |
| `ops.real_business_slice_month_fact` | Si | Si (CT) | **SI** | `V2_INHERITS_V1_RISK` |
| `serving.omniview_projection_daily_fact` | Si | No | No (V2 no lo usa) | `V2_ISOLATED_FROM_V1` |
| `ops.mv_plan_vs_real_monthly_fact` | Si | No (solo referencia) | No | `V2_ISOLATED_FROM_V1` |
| `raw_yango.mv_orders_day` | No | Si (Yango shadow) | No | `V2_ISOLATED_FROM_V1` |
| `raw_yango.mv_revenue_day` | No | Si (Yango shadow) | No | `V2_ISOLATED_FROM_V1` |
| `ops.omniview_v2_serving_snapshot` | No | Si | No | `V2_ISOLATED_FROM_V1` |

---

## 5. LIVE RECONCILIATION — EXECUTION GUIDE

### 5.1 Prerequisites

- Database access to the production/QA PostgreSQL instance
- Read access to `ops` and `public` schemas
- Known test month (e.g., `2026-05-01`)

### 5.2 Step-by-Step Execution

#### Step 1: Verify fact table data availability

```sql
SELECT
    'daily' as grain,
    MIN(trip_date) as min_date,
    MAX(trip_date) as max_date,
    COUNT(*) as row_count
FROM ops.real_business_slice_day_fact
WHERE country = 'peru' AND city = 'lima'

UNION ALL

SELECT 'weekly', MIN(week_start)::text, MAX(week_start)::text, COUNT(*)
FROM ops.real_business_slice_week_fact
WHERE country = 'peru' AND city = 'lima'

UNION ALL

SELECT 'monthly', MIN(month)::text, MAX(month)::text, COUNT(*)
FROM ops.real_business_slice_month_fact
WHERE country = 'peru' AND city = 'lima';
```

#### Step 2: Compare V1 vs V2 for KPIs

```sql
-- Test month: '2026-05-01', Lima, Peru

-- trips
SELECT 'V1_trips_monthly' as metric,
    SUM(trips_completed) as value
FROM ops.v_real_business_slice_month_serving
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'

UNION ALL

SELECT 'V2_trips_monthly' as metric,
    SUM(trips_completed) as value
FROM ops.real_business_slice_month_fact
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'

UNION ALL

-- revenue
SELECT 'V1_revenue_monthly' as metric,
    SUM(COALESCE(revenue_yego_final, revenue_yego_net)) as value
FROM ops.v_real_business_slice_month_serving
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'

UNION ALL

SELECT 'V2_revenue_monthly' as metric,
    SUM(revenue_yego_final) as value
FROM ops.real_business_slice_month_fact
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'

UNION ALL

-- drivers
SELECT 'V1_drivers_monthly' as metric,
    SUM(active_drivers) as value
FROM ops.v_real_business_slice_month_serving
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima'

UNION ALL

SELECT 'V2_drivers_monthly' as metric,
    SUM(active_drivers) as value
FROM ops.real_business_slice_month_fact
WHERE month = '2026-05-01' AND country = 'peru' AND city = 'lima';
```

#### Step 3: Revenue NULL gap detection

```sql
-- Find where revenue_yego_final IS NULL (V2 gap)
SELECT
    month,
    business_slice_name,
    trips_completed,
    revenue_yego_final,
    revenue_yego_net,
    CASE
        WHEN revenue_yego_final IS NULL THEN 'V2_WOULD_BE_NULL'
        WHEN revenue_yego_final != revenue_yego_net THEN 'VALUES_DIFFER'
        ELSE 'OK'
    END as v2_gap_status
FROM ops.real_business_slice_month_fact
WHERE country = 'peru' AND city = 'lima'
  AND month >= '2026-01-01'
  AND (revenue_yego_final IS NULL OR revenue_yego_final != revenue_yego_net)
ORDER BY month, business_slice_name;
```

#### Step 4: Snapshot vs Runtime comparison (V2)

```sql
-- Check if V2 snapshot matches runtime build
SELECT
    source_system,
    grain,
    operating_date,
    payload_type,
    status,
    generated_at,
    coverage_pct,
    freshness_status
FROM ops.omniview_v2_serving_snapshot
WHERE source_system = 'CT_TRIPS_2026'
  AND status = 'READY'
ORDER BY operating_date DESC
LIMIT 10;
```

---

## 6. EXPECTED FINDINGS (Based on Static Analysis)

| Finding | Likelihood | Severity |
|---------|------------|----------|
| trips match between V1 and V2 | **HIGH** (same table, same column) | N/A (expected) |
| revenue differs between V1 and V2 | **MEDIUM** (COALESCE vs direct) | **HIGH** if gap exists |
| drivers match between V1 and V2 | **HIGH** (same table, same column) | N/A (expected) |
| Plan vs Real missing in V2 | **CERTAIN** (not implemented) | **MEDIUM** (by design) |
| Snapshot may be stale | **MEDIUM** (depends on refresh schedule) | **MEDIUM** |
| V2 matrix shows same rows as V1 | **HIGH** (same fact table) | N/A (expected) |

---

## 7. RECONCILIATION STATUS

| KPI | Static Classification | Live Verification | Status |
|-----|----------------------|-------------------|--------|
| trips (all grains) | `SAME_SOURCE_SAME_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |
| revenue | `SAME_SOURCE_DIFFERENT_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |
| drivers | `SAME_SOURCE_SAME_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |
| ticket | `SAME_SOURCE_SAME_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |
| TPD | `SAME_SOURCE_SAME_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |
| Plan vs Real | `DIFFERENT_SOURCE_DIFFERENT_VALUE` | CONFIRMED (V2 doesn't compute) | `CONFIRMED_GAP` |
| commission_pct | `SAME_SOURCE_SAME_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |
| cancel_rate_pct | `SAME_SOURCE_SAME_VALUE` | PENDING — requires DB access | `PENDING_LIVE_VERIFICATION` |

**Note:** Full live reconciliation requires executing the SQL queries above against the actual database. The `PENDING_LIVE_VERIFICATION` items are expected to produce `SAME_SOURCE_SAME_VALUE` based on source chain analysis, but live verification is needed to confirm no edge cases (e.g., snapshot vs working fact routing differences in V1's `v_real_business_slice_month_serving` view).
