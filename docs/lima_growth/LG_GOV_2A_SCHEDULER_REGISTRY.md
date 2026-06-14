# LG_GOV_2A_SCHEDULER_REGISTRY

**Phase:** LG-CF-GOV-2A — Governance Hardening  
**Generated:** 2026-06-12

---

## SCHEDULER 1: `autonomous_tick` (APScheduler, every 5 min)

**Job ID:** `lima_growth_autonomous_tick`  
**File:** `backend/app/services/yego_lima_scheduler_service.py:537`  
**Registered:** `main.py:370`  
**Trigger:** `interval`, every 5 minutes  
**Lock:** `pg_try_advisory_lock(9001)` — prevents concurrent ticks  
**State:** ACTIVE (718 ticks, 710 success, 6 fail)

### Tables Updated (in execution order)

| Phase | Function | Table Written | Conditional? |
|-------|----------|--------------|-------------|
| Always | `ingest_recent_orders()` | `growth.yango_lima_orders_raw` | Always |
| Cascade | `build_driver_state_snapshot()` | `growth.yango_lima_driver_state_snapshot` | Raw > Snapshot |
| Cascade | `build_program_eligibility()` | `growth.yango_lima_program_eligibility_daily` | Raw > Snapshot |
| Cascade | `build_daily_opportunity_lists()` | `growth.yango_lima_daily_opportunity_list` | Raw > Snapshot |
| Cascade | `build_prioritized_opportunities()` | `growth.yango_lima_prioritized_opportunity_daily` | Raw > Snapshot |
| Cascade | `run_daily_refresh()` | → 4 tables below | Raw > Snapshot |
| Cascade | `sync_assignment_queue_to_control_loop()` | `growth.yego_lima_control_loop_state` | Raw > Snapshot |
| Catch-up | `run_daily_refresh()` | → 4 tables below | New day detected |
| Always | `sync_assignment_queue_to_control_loop()` | `growth.yego_lima_control_loop_state` | Always |
| Always | `generate_all_serving_facts()` | `growth.yego_lima_serving_fact` (8 fact types) | Always |
| Always | `_refresh_freshness_registry()` + governance | `growth.yego_lima_freshness_registry` | Always |
| Always | `build_intraday_signals()` | `growth.yego_lima_intraday_driver_signal` | Always |
| Always | `snapshot_queue_to_history()` | `growth.yego_lima_driver_list_history` | Always |
| Always | Logging (3 tables) | `refresh_run_log`, `scheduler_status`, `tick_log` | Always |

### `run_daily_refresh()` internal steps

| Step | Writes To |
|------|----------|
| 1. detect_operational_date | step_log only |
| 2. validate_source_readiness | step_log only |
| 3. create_assignment_batch() | `growth.yego_lima_assignment_queue`, `queue_build_audit` |
| 4. build_prioritized_opportunities() | `growth.yango_lima_prioritized_opportunity_daily` |
| 5. generate_all_serving_facts() | `growth.yego_lima_serving_fact` |

### Tables NOT Updated by autonomous_tick

| Table | Why Not |
|-------|---------|
| `growth.yego_lima_driver_lifecycle_daily` | Not in cascade. Only in V2 pipeline. |
| `growth.yego_lima_v2_taxonomy_daily` | Not in cascade. Only in V2 pipeline. |
| `growth.yego_lima_v2_movement_fact` | Not in cascade. Only in V2 pipeline. |
| `growth.yego_lima_v2_program_daily` | Not in cascade. Only in V2 pipeline. |
| `growth.rna_priority_fact` | Manual only. Not in cascade. |
| `growth.program_effectiveness_fact` | Manual recovery. Not in cascade. |
| `growth.yego_lima_driver_explorer_fact` | Not activated. Feature flag OFF. |
| `growth.yego_lima_driver_activity_*` | Manual only. Not in cascade. |

---

## SCHEDULER 2: `lima_growth_v2_daily_pipeline` (APScheduler cron, daily 04:45 AM)

**Job ID:** `lima_growth_v2_daily_pipeline`  
**File:** `backend/app/services/yego_lima_v2_daily_pipeline_service.py:210`  
**Registered:** `main.py:405`  
**Trigger:** `cron`, hour=4, minute=45, timezone=UTC  
**State:** REGISTERED but NOT EXECUTING (0 log entries for 06-11/12 by cron; all 17 runs triggered manually)  

### Tables Updated (V2 Shadow Pipeline, 9 steps)

| Step | Function | Table Written | Source |
|------|----------|--------------|--------|
| 1 | `_build_activity_daily()` | `growth.yego_lima_v2_activity_daily` | `ops.driver_daily_activity_fact` |
| 2 | `_build_activity_weekly()` | `growth.yego_lima_v2_activity_weekly` | `ops.driver_daily_activity_fact` |
| 3 | `_build_activity_monthly()` | `growth.yego_lima_v2_activity_monthly` | `ops.driver_daily_activity_fact` |
| 4 | `_build_lifecycle_daily()` | `growth.yego_lima_v2_lifecycle_daily` | `growth.yego_lima_driver_lifecycle_daily` |
| 5 | `_build_taxonomy_v2_daily()` | `growth.yego_lima_v2_taxonomy_daily` | `growth.yego_lima_driver_lifecycle_daily` |
| 6 | `_build_program_v2_daily()` | `growth.yego_lima_v2_program_daily` | `growth.yego_lima_driver_lifecycle_daily` |
| 7 | `_build_movement_fact()` | `growth.yego_lima_v2_movement_fact` | traces + taxonomy/program diff |
| 8 | `_build_observability_facts()` | `growth.yego_lima_v2_observability_fact` | `ops.v_observability_module_status` |
| 9 | `_build_effectiveness_facts()` | `growth.yego_lima_v2_effectiveness_fact` | `ops.driver_campaigns` |

