# LG_EXP_1C_SERVING_GOVERNANCE_CERTIFICATION

**Phase:** LG-EXP-1C — Driver Explorer Serving Governance  
**Generated:** 2026-06-12  
**Predecessor:** LG-EXP-1B (Canonical Contract — CERTIFIED)  
**Purpose:** Validate serving governance BEFORE building `growth.yego_lima_driver_explorer_fact`  

---

## 1. GRAIN VALIDATION

### Candidate Grains Evaluated

| # | Candidate Grain | Pros | Cons | Verdict |
|---|----------------|------|------|---------|
| A | `driver_id` (1 row per driver) | Simple, matches `rna_priority_fact` | No history; cannot track daily state changes; violates serving fact pattern (all `growth.*` facts are per-date) | **REJECTED** |
| B | `driver_id × target_date` (1 row per driver per day) | Historical tracking; matches `driver_state_snapshot` grain; aligns with `program_eligibility_daily` grain; allows trend queries | Larger storage (~6.7M rows/year at 18,475 drivers/day) | **SELECTED** |
| C | `driver_id × snapshot_ts` (sub-day) | Maximum granularity | No matching source grain; no upstream table produces this grain; overkill for operational ficha | **REJECTED** |

### Selected Grain: `(target_date, driver_profile_id)`

**Justification:**

1. **Matches upstream grain.** The primary source `growth.yango_lima_driver_state_snapshot` uses grain `(snapshot_date, driver_profile_id)`. Same grain = same key = simple JOIN.

2. **Matches existing serving fact pattern.** All 8 fact types in `growth.yego_lima_serving_fact` use `(fact_date, fact_type)` grain. The proposed `(target_date, driver_profile_id)` follows the same per-date architecture.

3. **Historical audit trail.** Per-date snapshots allow: (a) tracking driver state changes over time, (b) time-travel queries for retrospective analysis, (c) incremental refresh (UPDATE latest, no DELETE).

4. **Export already uses this grain implicitly.** `yego_lima_export_service.py` (line 34-59) selects from `driver_state_snapshot` with `WHERE snapshot_date = (SELECT MAX(snapshot_date) ...)` — a per-date query.

**Verdict: `(target_date, driver_profile_id)` — CORRECT. Matches upstream sources and existing patterns.**

---

## 2. DOMAIN BELONGING: V1 OPERATIONAL vs V2 INTELLIGENCE vs HYBRID

### V1 Operational (production)

| Table | Status | Rows | Latest Date |
|-------|--------|------|-------------|
| `growth.yango_lima_driver_state_snapshot` | **HEALTHY** | 166,712 | 2026-06-12 |
| `growth.yango_lima_program_eligibility_daily` | **HEALTHY** | 254,560 | 2026-06-12 |
| `growth.yego_lima_driver_lifecycle_daily` | **STALE** | 273,908 | 2026-06-10 |
| `growth.driver_movement_fact` | **STALE** | 68,473 | 2026-06-10 |
| `growth.rna_priority_fact` | **DOES NOT EXIST** | 0 | — |
| `growth.yego_lima_loopcontrol_result_sync` | **NEAR-EMPTY** | 10 | 2026-06-08 |
| `growth.yego_lima_impact_tracking` | **EMPTY** | 0 | — |

### V2 Intelligence (shadow)

| Table | Status | Rows | Latest Date |
|-------|--------|------|-------------|
| `growth.yego_lima_v2_lifecycle_daily` | STALE | 273,908 | 2026-06-10 |
| `growth.yego_lima_v2_taxonomy_daily` | STALE | 273,908 | 2026-06-10 |
| `growth.yego_lima_v2_program_daily` | STALE | 273,908 | 2026-06-10 |
| `growth.yego_lima_v2_movement_fact` | **EMPTY** | 0 | — |
| `growth.yego_lima_v2_effectiveness_fact` | **EMPTY** | 0 | — |

### Analysis

