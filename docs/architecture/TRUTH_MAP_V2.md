# YEGO CONTROL TOWER — TRUTH MAP V2

**Version:** 2.0.0
**Date:** 2026-06-13
**Status:** DEFINITIVE — All UNKNOWN resolved from live code audit
**Method:** Exhaustive trace: writer search (all .py in backend/), reader search (all .py in backend/app/), scheduler trace, freshness trace
**Entry point:** For any AI session, start at [AI_START_HERE.md](AI_START_HERE.md)
**Scope governance:** Before any implementation planning, read [ACTIVE_SCOPE_CONTRACT.md](ACTIVE_SCOPE_CONTRACT.md). This contract defines current in-scope work, out-of-scope engines/features, deferred backlog, and implementation gates. All implementation prompts must pass the Scope Escalation Test.
**Production status:** Growth Machine **Backend Core: CLOSED** (2026-06-14). **Worklist Writer: V2 ACTIVE default.** Universe Config V2 `UNIVERSE_V2_DRAFT_003` is ACTIVE for Lima. 19 fine segments. Writer auto-detects ACTIVE config and applies V2 rules. V1 fallback preserved. Control Loop still held (6,114 READY, 20260615 batch). UI operational (Comando Diario + Listas de Trabajo). Diagnostic Engine blocked.
**North Star:** Lima Growth Machine North Star is defined in `docs/lima_growth/LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md`. Future Growth Machine work must prioritize exclusive dynamic operational lists, Control Loop export, action tracking, and impact measurement.
**MVP Certification:** Exclusive lists MVP reached **Production GO** (2026-06-13). 18,545 drivers classified into 9 exclusive universes. 6,109 exportable, 0 duplicates, fully explained and synced to Control Loop. See `docs/lima_growth/LG_PROD_GO_1A_LIMA_GROWTH_MVP_PRODUCTION_CERTIFICATION.md`.
**New critical table:** `growth.yango_lima_exclusive_driver_worklist_daily` — serving fact for V1 exclusive universes. Writer: `refresh_exclusive_driver_worklist_daily()`. Freshness: chain + registry + audit (SLA 24h). Readers: CSV/API, Control Loop sync.

---

## TABLE 1: `ops.driver_day_slice_fact` (Driver Bridge)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `MULTI_WRITER` | 2 writers |
| **Writer #1 (CANONICAL)** | `backend/scripts/build_driver_bridge_direct.py:16` | `INSERT ... ON CONFLICT DO UPDATE` from `public.trips_2026` |
| **Writer #2 (LEGACY)** | `backend/scripts/build_driver_day_slice_fact.py:18` | `INSERT ... ON CONFLICT DO UPDATE` from resolved view. Superseded. |
| **Readers (serving)** | `omniview_v2.py` (drill/cell, cell-audit, reconciliation/park, freshness-observatory), `omniview_v2_matrix_repository.py:144` (active_drivers) | 13 query blocks, 4 files |
| **Readers (ETL)** | `rebuild_day_from_bridge.py`, `rebuild_week_from_day_and_bridge.py`, `rebuild_month_from_day_and_bridge.py` | Cascade builders |
| **Readers (audit)** | `omniview_cascade_service.py:264`, multiple audit scripts | Freshness + reconciliation |
| **Scheduler** | `omniview_cascade_refresh` (APScheduler, `main.py:313`) → `omniview_cascade_service.py:93-101` layer "driver_bridge" | Cron daily (if enabled) |
| **Refresh mechanism** | `build_driver_bridge_direct.py` via OV2 cascade | UPSERT idempotente |
| **Freshness contract** | `omniview_cascade_service.py:264` — checks `MAX(activity_date)`. NOT in `data_freshness_expectations`, `data_freshness_audit`, or `serving_registry`. | Cascade-only monitoring |
| **Owner service** | `omniview_cascade_service.py` (orchestrator), `build_driver_bridge_direct.py` (builder) | |
| **Risk** | Legacy writer still executable. Bridge not in serving_registry. | MEDIUM |

---

