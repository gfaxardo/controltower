# GROWTH MACHINE — FRESHNESS PREFLIGHT

**Version:** 2.0.0
**Date:** 2026-06-13
**Status:** UPDATED — Live DB audit (read-only SELECTs) + full code trace
**Scope:** Freshness governance for 5 Growth Machine critical tables
**Precedes:** GM-F1 Freshness Hardening
**Precedence:** TRUTH_MAP_V2.md prevails over all other docs
**Method:** Live `SELECT` against `yego_integral` DB (2026-06-13) + `git grep` + full service/cascade trace

---

## 0. Executive Decision

**CONDITIONAL GO — BLOCKERS IDENTIFIED**

Key findings:
- 5/5 tables HAVE automated refresh via `lima_growth_autonomous_tick` (every 5 min, APScheduler)
- **BUT `driver_history_weekly`** has a threshold bug in FH-1 logic: stale by 12 days, freshness_registry falsely reports "FRESH"
- **`driver_history_daily` is also stale** (`MAX(date) = 2026-06-04`, 9 days behind) — root cause of weekly staleness
- All 5 tables NOW have coverage in `freshness_registry`, `serving_freshness_fact`, and `freshness_chain`
- `control_loop_state` and `opportunity_list` previous gaps have been partially closed by recent changes
- DELETE mutations in `program_eligibility` and `opportunity_list` lack transaction wrapping
- Control Loop CAN operate with stale `driver_history_weekly` due to dual-source architecture (`driver_360_daily` compensates)

Priorities:
- **P0:** Fix FH-1 threshold + `driver_history_daily` staleness (root cause: raw orders ingestion)
- **P1:** Fix freshness_registry false-positive for `driver_history_weekly` (labels 12-day-old data as "FRESH")
- **P1:** DELETE transaction wrapping in `program_eligibility` and `opportunity_list`
- **P2:** Control Loop fail-closed guardrail on `driver_history_weekly` staleness

---

## 1. Phase Context

| Attribute | Value | Source |
|-----------|-------|--------|
| **active_engine** | Control Foundation | `ai_operating_system.md` engine list |
| **sub-system** | Growth Machine Freshness Hardening | `AI_START_HERE.md:68` |
| **active_phase** | OMNI-P0 Recovery (parallel OK) | `ai_current_phase.md:131-133` |
| **ready_next** | Diagnostic Engine 2A.3 (PAUSED) | `ai_current_phase.md:116` |
| **OV2 status** | Ownership/Freshness/Traceability CERTIFIED | Omniview V2 certification |
| **forbidden** | Diagnostic/Forecast/Suggestion/Decision/Action/AI/Learning | `ai_current_phase.md:56-65` |

---

## 2. Tables Under Review

| # | Table | Domain Role | TRUTH_MAP_V2 Status | Scheduler | Freshness | Risk |
|---|-------|------------|---------------------|-----------|-----------|------|
| 1 | `growth.yango_lima_driver_history_weekly` | Driver History Weekly | CERTIFIED — SINGLE_WRITER | `autonomous_tick` (5 min, FH-1 conditional) | Chain + registry + serving_freshness_fact | **HIGH** |
| 2 | `growth.yango_lima_driver_state_snapshot` | State Snapshot | CERTIFIED — SINGLE_WRITER | `autonomous_tick` (5 min) | Comprehensive (chain + registry + serving_freshness_fact) | MEDIUM (inherited) |
| 3 | `growth.yango_lima_program_eligibility_daily` | Program Eligibility | CERTIFIED — SINGLE_WRITER | `autonomous_tick` (5 min) | Covered (chain + registry + serving_freshness_fact) | LOW (DELETE without tx) |
| 4 | `growth.yango_lima_daily_opportunity_list` | Opportunity List | CERTIFIED — SINGLE_WRITER | `autonomous_tick` (5 min) | Covered (chain + registry + serving_freshness_fact) | LOW (DELETE without tx) |
| 5 | `growth.yego_lima_control_loop_state` | Control Loop State | CERTIFIED — SINGLE_WRITER | `autonomous_tick` (5 min) | Covered (chain + registry + serving_freshness_fact) | MEDIUM |

**Note on coverage evolution:** Previous audits (TRUTH_MAP_V2 G4, earlier PREFLIGHT v1) identified `control_loop_state` and `opportunity_list` as having zero/minimal freshness coverage. Live audit confirms both are now registered in all 3 freshness mechanisms (see Section 7).

---

## 3. Schema / Freshness Signal Audit

### 3.1 Table Creation (Migrations)