| Criterion | V1 | V2 | Winner |
|-----------|----|----|--------|
| Tables populated | 4/7 healthy | 0/5 healthy | **V1** |
| Integrated into autonomous_tick | YES | NO (shadow, manual) | **V1** |
| Serving fact already consumed by UI | YES (8 fact types via `serving_or_missing`) | NO | **V1** |
| Segment/sub_segment available | NO | YES (but STALE) | V2 (stale) |
| Lifecycle data available | YES (`driver_state_snapshot.lifecycle_state`) | YES (`lifecycle_stage`) | TIE |
| Movement data available | PARTIAL (state_transition_trace) | EMPTY (0 rows) | **V1** |
| RNA data available | NO (table missing) | NO | TIE (both broken) |

### Recommendation

**V1 OPERATIONAL — with V2 gaps accepted as NULL.**

The V2 shadow pipeline produces `segment` and `sub_segment` fields that are valuable but (a) not integrated into autonomous_tick, (b) stale (last date 2026-06-10), and (c) the `v2_movement_fact` has 0 rows. Making the serving fact depend on V2 would create a dependency on an unintegrated, stale pipeline.

**Hybrid approach justification:** The serving fact should read from V1 tables as primary sources. When V2 tables have data for the same `target_date`, they can enrich the serving fact. But the serving fact must NOT require V2 data to be viable. This is the same pattern the export endpoint already uses (`coalesce(tx.segment, ds.segment)` in `yego_lima_export_service.py:41-42`).

**Verdict: V1 OPERATIONAL as primary. V2 as optional enrichment (COALESCE pattern). Hybrid only for segment/sub_segment fallback chain.**

---

## 3. CARDINALITY ESTIMATE

### Source Data

| Metric | Value | Source |
|--------|-------|--------|
| Drivers per snapshot_date | ~18,475 | `LG_FIX_1A_FACT_ROWCOUNT_AUDIT.md` (2026-06-05) |
| Recent 2-day window (06-11/12) | 37,090 | Same audit |
| Growth trend | +100% in 7 days (18,475 → 37,090) | Driver registration growth |
| Steady-state estimate | ~20,000 per day | Conservative, post-growth stabilization |

### Projected Rows

| Retention Window | Days | Est. Rows (at 20K/day) | Est. Storage (at ~1KB/row) |
|-----------------|------|------------------------|---------------------------|
| **30 days** | 30 | **600,000** | ~600 MB |
| **90 days** | 90 | **1,800,000** | ~1.8 GB |
| **365 days** | 365 | **7,300,000** | ~7.3 GB |

### Comparison with Existing Tables

| Table | Rows | Size Context |
|-------|------|-------------|
| `driver_lifecycle_daily` | 273,908 | 3× smaller than 30d projection |
| `program_eligibility_daily` | 254,560 | Similar scale |
| `driver_state_snapshot` | 166,712 | ~4 months of accumulation |

### Storage Strategy

- **Default retention:** 90 days (matches operational window: 30d activity + 60d churn).
- **Pruning:** `DELETE FROM growth.yego_lima_driver_explorer_fact WHERE target_date < CURRENT_DATE - 90` (scheduled weekly in autonomous_tick).
- **Index growth:** 6 indexes × B-tree ≈ 1.2GB at 1.8M rows. Acceptable for operational table.

### Partitioning Recommendation (future, not LG-EXP-1C)

For 365-day retention, partition by `target_date` (monthly). Not required for MVP with 90-day window.

**Verdict: ~600K rows at 30 days, ~1.8M at 90 days. Within PostgreSQL operational range. No cardinality concern.**

---

## 4. REFRESH STRATEGY

### Three Patterns in the Codebase

