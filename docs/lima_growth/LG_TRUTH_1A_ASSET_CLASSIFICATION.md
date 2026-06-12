# LG-TRUTH-1A — ASSET CLASSIFICATION

**Date:** 2026-06-11

---

## Classification

### ACTIVE (consumed by UI, refreshed by scheduler)

| Asset | Table | Scheduler | Max Date | Status |
|-------|-------|-----------|----------|--------|
| driver_state_snapshot | growth.yango_lima_driver_state_snapshot | autonomous_tick (5min) | 2026-06-11 | FRESH |
| program_eligibility | growth.yango_lima_program_eligibility_daily | autonomous_tick (5min) | 2026-06-11 | FRESH |
| prioritized_opportunity | growth.yango_lima_prioritized_opportunity_daily | autonomous_tick (5min) | 2026-06-11 | FRESH |
| assignment_queue | growth.yego_lima_assignment_queue | autonomous_tick (5min) | 2026-06-11 | FRESH |
| serving_fact | growth.yego_lima_serving_fact | autonomous_tick (5min) | 2026-06-11 | FRESH |
| lifecycle_daily | growth.yego_lima_driver_lifecycle_daily | autonomous_tick (5min) | 2026-06-10 | FRESH (T-1) |
| lifecycle_event | growth.yego_lima_driver_lifecycle_event | autonomous_tick (5min) | 2026-06-10 | FRESH (T-1) |
| control_loop_state | growth.yego_lima_control_loop_state | autonomous_tick (5min) | 2026-06-11 | FRESH |
| driver_history_daily | growth.yango_lima_driver_history_daily | autonomous_tick (5min) | 2026-06-04 | PARTIAL |
| loopcontrol_export | growth.yango_lima_loopcontrol_campaign_export | on demand | 2026-06-09 | PARTIAL |
| capacity_config | growth.yego_lima_capacity_config | manual | N/A | STATIC |
| freshness_registry | growth.yego_lima_freshness_registry | governance scan | 2026-06-11 | FRESH |

### SHADOW (V2 pipeline output, NOT consumed by UI)

| Asset | Table | Scheduler | Max Date | UI Impact |
|-------|-------|-----------|----------|-----------|
| v2_activity_daily | growth.yego_lima_v2_activity_daily | V2 daily 04:45 | None (0 rows) | NONE |
| v2_activity_weekly | growth.yego_lima_v2_activity_weekly | V2 daily 04:45 | None (0 rows) | NONE |
| v2_activity_monthly | growth.yego_lima_v2_activity_monthly | V2 daily 04:45 | 2026-06-10 | NONE |
| v2_lifecycle_daily | growth.yego_lima_v2_lifecycle_daily | V2 daily 04:45 | 2026-06-10 | NONE |
| v2_taxonomy_daily | growth.yego_lima_v2_taxonomy_daily | V2 daily 04:45 | 2026-06-10 | NONE |
| v2_program_daily | growth.yego_lima_v2_program_daily | V2 daily 04:45 | 2026-06-10 | NONE |
| v2_movement_fact | growth.yego_lima_v2_movement_fact | V2 daily 04:45 | None (0 rows) | NONE |
| v2_observability_fact | growth.yego_lima_v2_observability_fact | V2 daily 04:45 | 2026-06-10 | NONE |
| v2_effectiveness_fact | growth.yego_lima_v2_effectiveness_fact | V2 daily 04:45 | None (0 rows) | NONE |

### LEGACY/DEPRECATED (not refreshed, not consumed)

| Asset | Table | Status |
|-------|-------|--------|
| driver_history_weekly | growth.yango_lima_driver_history_weekly | STALE (W22, Jun 1) |
| driver_segment_snapshot | growth.yango_lima_driver_segment_snapshot | STALE (282 rows) |
| hourly_snapshot | growth.yango_lima_hourly_snapshot | EMPTY |
| action_ledger | growth.yego_lima_action_ledger | EMPTY |
| impact_tracking | growth.yego_lima_impact_tracking | EMPTY |
| movement_tracking | growth.yego_lima_movement_tracking | EMPTY |
| attribution_candidates | growth.yego_lima_attribution_candidates | EMPTY |
| queue_build_log | growth.yego_lima_queue_build_log | EMPTY |

---

## ANSWER: Are the stale assets real or legacy?

**The CRITICAL/DEGRADED assets from LG-SERV-2A are SHADOW tables, not production assets.**

- 0 of 9 V2 shadow tables are consumed by any UI endpoint
- All 5 production tables consumed by UI are FRESH for today
- The scheduler is running every 5 minutes with 580 successful ticks

The LG-SERV-2A freshness audit correctly detected that V2 shadow tables are stale, but those tables are certification artifacts, not operational data sources. This is expected behavior for shadow mode.