| Table | Migration | File |
|-------|-----------|------|
| `driver_history_weekly` | 163 | `backend/alembic/versions/163_yego_lima_growth_history_bootstrap.py:47` |
| `driver_state_snapshot` | 170 | `backend/alembic/versions/170_yego_lima_state_based_loyalty_architecture.py:28` |
| `program_eligibility_daily` | 170 | `backend/alembic/versions/170_yego_lima_state_based_loyalty_architecture.py:104` |
| `daily_opportunity_list` | 170 | `backend/alembic/versions/170_yego_lima_state_based_loyalty_architecture.py:139` |
| `control_loop_state` | 199 | `backend/alembic/versions/199_yego_lima_control_loop.py:23` |
| `freshness_registry` | 198 | `backend/alembic/versions/198_yego_lima_program_freshness.py:48` |
| `serving_freshness_fact` | Runtime | `backend/app/services/serving_freshness_audit_service.py:231-243` (`CREATE TABLE IF NOT EXISTS`) |

### 3.2 Primary Keys

| Table | Primary Key |
|-------|------------|
| `driver_history_weekly` | `(week_start_date, driver_profile_id)` |
| `driver_state_snapshot` | `(snapshot_date, driver_profile_id)` |
| `program_eligibility_daily` | `(eligibility_date, driver_profile_id, program_code)` |
| `daily_opportunity_list` | `(opportunity_date, driver_profile_id, opportunity_type)` |
| `control_loop_state` | `id` (uuid) |

### 3.3 Operational Date Columns

| Table | Date Column | Generated/Refreshed Column |
|-------|------------|---------------------------|
| `driver_history_weekly` | `week_start_date` (date) | `last_calculated_at` (timestamptz) |
| `driver_state_snapshot` | `snapshot_date` (date) | `last_calculated_at` (timestamptz) |
| `program_eligibility_daily` | `eligibility_date` (date) | `created_at` (timestamptz) |
| `daily_opportunity_list` | `opportunity_date` (date) | `generated_at` (timestamptz) |
| `control_loop_state` | N/A (state machine) | `created_at`, `updated_at`, `state_changed_at` (timestamptz) |

### 3.4 Current Data State (Live DB — 2026-06-13 ~20:30 UTC-5)

| Table | Row Count | Max Operational Date | Max generated/refreshed_at | Distinct Dates | Assessment |
|-------|----------|---------------------|--------------------------|----------------|------------|
| `driver_history_weekly` | 135,812 | `week_start_date` = **2026-06-01** | `last_calculated_at` = 2026-06-08 04:02 | 67 weeks | **STALE (12 days)** |
| `driver_state_snapshot` | 185,257 | `snapshot_date` = **2026-06-13** | `last_calculated_at` = 2026-06-13 01:23 | — | FRESH |
| `program_eligibility` | 282,688 | `eligibility_date` = **2026-06-13** | `created_at` = 2026-06-13 01:23 | — | FRESH |
| `daily_opportunity_list` | 282,688 | `opportunity_date` = **2026-06-13** | `generated_at` = 2026-06-13 01:23 | — | FRESH |
| `control_loop_state` | 770 | N/A (state machine) | `created_at` = 2026-06-13 01:26 | — | FRESH (0 stale entries) |

**Critical finding:** `driver_history_weekly` is 12 days behind (last data from June 1, today is June 13). Root cause: `driver_history_daily` is also stale (`MAX(date) = 2026-06-04`, 9 days behind). The FH-1 threshold bug prevents auto-refresh. See Section 5.

### 3.5 Status/Freshness Columns

| Table | Status Column | Freshness Column |
|-------|--------------|-----------------|
| `driver_history_weekly` | `historical_band` (HISTORICAL_50_PLUS/30_49/10_29/00_09/NO_HISTORY) | `last_calculated_at` |
| `driver_state_snapshot` | `lifecycle_state`, `performance_state`, `retention_state` | `last_calculated_at` |
| `program_eligibility_daily` | `eligible_flag` (boolean) | `created_at` |
| `daily_opportunity_list` | `management_status` (PENDING_ACTION/...) | `generated_at` |
| `control_loop_state` | `current_state` (READY/ASSIGNED/...), `is_stale` (boolean) | `created_at`, `updated_at` |

### 3.6 Scope / Lima Partition

All 5 tables are Lima-scoped. Filtering happens at:
- `driver_history_weekly`: via `park_id` filter in `bootstrap_history()` (reads `public.trips_2025`/`trips_2026` with `park_id = 08e20910d81d42658d4334d3f6d10ac0`)
- Other 4 tables: inherit Lima scope through the pipeline (no explicit park_id column in table, filtered at ingestion/ETL level)

