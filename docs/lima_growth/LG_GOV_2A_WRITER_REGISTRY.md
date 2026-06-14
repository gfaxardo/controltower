# LG_GOV_2A_WRITER_REGISTRY

**Phase:** LG-CF-GOV-2A — Governance Hardening  
**Generated:** 2026-06-12  
**Scope:** Complete inventory of all Lima Growth writers

---

## WRITER REGISTRY — Core Operational Layer

| # | Table | Writer Function | File | Trigger | Scheduler | Frequency | Owner |
|---|-------|----------------|------|---------|-----------|-----------|-------|
| 1 | `growth.yango_lima_driver_state_snapshot` | `build_driver_state_snapshot()` | `yego_lima_driver_state_service.py:60` | `autonomous_tick` + `POST /state/build-driver-states` | autonomous_tick (when cascade) | Every 5 min (conditional) | Control Foundation |
| 2 | `growth.yango_lima_program_eligibility_daily` | `build_program_eligibility()` | `yego_lima_program_eligibility_service.py:41` | `autonomous_tick` + `POST /programs/build-eligibility` | autonomous_tick (when cascade) | Every 5 min (conditional) | Control Foundation |
| 3 | `growth.yango_lima_daily_opportunity_list` | `build_daily_opportunity_lists()` | `yego_lima_daily_opportunity_service.py:46` | `autonomous_tick` + `POST /opportunities/build-daily` | autonomous_tick (when cascade) | Every 5 min (conditional) | Control Foundation |
| 4 | `growth.yango_lima_prioritized_opportunity_daily` | `build_prioritized_opportunities()` | `yego_lima_opportunity_policy_service.py:157` | `autonomous_tick` + `POST /policy/build` | autonomous_tick (when cascade) | Every 5 min (conditional) | Control Foundation |
| 5 | `growth.yego_lima_assignment_queue` | `create_assignment_batch()` | `yego_lima_assignment_queue_service.py` | `run_daily_refresh()` Step 3 | autonomous_tick → daily_refresh | Every 5 min (conditional) | Control Foundation |
| 6 | `growth.yego_lima_control_loop_state` | `sync_assignment_queue_to_control_loop()` | `yego_lima_control_loop_sync_service.py` | `autonomous_tick` post-cascade | autonomous_tick | Every 5 min (always) | Control Foundation |
| 7 | `growth.yego_lima_serving_fact` | `generate_all_serving_facts()` | `yego_lima_serving_facts_service.py:160` | `autonomous_tick` + `run_daily_refresh()` Step 5 | autonomous_tick | Every 5 min (always) | Control Foundation |
| 8 | `growth.yego_lima_intraday_driver_signal` | `build_intraday_signals()` | `yego_lima_intraday_signal_service.py:53` | `autonomous_tick` + `POST /intraday-signals/build` | autonomous_tick | Every 5 min (always) | Control Foundation |
| 9 | `growth.yego_lima_driver_list_history` | `snapshot_queue_to_history()` | `yego_lima_driver_list_history_service.py` | `autonomous_tick` post-cascade | autonomous_tick | Every 5 min (always) | Control Foundation |
| 10 | `growth.yango_lima_orders_raw` | `ingest_recent_orders()` | `yango_raw_tick_ingestion_service.py` | `autonomous_tick` always | autonomous_tick | Every 5 min (always) | Raw Ingestion |

---

## WRITER REGISTRY — Intelligence Layer