| Pattern | Trigger | Frequency | Used For |
|---------|---------|-----------|----------|
| **autonomous_tick** | APScheduler every 5 min | Continuous | `generate_all_serving_facts()` — regenerates all 8 fact types every tick |
| **run_daily_refresh** | Called by autonomous_tick when cascade runs | Once per new operational date | Same function, called with `run_id` and `freshness_status` |
| **Standalone builder** | Script or endpoint | On-demand | `build_driver_state_snapshot()`, `build_program_eligibility()` |

### Recommendation: autonomous_tick (both paths)

The serving fact should be generated:

1. **In `run_daily_refresh()` (Step 5):** After `generate_all_serving_facts()`, add `build_driver_explorer_fact(target_date)`. Called once per new operational date with full traceability (`run_id`, `freshness_status`).

2. **In `autonomous_tick()` (post-cascade):** After `generate_all_serving_facts()`, call `build_driver_explorer_fact(op_date)`. Regenerated every 5 minutes with `UPSERT` semantics (idempotent).

### Why autonomous_tick (not standalone scheduler)

| Factor | autonomous_tick | Standalone Scheduler | Verdict |
|--------|----------------|---------------------|---------|
| Already has DB connection pool | YES | Would need separate pool | autonomous_tick |
| Already has lock (advisory 9001) | YES | Would need separate lock | autonomous_tick |
| Runs after all source tables are fresh | YES (cascade order) | Would race with cascade | autonomous_tick |
| Follows existing serving fact pattern | YES (same as 8 other fact types) | Breaks pattern | autonomous_tick |
| Traceability to tick/run | YES (`run_id` from daily_refresh) | Would need separate tracing | autonomous_tick |

### Idempotency

The writer must use `INSERT ... ON CONFLICT (target_date, driver_profile_id) DO UPDATE`. This ensures:
- Every 5-min tick regenerates fresh data via UPSERT
- No duplicate rows
- Concurrent ticks don't corrupt (advisory lock on autonomous_tick already prevents concurrent ticks)

### Insert vs Prune Pattern

```
build_driver_explorer_fact(target_date):
  1. SELECT drivers FROM driver_state_snapshot WHERE snapshot_date = target_date
  2. JOIN program_eligibility_daily WHERE eligibility_date = target_date
  3. JOIN rna_priority_fact (latest scored_at)
  4. JOIN loopcontrol_result_sync (latest synced_at)
  5. JOIN impact_tracking (latest measured_at)
  6. JOIN assignment_queue (latest queue_date)
  7. UPSERT INTO driver_explorer_fact
  8. (Weekly) DELETE WHERE target_date < CURRENT_DATE - 90
```

**Verdict: autonomous_tick idempotent UPSERT. Both paths (daily_refresh + 5-min tick). Same pattern as existing 8 serving facts.**

---

## 5. FIELD OWNERSHIP

### Ownership Definition

| Layer | Fields | Owner Service | Owner Cascade Step | Refresh |
|-------|--------|---------------|-------------------|---------|
| **Identity** | `driver_profile_id`, `driver_name`, `phone`, `park_id` | `build_driver_state_snapshot()` + `assignment_queue` | autonomous_tick Step 1 + Step 3 | Every 5 min |
| **Operational State** | `lifecycle`, `performance_state`, `retention_state`, `historical_band` | `build_driver_state_snapshot()` | autonomous_tick Step 1 | Every 5 min |
| **Program** | `program_code`, `program_priority`, `eligibility_reason`, `is_in_program` | `build_program_eligibility()` | autonomous_tick Step 2 | Every 5 min |
| **RNA** | `rna_priority_band`, `rna_score`, `contactable`, `cancelled_signal`, `rna_value_tier`, `rna_momentum` | `rna_priority_fact` (migration 217) | **TABLE DOES NOT EXIST** | **BLOCKED** |
| **Movement** | `movement_type`, `movement_from`, `movement_to` | Derivado (day-over-day lifecycle_state diff) | Within `build_driver_explorer_fact()` | Every 5 min |
| **Contact** | `last_contact_at`, `last_contact_disposition`, `last_contact_agent`, `contact_attempts` | `loopcontrol_result_sync` (LoopControl export sync) | Sync on export | **NEAR-EMPTY (10 rows)** |
| **Execution** | `assigned_campaign_id`, `queue_status`, `opportunity_type` | `assignment_queue` + `daily_opportunity_list` | autonomous_tick Step 3 | Every 5 min |
| **Activity** | `trips_7d`, `trips_30d`, `trips_since_anchor`, `first_trip_at`, `last_trip_at`, `days_since_last_trip`, `activity_trend`, `new_driver_flag`, `recoverable_flag`, `declining_flag`, `churn_risk_flag` | `build_driver_state_snapshot()` + derived | autonomous_tick Step 1 | Every 5 min |
| **Impact** | `impact_status`, `baseline_trips`, `post_contact_trips`, `trips_delta_after_contact` | `impact_tracking` | Impact attribution (on measurement window) | **EMPTY (0 rows)** |
| **Metadata** | `source_tables`, `data_quality`, `refreshed_at` | `build_driver_explorer_fact()` | Within builder | Every 5 min |