---

## 4. Writer Inventory

### 4.1 `growth.yango_lima_driver_history_weekly`

| ID | Writer | Path | Operation | Caller | Scheduler | Classification | Risk | Evidence |
|----|--------|------|-----------|--------|-----------|---------------|------|----------|
| W1-HW | `_build_weekly_sql_bulk()` | `yego_lima_growth_history_service.py:218` | `INSERT ... ON CONFLICT DO UPDATE` (UPSERT) | `refresh_weekly_history()` via `autonomous_tick` (FH-1, conditional) OR `bootstrap_history()` (manual) | `autonomous_tick` (5 min, inside cascade block) | **CANONICAL** | HIGH | UPSERT from `driver_history_daily` with window functions |
| W2-HW | `upsert_history_weekly()` | `yego_lima_growth_history_repository.py:60` | INSERT UPSERT | **NEVER CALLED** (dead code) | NONE | **DEAD** | LOW | TRUTH_MAP_V2.md confirmed: "never called in any Python file" |

**Classification:** 1 CANONICAL + 1 DEAD. Canonical writer has automated trigger inside autonomous_tick (FH-1) but is CONDITIONALLY gated (see Section 5).

### 4.2 `growth.yango_lima_driver_state_snapshot`

| ID | Writer | Path | Operation | Caller | Scheduler | Classification | Risk | Evidence |
|----|--------|------|-----------|--------|-----------|---------------|------|----------|
| W1-SS | `_upsert_snapshot()` | `yego_lima_driver_state_service.py:335` | `INSERT ... ON CONFLICT (snapshot_date, driver_profile_id) DO UPDATE` | `autonomous_tick` → `build_driver_state_snapshot()` | `autonomous_tick` (5 min) | **CANONICAL** | LOW | 30 columns, 3-axis classification. Dual-source (360_daily + history_weekly). |

**Classification:** 1 CANONICAL. No parallel writers. Dual-source architecture provides partial resilience to `driver_history_weekly` staleness.

### 4.3 `growth.yango_lima_program_eligibility_daily`

| ID | Writer | Path | Operation | Caller | Scheduler | Classification | Risk | Evidence |
|----|--------|------|-----------|--------|-----------|---------------|------|----------|
| W1-PE | `build_program_eligibility()` | `yego_lima_program_eligibility_service.py:56+63+100+143` | `DELETE WHERE eligibility_date` + 3 INSERTs | `autonomous_tick` → cascade block | `autonomous_tick` (5 min) | **CANONICAL** | MEDIUM | DELETE before INSERT. No transaction wrapping. 3 hardcoded programs. |

**Classification:** 1 CANONICAL. DELETE risk documented in Section 8.

### 4.4 `growth.yango_lima_daily_opportunity_list`

| ID | Writer | Path | Operation | Caller | Scheduler | Classification | Risk | Evidence |
|----|--------|------|-----------|--------|-----------|---------------|------|----------|
| W1-OL | `build_daily_opportunity_lists()` | `yego_lima_daily_opportunity_service.py:66+73+127+201+224` | `DELETE WHERE opportunity_date` + `INSERT ON CONFLICT DO NOTHING` + UPDATEs | `autonomous_tick` → cascade block | `autonomous_tick` (5 min) | **CANONICAL** | LOW | Same DELETE pattern as eligibility. |

**Classification:** 1 CANONICAL.

### 4.5 `growth.yego_lima_control_loop_state`

| ID | Writer | Path | Operation | Caller | Scheduler | Classification | Risk | Evidence |
|----|--------|------|-----------|--------|-----------|---------------|------|----------|
| W1-CL | `sync_assignment_queue_to_control_loop()` | `yego_lima_control_loop_sync_service.py:26` | `INSERT ... SELECT ... WHERE NOT EXISTS` (insert-only, never overwrites) | `autonomous_tick` → always (post-cascade + post-refresh) | `autonomous_tick` (5 min) | **CANONICAL** | LOW | Insert-only design. `NOT EXISTS` guard. SQL at line 26-41. |
| W2-CL | `ctrl_bridge_sync.py` | `backend/scripts/ctrl_bridge_sync.py:28` | Manual sync script | CLI-only | NONE | **LEGACY** | LOW | Not in scheduler. File not found in current repo (listed in TRUTH_MAP_V2 as manual). |

**Classification:** 1 CANONICAL + 1 LEGACY (possibly removed).