## TABLE 2: `ops.real_business_slice_day_fact` (Day Fact)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `MULTI_WRITER` | 4 distinct scripts |
| **Writer #1 (LEGACY)** | `business_slice_incremental_load.py:331+1330+1739+2158+2169` | DELETE+INSERT from enriched trip resolution |
| **Writer #2 (AD-HOC)** | `backfill_runner.py:123+185+190` | DELETE per date range |
| **Writer #3 (CANONICAL)** | `rebuild_day_from_bridge.py:99+101` | DELETE+INSERT from driver bridge via staging |
| **Writer #4 (AD-HOC)** | `quick_backfill_may2026.py:13+154` | Hardcoded backfill |
| **Readers (serving)** | `business_slice_service.py:3013-3030` (daily aggregation), `omniview_v2_matrix_repository.py:104-124` (matrix), `business_slice_omniview_service.py` (Omniview) | ~23 files, ~50+ query blocks |
| **Readers (audit)** | `omniview_matrix_integrity_service.py`, `omniview_v1_trust_sensor.py`, `omniview_v1_waterfall_validation.py`, `period_closure_service.py:52` | Extensive integrity checks |
| **Scheduler** | `omniview_cascade_refresh` (via cascade layer "day_fact", `omniview_cascade_service.py:103-111`) | Cron daily |
| **Also triggered by** | `business_slice_real_refresh_job` (APScheduler, `main.py`) — legacy path | Every 15 min |
| **Refresh mechanism** | Canonical: `rebuild_day_from_bridge.py` (staging swap, atomic). Legacy: `business_slice_incremental_load.py` (staging swap). | Two competing mechanisms |
| **Freshness contract** | `business_slice_real_freshness_service.py:88` — checks `MAX(trip_date)`, `MAX(loaded_at)`, `MAX(refreshed_at)`. NOT in `data_freshness_expectations`, `data_freshness_audit`, or `serving_registry`. | Service-level only |
| **Owner service** | `omniview_cascade_service.py` (CANONICAL), `business_slice_incremental_load.py` (LEGACY) | Two owners — conflict risk |
| **Risk** | 4 writers, 2 competing refresh mechanisms. No serving_registry registration. | HIGH |

---

## TABLE 3: `ops.real_business_slice_week_fact` (Week Fact)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `MULTI_WRITER` | 7 distinct scripts |
| **Writer #1 (LEGACY)** | `business_slice_incremental_load.py:544+739+819+1399+1877+1884+2178+2189` | DELETE+INSERT rollup from day fact |
| **Writer #2 (AD-HOC)** | `backfill_runner.py:201` | DELETE per date range |
| **Writer #3 (CANONICAL)** | `rebuild_week_from_day_and_bridge.py:122+124` | DELETE+INSERT from day_fact + bridge via staging |
| **Writer #4 (BROKEN)** | `rebuild_week_fact_from_day_fact.py:147+154` | **BROKEN** — uses SUM(DISTINCT) for active_drivers. Documented as broken in `omniview_v1_trust_sensor.py:334`. |
| **Writer #5 (AD-HOC)** | `backfill_week_fact_apr_may.py:20+27` | DELETE+INSERT hardcoded range |
| **Writer #6 (BLOCKED)** | `backfill_week_from_day_fact.py:46+109` | BLOCKED by safety guard |
| **Writer #7 (AD-HOC)** | `quick_backfill_may2026_week.py:11+143` | Hardcoded backfill |
| **Readers (serving)** | `business_slice_service.py:2847-2863` (weekly aggregation), `omniview_v2_matrix_repository.py` (matrix) | ~10 files, ~20 query blocks |
| **Readers (audit)** | `omniview_matrix_integrity_service.py:1987-2003`, `omniview_v1_trust_sensor.py`, `omniview_v1_waterfall_validation.py:64` | Integrity + trust |
| **Scheduler** | `omniview_cascade_refresh` (cascade layer "week_fact", `omniview_cascade_service.py:113-121`) | Cron daily |
| **Also triggered by** | `business_slice_real_refresh_job` (legacy path) | Every 15 min |
| **Refresh mechanism** | Canonical: `rebuild_week_from_day_and_bridge.py` (staging swap). Legacy: `business_slice_incremental_load.py` (rollup). | Two competing mechanisms |
| **Freshness contract** | `business_slice_real_freshness_service.py:100` — checks `MAX(week_start)`, `MAX(loaded_at)`, `MAX(refreshed_at)`. NOT in `data_freshness_expectations`, `data_freshness_audit`, or `serving_registry`. | Service-level only |
| **Owner service** | `omniview_cascade_service.py` (CANONICAL), `business_slice_incremental_load.py` (LEGACY) | Two owners |
| **Risk** | **CRITICAL.** 7 writers. 1 BROKEN writer executable. Race condition risk between any of them. | CRITICAL |

---

