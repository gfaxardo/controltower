# OV2-F.6B — SOURCE INVENTORY

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE

## CT SIDE

| Source | Rows (Lima) | Min Date | Max Date | Parks | Drivers | Freshness |
|--------|-------------|----------|----------|-------|---------|-----------|
| `ops.driver_day_slice_fact` | 284,329 | 2026-04-01 | 2026-06-07 | 22 | 18,341 | D-1 |
| `ops.real_business_slice_day_fact` | 2,569 | — | 2026-06-07 | — | 2,481 (Jun 6) | D-1 |
| `ops.real_business_slice_week_fact` | 60 | — | 2026-06-01 | — | 34,036 | Current week |
| `ops.real_business_slice_month_fact` | 86 | — | 2026-06-01 | — | 9,155 | Current month |

## YANGO SIDE

| Source | Rows | Min Date | Max Date | Parks | Drivers | Freshness |
|--------|------|----------|----------|-------|---------|-----------|
| `raw_yango.orders_raw` | 12,087 | 2026-06-04 | 2026-06-06 | 1 | 468/day | D-3 (max) |
| `raw_yango.mv_orders_day` | 3 | 2026-06-04 | 2026-06-06 | 1 | 468/day | D-3 |
| `raw_yango.mv_driver_profiles_snapshot` | — | — | — | — | — | Unknown |
| `raw_yango.mv_revenue_day` | — | — | — | — | — | Unknown |

## GAP

- CT has 22 parks, Yango has 1 (only Lima main park ingested)
- CT has 284K bridge rows, Yango has 12K raw orders
- CT bridge covers Apr-Jun, Yango covers only Jun 4-6