---

## 5. Scheduler / Refresh Mechanism Audit

### 5.1 Scheduler Registration

`lima_growth_autonomous_tick` is registered in `main.py:363-374` as an APScheduler interval job:
- Frequency: every 5 minutes
- `max_instances=1`, `coalesce=True`, `misfire_grace_time=600`
- Protected by advisory lock (lock ID from `yego_lima_scheduler_service.py:46`)
- Overlap protection: `_try_acquire_tick_lock()` (line 571)

### 5.2 Per-Table Refresh Summary

| Table | Scheduler | Trigger Mechanism | Frequency | Lock | Freshness Signal | Gap |
|-------|-----------|-------------------|-----------|------|-----------------|-----|
| `driver_history_weekly` | `autonomous_tick` (FH-1) | `refresh_weekly_history()` — **conditional** (inside `if cascade_required:` block only) | Every 5 min (when cascade active) | Only scheduler-level advisory lock | Chain + registry + serving_freshness_fact | **CRITICAL: Threshold bug makes NOOP even when stale. Also: never refreshed outside cascade path.** |
| `driver_state_snapshot` | `autonomous_tick` | `build_driver_state_snapshot(target_date)` — inside cascade block | Every 5 min (when cascade active) | Scheduler-level advisory lock | Chain + registry + serving_freshness_fact | Depends on stale `driver_history_weekly` for historical metrics |
| `program_eligibility_daily` | `autonomous_tick` | `build_program_eligibility(target_date)` — inside cascade block | Every 5 min (when cascade active) | Scheduler-level advisory lock | Chain + registry + serving_freshness_fact | DELETE without transaction |
| `daily_opportunity_list` | `autonomous_tick` | `build_daily_opportunity_lists(target_date)` — inside cascade block | Every 5 min (when cascade active) | Scheduler-level advisory lock | Chain + registry + serving_freshness_fact | Minimal gap |
| `control_loop_state` | `autonomous_tick` | `sync_assignment_queue_to_control_loop()` — always (post-cascade + post-refresh at lines 797-804) | Every 5 min | Scheduler-level advisory lock | Chain + registry + serving_freshness_fact | Previously uncovered; now registered |

### 5.3 autonomous_tick Execution Flow (Full Trace)

From `yego_lima_scheduler_service.py`:

```
1. acquire_tick_lock (advisory lock, prevents overlap)
2. check scheduler enabled
3. ingest_recent_orders() — raw Yango API → raw_yango.orders_raw
4. detect_latest_closed_data_date() → op_date
5. DETECT cascade_required:
   IF raw_max_date > snapshot_max_date → cascade_required = True
6. IF cascade_required:
     6a. → refresh_weekly_history() [FH-1] — conditional; may NOOP due to threshold
     6b. → build_driver_state_snapshot(target_date)
     6c. → build_program_eligibility(target_date)
     6d. → build_daily_opportunity_lists(target_date)
     6e. → build_prioritized_opportunities(target_date)
     6f. → run_daily_refresh(target_date)
     6g. → sync_assignment_queue_to_control_loop(target_date)
7. IF NOT cascade_required AND new day:
     7a. → run_daily_refresh(op_date) [does NOT refresh weekly history]
     7b. → sync_assignment_queue_to_control_loop(op_date)
8. Always: generate_all_serving_facts, refresh_freshness_registry, governance check
```

**FH-1 Threshold Bug (lines 437-472 in `yego_lima_growth_history_service.py`):**
```python
if max_week_d >= latest_complete_monday - timedelta(days=7):
    return {"refreshed": False, "status": "NOOP", ...}  # SKIPS refresh
```
On 2026-06-13 (Saturday):
- `latest_complete_monday` = 2026-06-08
- `latest_complete_monday - 7 days` = 2026-06-01
- `max_week_d` = 2026-06-01
- Condition: `2026-06-01 >= 2026-06-01` → **True → NOOP**

**The threshold incorrectly considers data from June 1 as "up to date" when today is June 13.** The current week (June 8-14) is not reflected. The threshold should be `latest_complete_monday` (June 8) not `latest_complete_monday - 7 days` (June 1).

### 5.4 Root Cause of staleness

`driver_history_daily` `MAX(date) = 2026-06-04` (9 days stale). This feeds into `driver_history_weekly`. The daily data staleness is upstream of weekly staleness — likely caused by raw orders ingestion gap (`raw_orders` shows `MAX(ended_at) = 2026-06-09` with status "STALE").

---

## 6. Control Loop Stale Risk