## TABLE 4: `ops.real_business_slice_month_fact` (Month Fact)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `MULTI_WRITER` | 3 distinct scripts |
| **Writer #1 (LEGACY/DEPRECATED)** | `business_slice_incremental_load.py:41+1034+1043+1467+1591+2199+2210` | DELETE+INSERT from enriched trip resolution. DEPRECATED at line 1553. |
| **Writer #2 (AD-HOC)** | `backfill_runner.py:127` | DELETE per month |
| **Writer #3 (CANONICAL)** | `rebuild_month_from_day_and_bridge.py:110+112` | DELETE+INSERT from day_fact + bridge via staging |
| **Readers (serving)** | `business_slice_service.py:2197` (via serving view), `business_slice_omniview_service.py:801`, `control_loop_plan_vs_real_service.py` (PvR), `yango_loyalty_performance_service.py:237`, `yango_loyalty_definition_service.py:264` | ~24 files, ~40+ query blocks |
| **Readers (audit)** | `omniview_matrix_integrity_service.py` (~15 sites), `omniview_v1_trust_sensor.py`, `omniview_v1_waterfall_validation.py`, `last_good_data_service.py:38+213`, `period_closure_service.py:407`, `revenue_quality_service.py:182` | Extensive integrity + period closure |
| **Scheduler** | `omniview_cascade_refresh` (cascade layer "month_fact", `omniview_cascade_service.py:123-131`) | Cron daily |
| **Also triggered by** | `refresh_business_slice_mvs.py`, `business_slice_real_refresh_job` | Multiple paths |
| **Snapshot mechanism** | `last_good_data_service.py` creates `ops.real_business_slice_month_snapshot` for locked periods. Serving view `v_real_business_slice_month_serving` redirects: locked → snapshot, open → month_fact. | |
| **Freshness contract** | `business_slice_real_freshness_service.py:157` — uses `FACT_MONTHLY_RAW`. NOT in `data_freshness_expectations`, `data_freshness_audit`, or `serving_registry`. | Service-level only |
| **Owner service** | `omniview_cascade_service.py` (CANONICAL), `last_good_data_service.py` (snapshot), `period_closure_service.py` (closure) | Three owners |
| **Risk** | 3 writers (1 deprecated but still referenced). Only fact table with snapshot+serving_view. | MEDIUM |

---

## TABLE 5: `growth.yango_lima_driver_history_weekly` (Driver History Weekly)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `CERTIFIED` — SINGLE_WRITER | 1 active writer |
| **Writer (ONLY)** | `backend/app/services/yego_lima_growth_history_service.py:218` | `_build_weekly_sql_bulk()` — UPSERT via `INSERT ... ON CONFLICT DO UPDATE`. Reads from `growth.yango_lima_driver_history_daily`, computes rolling metrics (4w/8w/12w avg, best_week_12w, historical_band) via window functions. |
| **Dead code** | `backend/app/repositories/yego_lima_growth_history_repository.py:60` | `upsert_history_weekly()` defined but **NEVER called** in any Python file. |
| **Readers (serving)** | `yego_lima_driver_state_service.py:86-94` (primary universe for state snapshot), `yego_lima_driver_segmentation_service.py:122-136` (segment L1/L2/L3), `yego_lima_loyalty_sub50_service.py:174-178`, `yego_lima_opportunity_policy_service.py:224-227`, `yego_lima_productivity_service.py:220-223`, `yego_lima_program_explainability_service.py:218-221` | 11 files read actively |
| **Readers (audit)** | `yego_lima_universe.py:77-81` (governance), `yego_lima_freshness_chain_service.py:36`, `yego_lima_daily_pipeline_service.py:224` (validation) | |
| **Scheduler** | **NOT COVERED** — no APScheduler job, no autonomous tick. Manual bootstrap only via `bootstrap_history()` in `yego_lima_growth_history_service.py:93`. | **GAP** |
| **Refresh mechanism** | `bootstrap_history()` (manual): reads `public.trips_2025` + `public.trips_2026` (Lima park filter), builds `driver_history_daily`, then rolls up to `driver_history_weekly`. | Manual only |
| **Freshness contract** | `yego_lima_freshness_chain_service.py:36` — checks `MAX(week_start_date)`. NOT in `yego_lima_freshness_registry` or `yego_lima_serving_freshness_fact`. | Chain-only monitoring |
| **Owner service** | `yego_lima_growth_history_service.py` | |
| **Risk** | No automated refresh. Entire Growth Machine state pipeline depends on this table being current. If bootstrap not run manually, driver_state_snapshot uses stale data. | HIGH |

