# LG-SERV-2A — SERVING ASSET INVENTORY

**Date:** 2026-06-11  
**Phase:** LG-SERV-2A / Serving Governance  
**Database:** yego_integral

---

## SERVING ASSETS — Complete Inventory

### 13 Assets Tracked by Serving Freshness Engine

| # | Asset Name | Table/View | Owner | Writer | Source | Scheduler | SLA |
|---|-----------|-----------|-------|--------|--------|-----------|-----|
| 1 | activity_daily | growth.yego_lima_v2_activity_daily | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | ops.driver_daily_activity_fact | 04:45 AM daily | 25h |
| 2 | activity_weekly | growth.yego_lima_v2_activity_weekly | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | ops.driver_daily_activity_fact (7d) | 04:45 AM daily | 25h |
| 3 | activity_monthly | growth.yego_lima_v2_activity_monthly | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | ops.driver_daily_activity_fact (30d) | 04:45 AM daily | 25h |
| 4 | lifecycle_daily | growth.yego_lima_v2_lifecycle_daily | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | growth.yego_lima_driver_lifecycle_daily | 04:45 AM daily | 25h |
| 5 | taxonomy_v2 | growth.yego_lima_v2_taxonomy_daily | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | growth.yego_lima_driver_lifecycle_daily | 04:45 AM daily | 25h |
| 6 | program_v2 | growth.yego_lima_v2_program_daily | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | growth.yego_lima_driver_lifecycle_daily | 04:45 AM daily | 25h |
| 7 | movement_fact | growth.yego_lima_v2_movement_fact | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | state_transition_trace + program_decision_trace | 04:45 AM daily | 25h |
| 8 | observability_fact | growth.yego_lima_v2_observability_fact | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | ops.v_observability_module_status | 04:45 AM daily | 25h |
| 9 | effectiveness_fact | growth.yego_lima_v2_effectiveness_fact | V2 Daily Pipeline | yego_lima_v2_daily_pipeline_service | ops.driver_campaigns + effectiveness | 04:45 AM daily | 25h |
| 10 | program_assignment | growth.yango_lima_program_eligibility_daily | Autonomous Tick | yego_lima_program_eligibility_service | driver_state_snapshot | Every 5 min | 5h |
| 11 | serving_driver_explorer | growth.yego_lima_serving_fact | Serving Facts | yego_lima_serving_facts_service | 8 fact types | Every 5 min | 5h |
| 12 | driver_state_snapshot | growth.yango_lima_driver_state_snapshot | Autonomous Tick | yego_lima_driver_state_service | Yango API + history | Every 5 min | 5h |
| 13 | RNA_serving | growth.yango_lima_driver_history_daily | Autonomous Tick | scheduler (incremental) | raw_yango.orders_raw | Every 5 min | 6h |

### Current Freshness Status (2026-06-11 21:00 Lima)

| Asset | Status | Age | Rows | Latest Data |
|-------|--------|-----|------|-------------|
| activity_daily | CRITICAL | N/A | 0 | No data for target (source ends 2026-05-21) |
| activity_weekly | CRITICAL | N/A | 0 | No data for target (source ends 2026-05-21) |
| activity_monthly | DEGRADED | 50.17h | 27,629 | 2026-06-10 |
| lifecycle_daily | DEGRADED | 50.17h | 273,908 | 2026-06-10 |
| taxonomy_v2 | DEGRADED | 50.17h | 273,908 | 2026-06-10 |
| program_v2 | DEGRADED | 50.17h | 273,908 | 2026-06-10 |
| movement_fact | CRITICAL | N/A | 0 | No source data for target |
| observability_fact | DEGRADED | 50.17h | 24 | 2026-06-10 |
| effectiveness_fact | CRITICAL | N/A | 0 | No campaigns active |
| program_assignment | CRITICAL | 26.17h | 226,432 | 2026-06-11 |
| driver_state_snapshot | CRITICAL | 26.17h | 148,167 | 2026-06-11 |
| serving_driver_explorer | CRITICAL | 26.17h | 48 | 2026-06-11 |
| RNA_serving | CRITICAL | 194.17h | 520,340 | Rolling history |

### Upstream Source Freshness

| Source | Max Date | Status |
|--------|----------|--------|
| ops.driver_daily_activity_fact | 2026-05-21 | **21 days stale** |
| growth.yango_lima_orders_raw | 2026-06-09 15:47 | **2 days stale** |
| growth.yango_lima_driver_history_weekly | 2026-06-01 (W22) | **10 days stale** |
| growth.yango_lima_data_freshness (all 6 APIs) | 2026-06-03 | **8 days stale** |
| Yango API: orders_api | 2026-06-03 15:26 | NOT refreshing |
| Yango API: driver360 | 2026-06-03 15:26 | NOT refreshing |

### Additional Lima Growth Tables (94 total in growth.*)

**Production pipeline tables (autonomous tick):**
- yango_lima_driver_state_snapshot (148K rows, fresh to 2026-06-11)
- yango_lima_program_eligibility_daily (226K rows, fresh to 2026-06-11)
- yango_lima_prioritized_opportunity_daily (44K rows, fresh to 2026-06-11)
- yango_lima_driver_history_daily (520K rows, rolling)
- yango_lima_driver_history_weekly (135K rows, max 2026-06-01)
- yego_lima_driver_lifecycle_daily (273K rows, max 2026-06-10)
- yego_lima_driver_lifecycle_event (48K rows, max 2026-06-10)
- yego_lima_driver_taxonomy_v2_daily (273K rows, max 2026-06-10)
- yego_lima_assignment_queue (2,104 rows, fresh)
- yego_lima_control_loop_state (668 rows)
- yego_lima_scheduler_tick_log (580 ticks)
- yego_lima_intraday_driver_signal (310 signals, last 2026-06-05)

**Legacy/empty tables (14 with 0 rows):** hour_snapshot, action_ledger, impact_tracking, movement_tracking, attribution_candidates, queue_build_log, driver_taxonomy_v2_transition, program_capacity_policy_audit, v2_activity_daily, v2_activity_weekly, v2_effectiveness_fact, v2_movement_fact