### 6.1 Consumption Chain

```
raw_yango.orders_raw → driver_history_daily → driver_history_weekly
                                                      ↓
                                    driver_state_snapshot (dual-source:
                                    history_weekly + driver_360_daily)
                                                      ↓
                                    program_eligibility_daily
                                                      ↓
                                    daily_opportunity_list
                                                      ↓
                                    assignment_queue → control_loop_state → UI/agents
```

### 6.2 Dual-Source Resilience

`build_driver_state_snapshot()` reads from:
- `driver_history_weekly` → historical metrics (avg_orders_4w/8w/12w, best_week_12w, historical_band)
- `driver_360_daily` → current daily/weekly metrics (completed_orders_day/week, supply_hours, etc.)

When `driver_history_weekly` is stale:
- Historical classification (historical_band, best_week) is **outdated**
- Daily/weekly operational metrics from `driver_360_daily` are **accurate** (if 360 is fresh)
- State classification (lifecycle/performance/retention) may be **degraded** for drivers whose historical behavior changed

### 6.3 Risk Assessment

| Consumer | Tables Used | Freshness Check? | Failure Behavior | Stale Risk | Required Guardrail |
|----------|------------|-----------------|-----------------|------------|-------------------|
| `driver_state_snapshot` | `driver_history_weekly` + `driver_360_daily` | NO explicit check | Uses stale history → degraded historical classification | **MEDIUM** (360 compensates partially) | Fail-closed if history > 14 days stale |
| `program_eligibility` | `driver_state_snapshot` | NO | Stale state → potentially wrong eligibility | LOW | Log staleness detection |
| `daily_opportunity_list` | `program_eligibility` + `driver_state_snapshot` | NO | Stale opportunities possible | LOW | Log staleness detection |
| `control_loop_sync` | `assignment_queue` → `control_loop_state` | NO | Queue entries may exist for drivers with stale classification | LOW | Verify source freshness |
| `UI / endpoints` | All 5 tables | NO | UI shows data from June 13 but with degraded historical context | MEDIUM | Freshness banner for weekly history |

### 6.4 Key Findings

1. **`driver_history_daily` stale (June 4) → `driver_history_weekly` stale (June 1).** Root cause is upstream raw orders ingestion.
2. **FH-1 threshold bug prevents auto-recovery** even when cascade is active.
3. **`driver_360_daily` provides partial resilience** — state snapshots can still be generated with fresh daily metrics, but historical band/best_week is outdated.
4. **No fail-closed mechanism.** Pipeline continues silently. `freshness_registry` falsely reports "FRESH" for `driver_history_weekly`.
5. **`control_loop_state` currently has 0 stale entries** (`COUNT(*) WHERE is_stale = 0`). State transitions beyond READY are handled externally (not by this sync mechanism — see TRUTH_MAP_V2 note).

---

## 7. Serving Registry / Freshness Governance

### 7.1 Freshness Infrastructure (Live DB Verification)

Growth Machine uses its own freshness governance layer (separate from OV2 `ops.serving_registry`):

| Table | `freshness_registry` component | `serving_freshness_fact` asset | `freshness_chain` layer |
|-------|------------------------------|------------------------------|------------------------|
| `driver_history_weekly` | `driver_history_weekly` — FRESH (FALSE POSITIVE!) | `driver_history_weekly` — HEALTHY (within 336h SLA) | `history_weekly` — layer 3 |
| `driver_state_snapshot` | `driver_state` — WARNING (1524 min latency) | `driver_state_snapshot` — DEGRADED (14.22h, SLA 5h) | `snapshot` — layer 4 |
| `program_eligibility_daily` | `eligibility` — WARNING (1524 min) | `program_assignment` — DEGRADED (14.22h, SLA 5h) | `eligibility` — layer 5 |
| `daily_opportunity_list` | `opportunity` — FRESH (963 min) | `daily_opportunity_list` — HEALTHY (14.22h, SLA 24h) | `opportunity` — layer 6 |
| `control_loop_state` | `control_loop` — FRESH (277 min) | `control_loop_state` — HEALTHY (2.78h, SLA 8h) | `control_loop` — layer 10 |

**Source infrastructure:**
- `growth.yego_lima_freshness_registry` (migration 198) — 10 components
- `growth.yego_lima_serving_freshness_fact` (runtime creation, `serving_freshness_audit_service.py:231`) — 16 assets
- `yego_lima_freshness_chain_service.py` — 10-layer waterfall check
- `yego_lima_refresh_governance_service.py` — 10 components, auto-updates registry
- `serving_freshness_audit_service.py` — 16 SERVING_ASSETS, auto-updates serving_freshness_fact