---

## TABLE 6: `growth.yango_lima_driver_state_snapshot` (State Snapshot)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `CERTIFIED` — SINGLE_WRITER | 1 writer |
| **Writer (ONLY)** | `backend/app/services/yego_lima_driver_state_service.py:335` | `_upsert_snapshot()` — UPSERT `INSERT ... ON CONFLICT (snapshot_date, driver_profile_id) DO UPDATE`. 30 columns: lifecycle_state (7 states), performance_state (5 states), retention_state (4 states), plus day/week metrics, flags, TPH, distance_to_target. |
| **Readers (serving)** | `yego_lima_driver_state_summary_service.py:33+71` (summary for UI), `yego_lima_operational_summary_service.py:127-137` (operational summary), `yego_lima_executive_metrics_service.py:19`, `yego_lima_daily_opportunity_service.py:88-91` (enrichment), `yego_lima_program_explainability_service.py:168-184`, `yego_lima_opportunity_worklist_service.py:99` (LEFT JOIN enrichment) | ~26 files read |
| **Readers (ETL)** | `yego_lima_program_eligibility_service.py:49-53` (source for eligibility), `yego_lima_daily_opportunity_service.py:61-63` (source for opportunity), `yego_lima_driver_explorer_fact_service.py:27`, `yego_lima_taxonomy_service.py:19` | Multiple downstream builders |
| **Readers (audit)** | `yego_lima_freshness_chain_service.py:37`, `yego_lima_refresh_governance_service.py:79`, `yego_lima_governance_service.py:92`, `serving_freshness_audit_service.py:165-175` | Multi-layer freshness |
| **Scheduler** | `lima_growth_autonomous_tick` (APScheduler interval 5 min, `main.py:370`) → `yego_lima_scheduler_service.py:685` calls `build_driver_state_snapshot()` when cascade needed | Every 5 min |
| **Also triggered by** | `yego_lima_daily_pipeline_service.py` (step 6: `build_driver_state_snapshot`) | Daily pipeline |
| **Refresh mechanism** | `yego_lima_driver_state_service.py:60` `build_driver_state_snapshot()` — reads from `driver_history_weekly` + `driver_360_daily`, classifies 3-axis state, UPSERTs. | Automated via scheduler |
| **Freshness contract** | `yego_lima_freshness_chain_service.py:37` (chain), `serving_freshness_audit_service.py:165-175` (SERVING_ASSETS entry `"driver_state_snapshot"`), `yego_lima_refresh_governance_service.py:20` (COMPONENT `"driver_state"`), `growth.yego_lima_freshness_registry` (component `"driver_state"`), `growth.yego_lima_serving_freshness_fact` (asset `"driver_state_snapshot"`) | Comprehensive — the best-covered table |
| **Owner service** | `yego_lima_driver_state_service.py` | |
| **Risk** | Depends on `driver_history_weekly` which has no automated refresh. If history is stale, state is stale. | MEDIUM (inherited) |

---

## TABLE 7: `growth.yango_lima_program_eligibility_daily` (Program Eligibility)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `CERTIFIED` — SINGLE_WRITER | 1 writer |
| **Writer (ONLY)** | `backend/app/services/yego_lima_program_eligibility_service.py:56+63+100+143` | `build_program_eligibility()` — DELETE WHERE eligibility_date + 3 INSERTs (PROGRAM_14_90, PROGRAM_ACTIVE_GROWTH, PROGRAM_CHURN_PREVENTION). Reads from `driver_state_snapshot`. |
| **Readers (serving)** | `yego_lima_programs_summary_service.py:34`, `yego_lima_program_status_service.py:61`, `yego_lima_program_explainability_service.py`, `yego_lima_executive_metrics_service.py:20`, `yego_lima_operational_summary_service.py:39`, `yego_lima_todays_action_plan_service.py:65`, `yego_lima_effectiveness_service.py:16` | ~24 files read |
| **Readers (ETL)** | `yego_lima_daily_opportunity_service.py:54-56+87-91` (primary consumer — builds `daily_opportunity_list`) | Downstream builder |
| **Readers (audit)** | `yego_lima_freshness_chain_service.py:38`, `yego_lima_refresh_governance_service.py:21`, `serving_freshness_audit_service.py:141-151` (SERVING_ASSETS `"program_assignment"`) | Multi-layer freshness |
| **Scheduler** | `lima_growth_autonomous_tick` (5 min) → `yego_lima_scheduler_service.py:688` calls `build_program_eligibility()` when cascade needed | Every 5 min |
| **Also triggered by** | `yego_lima_daily_pipeline_service.py` (step 7: `build_program_eligibility`) | Daily pipeline |
| **Refresh mechanism** | DELETE+INSERT idempotente per eligibility_date. Rules: 3 hardcoded program criteria evaluated against `driver_state_snapshot`. | Automated |
| **Freshness contract** | `yego_lima_freshness_chain_service.py:38`, `serving_freshness_audit_service.py:141-151`, `growth.yego_lima_freshness_registry` (component `"eligibility"`), `growth.yego_lima_serving_freshness_fact` (asset `"program_assignment"`) | Covered |
| **Owner service** | `yego_lima_program_eligibility_service.py` | |
| **Risk** | DELETE before INSERT without transaction wrapping — data loss if INSERT fails. | LOW (auto-recovered by next tick) |

