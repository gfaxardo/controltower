# OV2-F.1 — REFRESH CHAIN INVENTORY

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** INVENTORY COMPLETE

---

## LAYER 0: RAW / LANDING

| # | Source | Destination | Script | Frequency | Depends On | Status |
|---|--------|-------------|--------|-----------|------------|--------|
| 1 | `public.trips_2026` | *(already raw)* | N/A (ELT source) | Continuous | Rider app | ACTIVE |
| 2 | Yango Fleet API | `raw_yango.mv_orders_day` | `refresh_raw_yango_mvs.py` | Daily | API availability | ACTIVE |
| 3 | Yango Fleet API | `raw_yango.mv_transactions_day` | `refresh_raw_yango_mvs.py` | Daily | API availability | ACTIVE |
| 4 | Yango Fleet API | `raw_yango.mv_revenue_day` | `refresh_raw_yango_mvs.py` | Daily | API availability | ACTIVE |
| 5 | Yango Fleet API | `raw_yango.mv_driver_profiles_snapshot` | `refresh_raw_yango_mvs.py` | Daily | API availability | ACTIVE |
| 6 | Yango Fleet API | `raw_yango.mv_source_coverage_day` | `refresh_raw_yango_mvs.py` | Daily | API availability | ACTIVE |
| 7 | Excel template | `ops.plan_trips_monthly` | `plan_template_parser_service.py` | Ad-hoc (per version) | Template upload | ACTIVE |
| 8 | Excel template | `ops.plan_versions_metadata` | `plan_template_parser_service.py` | Ad-hoc (per version) | Template upload | ACTIVE |

## LAYER 1: ENRICHED / DIMENSION

| # | Source | Destination | Script | Frequency | Depends On | Status |
|---|--------|-------------|--------|-----------|------------|--------|
| 9 | `public.trips_2026` | `ops.mv_real_drill_enriched` | `safe_refresh_real_lob.py` | On-demand | L0 | ACTIVE |
| 10 | `public.trips_2026` | `ops.driver_daily_activity_fact` | `refresh_driver_daily_activity_fact.py` | Daily/backfill | L0 | ACTIVE |
| 11 | `public.trips_2026` | `ops.driver_trip_behavior_daily_fact` | `refresh_phase2b2_operational_behavior_facts.py` | On-demand | L0 | ACTIVE |
| 12 | `public.trips_2026` | `fraud.trip_behavior_feature_cache` | `fraud_refresh_trip_behavior_cache.py` | D-30 window | L0 | ACTIVE |

## LAYER 2: HOURLY-FIRST CHAIN (hour → day → week → month)

| # | Source | Destination | Script | Frequency | Depends On | Status |
|---|--------|-------------|--------|-----------|------------|--------|
| 13 | `trips_2026` | `ops.mv_real_lob_hour_v2` | `refresh_hourly_first_chain.py` | Pipeline step 1 | L0 | ACTIVE |
| 14 | L2-13 | `ops.mv_real_lob_day_v2` | `refresh_hourly_first_chain.py` | Pipeline step 2 | L2-13 | ACTIVE |
| 15 | L2-14 | `ops.mv_real_lob_week_v3` | `refresh_hourly_first_chain.py` | Pipeline step 3 | L2-14 | ACTIVE |
| 16 | L2-15 | `ops.mv_real_lob_month_v3` | `refresh_hourly_first_chain.py` | Pipeline step 4 | L2-15 | ACTIVE |
| 17 | L2-14 | `ops.real_drill_dim_fact` | `populate_real_drill_from_hourly_chain` | After chain | L2-14 | ACTIVE |

## LAYER 3: BUSINESS SLICE FACTS (day → week → month)

| # | Source | Destination | Script | Frequency | Depends On | Status |
|---|--------|-------------|--------|-----------|------------|--------|
| 18 | `trips_2026` | `ops.real_business_slice_day_fact` | `refresh_omniview_real_slice_incremental.py` | Daily (APScheduler) | L0 | **ACTIVE** |
| 19 | L3-18 | `ops.real_business_slice_week_fact` | `refresh_omniview_real_slice_incremental.py` | Daily (APScheduler) | L3-18 | **ACTIVE** |
| 20 | L3-18+19 | `ops.real_business_slice_month_fact` | `refresh_omniview_real_slice_incremental.py` | Daily (APScheduler) | L3-18+19 | **ACTIVE** |

## LAYER 4: DOMAIN FACTS

| # | Source | Destination | Script | Frequency | Depends On | Status |
|---|--------|-------------|--------|-----------|------------|--------|
| 21 | L3 facts | `ops.mv_driver_lifecycle_base` | `refresh_driver_lifecycle.py` | On-demand | L3 | ACTIVE |
| 22 | L3 facts | `ops.mv_plan_vs_real_monthly_fact` | `refresh_plan_vs_real_monthly_mvs.py` | Daily | L3, plan | ACTIVE |
| 23 | L3 facts | `ops.mv_real_financials_monthly` | `refresh_and_validate_financials.py` | On-demand | L3 | ACTIVE |
| 24 | Yango API | `growth.* serving facts` | `yego_lima_daily_refresh_service.py` | Daily (APScheduler) | L0-Yango | ACTIVE |

## LAYER 5: SERVING SNAPSHOTS

| # | Source | Destination | Script | Frequency | Depends On | Status |
|---|--------|-------------|--------|-----------|------------|--------|
| 25 | L3 facts | `ops.omniview_v2_serving_snapshot` | `refresh_omniview_v2_snapshots.py` | Ad-hoc/daily | L3 | **ACTIVE** |
| 26 | Plan table | `serving.omniview_projection_daily_fact` | `refresh_omniview_projection_facts.py` | Daily (APScheduler) | L8 | ACTIVE |

## LAYER 6: UI ENDPOINT (reading)

| # | Endpoint | Reads From | Type |
|---|----------|-----------|------|
| 27 | `GET /ops/omniview-v2/shell` | L5-25 (snapshot), else L3-18 (runtime) | Snapshot-first |
| 28 | `GET /ops/omniview-v2/matrix` | L5-25 (snapshot), else L3-18 (runtime) | Snapshot-first |
| 29 | `GET /ops/omniview-v2/operating-date` | L3-18 (MAX date) | Runtime |
| 30 | `GET /ops/omniview-v2/plan-real/monthly` | L8 (plan) + L3-20 (month_fact) | Runtime (Tier S) |

## CURRENT REFRESH STATUS (2026-06-07)

| Layer | Max Date | Freshness | Gap |
|-------|----------|-----------|-----|
| RAW trips | 2026-06-06 | D-1 | 1 day |
| RAW Yango | 2026-06-05 | D-2 | 2 days |
| DAY_FACT | 2026-06-06 | D-1 | 1 day |
| WEEK_FACT | 2026-04-20 | **STALE** | 48 days |
| MONTH_FACT | 2026-06-01 | Current | 6 days (partial month) |
| SNAPSHOT | 2026-06-05 | D-2 | 2 days |
| OPERATING_DATE | 2026-06-06 | D-1 | OK |
| REVENUE | 77/92 (83.7%) | PARTIAL | 15 NULL rows (Jan-Feb) |

## APSCHEDULER JOBS

| Job | Schedule | Function |
|-----|----------|----------|
| `omniview_business_slice_real_refresh` | Daily 04:00 | Recalc day_fact + week_fact + month_fact |
| `serving_fact_daily_refresh` | Daily 05:00 | Refresh projection facts |
| `omniview_real_data_watchdog` | Every 15min | Monitor freshness |

---

*End of Refresh Chain Inventory*