### 7.2 Freshness Computation Bug

`compute_freshness()` labels `driver_history_weekly` as "FRESH" because:
- `MAX(week_start_date)` = 2026-06-01
- Freshness check only compares date vs today (is it today/yesterday?)
- June 1 passes because the date format comparison is lenient

**This is a FALSE POSITIVE.** Data from June 1 (12 days ago) should be classified as STALE or DEGRADED, not FRESH.

### 7.3 Coverage Evolution

| # | Gap (TRUTH_MAP_V2) | Status (2026-06-13) |
|---|-------------------|---------------------|
| G4 | `control_loop_state` zero freshness | **PARTIALLY CLOSED.** Now in freshness_registry (component `control_loop`), serving_freshness_fact (asset `control_loop_state`), and freshness_chain (layer `control_loop`). |
| G2 | `driver_history_weekly` no scheduler | **PARTIALLY ADDRESSED.** FH-1 adds `refresh_weekly_history()` to autonomous_tick but with threshold bug and only inside cascade block. |
| — | `opportunity_list` minimal freshness | **CLOSED.** Now in serving_freshness_fact as `daily_opportunity_list` asset. |
| — | `control_loop_state` missing from freshness_chain | **CLOSED.** Now in chain as layer `control_loop` (line 44). |

---

## 8. Dangerous DELETE / Backfill Risk

### 8.1 DELETE Operations

| Path | Table | Operation | Scope | Guard | Risk | Recommendation |
|------|-------|-----------|-------|-------|------|---------------|
| `yego_lima_program_eligibility_service.py:56` | `program_eligibility_daily` | `DELETE WHERE eligibility_date = %s` | Bounded (single date) | NO transaction wrapping | **MEDIUM.** If INSERT fails after DELETE, data lost for that date until next tick. | Wrap DELETE + INSERTs in explicit transaction |
| `yego_lima_daily_opportunity_service.py:66` | `daily_opportunity_list` | `DELETE WHERE opportunity_date = %s` | Bounded (single date) | NO transaction wrapping | **MEDIUM.** Same pattern. | Wrap in transaction |

**No TRUNCATE, unbounded DELETE, DROP TABLE, or CREATE OR REPLACE found on any Growth Machine production table.** All DROP TABLE operations are exclusively in `downgrade()` migration methods (never executed in production).

### 8.2 Backfill / Bootstrap Risks

| Risk | Table | Severity | Current Behavior |
|------|-------|----------|-----------------|
| `bootstrap_history()` manual execution | `driver_history_weekly` + `driver_history_daily` | **HIGH** | FH-1 automates `refresh_weekly_history()` but only inside cascade block + threshold bug prevents refresh when stale |
| `rebuild_history_until_cutover()` manual script | `driver_history_daily` + `driver_history_weekly` | MEDIUM | With `dry_run=True` (default), safe to call. With `dry_run=False`, performs full backfill. |
| `ctrl_bridge_sync.py` manual sync | `control_loop_state` | LOW | Insert-only, supplementary to automated tick. File may not exist in current repo. |

### 8.3 Driver History Daily Gap

Live data shows `driver_history_daily` is stale:
- `MAX(date) = 2026-06-04` (9 days behind)
- `MIN(date) = 2025-02-21`
- This gap propagates to `driver_history_weekly`

Root cause chain: `raw_yango.orders_raw` → `yango_raw_tick_ingestion_service.ingest_recent_orders()` → ??? The API ingestion may be failing or not importing dates after June 4/9. `raw_orders` shows `MAX(ended_at) = 2026-06-09` with status "STALE" (6036 min latency).

---

## 9. Gaps Summary