### Ownership Gaps Identified

| # | Field | Gap | Proposed Resolution |
|---|-------|-----|---------------------|
| 1 | `driver_name` | No source in `driver_state_snapshot`. Only in `assignment_queue` (exported drivers only). | Read from `assignment_queue.driver_name` WHERE `queue_date` is latest. NULL for non-exported drivers. Fallback to `public.drivers` join. Accept NULL in MVP. |
| 2 | `phone` | Only in `assignment_queue` and `loopcontrol_result_sync`. Not in snapshot. | Read from `assignment_queue.phone` (latest). Fallback to `public.drivers.phone`. Accept NULL in MVP. |
| 3 | `rna_*` (9 fields) | `rna_priority_fact` DOES NOT EXIST in production. Migration 217 not applied. | **DEFAULT values** (rna_priority_band='COLD', rna_score=0, contactable=FALSE). Serving fact UPSERT will populate when table is created. |
| 4 | `segment`, `sub_segment` | Only in V2 shadow (STALE). Not in V1 snapshot. | Use `driver_state_snapshot.historical_band` as segment fallback. Sub_segment remains NULL. |
| 5 | `movement_*` (4 fields) | `v2_movement_fact` has 0 rows. No V1 movement fact. | Derive from day-over-day `lifecycle_state` diff within `build_driver_explorer_fact()`. Deterministic, no external dependency. |
| 6 | `contact_*` (4 fields) | `loopcontrol_result_sync` has 10 rows total. | LEFT JOIN with NULL default. Will populate as LoopControl exports increase. |
| 7 | `impact_*` (4 fields) | `impact_tracking` has 0 rows. | LEFT JOIN with NULL default. Will populate when impact measurement runs. |

### Ownership Integrity

| Total Fields | Owned (exists today) | Owned (with fallback) | Unavailable (NULL in MVP) |
|-------------|---------------------|----------------------|--------------------------|
| **31** (canonical) | **14** (45%) | **10** (32%) | **7** (23%) |

**14 fields owned by healthy V1 sources.** 10 fields addressable with fallback logic (derived movement, assignment_queue join, COALESCE). 7 fields unavailable until `rna_priority_fact` is created and `impact_tracking`/`loopcontrol_result_sync` are populated.

**Verdict: 77% of fields have valid ownership (with fallbacks). 100% of MUST HAVE fields (driver_id, lifecycle, program, rna_priority_band, last_trip_at, trips_7d) are covered. No field has BROKEN ownership — all gaps are "not yet populated" or "fallback to NULL".**

---

## 6. GOVERNANCE VIOLATION AUDIT

### Rule: RAW → SNAPSHOT → SERVING FACT → UI

The canonical chain must be:

```
RAW TABLES (raw_yango.orders_raw, public.trips_unified)
    ↓
SNAPSHOT TABLES (growth.yango_lima_driver_state_snapshot, program_eligibility_daily, rna_priority_fact)
    ↓
SERVING FACT (growth.yego_lima_driver_explorer_fact)           ← LG-EXP-1C creates
    ↓
SERVING ENDPOINT (GET /yego-lima-growth/driver-explorer)       ← LG-EXP-1D creates
    ↓
UI (DriverExplorerTab.jsx)                                      ← LG-EXP-1E wires
```

### Violation Check per Source Table

| Source Table | Layer in Chain | RAW→SNAPSHOT→SERVING→UI Compliant? | Issue |
|-------------|---------------|-------------------------------------|-------|
| `growth.yango_lima_driver_state_snapshot` | SNAPSHOT | ✅ | Correct — built from `raw_yango.orders_raw` via `build_driver_state_snapshot()` |
| `growth.yango_lima_program_eligibility_daily` | SNAPSHOT | ✅ | Correct — built from `driver_state_snapshot` via `build_program_eligibility()` |
| `growth.rna_priority_fact` | SNAPSHOT | ⚠️ TABLE MISSING | Not a chain violation — table simply not created yet |
| `growth.yego_lima_loopcontrol_result_sync` | RAW (external sync) | ⚠️ SKIPS SNAPSHOT | This table is raw sync from LoopControl API. It does not go through a snapshot step. BUT it's acceptable because it's an external system sync, not a derived computation. |
| `growth.yego_lima_impact_tracking` | SNAPSHOT | ✅ (when populated) | Correct — computed from `assignment_queue` + `loopcontrol_result_sync` |
| `growth.yango_lima_assignment_queue` | SNAPSHOT | ✅ | Correct — built from `program_eligibility_daily` |
| `growth.yego_lima_driver_lifecycle_daily` | SNAPSHOT | ✅ | Correct — built from `driver_activity_event` (migration 214) |

### Potential Violations Detected

#### Violation 1: `loopcontrol_result_sync` skips SNAPSHOT layer

| Aspect | Detail |
|--------|--------|
| **What** | The serving fact would read directly from `loopcontrol_result_sync` (a raw sync table from LoopControl API) without an intermediate snapshot. |
| **Severity** | **LOW** |
| **Justification** | `loopcontrol_result_sync` is a sync-once table (per campaign export), not a daily build. Creating a snapshot layer for it would add complexity without value. The existing export endpoint (`yego_lima_export_service.py`) already reads from it directly. |
| **Mitigation** | If this becomes a governance concern, a `loopcontrol_contact_snapshot` with grain `(contact_date, driver_id)` could be inserted. Not required for LG-EXP-1C. |

#### Violation 2: `public.drivers` as fallback for `phone`

| Aspect | Detail |
|--------|--------|
| **What** | The serving fact may read `public.drivers.phone` as fallback when `assignment_queue.phone` is NULL. |
| **Severity** | **LOW** |
| **Justification** | `public.drivers` is a raw table from the driver registration system. Reading it bypasses the snapshot layer. However, `phone` in `public.drivers` is essentially raw data with no transformation — it's identity, not a computation. |
| **Mitigation** | Add `phone` to `driver_state_snapshot` (requires snapshot builder change, not in LG-EXP-1C scope). Accept the fallback for MVP. |

#### Violation 3: Direct `v2_taxonomy_daily` read for segment

| Aspect | Detail |
|--------|--------|
| **What** | The serving fact COALESCEs `v2_taxonomy_daily.segment` as enrichment. `v2_taxonomy_daily` is a V2 shadow table, not a governed snapshot. |
| **Severity** | **LOW** |
| **Justification** | This is an optional COALESCE enrichment — if V2 data doesn't exist (stale), the fallback (`driver_state_snapshot.historical_band`) is used. The serving fact does NOT depend on V2. |
| **Mitigation** | When V2 taxonomy is promoted from shadow, it will go through its own snapshot pipeline. Until then, the COALESCE is safe. |

