# LG-R1.8 — Legacy Deprecation Report

**Date:** 2026-06-07
**Phase:** LG-INFRA-R1.8
**Status:** CANONICAL

---

## CLASSIFICATION OF ALL LIMA GROWTH TABLES

### CANONICAL (Active operational chain)

| Table | Role | Evidence |
|-------|------|----------|
| `raw_yango.orders_raw` | Live order ingestion | API source, 11,087 rows |
| `growth.yango_lima_orders_raw` | Normalized orders | Fed by ingestion |
| `growth.yango_lima_driver_history_daily` | Historical daily | Bootstrap from trips |
| `growth.yango_lima_driver_history_weekly` | Historical weekly | PRIMARY universe feeder |
| `growth.yango_lima_driver_state_snapshot` | **KEYSTONE** | Feeds eligibility → opportunity → prioritized → queue → serving → UI |
| `growth.yango_lima_program_eligibility_daily` | Program assignment | 28,493 rows, feeds opportunity |
| `growth.yango_lima_daily_opportunity_list` | Daily opportunities | 28,493 rows, feeds prioritized |
| `growth.yango_lima_prioritized_opportunity_daily` | Scored & ranked | 5,604 rows, feeds queue |
| `growth.yego_lima_assignment_queue` | Operational queue | 500 rows, feeds export |
| `growth.yego_lima_serving_fact` | UI cache | 8 facts, serving-first |
| `growth.yego_lima_driver_list_history` | Immutable trace | 500 rows, R1.5 |
| `growth.yego_lima_intraday_driver_signal` | Live observation | R1.3 |
| `growth.yego_lima_scheduler_status` | Scheduler state | R1.2 |
| `growth.yego_lima_scheduler_tick_log` | Tick evidence | R1.6 |

### DERIVED (Analytics, non-critical path)

| Table | Role |
|-------|------|
| `growth.yango_lima_driver_segment_snapshot` | Driver segmentation |
| `growth.yango_lima_loyalty_sub50_weekly` | Loyalty analysis |
| `growth.yango_lima_driver_segment_transition_daily` | Segment transitions |
| `growth.yango_lima_driver_action_daily_impact` | Impact tracking |
| `growth.yango_lima_action_attribution_daily` | Attribution |
| `growth.yego_lima_impact_tracking` | Impact tracking |
| `growth.yego_lima_movement_tracking` | Movement tracking |
| `growth.yego_lima_attribution_candidates` | Attribution candidates |
| `growth.yango_lima_productivity_daily/weekly/monthly` | Productivity metrics |

### CONFIG (Read-only parameters)

| Table | Role |
|-------|------|
| `growth.yango_lima_opportunity_policy_config` | Scoring policy |
| `growth.yango_lima_loopcontrol_config` | LoopControl settings |
| `growth.yego_lima_capacity_config` | Agent capacity |
| `growth.yego_lima_program_capacity_policy` | Program caps |

### AUDIT (Operational logs)

| Table | Role |
|-------|------|
| `growth.yango_lima_pipeline_run_log` | Pipeline execution |
| `growth.yango_lima_pipeline_run_step_log` | Step details |
| `growth.yego_lima_refresh_run_log` | Refresh execution |
| `growth.yego_lima_refresh_step_log` | Step details |
| `growth.yego_lima_queue_build_audit` | Queue audit |
| `growth.yango_lima_loopcontrol_export_job_run` | Export jobs |
| `growth.yango_lima_loopcontrol_export_job_program` | Export programs |
| `growth.yango_lima_loopcontrol_campaign_export` | Campaign exports |
| `growth.yego_lima_loopcontrol_result_sync` | Result sync (orphaned) |
| `growth.yango_lima_data_freshness` | Freshness tracking |

---

## SPECIFIC DEPRECATION VERDICTS

### 1. `public.trips_2025` and `public.trips_2026`

| Table | Status | Verdict |
|-------|:------:|---------|
| `trips_2025` | **LEGACY** | KEEP — historical enrichment only. Needed for `driver_history_daily` bootstrap. Do not use for freshness. |
| `trips_2026` | **LEGACY** | KEEP — historical enrichment only. Same as trips_2025. |

**Evidence:** `yego_lima_growth_history_service` bootstraps `driver_history_daily` from trips tables. Without them, `driver_history_weekly` and therefore `driver_state_snapshot` cannot be built.

**DO NOT REMOVE.** Usage is restricted to historical enrichment per `LG_DEPRECATED_OPERATIONAL_SOURCES.md`.

---

### 2. `growth.yango_lima_driver_360_daily`

| Verdict | **CANDIDATE FOR REMOVAL** |
|---------|---------------------------|

**Evidence:**
- `build_driver_state_snapshot()` uses `driver_360_daily` as **SECONDARY enrichment** (comment line 98: "360_daily data for supply enrichment")
- PRIMARY universe comes from `driver_history_weekly` (comment line 80)
- Every field from 360 defaults to 0/None when missing (lines 167-179)
- Snapshot produces **18,475 rows** with driver_360 having **0 rows** → proves 360 is optional
- `driver_360_daily` has **0 rows for ALL dates** (06-03, 06-04, 06-05) → table is effectively dead

**Action:** Deprecate. Remove from pipeline mandatory steps. Keep table for historical reference but stop building it.

---

### 3. `growth.yango_lima_eligible_universe_daily`

| Verdict | **CANDIDATE FOR REMOVAL** |
|---------|---------------------------|

**Evidence:**
- Only consumer is `stabilize_driver_360_day()` (which is itself dead)
- No other service reads from this table
- `build_driver_state_snapshot()` does NOT read from it
- `build_program_eligibility()` does NOT read from it
- Table has 0 rows for 06-03/04, only 1000 for 06-05 (from prior manual run)

**Action:** Deprecate. Pipeline skips it already. No operational impact from removal.

---

### 4. Legacy Tables (Superseded)

| Table | Superseded By | Verdict |
|-------|---------------|:------:|
| `growth.yango_lima_actionable_list_daily` | `daily_opportunity_list` | **DEPRECATE NOW** |
| `growth.yango_lima_actionable_list_outcome_daily` | Superseded | **DEPRECATE NOW** |
| `growth.yango_lima_driver_action_registry` | Superseded | **DEPRECATE NOW** |
| `growth.yango_lima_hourly_snapshot` | `driver_360_daily` (also dead) | **DEPRECATE NOW** |

These 4 tables are superseded by the Fase 2D-R pipeline. No service reads from them in the current operational path. They can be safely deprecated or archived.

---

## SUMMARY

| Category | Count |
|----------|:-----:|
| CANONICAL | 14 |
| DERIVED | 9 |
| CONFIG | 4 |
| AUDIT | 10 |
| KEEP (legacy, needed) | 2 (trips_2025, trips_2026) |
| CANDIDATE FOR REMOVAL | 2 (driver_360, eligible_universe) |
| DEPRECATE NOW | 4 (actionable_list*, driver_action_registry, hourly_snapshot) |

---

## FIRMA

```
LEGACY DEPRECATION REPORT
LG-INFRA-R1.8 Canonical Lineage Certification
Date: 2026-06-07
```