| # | Table | Writer Function | File | Trigger | Scheduler | Frequency | Owner |
|---|-------|----------------|------|---------|-----------|-----------|-------|
| 11 | `growth.yego_lima_driver_activity_daily` | `build_activity_daily()` | `yego_lima_lifecycle_service.py:182` | V2 pipeline Step 1 + `POST /lifecycle/build` | V2 cron 04:45 (failing) | Daily (manual currently) | Intelligence |
| 12 | `growth.yego_lima_driver_activity_weekly` | `build_activity_weekly()` | `yego_lima_lifecycle_service.py:260` | V2 pipeline Step 2 + `POST /lifecycle/build` | V2 cron 04:45 (failing) | Daily (manual currently) | Intelligence |
| 13 | `growth.yego_lima_driver_activity_monthly` | `build_activity_monthly()` | `yego_lima_lifecycle_service.py:329` | V2 pipeline Step 3 + `POST /lifecycle/build` | V2 cron 04:45 (failing) | Daily (manual currently) | Intelligence |
| 14 | `growth.yego_lima_driver_lifecycle_daily` | `build_lifecycle_daily()` | `yego_lima_lifecycle_service.py:394` | V2 pipeline Step 4 + `POST /lifecycle/build` | V2 cron 04:45 (failing) | Daily (manual currently) | Intelligence |
| 15 | `growth.yego_lima_driver_lifecycle_event` | `build_lifecycle_events()` | `yego_lima_lifecycle_service.py:562` | `POST /lifecycle/build` | Manual only | On-demand | Intelligence |
| 16 | `growth.yego_lima_driver_activity_event` | `backfill_activity_events_from_trips()` | `yego_lima_lifecycle_service.py` | `POST /lifecycle/backfill` | Manual only | On-demand | Intelligence |

---

## WRITER REGISTRY — V2 Shadow Pipeline (separate scheduler)

| # | Table | Writer Function | File | Trigger | Scheduler | Frequency | Owner |
|---|-------|----------------|------|---------|-----------|-----------|-------|
| 17 | `growth.yego_lima_v2_activity_daily` | `_build_activity_daily()` | `yego_lima_v2_daily_pipeline_service.py` | V2 pipeline Step 1 | V2 cron 04:45 | Daily | V2 Intelligence |
| 18 | `growth.yego_lima_v2_activity_weekly` | `_build_activity_weekly()` | same file | V2 pipeline Step 2 | V2 cron 04:45 | Daily | V2 Intelligence |
| 19 | `growth.yego_lima_v2_activity_monthly` | `_build_activity_monthly()` | same file | V2 pipeline Step 3 | V2 cron 04:45 | Daily | V2 Intelligence |
| 20 | `growth.yego_lima_v2_lifecycle_daily` | `_build_lifecycle_daily()` | same file | V2 pipeline Step 4 | V2 cron 04:45 | Daily | V2 Intelligence |
| 21 | `growth.yego_lima_v2_taxonomy_daily` | `_build_taxonomy_v2_daily()` | same file | V2 pipeline Step 5 | V2 cron 04:45 | Daily | V2 Intelligence |
| 22 | `growth.yego_lima_v2_program_daily` | `_build_program_v2_daily()` | same file | V2 pipeline Step 6 | V2 cron 04:45 | Daily | V2 Intelligence |
| 23 | `growth.yego_lima_v2_movement_fact` | `_build_movement_fact()` | same file | V2 pipeline Step 7 | V2 cron 04:45 | Daily | V2 Intelligence |
| 24 | `growth.yego_lima_v2_observability_fact` | `_build_observability_facts()` | same file | V2 pipeline Step 8 | V2 cron 04:45 | Daily | V2 Intelligence |
| 25 | `growth.yego_lima_v2_effectiveness_fact` | `_build_effectiveness_facts()` | same file | V2 pipeline Step 9 | V2 cron 04:45 | Daily | V2 Intelligence |

---

## WRITER REGISTRY — Specialized / Manual