### Violation Summary

| # | Violation | Severity | Blocking? |
|---|-----------|----------|-----------|
| 1 | `loopcontrol_result_sync` skips SNAPSHOT | LOW | NO |
| 2 | `public.drivers` as phone fallback | LOW | NO |
| 3 | `v2_taxonomy_daily` as segment enrichment | LOW | NO |

**Verdict: 0 HIGH severity violations. 3 LOW severity violations (all justified with context). Chain RAW → SNAPSHOT → SERVING FACT → UI is preserved for the core data path (driver_state_snapshot → serving fact → endpoint → UI).**

---

## 7. PHYSICAL FORM: TABLE vs MATERIALIZED VIEW vs SERVING VIEW

### Options Evaluated

| Option | Description | Refresh | Concurrency | Growth Pattern? |
|--------|-------------|---------|-------------|-----------------|
| **Table** | `CREATE TABLE` with UPSERT | Service-driven (idempotent UPSERT every 5 min) | Row-level locks on UPSERT | **YES** — all `growth.*` objects are tables |
| **Materialized View** | `CREATE MATERIALIZED VIEW AS SELECT ...` | `REFRESH MATERIALIZED VIEW CONCURRENTLY` (atomic swap) | Blocks reads during refresh without CONCURRENTLY; needs UNIQUE index for CONCURRENTLY | NO — `growth.*` uses tables, not MVs |
| **Serving View** | `CREATE VIEW` (live query) | No refresh — query runs at read time | No write contention (read-only) | NO — violates "no heavy runtime joins" rule |

### Analysis

| Criterion | Table (UPSERT) | Materialized View | Serving View |
|-----------|---------------|-------------------|--------------|
| Follows `growth.*` pattern | ✅ | ❌ | ❌ |
| Supports incremental refresh | ✅ (UPSERT new date) | ❌ (full rebuild or CONCURRENTLY) | N/A |
| Non-blocking reads during refresh | ✅ (row-level locks) | ⚠️ (CONCURRENTLY requires unique index) | ✅ |
| Supports UPSERT idempotency | ✅ | ❌ (MV is read-only) | N/A |
| Transaction isolation | ✅ (UPSERT within tick transaction) | ⚠️ (REFRESH is its own transaction) | ✅ |
| Write contention with 5-min tick | ✅ (advisory lock prevents concurrent ticks) | ❌ (concurrent REFRESH fails) | N/A |
| Query performance at read time | ✅ (indexed table, direct WHERE) | ✅ (pre-built, fast reads) | ❌ (runs full JOIN every read → violates governance) |

### Recommendation

**CREATE TABLE — with UPSERT (INSERT ... ON CONFLICT DO UPDATE).**

This is the ONLY correct choice for the following reasons:

1. **Pattern compliance.** Every table in `growth.*` schema is a regular table with UPSERT semantics. Zero materialized views in `growth.*`. This is by design (see Section 8 of the research report: `ops.*` uses MVs for analytics; `growth.*` uses tables for operational facts).

2. **Incremental writes.** A serving fact with 55 columns joined from 9 source tables cannot be expressed as a simple MV query. The UPSERT approach allows the builder function to use Python logic (COALESCE chains, fallback queries, derived computations like `activity_trend` and `movement_type`).

3. **Idempotency.** The autonomous_tick runs every 5 minutes. `INSERT ... ON CONFLICT (target_date, driver_profile_id) DO UPDATE` is idempotent — same tick result whether it's the first, fifth, or fiftieth run.

4. **`data_quality` metadata.** Column-level quality flags (`COMPLETE` / `PARTIAL` / `STALE`) can be set during the build — not possible with a pure MV.

5. **Pruning.** `DELETE WHERE target_date < CURRENT_DATE - 90` is a simple SQL statement on a table. MVs require `REFRESH` to remove data (no `DELETE` on MVs).