| # | Gap | Table(s) | Severity | Evidence | Action |
|---|-----|---------|----------|----------|--------|
| **G1** | `driver_history_daily` stale (9 days) → `driver_history_weekly` stale (12 days) | `driver_history_daily`, `driver_history_weekly` | **CRITICAL (P0)** | Live DB: daily MAX = 2026-06-04, weekly MAX = 2026-06-01. Raw orders also stale. | Investigate root cause: raw orders ingestion gap + FH-1 threshold bug |
| **G2** | FH-1 threshold bug: `refresh_weekly_history()` NOOPs when stale | `driver_history_weekly` | **CRITICAL (P0)** | `yego_lima_growth_history_service.py:468`: `max_week_d >= latest_complete_monday - 7 days` allows 2-week-old data to be considered "up to date" | Fix threshold to `latest_complete_monday` |
| **G3** | `freshness_registry` false positive for `driver_history_weekly` | `driver_history_weekly` | **HIGH (P1)** | Registry status = "FRESH" but data is 12 days old (latency 18243 minutes) | Fix `compute_freshness()` or registry update logic to detect multi-day staleness |
| **G4** | DELETE without transaction wrapping | `program_eligibility`, `opportunity_list` | **MEDIUM (P1)** | Code audit: DELETE then INSERT, no explicit BEGIN/COMMIT | Wrap in transaction block |
| **G5** | Control Loop no fail-closed guardrail | All pipeline | **MEDIUM (P2)** | Pipeline continues silently with stale `driver_history_weekly`. State snapshot dual-source provides partial resilience. | Add staleness check at start of cascade block |
| **G6** | No dedicated advisory lock for `refresh_weekly_history()` | `driver_history_weekly` | **LOW (P2)** | Only scheduler-level tick lock. No lock specific to weekly history refresh. | Low priority — UPSERT is idempotent, tick lock prevents parallel runs |

---

## 10. Proposed Freshness Contracts

| Table | Freshness Column | Max Lag | Owner Service | Canonical Writer | Blocking? | Remediation |
|-------|-----------------|---------|---------------|-----------------|-----------|-------------|
| `driver_history_weekly` | `week_start_date` | 7 days | `yego_lima_growth_history_service.py` | `_build_weekly_sql_bulk()` via `refresh_weekly_history()` | **YES** | Fix FH-1 threshold. Investigate raw orders daily ingestion gap. |
| `driver_state_snapshot` | `snapshot_date` | 1 day | `yego_lima_driver_state_service.py` | `_upsert_snapshot()` | **YES** | Next tick recovers. Alert if > 1 day. |
| `program_eligibility_daily` | `eligibility_date` | 1 day | `yego_lima_program_eligibility_service.py` | `build_program_eligibility()` | YES | Wrap DELETE+INSERT in transaction. |
| `daily_opportunity_list` | `opportunity_date` | 1 day | `yego_lima_daily_opportunity_service.py` | `build_daily_opportunity_lists()` | YES | Wrap DELETE+INSERT in transaction. |
| `control_loop_state` | `created_at` | 1 day (inserts) | `yego_lima_control_loop_sync_service.py` | `sync_assignment_queue_to_control_loop()` | NO (insert-only) | Monitor `MAX(created_at)` + stale entries. |

---

## 11. GM-F1 Implementation Plan

### F1A — Driver History Bootstrap Hardening (P0)

**Objective:** Fix FH-1 threshold + investigate daily history staleness root cause.

1. Fix threshold in `refresh_weekly_history()`: change `latest_complete_monday - timedelta(days=7)` → `latest_complete_monday`.
2. Move `refresh_weekly_history()` OUTSIDE `if cascade_required:` block so it runs every tick independently.
3. Investigate why `driver_history_daily` is stale: check `raw_yango.orders_raw` ingestion pipeline, `yango_raw_tick_ingestion_service.py`.
4. Verify `driver_360_daily` freshness (the dual-source compensator).
5. Add advisory lock for weekly history refresh if needed.

### F1B — Freshness Computation Fix (P1)

**Objective:** Stop freshness_registry from falsely reporting STALE data as FRESH.

1. Fix `compute_freshness()` to detect multi-day staleness (not just "is it today?").
2. Add staleness classification: 0-7 days = FRESH, 7-14 = WARNING, 14+ = CRITICAL for weekly tables.
3. Verify `freshness_registry` and `serving_freshness_fact` reflect accurate status.

### F1C — DELETE Transaction Wrapping (P1)

**Objective:** Prevent data loss on INSERT failure after DELETE.

1. Wrap `build_program_eligibility()` DELETE+INSERTs in explicit transaction block.
2. Same for `build_daily_opportunity_lists()`.
3. Add rollback logging.

### F1D — Control Loop Fail-Closed Guardrail (P2)

**Objective:** Prevent cascade from operating on critically stale weekly history.

1. Add freshness check at start of cascade: `SELECT MAX(week_start_date) FROM driver_history_weekly`.
2. If > 14 days stale: log CRITICAL, skip eligibility/opportunity generation, set degraded status.
3. If 7-14 days stale: log WARNING, continue but report degraded.
4. Do NOT block state snapshot generation (dual-source resilience).

### F1E — Validation / Smoke Pack