### Pipeline Run Log (all manual triggers)

| Date | Triggered At | By | Status |
|------|-------------|-----|--------|
| 2026-06-12 | 17:31:40 -05 | `canonical-freshness` | SUCCESS |
| 2026-06-11 | 17:30:11 -05 | `canonical-freshness` | SUCCESS |
| 2026-06-11 | 16:42:01 -05 | `backfill-canonical` | SUCCESS |
| 2026-06-10 | 16:41:10 -05 | `backfill-canonical` | SUCCESS |
| 2026-06-10 | 16:26:14 -05 | `backfill-canonical` | SUCCESS |
| 2026-06-10 | 20:55:38 -05 (06-11) | `multi-day-replay-final` | SUCCESS |
| 06-09 to 06-07 | 20:54 - 20:52 (06-11) | `multi-day-replay-final` | SUCCESS |
| 06-10 | 20:52:03 (06-11) | `certification-final` | SUCCESS |

**Total: 17 runs. All SUCCESS. All triggered manually via `POST /yego-lima-growth/v2-pipeline/run`.**

### Why Cron Isn't Executing

The job is registered at `main.py:405` with `cron(hour=4, minute=45)`. Possible causes:
1. APScheduler timezone mismatch (UTC vs local)
2. Server not running at 04:45 AM (dev/staging server)
3. Job misfire grace period exceeded
4. Silent exception in wrapper function `_v2_daily_pipeline_wrapper`

---

## SCHEDULER 3: Manual Triggers (POST endpoints)

### Build endpoints that populate tables

| # | Endpoint | Table Populated |
|---|----------|----------------|
| 1 | `POST /yego-lima-growth/state/build-driver-states` | `driver_state_snapshot` |
| 2 | `POST /yego-lima-growth/programs/build-eligibility` | `program_eligibility_daily` |
| 3 | `POST /yego-lima-growth/opportunities/build-daily` | `daily_opportunity_list` |
| 4 | `POST /yego-lima-growth/lifecycle/build` | `driver_activity_daily`, `_weekly`, `_monthly`, `driver_lifecycle_daily`, `driver_lifecycle_event` |
| 5 | `POST /yego-lima-growth/lifecycle/backfill` | `driver_activity_event` |
| 6 | `POST /yego-lima-growth/taxonomy/build` | `driver_taxonomy_daily`, `_explanation`, `_transition` |
| 7 | `POST /yego-lima-growth/rna-priority/build` | `rna_priority_fact` |
| 8 | `POST /yego-lima-growth/rna-pilot/build` | `rna_pilot_measurement_fact` |
| 9 | `POST /yego-lima-growth/v2-pipeline/run` | All 9 V2 shadow tables |
| 10 | `POST /yego-lima-growth/refresh/run` | `assignment_queue` + `serving_fact` |
| 11 | `POST /yego-lima-growth/intraday-signals/build` | `intraday_driver_signal` |
| 12 | `POST /yego-lima-growth/control-loop/build-actionable-lists` | `actionable_list_daily` |
| 13 | `POST /yego-lima-growth/control-loop/build-daily-impact` | `driver_action_daily_impact` |
| 14 | `POST /yego-lima-growth/control-loop/build-segment-transitions` | `driver_segment_transition_daily` |
| 15 | `POST /yego-lima-growth/control-loop/build-list-outcomes` | `actionable_list_outcome_daily` |
| 16 | `POST /yego-lima-growth/control-loop/build-impact-attribution` | `action_attribution_daily` |

### Script-based triggers

| Script | Table Populated |
|--------|----------------|
| `build_driver_explorer_fact.py --date YYYY-MM-DD` | `driver_explorer_fact` |
| `run_driver_lifecycle_build.py` | lifecycle tables |
| `obs_1b_rebuild.py` | observability facts |
| `rebuild_queue.py` | `assignment_queue` |

---

## SCHEDULER 4: Other APScheduler Jobs

| Job ID | Function | Trigger | Writes To |
|--------|----------|---------|-----------|
| `serving_fact_daily_refresh` | `scheduled_daily_refresh()` | cron 05:00 UTC | `growth.yego_lima_serving_fact` |
| `omniview_cascade_refresh` | `run_cascade_with_lock()` | cron daily | `ops.*` MVs |
| `omniview_real_data_watchdog` | `run_real_data_watchdog()` | interval N min | `ops.*` freshness |

---

## COVERAGE MATRIX

### Tables Covered by Scheduling

| Schedule | Tables | % of Total |
|----------|--------|-----------|
| autonomous_tick (every 5 min) | 10 core + 3 logging | 31% |
| V2 cron (04:45 AM, failing) | 9 shadow | 21% |
| Manual POST endpoints | 16 | 38% |
| Scripts | 3 | 7% |
| Other APScheduler | 1 (serving_fact) | 2% |

**Only 31% of tables have automated, operational scheduling. 69% require manual intervention or have failing cron jobs.**
