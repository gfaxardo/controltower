# OV2 Refresh Freshness Audit

**Generated:** 2026-06-08T00:53:58.991426+00:00

| Layer | Grain | Source | Max Date | Gap (days) | Status |
|-------|-------|--------|----------|------------|--------|
| RAW_TRIPS | day | public.trips_2026 | 2026-06-06 | -1 | OK |
| RAW_YANGO | day | raw_yango.mv_orders_day | 2026-06-05 | -2 | OK |
| SOURCE_COVERAGE | day | raw_yango.mv_source_coverage_day | 2026-06-05 | -2 | OK |
| DAY_FACT | day | ops.real_business_slice_day_fact | 2026-06-06 | -1 | FRESH |
| WEEK_FACT | week | ops.real_business_slice_week_fact | 2026-04-20 | -48 | OK |
| MONTH_FACT | month | ops.real_business_slice_month_fact | 2026-06-01 | -6 | OK |
| SNAPSHOT | day | ops.omniview_v2_serving_snapshot | 2026-06-05 | -2 | STALE |
| OPERATING_DATE | day | from day_fact MAX(trip_date) | 2026-06-06 | -1 | OK |
| REVENUE | month | month_fact.revenue_yego_final | - | - | 77/92 (83.7%) |
| SLICE_COVERAGE | month | month_fact slices (Lima) | - | - | 6 slices |
| PLAN_VERSION | month | ops.plan_trips_monthly | - | - | e2e_20260526_165110 |

## Summary

- Critical gaps (>2 days): 2
- Stale facts (>=1 day): 8
- Layers with data: 8