1. Run `autonomous_tick` with FH-1 fix, verify weekly history refreshes.
2. Run `autonomous_tick` with stale guard, verify fail-closed behavior.
3. Verify freshness_registry and serving_freshness_fact accuracy.
4. Read-only SELECTs on all 5 tables: confirm MAX dates advancing.
5. Confirm no backward compatibility breaks.

---

## 12. Rollback Plan

| Phase | Rollback |
|-------|----------|
| F1A | Revert threshold change. Move `refresh_weekly_history()` back inside cascade block. |
| F1B | Revert `compute_freshness()` changes. Previous "FRESH" false-positive behavior restored. |
| F1C | Revert transaction wrapping. DELETE+INSERT revert to original no-transaction pattern. |
| F1D | Remove staleness guard. Revert to silent continuation. |
| F1E | Revert docs only. No DB changes. |

No schema migrations required. All changes are code-level guardrails or governance table updates.

---

## 13. Final Recommendation

**CONDITIONAL GO FOR GM-F1 FRESHNESS HARDENING.**

The Growth Machine has an automated scheduler (`lima_growth_autonomous_tick`) that covers all 5 tables. FH-1 partially addressed the `driver_history_weekly` bootstrap gap but has a threshold bug that prevents refresh when data is actually stale. The `driver_history_daily` table itself is stale (June 4) due to what appears to be a raw orders ingestion gap upstream.

**Immediate blocker:** Fix FH-1 threshold + investigate daily history staleness.

**Secondary:** Fix freshness false-positive in registry. Wrap DELETEs in transactions.

**Do NOT open:** Diagnostic Engine, Forecast, Suggestion, Decision, Action, AI Copilot, Learning Engine.

Growth Machine freshness hardening is parallel to OMNI-P0 Recovery and does not conflict.

---

*Generated from live DB SELECTs (2026-06-13, yego_integral), full code trace across 200+ files, git grep, and migration audit. No DB writes, refreshes, backfills, or UI changes were executed.*

---

## 14. GM-F1A Driver History Weekly Governance Result

**Date:** 2026-06-13
**Status:** IMPLEMENTED — Freshness gate + fail-closed guard

### Implementation Summary

| Area | Before | After | Result |
|------|--------|-------|--------|
| **FH-1 threshold** | `latest_complete_monday - 7 days` (2-week tolerance) | `latest_complete_monday` (current ISO week) | Fixed. Stale detection is now accurate. |
| **refresh trigger** | Only inside `if cascade_required:` block | Always runs at tick start (before cascade check) | Weekly history evaluated every 5 min. |
| **Advisory lock** | None (only tick-level lock) | `pg_try_advisory_lock(9002)` on weekly refresh | Concurrent rebuilds prevented. |
| **Freshness gate** | None | `check_driver_history_weekly_freshness()` → returns `{status, blocking, lag_days, ...}` | Contract defined. |
| **Tick behavior (fresh)** | Cascade/refresh runs normally | Same. Weekly history refresh runs + freshness check passes → cascade proceeds. | No regression. |
| **Tick behavior (stale)** | Cascade proceeded with stale data | Tick blocked: status = `"blocked_by_stale_driver_history_weekly"`. No driver_state_snapshot, eligibility, opportunity, or control_loop_state built. | Fail-closed. |
| **Tick behavior (error)** | N/A | Fail-closed. Freshness query error → tick blocked. | Safe. |
| **Dead writer** | `upsert_history_weekly()` in repository (never called) | Not activated. Still dead. | No legacy revival. |
| **Tests** | None | 9 tests (4 freshness check, 3 refresh, 2 lock) | 9/9 PASS. |

### Files Modified

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_growth_history_service.py` | Added `check_driver_history_weekly_freshness()`, `_acquire_weekly_history_lock()`, `_release_weekly_history_lock()`; fixed FH-1 threshold; added advisory lock to `refresh_weekly_history()` |
| `backend/app/services/yego_lima_scheduler_service.py` | Moved `refresh_weekly_history()` before cascade block (always runs now); integrated freshness gate; blocked cascade/run_refresh/control_loop when stale |
| `backend/tests/test_growth_machine_freshness_gate.py` | 9 non-destructive tests with mocks |

### Remaining Gaps for GM-F1B

1. `freshness_registry` false positive for `driver_history_weekly` (labels stale data as "FRESH")
2. DELETE transaction wrapping in `program_eligibility` and `opportunity_list`
3. Control loop fail-closed guardrail for non-cascade paths (partially addressed — non-cascade `run_daily_refresh` also blocked)
4. Serving registry/freshness contract formalization