| # | Table | Writer Function | File | Trigger | Scheduler | Frequency | Owner |
|---|-------|----------------|------|---------|-----------|-----------|-------|
| 26 | `growth.rna_priority_fact` | `build_rna_priority()` | `yego_lima_rna_priority_service.py:34` | `POST /rna-priority/build` | Manual | On-demand | RNA |
| 27 | `growth.rna_pilot_measurement_fact` | `build_pilot_measurement()` | `yego_lima_rna_pilot_measurement_service.py:19` | `POST /rna-pilot/build` | Manual | On-demand | RNA |
| 28 | `growth.program_effectiveness_fact` | `_build_effectiveness_facts()` | `yego_lima_v2_daily_pipeline_service.py` (V2 step 9) | V2 pipeline + manual recovery | V2 cron 04:45 | Daily | Effectiveness |
| 29 | `growth.yego_lima_driver_taxonomy_daily` | `build_driver_taxonomy()` | `yego_lima_taxonomy_service.py:127` | `POST /taxonomy/build` | Manual only | On-demand | Taxonomy |
| 30 | `growth.yego_lima_driver_explorer_fact` | `build_driver_explorer_fact()` | `yego_lima_driver_explorer_fact_service.py:62` | Script `build_driver_explorer_fact.py` | NOT ACTIVATED | Manual | Explorer |
| 31 | `growth.yego_lima_loopcontrol_result_sync` | `sync_loopcontrol_results()` | `yego_lima_loopcontrol_result_sync_service.py` | LoopControl export sync | On export | On-demand | Control Loop |
| 32 | `growth.yego_lima_impact_tracking` | Impact builders | `yego_lima_impact_service.py` | Manual attribution | Manual | On-demand | Impact |

---

## WRITER REGISTRY — Operational Logging (infrastructure)

| # | Table | Writer Function | File | Trigger | Scheduler | Frequency |
|---|-------|----------------|------|---------|-----------|-----------|
| 33 | `growth.yego_lima_refresh_run_log` | `_create_run()` / `_finish_run()` | `yego_lima_daily_refresh_service.py` | `run_daily_refresh()` | autonomous_tick | On cascade |
| 34 | `growth.yego_lima_refresh_step_log` | `_log_step()` | `yego_lima_daily_refresh_service.py` | `run_daily_refresh()` | autonomous_tick | On cascade |
| 35 | `growth.yego_lima_scheduler_status` | `_ensure_scheduler_row()` / `_update_scheduler()` | `yego_lima_scheduler_service.py` | `autonomous_tick()` always | autonomous_tick | Every 5 min |
| 36 | `growth.yego_lima_scheduler_tick_log` | `_write_tick_log_always()` | `yego_lima_scheduler_service.py` | `autonomous_tick()` always | autonomous_tick | Every 5 min |
| 37 | `growth.yego_lima_v2_pipeline_run_log` | Pipeline run logger | `yego_lima_v2_daily_pipeline_service.py` | V2 pipeline | V2 cron | Daily |
| 38 | `growth.yego_lima_v2_pipeline_step_log` | Pipeline step logger | `yego_lima_v2_daily_pipeline_service.py` | V2 pipeline | V2 cron | Daily |
| 39 | `growth.yego_lima_freshness_registry` | `_refresh_freshness_registry()` | `yego_lima_scheduler_service.py` | `autonomous_tick()` always | autonomous_tick | Every 5 min |
| 40 | `growth.yego_lima_v2_freshness_registry` | `_update_freshness_registry()` | `yego_lima_v2_daily_pipeline_service.py` | V2 pipeline | V2 cron | Daily |
| 41 | `growth.yego_lima_serving_freshness_fact` | `run_serving_freshness_audit()` | `serving_freshness_audit_service.py` | serving audit scheduler | Serving cron | Daily |
| 42 | `growth.yego_lima_export_audit` | `create_export()` | `yego_lima_export_service.py` | Export endpoints | On-demand | On export |

---

## SUMMARY

| Category | Tables | Auto-scheduled | Manual-only | Not Active |
|----------|--------|---------------|-------------|------------|
| Core Operational | 10 | 10 (autonomous_tick) | 0 | 0 |
| Intelligence | 6 | 0 (V2 cron failing) | 6 | 0 |
| V2 Shadow | 9 | 0 (V2 cron failing) | 9 (manual trigger) | 0 |
| Specialized | 7 | 0 | 7 | 1 (explorer_fact) |
| Logging | 10 | 8 | 2 | 0 |
| **Total** | **42** | **18** | **24** | **1** |

**18 of 42 tables (43%) have automated schedulers. 24 of 42 (57%) require manual trigger.**