---

## TABLE 8: `growth.yango_lima_daily_opportunity_list` (Opportunity List)

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `CERTIFIED` — SINGLE_WRITER | 1 writer |
| **Writer (ONLY)** | `backend/app/services/yego_lima_daily_opportunity_service.py:66+73+127+201+224` | `build_daily_opportunity_lists()` — DELETE WHERE opportunity_date + INSERT ON CONFLICT DO NOTHING (3 opportunity types). Plus UPDATE operations for management_status, assigned_agent, action_id linking. |
| **Readers (serving)** | `yego_lima_executive_metrics_service.py:21`, `yego_lima_opportunity_policy_service.py:25`, `yego_lima_universe.py:144-150` (governance) | ~7 files read |
| **Readers (operational)** | `yego_lima_action_registry_service.py:26` (action linking) | |
| **Readers (audit)** | `yego_lima_daily_pipeline_service.py:255+267-268` (pipeline validation), `yego_lima_freshness_chain_service.py:39` | |
| **Scheduler** | `lima_growth_autonomous_tick` (5 min) → `yego_lima_scheduler_service.py:691` calls `build_daily_opportunity_lists()` when cascade needed | Every 5 min |
| **Also triggered by** | `yego_lima_daily_pipeline_service.py` (step 8: `build_daily_opportunity_lists`) | Daily pipeline |
| **Refresh mechanism** | DELETE+INSERT idempotente per opportunity_date. Reads from `program_eligibility_daily` + `driver_state_snapshot`. | Automated |
| **Freshness contract** | `yego_lima_freshness_chain_service.py:39` only. NOT in `yego_lima_freshness_registry`, `yego_lima_serving_freshness_fact`, or `serving_freshness_audit_service`. | Minimal |
| **Owner service** | `yego_lima_daily_opportunity_service.py` | |
| **Risk** | Minimal freshness monitoring. No freshness registry entry. | LOW |

---

## TABLE 9: `growth.yego_lima_control_loop_state` (Control Loop State)

**NOTE:** Actual table name is `growth.yego_lima_control_loop_state` (NOT `yango_lima` as previously assumed). Created by migration `199_yego_lima_control_loop.py:23`.

| Dimension | Value | Evidence |
|-----------|-------|----------|
| **Classification** | `CERTIFIED` — SINGLE_WRITER | 1 writer |
| **Writer (ONLY)** | `backend/app/services/yego_lima_control_loop_sync_service.py:26` | `sync_assignment_queue_to_control_loop()` — `INSERT INTO growth.yego_lima_control_loop_state SELECT ... FROM growth.yego_lima_assignment_queue WHERE queue_status='READY' AND NOT EXISTS (already in state)`. Only inserts NEW drivers, never overwrites. |
| **Also written by** | `backend/scripts/ctrl_bridge_sync.py:28` | Manual sync script |
| **Readers (serving)** | `yego_lima_control_loop_service.py:21-85` — `get_control_loop_summary()`, `get_agent_summary()`, `get_stale_drivers()`, `get_driver_control_loop()` | All serving reads |
| **Readers (ETL)** | `yego_lima_control_loop_sync_service.py` — `SELECT COUNT(*)` for verification after insert | |
| **Scheduler** | `lima_growth_autonomous_tick` (5 min) → `yego_lima_scheduler_service.py:711+784` calls `sync_assignment_queue_to_control_loop()` always (post-cascade + post-daily-refresh) | Every 5 min |
| **Refresh mechanism** | INSERT from `assignment_queue` with `NOT EXISTS` guard. State machine: READY→CONTACTED→DONE. | Automated |
| **Freshness contract** | **NOT COVERED.** No entry in `yego_lima_freshness_chain_service.py`, `yego_lima_freshness_registry`, `yego_lima_serving_freshness_fact`, `serving_freshness_audit_service`, `data_freshness_expectations`, or `data_freshness_audit`. | **GAP** |
| **Owner service** | `yego_lima_control_loop_sync_service.py` | |
| **Risk** | Zero freshness monitoring. Insert-only (never updates existing states — how do states transition beyond READY?). | MEDIUM |