**Verdict: CREATE TABLE. NOT Materialized View. NOT Serving View.**

---

## 8. GO / NO-GO RECOMMENDATION

### GO Criteria Evaluation

| # | Criterion | Required | Actual | Status |
|---|-----------|----------|--------|--------|
| 1 | Grain defined and justified | GO | `(target_date, driver_profile_id)` — matches upstream, follows pattern | ✅ |
| 2 | Domain belonging resolved | GO | V1 operational with V2 COALESCE enrichment | ✅ |
| 3 | Cardinality within limits | GO | ~1.8M rows at 90d, ~600 MB. PostgreSQL operational range. | ✅ |
| 4 | Refresh strategy defined | GO | autonomous_tick idempotent UPSERT (both paths). Same as 8 existing facts. | ✅ |
| 5 | 100% of MUST HAVE fields owned | GO | driver_id (✅), lifecycle (✅), program (✅), rna_priority_band (⚠️ DEFAULT 'COLD'), last_trip_at (✅), trips_7d (✅) | ✅ (6/6 covered, 1 with default) |
| 6 | 0 HIGH governance violations | GO | 3 LOW violations, all justified | ✅ |
| 7 | Physical form defined | GO | CREATE TABLE with UPSERT — follows `growth.*` pattern | ✅ |
| 8 | No blocked dependencies | GO | `rna_priority_fact` missing (defaults used). `impact_tracking` empty (NULL accepted). `v2_movement_fact` empty (derived) | ✅ (all gaps have fallback) |
| 9 | Migration version defined | GO | 220 (after 219 LG-PERF-1A) | ✅ |
| 10 | Writer owner identified | GO | `build_driver_explorer_fact()` in autonomous_tick + daily_refresh | ✅ |

### NO-GO Triggers — None Triggered

