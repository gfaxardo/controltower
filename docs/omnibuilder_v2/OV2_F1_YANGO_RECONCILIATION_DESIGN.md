# OV2-F.1 — YANGO RECONCILIATION DESIGN

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** DESIGN — NOT IMPLEMENTED

---

## 1. PURPOSE

Comparar los KPIs de Control Tower contra Yango Fleet Room (fuente de verdad externa) para detectar discrepancias entre la captura de datos interna y la plataforma Yango.

---

## 2. RECONCILIATION KEYS

| Dimension | CT Value | Yango Value |
|-----------|----------|-------------|
| `park_id` | `08e20910d81d42658d4334d3f6d10ac0` (Lima) | Same — from Yango Fleet API |
| `date` | `trip_date` (day_fact) / `order_date` (raw_yango) | `order_date` from `raw_yango.mv_orders_day` |
| `trips` | `SUM(trips_completed)` from day_fact | `COUNT(order_id)` from `raw_yango.mv_orders_day` |
| `revenue` | `SUM(revenue_yego_final)` from day_fact | `SUM(revenue)` from `raw_yango.mv_revenue_day` |
| `drivers` | `SUM(active_drivers)` from day_fact | `COUNT(DISTINCT driver_id)` from `raw_yango.mv_driver_profiles_snapshot` |
| `business_slice` | `business_slice_name` from day_fact | Not available — Yango uses fleet categories |

---

## 3. COMPARISON STATUS CODES

| Code | Condition | Delta | Severity |
|------|-----------|-------|----------|
| `MATCH` | \|CT - Yango\| / Yango ≤ 1% | Within tolerance | OK |
| `MINOR_DELTA` | 1% < delta ≤ 5% | Small deviation | INFO |
| `MAJOR_DELTA` | 5% < delta ≤ 15% | Significant gap | WARNING |
| `CT_ONLY` | CT has data, Yango has 0 or NULL | Missing from Yango | WARNING |
| `YANGO_ONLY` | Yango has data, CT has 0 or NULL | Missing from CT | CRITICAL |
| `NOT_COMPARABLE` | Different dimensions/park_ids/dates | Cannot compare | INFO |

---

## 4. DATA SOURCES

### Control Tower side

```sql
SELECT trip_date,
       SUM(trips_completed) AS ct_trips,
       SUM(revenue_yego_final) AS ct_revenue,
       SUM(active_drivers) AS ct_drivers
FROM ops.real_business_slice_day_fact
WHERE LOWER(TRIM(country)) = 'peru'
  AND LOWER(TRIM(city)) = 'lima'
GROUP BY trip_date
```

### Yango side

```sql
SELECT order_date,
       COUNT(*) AS yango_trips,
       SUM(COALESCE(revenue, 0)) AS yango_revenue
FROM raw_yango.mv_orders_day
WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
GROUP BY order_date
```

---

## 5. RECONCILIATION QUERY (PostgreSQL)

```sql
WITH ct AS (
    SELECT trip_date AS dt, SUM(trips_completed) AS ct_trips,
           SUM(revenue_yego_final) AS ct_revenue, SUM(active_drivers) AS ct_drivers
    FROM ops.real_business_slice_day_fact
    WHERE LOWER(TRIM(country)) = 'peru' AND LOWER(TRIM(city)) = 'lima'
    GROUP BY trip_date
),
yango AS (
    SELECT order_date AS dt, COUNT(*) AS y_trips, SUM(COALESCE(revenue, 0)) AS y_revenue
    FROM raw_yango.mv_orders_day
    WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
    GROUP BY order_date
)
SELECT COALESCE(c.dt, y.dt) AS date,
       c.ct_trips, y.y_trips,
       ROUND((c.ct_trips - COALESCE(y.y_trips, 0)) / NULLIF(y.y_trips, 0) * 100, 1) AS trips_delta_pct,
       c.ct_revenue, y.y_revenue,
       ROUND((c.ct_revenue - COALESCE(y.y_revenue, 0)) / NULLIF(y.y_revenue, 0) * 100, 1) AS revenue_delta_pct,
       CASE WHEN c.ct_trips IS NULL THEN 'YANGO_ONLY'
            WHEN y.y_trips IS NULL THEN 'CT_ONLY'
            WHEN ABS((c.ct_trips - y.y_trips) / NULLIF(y.y_trips, 0) * 100) <= 1 THEN 'MATCH'
            WHEN ABS((c.ct_trips - y.y_trips) / NULLIF(y.y_trips, 0) * 100) <= 5 THEN 'MINOR_DELTA'
            WHEN ABS((c.ct_trips - y.y_trips) / NULLIF(y.y_trips, 0) * 100) <= 15 THEN 'MAJOR_DELTA'
            ELSE 'MAJOR_DELTA' END AS status
FROM ct c FULL OUTER JOIN yango y ON c.dt = y.dt
ORDER BY date DESC
```

---

## 6. REFRESH DEPENDENCY

Reconciliation runs AFTER:
1. `refresh_raw_yango_mvs` has fresh data
2. `refresh_omniview_real_slice_incremental` has fresh day_fact
3. Both sources have the same date range available

---

## 7. UI EXPOSURE

| Level | Component |
|-------|-----------|
| Dashboard badge | "CT vs Yango: MATCH (δ=0.3%)" |
| Cell inspector | `comparison_status` on Yango-sourced cells |
| Reconciliation panel | Side-by-side: CT | Yango | Delta |
| Alert strip | MAJOR_DELTA → WARNING in OmniviewV2AlertStrip |

---

## 8. IMPLEMENTATION BACKLOG

| # | Task | Priority |
|---|------|----------|
| 1 | Create `GET /ops/omniview-v2/reconciliation/yango` endpoint | P2 |
| 2 | Store daily reconciliation results in `ops.ov2_yango_reconciliation_log` | P2 |
| 3 | Add Yango comparison status to MatrixCell (new `comparison_source`) | P2 |
| 4 | Add reconciliation badge to CommandHeader | P3 |

---

*End of Yango Reconciliation Design*
