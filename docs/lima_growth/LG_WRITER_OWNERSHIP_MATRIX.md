# LG_WRITER_OWNERSHIP_MATRIX

**Phase:** LG-CF-RECOVERY-2A — Control Foundation Closure  
**Generated:** 2026-06-12  

---

## CRITICALITY DEFINITION

| Level | Definition | Impact if Writer Fails |
|-------|-----------|----------------------|
| **P0** | Core operational. Failure = dashboard unusable. | Intelligence Dashboard shows stale/broken data for 1+ tabs. |
| **P1** | Intelligence/Serving. Failure = degraded but dashboard still functional. | 1+ tabs show stale data. Core operational tabs still work. |
| **P2** | Specialized/Logging. Failure = no visible impact on dashboard. | Internal monitoring/audit only. |

---

## OWNERSHIP MATRIX

### P0 — CRITICAL (dashboard unusable if writer fails)

| # | Table | Writer | Owner Service | Consumer Tabs | Trigger | Frequency | Criticidad |
|---|-------|--------|---------------|---------------|---------|-----------|------------|
| 1 | `yango_lima_driver_state_snapshot` | `build_driver_state_snapshot()` | `yego_lima_driver_state_service.py` | Overview, Programs, DriverState, Explorer | autonomous_tick | Every 5 min (cascade) | **P0** |
| 2 | `yango_lima_program_eligibility_daily` | `build_program_eligibility()` | `yego_lima_program_eligibility_service.py` | Programs, Overview, Explorer | autonomous_tick | Every 5 min (cascade) | **P0** |
| 3 | `yego_lima_assignment_queue` | `create_assignment_batch()` | `yego_lima_assignment_queue_service.py` | Control Loop, Export | autonomous_tick → daily_refresh Step 3 | Every 5 min (cascade) | **P0** |
| 4 | `yego_lima_serving_fact` | `generate_all_serving_facts()` | `yego_lima_serving_facts_service.py` | Overview, Programs, Queue, ActionPlan | autonomous_tick | Every 5 min (always) | **P0** |

### P1 — HIGH (dashboard degraded if writer fails)

| # | Table | Writer | Owner Service | Consumer Tabs | Trigger | Frequency | Criticidad |
|---|-------|--------|---------------|---------------|---------|-----------|------------|
| 5 | `yego_lima_driver_lifecycle_daily` | `build_lifecycle_daily()` | `yego_lima_lifecycle_service.py` | Overview, Explorer, V2 pipeline | V2 pipeline Step 4 / Manual POST | Daily (manual currently) | **P1** |
| 6 | `yego_lima_v2_taxonomy_daily` | `_build_taxonomy_v2_daily()` | `yego_lima_v2_daily_pipeline_service.py` | Segments, Explorer (COALESCE) | V2 pipeline Step 5 / Manual POST | Daily (manual currently) | **P1** |
| 7 | `yego_lima_v2_program_daily` | `_build_program_v2_daily()` | `yego_lima_v2_daily_pipeline_service.py` | Programs | V2 pipeline Step 6 / Manual POST | Daily (manual currently) | **P1** |
| 8 | `yego_lima_v2_movement_fact` | `_build_movement_fact()` | `yego_lima_v2_daily_pipeline_service.py` | Movement Analytics, Explorer | V2 pipeline Step 7 / Manual POST | Daily (manual currently) | **P1** |
| 9 | `rna_priority_fact` | `build_rna_priority()` | `yego_lima_rna_priority_service.py` | RNA Tab, Explorer | Manual POST | On-demand | **P1** |
| 10 | `program_effectiveness_fact` | `_build_effectiveness_facts()` | `yego_lima_v2_daily_pipeline_service.py` | Effectiveness Tab | V2 pipeline Step 9 / Manual POST | Daily (manual currently) | **P1** |
| 11 | `yego_lima_driver_explorer_fact` | `build_driver_explorer_fact()` | `yego_lima_driver_explorer_fact_service.py` | Driver Explorer Tab | Script / Feature flag | On-demand (not active) | **P1** |

### P2 — MEDIUM (no visible dashboard impact)