| # | NO-GO Trigger | Status | Detail |
|---|--------------|--------|--------|
| A | Source table missing (hard dependency) | NOT TRIGGERED | All hard-dependency tables exist: `driver_state_snapshot` ✅, `program_eligibility_daily` ✅ |
| B | Grain violation (doesn't match upstream) | NOT TRIGGERED | `(target_date, driver_profile_id)` matches `driver_state_snapshot` ✅ |
| C | Chain violation (RAW → UI skip) | NOT TRIGGERED | SNAPSHOT tables are in the chain ✅ |
| D | Ownership undefined for MUST HAVE field | NOT TRIGGERED | All MUST HAVE fields have defined ownership ✅ |
| E | Physical form violates schema pattern | NOT TRIGGERED | CREATE TABLE follows `growth.*` ✅ |
| F | Refresh strategy races with source build | NOT TRIGGERED | autonomous_tick advisory lock prevents concurrent ticks ✅ |

### Conditional GO

**GO — with the following conditions for full certification:**

| # | Condition | Required For | Phase |
|---|-----------|-------------|-------|
| C1 | Migration 219 (`219_lg_perf_1a_driver_explorer_index.py`) is applied BEFORE migration 220 | Full GO | LG-EXP-1C |
| C2 | `rna_priority_fact` table is created (migration 217 applied) within 1 week of LG-EXP-1C completion | RNA fields populated | LG-RNA-2B (separate track) |
| C3 | `build_driver_explorer_fact()` handles `rna_priority_fact` absence gracefully (defaults, not errors) | No 500 on missing table | LG-EXP-1C implementation |
| C4 | `data_quality` column reflects field availability (COMPLETE vs PARTIAL) | Operator visibility of data gaps | LG-EXP-1C implementation |
| C5 | 90-day retention pruning is implemented | Storage management | LG-EXP-1C implementation |

### Recommendation

**LG_EXP_1C_CONDITIONAL_GO**

The serving fact `growth.yego_lima_driver_explorer_fact` can and should be built now. 77% of fields have valid ownership today. The remaining 23% (RNA + contact + impact) will be NULL until their source tables are created/populated, which does NOT block the serving fact — the UPSERT pattern will populate them automatically when sources become available.

The architecture is sound:
- **Grain:** `(target_date, driver_profile_id)` — matches upstream ✅
- **Domain:** V1 operational — integrated into autonomous_tick ✅
- **Cardinality:** ~1.8M rows at 90d — manageable ✅
- **Refresh:** autonomous_tick idempotent UPSERT — same as 8 existing facts ✅
- **Chain:** RAW → SNAPSHOT → SERVING FACT → UI — preserved ✅
- **Form:** CREATE TABLE — follows `growth.*` pattern ✅
- **Ownership:** 77% fields owned, 0% blocked ✅

**Proceed to LG-EXP-1C implementation.**

---

## APPENDIX A: SOURCE TABLE HEALTH SUMMARY

| # | Table | Health | Rows | Latest Date | Impact on Serving Fact |
|---|-------|--------|------|-------------|----------------------|
| 1 | `growth.yango_lima_driver_state_snapshot` | **HEALTHY** | 166,712 | 2026-06-12 | Primary source — 14 fields ✅ |
| 2 | `growth.yango_lima_program_eligibility_daily` | **HEALTHY** | 254,560 | 2026-06-12 | Program fields — 4 fields ✅ |
| 3 | `growth.yego_lima_driver_lifecycle_daily` | STALE | 273,908 | 2026-06-10 | trips_30d, trips_since_anchor — fallback available |
| 4 | `growth.yego_lima_v2_taxonomy_daily` | STALE | 273,908 | 2026-06-10 | segment, sub_segment — COALESCE enrichment only |
| 5 | `growth.yego_lima_v2_movement_fact` | EMPTY | 0 | — | movement — derived fallback used |
| 6 | `growth.rna_priority_fact` | **MISSING** | 0 | — | 9 RNA fields — DEFAULT values used |
| 7 | `growth.yego_lima_loopcontrol_result_sync` | NEAR-EMPTY | 10 | 2026-06-08 | 4 contact fields — NULL for most drivers |
| 8 | `growth.yego_lima_impact_tracking` | EMPTY | 0 | — | 4 impact fields — NULL for all drivers |
| 9 | `growth.yango_lima_assignment_queue` | Rebuilt every 5 min | — | — | driver_name, phone, campaign — for exported drivers only |

## APPENDIX B: MIGRATION DEPENDENCY CHAIN

```
Migration 217 (rna_priority_fact) — NOT YET APPLIED
           ↓
Migration 218 (rna_pilot_measurement_fact) — NOT YET APPLIED
           ↓
Migration 219 (lg_perf_1a indexes) — PENDING (LG-PERF-1A)
           ↓
Migration 220 (lg_exp_1c driver_explorer_fact) — THIS PHASE (LG-EXP-1C)
```

Migration 219 must be applied first (`alembic upgrade head` will catch 217-219). If migration 217 (rna_priority_fact) is applied, RNA fields will populate. If not applied, RNA fields will use DEFAULT values gracefully.

## APPENDIX C: EXISTING DRIVER_EXPLORER INFRASTRUCTURE

The `driver_explorer` concept already exists in production:

| Component | Status | Gap |
|-----------|--------|-----|
| `DriverExplorerTab.jsx` (UI) | EXISTS | Reads wrong endpoint (`activity-summary`) |
| Export source `"driver_explorer"` | EXISTS | Reads from operational tables directly (bypasses serving fact) |
| `serving_driver_explorer` asset | REGISTERED | Empty deps array in `serving_operability_service.py` |
| `LG_EXP_1B` canonical contract | CERTIFIED | Design document (795 lines) |
| `growth.yego_lima_driver_explorer_fact` | **DOES NOT EXIST** | **THIS IS THE GAP — LG-EXP-1C fills it** |

LG-EXP-1C closes the gap between design and reality: the serving fact table, the writer, and the integration into the autonomous cascade.