---

## SUMMARY MATRIX

| # | Table | Classification | Writers | Scheduler | Freshness | Risk |
|---|-------|---------------|---------|-----------|-----------|------|
| 1 | `ops.driver_day_slice_fact` | MULTI_WRITER | 2 (1 canon, 1 legacy) | `omniview_cascade_refresh` (cron) | Cascade-only | MEDIUM |
| 2 | `ops.real_business_slice_day_fact` | MULTI_WRITER | 4 | `omniview_cascade_refresh` + `real_refresh_job` (15min) | Service-level only | HIGH |
| 3 | `ops.real_business_slice_week_fact` | MULTI_WRITER | 7 (1 BROKEN) | `omniview_cascade_refresh` + `real_refresh_job` (15min) | Service-level only | CRITICAL |
| 4 | `ops.real_business_slice_month_fact` | MULTI_WRITER | 3 (1 DEPRECATED) | `omniview_cascade_refresh` (cron) | Service-level only | MEDIUM |
| 5 | `growth.yango_lima_driver_history_weekly` | CERTIFIED | 1 | **NONE** (manual bootstrap) | Chain-only | HIGH |
| 6 | `growth.yango_lima_driver_state_snapshot` | CERTIFIED | 1 | `lima_growth_autonomous_tick` (5 min) | Comprehensive (chain + registry + audit) | MEDIUM |
| 7 | `growth.yango_lima_program_eligibility_daily` | CERTIFIED | 1 | `lima_growth_autonomous_tick` (5 min) | Chain + registry + audit | LOW |
| 8 | `growth.yango_lima_daily_opportunity_list` | CERTIFIED | 1 | `lima_growth_autonomous_tick` (5 min) | Chain-only | LOW |
| 9 | `growth.yego_lima_control_loop_state` | CERTIFIED | 1 | `lima_growth_autonomous_tick` (5 min) | **NONE** | MEDIUM |

---

## TOP GAPS (Priority Order)

| # | Gap | Impact | Action |
|---|-----|--------|--------|
| G1 | **Week fact: 7 writers, 1 BROKEN executable** | Data corruption risk every time any script runs | Consolidate to 1 canonical writer. Block `rebuild_week_fact_from_day_fact.py`. Deprecate `business_slice_incremental_load.py` week path. |
| G2 | **Driver history weekly: NO automated scheduler** | Entire Growth Machine pipeline depends on stale data if bootstrap not run | Add to `lima_growth_autonomous_tick` cascade or `omniview_cascade_refresh`. |
| G3 | **Day/Week/Month facts NOT in `serving_registry`** | No governed freshness monitoring | Register all 3 fact tables in `ops.serving_registry`. |
| G4 | **Control loop state: NO freshness monitoring** | No way to detect stale control loop data | Add to `yego_lima_freshness_chain_service.py` and `yego_lima_freshness_registry`. |
| G5 | **Driver bridge: 2 writers (legacy + canonical)** | Legacy `build_driver_day_slice_fact.py` still executable | Block/deprecate legacy writer. |
| G6 | **Day fact: 2 competing refresh mechanisms** | Cascade + real_refresh_job could race | Consolidate to OV2 cascade only. |

---

## CROSS-REFERENCES

- [TRUTH_MAP.md](TRUTH_MAP.md) — Truth Map V1 (motors, phases, risks, bypasses)
- [SYSTEM_MAP.md](SYSTEM_MAP.md) — System map
- [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — Constraints
- [OMNIVIEW_V2_CANONICAL.md](OMNIVIEW_V2_CANONICAL.md) — Omniview V2 domain
- [GROWTH_MACHINE_CANONICAL.md](GROWTH_MACHINE_CANONICAL.md) — Growth Machine domain

---

*Generated from exhaustive live code audit. Evidence for each cell comes from actual file + line number traces across `backend/app/`, `backend/scripts/`, `backend/app/repositories/`, `backend/app/routers/`, and `backend/alembic/versions/`.*