| # | Table | Writer | Owner Service | Consumer Tabs | Trigger | Frequency | Criticidad |
|---|-------|--------|---------------|---------------|---------|-----------|------------|
| 12 | `yango_lima_daily_opportunity_list` | `build_daily_opportunity_lists()` | `yego_lima_daily_opportunity_service.py` | Internal (policy engine) | autonomous_tick | Every 5 min (cascade) | **P2** |
| 13 | `yango_lima_prioritized_opportunity_daily` | `build_prioritized_opportunities()` | `yego_lima_opportunity_policy_service.py` | Internal (policy engine) | autonomous_tick | Every 5 min (cascade) | **P2** |
| 14 | `yego_lima_driver_activity_daily` | `build_activity_daily()` | `yego_lima_lifecycle_service.py` | Internal (lifecycle input) | V2 pipeline Step 1 | Daily | **P2** |
| 15 | `yego_lima_driver_activity_weekly` | `build_activity_weekly()` | `yego_lima_lifecycle_service.py` | Internal (lifecycle input) | V2 pipeline Step 2 | Daily | **P2** |
| 16 | `yego_lima_driver_activity_monthly` | `build_activity_monthly()` | `yego_lima_lifecycle_service.py` | Internal (lifecycle input) | V2 pipeline Step 3 | Daily | **P2** |
| 17 | `yego_lima_intraday_driver_signal` | `build_intraday_signals()` | `yego_lima_intraday_signal_service.py` | Internal (monitoring) | autonomous_tick | Every 5 min (always) | **P2** |
| 18 | `yego_lima_driver_list_history` | `snapshot_queue_to_history()` | `yego_lima_driver_list_history_service.py` | Internal (audit) | autonomous_tick | Every 5 min (always) | **P2** |
| 19 | `yango_lima_orders_raw` | `ingest_recent_orders()` | `yango_raw_tick_ingestion_service.py` | Internal (raw data source) | autonomous_tick | Every 5 min (always) | **P2** |
| 20 | `yego_lima_control_loop_state` | `sync_assignment_queue_to_control_loop()` | `yego_lima_control_loop_sync_service.py` | Internal (sync) | autonomous_tick | Every 5 min (always) | **P2** |
| 21 | `yego_lima_loopcontrol_result_sync` | `sync_loopcontrol_results()` | `yego_lima_loopcontrol_result_sync_service.py` | Internal (contact tracking) | On export | On-demand | **P2** |
| 22 | `yego_lima_impact_tracking` | Impact builders | `yego_lima_impact_service.py` | Internal (impact measurement) | Manual | On-demand | **P2** |
| 23 | `rna_pilot_measurement_fact` | `build_pilot_measurement()` | `yego_lima_rna_pilot_measurement_service.py` | RNA Pilot | Manual POST | On-demand | **P2** |
| 24 | `yego_lima_driver_taxonomy_daily` | `build_driver_taxonomy()` | `yego_lima_taxonomy_service.py` | Legacy Segments | Manual POST | On-demand | **P2** |

### Logging/Infrastructure (P2)

| # | Table | Writer | Frequency | Criticidad |
|---|-------|--------|-----------|------------|
| 25-34 | `refresh_run_log`, `step_log`, `scheduler_status`, `tick_log`, `pipeline_run_log`, `pipeline_step_log`, `freshness_registry`, `v2_freshness_registry`, `serving_freshness_fact`, `export_audit` | Various logging services | Various | **P2** |

---

## SUMMARY

| Criticality | Count | % | Notes |
|------------|-------|---|-------|
| **P0** | 4 | 12% | All 4 are in autonomous_tick. Operational coverage is solid. |
| **P1** | 7 | 21% | 5 of 7 require manual trigger. Only lifecycle + explorer can be automated. |
| **P2** | 23 | 68% | Internal/logging. Low operational risk. |
| **Total** | **34** | **100%** | |

### Key Finding

**All P0 writers are automated (autonomous_tick). The operational foundation is solid.**

**The governance gap is entirely in P1:** 5 of 7 P1 writers (lifecycle, taxonomy, program_v2, movement, rna, effectiveness) require manual trigger. These serve the Intelligence Dashboard tabs (Segments, Movement, RNA, Effectiveness, Explorer).

**If autonomous_tick is running, the dashboard will ALWAYS show data in Overview and Programs tabs.** The risk is limited to Intelligence tabs (Segments, Movement, RNA, Effectiveness, Explorer) which depend on P1 writers.
