# LG_EXP_1B_DRIVER_EXPLORER_CANONICAL_CONTRACT

**Phase:** LG-EXP-1B — Driver Explorer Canonical Contract  
**Generated:** 2026-06-12  
**Status:** DESIGN PHASE — NO code, NO migrations, NO frontend changes  

---

## TASK 0 — GOVERNANCE VALIDATION

### Governance Docs Read

| Document | Path | Lines |
|----------|------|-------|
| `ai_operating_system.md` | `C:\cursor\controltower\controltower\ai_operating_system.md` | 225 |
| `ai_current_phase.md` | `C:\cursor\controltower\controltower\ai_current_phase.md` | 167 |

### Governance Rules Active

1. **Engine order**: Control Foundation → Diagnostic → Reachability → Forecast → Suggestion → Decision → Action → AI Copilot → Learning
2. **Serving governance**: RAW TABLES → SNAPSHOT → SERVING FACT → UI. Never bypass.
3. **No mixing engines**
4. **No heavy runtime fallback** for production-facing UI
5. **Deterministic logic first**; AI interprets, does not govern core truth
6. **Max 1 ACTIVE phase + 1 READY NEXT phase**

### Current Phase Status

| Phase | Status |
|-------|--------|
| Control Foundation | **REOPENED / P0** — Omniview False GO Recovery (OMNI-P0) |
| Diagnostic Engine | **PAUSED** — blocked until Omniview P0 Recovery |
| AI Copilot | BACKLOG |
| Learning | PROTOTYPE ONLY |

### LG-EXP-1B Alignment Check

| Rule | Check | Result |
|------|-------|--------|
| Control Foundation scope? | Driver Explorer is a Control Foundation surface | **PASS** — Reads operational snapshot data, does not open Diagnostic/Forecast/Suggestion/AI |
| No new engine? | This is a data contract refactor, not a new engine | **PASS** |
| Serving governance preserved? | LG-EXP-1B designs a serving fact; no raw table access from UI | **PASS** |
| No mixing engines? | All sources are Control Foundation (snapshot, eligibility, RNA, loopcontrol) | **PASS** |

**Governance Verdict:** LG-EXP-1B operates within Control Foundation boundaries. No engine activation required.

---

## TASK 1 — DRIVER EXPLORER CONTRACT AUDIT

### Canonical Definition of a Driver in Lima Growth

A driver within Lima Growth is a **conductor profile** identified by `driver_profile_id` (from Yango/Lima fleet systems). The Driver Explorer must present the **operational ficha** (card) of each driver, consolidating:

1. **Identity** — Who is this driver?
2. **Operational State** — What is their current state in the growth machine?
3. **Program Assignment** — Are they in a program? Which one?
4. **RNA (Reachability)** — Are they contactable? Priority band?
5. **Movement** — Have they changed state recently?
6. **Contact History** — Have we contacted them? What happened?
7. **Activity** — How many trips in recent windows?
8. **Impact** — Did our actions change their behavior?

### Canonical Attribute Matrix

| # | Campo | Backend (activity-summary) | DriverState Snapshot | Program Eligibility | RNA Priority Fact | LoopControl Result | Impact Tracking | V2 Shadow Tables | Canónico |
|---|-------|---------------------------|---------------------|--------------------|--------------------|--------------------|------------------|------------------|---------|
| 1 | `driver_id` | `d.driver_id` ✅ | `driver_profile_id` ✅ | `driver_profile_id` ✅ | `driver_profile_id` ✅ | `driver_id` ✅ | `driver_id` ✅ | `driver_id` ✅ | **CANONICAL** |
| 2 | `driver_name` | `COALESCE(vr.driver_name, dd.full_name)` ⚠️ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **NOT IN CANONICAL TABLES** |
| 3 | `phone` | `d.phone::text` ✅ | ❌ | ❌ | ❌ | `phone` ✅ | ❌ | ❌ | **LAGGED** (only after export) |
| 4 | `lifecycle` | `lb.*` ✅ | `lifecycle_state` ✅ | `lifecycle_state` ✅ | `lifecycle` ✅ | ❌ | ❌ | `lifecycle_stage` ✅ | **CANONICAL** (snapshot) |
| 5 | `segment` | ❌ | ❌ (performance_state?) | ❌ | ❌ | ❌ | ❌ | `segment` ✅ | **ONLY IN V2 SHADOW** |
| 6 | `sub_segment` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `sub_segment` ✅ | **ONLY IN V2 SHADOW** |
| 7 | `value_tier` | ❌ | `historical_band` ⚠️ | ❌ | `value_tier` ✅ | ❌ | ❌ | `elite_tier`/`loyalty_tier` ⚠️ | **PARTIAL** (RNA or V2) |
| 8 | `program` | ❌ | ❌ | `program_code` ✅ | `program_code` ✅ | ❌ | ❌ | `program_code` ✅ | **CANONICAL** (eligibility) |
| 9 | `rna_priority` | ❌ | ❌ | ❌ | `priority_band` ✅ | ❌ | ❌ | ❌ | **CANONICAL** (rna_priority_fact) |
| 10 | `rna_score` | ❌ | ❌ | ❌ | `rna_score` ✅ | ❌ | ❌ | ❌ | **CANONICAL** |
| 11 | `movement` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `movement_type` ✅ | **ONLY IN V2 SHADOW** |
| 12 | `last_trip` | `lb.last_completed_ts` ✅ | `last_trip_at` ✅ | ❌ | ❌ | ❌ | ❌ | `last_trip_at` ✅ | **CANONICAL** (snapshot) |
| 13 | `first_trip` | `lb.activation_ts` ✅ | `first_trip_at` ✅ | ❌ | ❌ | ❌ | ❌ | `first_trip_at` ✅ | **CANONICAL** (snapshot) |
| 14 | `trips_7d` | `t7` ✅ | `completed_orders_week` ⚠️ | ❌ | `trips_7d` ✅ | ❌ | ❌ | via lifecycle | **CANONICAL** (RNA or lifecycle) |
| 15 | `trips_30d` | `t30` ✅ | ❌ | ❌ | `trips_30d` ✅ | ❌ | ❌ | via lifecycle_daily | **CANONICAL** (RNA or lifecycle) |
| 16 | `days_since_last_trip` | `days_since_last_trip` ✅ | ❌ | ❌ | `days_since_last_trip` ✅ | ❌ | ❌ | via lifecycle_daily | **CANONICAL** (RNA) |
| 17 | `contactable` | ❌ | ❌ | ❌ | `contactable` ✅ | ❌ | ❌ | ❌ | **CANONICAL** (RNA) |
| 18 | `cancelled_signal` | ❌ | ❌ | ❌ | `cancelled_signal` ✅ | ❌ | ❌ | ❌ | **CANONICAL** (RNA) |
| 19 | `assigned_queue` | ❌ | ❌ | ❌ | ❌ | via `assignment_queue_id` | ❌ | via program_assignment | **LAGGED** (only after assignment) |
| 20 | `last_contact` | ❌ | ❌ | ❌ | ❌ | `last_call_at` ✅ | `contact_date` ✅ | ❌ | **CANONICAL** (loopcontrol) |
| 21 | `contact_result` | ❌ | ❌ | ❌ | ❌ | `disposition` ✅ | `contact_status` ✅ | ❌ | **CANONICAL** (loopcontrol) |
| 22 | `contact_agent` | ❌ | ❌ | ❌ | ❌ | `agent` ✅ | ❌ | ❌ | **CANONICAL** (loopcontrol) |
| 23 | `impact_status` | ❌ | ❌ | ❌ | ❌ | ❌ | `impact_status` ✅ | ❌ | **CANONICAL** (impact) |
| 24 | `activity_trend` | `activity_trend` ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **DERIVED** (computed from trips) |

### Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Field exists and is populated |
| ⚠️ | Field exists but may be empty, deprecated, or different semantics |
| ❌ | Field does not exist in this source |

### Audit Verdict

| Category | Count | Fields |
|----------|-------|--------|
| **CANONICAL (available today)** | 15 | driver_id, phone, lifecycle, program, rna_priority, rna_score, last_trip, first_trip, trips_7d, trips_30d, days_since_last_trip, contactable, cancelled_signal, last_contact, contact_result, contact_agent, impact_status |
| **LAGGED (only after export/assignment)** | 2 | phone (V1), assigned_queue |
| **PARTIAL (limited source availability)** | 2 | value_tier, driver_name |
| **ONLY IN V2 SHADOW** | 3 | segment, sub_segment, movement |
| **DERIVED (computed)** | 1 | activity_trend |
| **MISSING (no source)** | 1 | driver_name (no clean canonical source in growth.* tables) |

**Key Gap:** `driver_name` has no canonical source in Lima Growth tables. It exists in `assignment_queue` (populated at export time) and in `ops.v_dim_driver_resolved` (which is empty). A driver profile identity table would be needed for this field.

---

## TASK 2 — SOURCE OF TRUTH MATRIX

### Active Tables Audited

| Table | Schema | Grain | Populated By | Frequency | Status |
|-------|--------|-------|-------------|-----------|--------|
| `growth.yango_lima_driver_state_snapshot` | growth | `(snapshot_date, driver_profile_id)` | `build_driver_state_snapshot()` in autonomous_tick | Every 5 min (when raw ahead) | **ACTIVE** |
| `growth.yango_lima_program_eligibility_daily` | growth | `(eligibility_date, driver_profile_id, program_code)` | `build_program_eligibility()` in autonomous_tick | Every 5 min | **ACTIVE** |
| `growth.rna_priority_fact` | growth | `driver_profile_id` (1 row per driver) | RNA priority service (scored_at) | On-demand / daily | **ACTIVE** |
| `growth.yego_lima_loopcontrol_result_sync` | growth | `id` (UUID) | LoopControl export sync | On export | **ACTIVE** |
| `growth.yego_lima_impact_tracking` | growth | `id` (UUID) | Impact attribution service | On measurement | **ACTIVE** |
| `growth.yango_lima_assignment_queue` | growth | `id` (UUID) | Queue builder in autonomous_tick | Every 5 min | **ACTIVE** |
| `growth.yango_lima_daily_opportunity_list` | growth | `(opportunity_date, driver_profile_id, opportunity_type)` | Opportunity builder in autonomous_tick | Every 5 min | **ACTIVE** |
| `growth.yango_lima_driver_360_daily` | growth | `(driver_profile_id, date)` | 360 daily builder | Daily | **ACTIVE** |
| `growth.yego_lima_v2_lifecycle_daily` | growth | `(target_date, driver_id)` | `_build_lifecycle_daily()` in V2 pipeline | Manual / on-demand | **SHADOW** |
| `growth.yego_lima_v2_taxonomy_daily` | growth | `(target_date, driver_id)` | `_build_taxonomy_v2_daily()` in V2 pipeline | Manual / on-demand | **SHADOW** |
| `growth.yego_lima_v2_program_daily` | growth | `(target_date, driver_id, program_code)` | `_build_program_v2_daily()` in V2 pipeline | Manual / on-demand | **SHADOW** |
| `growth.yego_lima_v2_movement_fact` | growth | `(target_date, driver_id, movement_type)` | `_build_movement_fact()` in V2 pipeline | Manual / on-demand | **SHADOW** |
| `growth.yego_lima_v2_activity_daily` | growth | `(target_date, driver_id)` | `_build_activity_daily()` in V2 pipeline | Manual / on-demand | **SHADOW** |

### Source of Truth Per Field (Production-Grade Only)

| # | Field | Source of Truth Table | Source Column | Join Key |
|---|-------|----------------------|---------------|----------|
| 1 | `driver_id` | `growth.yango_lima_driver_state_snapshot` | `driver_profile_id` | — |
| 2 | `lifecycle` | `growth.yango_lima_driver_state_snapshot` | `lifecycle_state` | — |
| 3 | `performance_state` | `growth.yango_lima_driver_state_snapshot` | `performance_state` | — |
| 4 | `retention_state` | `growth.yango_lima_driver_state_snapshot` | `retention_state` | — |
| 5 | `historical_band` | `growth.yango_lima_driver_state_snapshot` | `historical_band` | — |
| 6 | `last_trip_at` | `growth.yango_lima_driver_state_snapshot` | `last_trip_at` | — |
| 7 | `first_trip_at` | `growth.yango_lima_driver_state_snapshot` | `first_trip_at` | — |
| 8 | `completed_orders_week` | `growth.yango_lima_driver_state_snapshot` | `completed_orders_week` | — |
| 9 | `program_code` | `growth.yango_lima_program_eligibility_daily` | `program_code` | `driver_profile_id` + same date |
| 10 | `priority` | `growth.yango_lima_program_eligibility_daily` | `priority` | `driver_profile_id` + same date |
| 11 | `rna_score` | `growth.rna_priority_fact` | `rna_score` | `driver_profile_id` |
| 12 | `priority_band` | `growth.rna_priority_fact` | `priority_band` | `driver_profile_id` |
| 13 | `contactable` | `growth.rna_priority_fact` | `contactable` | `driver_profile_id` |
| 14 | `cancelled_signal` | `growth.rna_priority_fact` | `cancelled_signal` | `driver_profile_id` |
| 15 | `trips_7d` | `growth.rna_priority_fact` | `trips_7d` | `driver_profile_id` |
| 16 | `trips_30d` | `growth.rna_priority_fact` | `trips_30d` | `driver_profile_id` |
| 17 | `days_since_last_trip` | `growth.rna_priority_fact` | `days_since_last_trip` | `driver_profile_id` |
| 18 | `value_tier` | `growth.rna_priority_fact` | `value_tier` | `driver_profile_id` |
| 19 | `momentum` | `growth.rna_priority_fact` | `momentum` | `driver_profile_id` |
| 20 | `last_call_at` | `growth.yego_lima_loopcontrol_result_sync` | `last_call_at` | `driver_id` + latest |
| 21 | `disposition` | `growth.yego_lima_loopcontrol_result_sync` | `disposition` | `driver_id` + latest |
| 22 | `agent` | `growth.yego_lima_loopcontrol_result_sync` | `agent` | `driver_id` + latest |
| 23 | `impact_status` | `growth.yego_lima_impact_tracking` | `impact_status` | `driver_id` + latest |
| 24 | `baseline_trips` | `growth.yego_lima_impact_tracking` | `baseline_trips` | `driver_id` + latest |
| 25 | `post_contact_trips` | `growth.yego_lima_impact_tracking` | `post_contact_trips` | `driver_id` + latest |

### Source Gaps Identified

| # | Field | Gap | Severity |
|---|-------|-----|----------|
| 1 | `driver_name` | No clean source in `growth.*` tables. Only in `assignment_queue` (at export time) or `ops.v_dim_driver_resolved` (empty). | **HIGH** |
| 2 | `segment` | Only in V2 shadow table `v2_taxonomy_daily.segment`. Not in V1 production tables. | **MEDIUM** |
| 3 | `sub_segment` | Only in V2 shadow table `v2_taxonomy_daily.sub_segment`. | **MEDIUM** |
| 4 | `movement` | Only in V2 shadow table `v2_movement_fact`. Not in V1 production tables. | **MEDIUM** |
| 5 | `phone` | In `loopcontrol_result_sync` (only for contacted drivers) and `public.drivers` (legacy). No canonical Lima Growth source for ALL drivers. | **MEDIUM** |
| 6 | `assigned_queue` | Only in `assignment_queue` and `daily_opportunity_list`. Only populated for drivers in active programs. | **LOW** |

---

## TASK 3 — SERVING FACT DESIGN

### Fact Identity

| Attribute | Value |
|-----------|-------|
| **Table Name** | `growth.yego_lima_driver_explorer_fact` |
| **Schema** | `growth` |
| **Grain** | `(target_date, driver_profile_id)` — One row per driver per operational date |
| **Type** | Serving fact (pre-joined, pre-computed, snapshot) |
| **Refresh** | Daily, after autonomous_tick cascade completes |
| **Ownership** | Control Foundation — Lima Growth Machine |

### Column Definition

#### Layer 1: Identity (from driver_state_snapshot)

| Column | Type | Source | Default | Notes |
|--------|------|--------|---------|-------|
| `target_date` | `DATE NOT NULL` | Pipeline param | — | PK part 1 |
| `driver_profile_id` | `TEXT NOT NULL` | `driver_state_snapshot.driver_profile_id` | — | PK part 2 |
| `driver_name` | `TEXT` | `assignment_queue.driver_name` (latest) or `v_dim_driver_resolved.driver_name` | `NULL` | **Gap**: may be NULL for non-queued drivers |
| `phone` | `TEXT` | `loopcontrol_result_sync.phone` (latest) or `public.drivers.phone` | `NULL` | **Gap**: may be NULL if never exported |
| `park_id` | `TEXT` | `driver_state_snapshot` via `program_eligibility_daily` or `v2_taxonomy_daily` | `NULL` | Parking location |

#### Layer 2: Operational State (from driver_state_snapshot)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `lifecycle` | `TEXT` | `driver_state_snapshot.lifecycle_state` | `'UNKNOWN'` |
| `performance_state` | `TEXT` | `driver_state_snapshot.performance_state` | `'UNKNOWN'` |
| `retention_state` | `TEXT` | `driver_state_snapshot.retention_state` | `'UNKNOWN'` |
| `historical_band` | `TEXT` | `driver_state_snapshot.historical_band` | `NULL` |
| `segment` | `TEXT` | Fallback chain: `rna_priority_fact.value_tier` → `driver_state_snapshot.historical_band` → `'UNKNOWN'` | `'UNKNOWN'` |
| `sub_segment` | `TEXT` | Derived from `performance_state` + `completed_orders_week` | `NULL` |

#### Layer 3: Program (from program_eligibility_daily)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `program_code` | `TEXT` | `program_eligibility_daily.program_code` | `NULL` |
| `program_priority` | `INTEGER` | `program_eligibility_daily.priority` | `NULL` |
| `eligibility_reason` | `TEXT` | `program_eligibility_daily.eligibility_reason` | `NULL` |
| `is_in_program` | `BOOLEAN` | `program_code IS NOT NULL` | `FALSE` |

#### Layer 4: RNA (from rna_priority_fact)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `rna_priority_band` | `TEXT` | `rna_priority_fact.priority_band` | `'COLD'` |
| `rna_score` | `NUMERIC(6,2)` | `rna_priority_fact.rna_score` | `0` |
| `contactable` | `BOOLEAN` | `rna_priority_fact.contactable` | `FALSE` |
| `cancelled_signal` | `BOOLEAN` | `rna_priority_fact.cancelled_signal` | `FALSE` |
| `rna_value_tier` | `TEXT` | `rna_priority_fact.value_tier` | `NULL` |
| `rna_momentum` | `TEXT` | `rna_priority_fact.momentum` | `NULL` |

#### Layer 5: Movement (from state transition traces or diff logic)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `movement_type` | `TEXT` | Diff of `lifecycle_state` vs previous date, or `v2_movement_fact.movement_type` | `NULL` |
| `movement_from` | `TEXT` | Previous value | `NULL` |
| `movement_to` | `TEXT` | Current value | `NULL` |
| `movement_trigger` | `TEXT` | `state_transition_trace.trigger_reason` | `NULL` |

#### Layer 6: Contactability (from loopcontrol_result_sync)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `last_contact_at` | `TIMESTAMPTZ` | `loopcontrol_result_sync.last_call_at` | `NULL` |
| `last_contact_disposition` | `TEXT` | `loopcontrol_result_sync.disposition` | `NULL` |
| `last_contact_agent` | `TEXT` | `loopcontrol_result_sync.agent` | `NULL` |
| `contact_attempts` | `INTEGER` | `loopcontrol_result_sync.attempts` | `NULL` |

#### Layer 7: Execution / Assignment (from assignment_queue + opportunity_list)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `assigned_campaign_id` | `TEXT` | `assignment_queue.campaign_id_external` | `NULL` |
| `queue_status` | `TEXT` | `assignment_queue.status` | `NULL` |
| `opportunity_type` | `TEXT` | `daily_opportunity_list.opportunity_type` | `NULL` |

#### Layer 8: Activity (from driver_state_snapshot + rna_priority_fact)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `trips_7d` | `INTEGER` | `driver_state_snapshot.completed_orders_week` (COALESCE with `rna_priority_fact.trips_7d`) | `0` |
| `trips_30d` | `INTEGER` | `rna_priority_fact.trips_30d` (COALESCE with lifecycle_daily) | `0` |
| `trips_since_anchor` | `INTEGER` | `driver_lifecycle_daily.completed_trips_since_anchor` | `0` |
| `first_trip_at` | `TIMESTAMPTZ` | `driver_state_snapshot.first_trip_at` | `NULL` |
| `last_trip_at` | `TIMESTAMPTZ` | `driver_state_snapshot.last_trip_at` | `NULL` |
| `days_since_last_trip` | `INTEGER` | `rna_priority_fact.days_since_last_trip` | `NULL` |
| `activity_trend` | `TEXT` | Computed: `trips_7d` vs `trips_prev_7d` | `'UNKNOWN'` |
| `new_driver_flag` | `BOOLEAN` | `driver_state_snapshot.new_driver_flag` | `FALSE` |
| `recoverable_flag` | `BOOLEAN` | `driver_state_snapshot.recoverable_flag` | `FALSE` |
| `declining_flag` | `BOOLEAN` | `driver_state_snapshot.declining_flag` | `FALSE` |
| `churn_risk_flag` | `BOOLEAN` | `driver_state_snapshot.churn_risk_flag` | `FALSE` |

#### Layer 9: Impact (from impact_tracking)

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `impact_status` | `TEXT` | `impact_tracking.impact_status` | `'PENDING_WINDOW'` |
| `baseline_trips` | `INTEGER` | `impact_tracking.baseline_trips` | `0` |
| `post_contact_trips` | `INTEGER` | `impact_tracking.post_contact_trips` | `0` |
| `trips_delta_after_contact` | `INTEGER` | `post_contact_trips - baseline_trips` | `NULL` |

#### Layer 10: Metadata

| Column | Type | Source | Default |
|--------|------|--------|---------|
| `source_tables` | `TEXT[]` | Array of source table names used | Auto |
| `data_quality` | `TEXT` | `'PARTIAL'` / `'COMPLETE'` / `'STALE'` | `'PARTIAL'` |
| `refreshed_at` | `TIMESTAMPTZ` | `NOW()` | Auto |

### DDL

```sql
CREATE TABLE IF NOT EXISTS growth.yego_lima_driver_explorer_fact (
    target_date                 DATE NOT NULL,
    driver_profile_id           TEXT NOT NULL,

    -- Identity
    driver_name                 TEXT,
    phone                       TEXT,
    park_id                     TEXT,

    -- Operational State
    lifecycle                   TEXT NOT NULL DEFAULT 'UNKNOWN',
    performance_state           TEXT,
    retention_state             TEXT,
    historical_band             TEXT,
    segment                     TEXT,
    sub_segment                 TEXT,

    -- Program
    program_code                TEXT,
    program_priority            INTEGER,
    eligibility_reason          TEXT,
    is_in_program               BOOLEAN NOT NULL DEFAULT FALSE,

    -- RNA
    rna_priority_band           TEXT NOT NULL DEFAULT 'COLD',
    rna_score                   NUMERIC(6,2) NOT NULL DEFAULT 0,
    contactable                 BOOLEAN NOT NULL DEFAULT FALSE,
    cancelled_signal            BOOLEAN NOT NULL DEFAULT FALSE,
    rna_value_tier              TEXT,
    rna_momentum                TEXT,

    -- Movement
    movement_type               TEXT,
    movement_from               TEXT,
    movement_to                 TEXT,
    movement_trigger            TEXT,

    -- Contactability
    last_contact_at             TIMESTAMPTZ,
    last_contact_disposition    TEXT,
    last_contact_agent          TEXT,
    contact_attempts            INTEGER,

    -- Execution
    assigned_campaign_id        TEXT,
    queue_status                TEXT,
    opportunity_type            TEXT,

    -- Activity
    trips_7d                    INTEGER NOT NULL DEFAULT 0,
    trips_30d                   INTEGER NOT NULL DEFAULT 0,
    trips_since_anchor          INTEGER NOT NULL DEFAULT 0,
    first_trip_at               TIMESTAMPTZ,
    last_trip_at                TIMESTAMPTZ,
    days_since_last_trip        INTEGER,
    activity_trend              TEXT NOT NULL DEFAULT 'UNKNOWN',
    new_driver_flag             BOOLEAN NOT NULL DEFAULT FALSE,
    recoverable_flag            BOOLEAN NOT NULL DEFAULT FALSE,
    declining_flag              BOOLEAN NOT NULL DEFAULT FALSE,
    churn_risk_flag             BOOLEAN NOT NULL DEFAULT FALSE,

    -- Impact
    impact_status               TEXT,
    baseline_trips              INTEGER DEFAULT 0,
    post_contact_trips          INTEGER DEFAULT 0,
    trips_delta_after_contact   INTEGER,

    -- Metadata
    source_tables               TEXT[],
    data_quality                TEXT NOT NULL DEFAULT 'PARTIAL',
    refreshed_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (target_date, driver_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_explorer_lifecycle
    ON growth.yego_lima_driver_explorer_fact (target_date, lifecycle);

CREATE INDEX IF NOT EXISTS idx_explorer_program
    ON growth.yego_lima_driver_explorer_fact (target_date, program_code);

CREATE INDEX IF NOT EXISTS idx_explorer_rna
    ON growth.yego_lima_driver_explorer_fact (target_date, rna_priority_band);

CREATE INDEX IF NOT EXISTS idx_explorer_segment
    ON growth.yego_lima_driver_explorer_fact (target_date, segment);

CREATE INDEX IF NOT EXISTS idx_explorer_search
    ON growth.yego_lima_driver_explorer_fact (driver_profile_id text_pattern_ops);
```

### Inputs

| # | Source Table | Join Key | What It Provides |
|---|-------------|----------|-----------------|
| 1 | `growth.yango_lima_driver_state_snapshot` | `driver_profile_id` + `snapshot_date = target_date` | Identity, lifecycle, activity, flags |
| 2 | `growth.yango_lima_program_eligibility_daily` | `driver_profile_id` + `eligibility_date = target_date` | Program assignment |
| 3 | `growth.rna_priority_fact` | `driver_profile_id` (latest) | RNA scoring, trips_7d/30d, value_tier, momentum |
| 4 | `growth.yego_lima_loopcontrol_result_sync` | `driver_id = driver_profile_id` (latest) | Contact history |
| 5 | `growth.yango_lima_assignment_queue` | `driver_profile_id` (latest) | driver_name, assigned campaign |
| 6 | `growth.yango_lima_daily_opportunity_list` | `driver_profile_id` + `opportunity_date = target_date` | Opportunity type, queue status |
| 7 | `growth.yego_lima_impact_tracking` | `driver_id = driver_profile_id` (latest) | Impact measurement |
| 8 | `growth.yego_lima_driver_lifecycle_daily` | `driver_profile_id` + `snapshot_date = target_date` | trips_30d, trips_since_anchor |
| 9 | `public.drivers` | `driver_id = driver_profile_id` | phone (fallback) |

### Outputs

| # | Consumer | Endpoint | Format |
|---|----------|----------|--------|
| 1 | Driver Explorer Tab | `GET /yego-lima-growth/driver-explorer?target_date=&lifecycle=&program=&rna_band=&segment=&search=&limit=&offset=` | JSON array of driver records |
| 2 | Export CSV | `POST /yego-lima-growth/export` with `source: 'driver_explorer'` | CSV blob |
| 3 | Drilldown from other tabs | Pass `driver_id` filter to Explorer | Filters applied |

### Ownership

| Role | Responsibility |
|------|---------------|
| **Builder** | Autonomous tick cascade (LG-EXP-1C) |
| **Refresher** | Daily, after `build_driver_state_snapshot()` + `build_program_eligibility()` complete |
| **Reader** | `yego_lima_driver_explorer_service.py` (LG-EXP-1D) |
| **Router** | `yego_lima_driver_explorer` router (LG-EXP-1D) |
| **Consumer** | `DriverExplorerTab.jsx` (LG-EXP-1E) |

---

## TASK 4 — WRITER DESIGN

### Options Evaluated

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A: autonomous_tick** | Add `build_driver_explorer_fact()` as a new step in the autonomous_tick cascade, after `generate_all_serving_facts()` | Already runs every 5 min; has access to all V1 tables; writes to `growth.*`; follows existing pattern | Does NOT populate V2 shadow tables (segment, sub_segment, movement from taxonomy); those would be NULL |
| **B: V2 pipeline** | Add `_build_explorer_fact()` as Step 10 in `run_lima_growth_v2_daily_pipeline()` | Has richer taxonomy/segment/movement data; already writes to `growth.yego_lima_v2_*` | SHADOW MODE — not integrated into autonomous_tick; runs manually/on-demand; would create a V2-only fact disconnected from V1 operational data (snapshot, eligibility, RNA) |
| **C: New serving builder** | Create standalone `build_driver_explorer_fact.py` script, scheduled separately | Clean separation; can join V1 + V2 sources | New scheduling dependency; adds complexity; violates "one cascade" principle |

### Recommendation: Option A (autonomous_tick)

**Justification:**

1. **V1 tables already contain 80% of the canonical fields.** The `driver_state_snapshot`, `program_eligibility_daily`, `rna_priority_fact`, `loopcontrol_result_sync`, and `impact_tracking` tables provide identity, lifecycle, program, RNA, contact history, and impact data.

2. **The gaps (segment, sub_segment, movement) should be backfilled into V1, not solved by adding V2 as a dependency.** The correct architectural fix is to add `segment` and `movement` columns to `driver_state_snapshot` or create a V1 taxonomy snapshot table, rather than making the serving fact depend on a shadow pipeline.

3. **Existing pattern compliance.** The `generate_all_serving_facts()` function already builds 8 fact types within autonomous_tick. Adding a 9th fact type (`driver_explorer`) follows the established pattern: build → save → serve.

4. **The governance rule is RAW → SNAPSHOT → SERVING FACT → UI.** The V1 snapshot tables ARE the snapshot layer. The serving fact (explorer_fact) sits on top. No new snapshot layer needed.

### Writer Architecture (Option A)

```
autonomous_tick() every 5 min:
  ├── ingest_recent_orders()
  ├── detect_latest_closed_data_date()
  ├── [if raw ahead of snapshot]:
  │   ├── build_driver_state_snapshot(d)         ← source: lifecycle, activity, flags
  │   ├── build_program_eligibility(d)           ← source: program_code, priority
  │   ├── build_daily_opportunity_lists(d)       ← source: opportunity_type
  │   ├── build_prioritized_opportunities(d)
  │   └── run_daily_refresh(d)
  ├── sync_assignment_queue_to_control_loop()    ← source: assigned_campaign
  ├── generate_all_serving_facts(op_date)        ← existing serving facts
  │   └── [NEW] build_driver_explorer_fact(op_date)  ← NEW STEP (LG-EXP-1C)
  ├── build_intraday_signals()
  ├── snapshot_queue_to_history()
  └── governance_status_refresh()
```

### How `build_driver_explorer_fact(target_date)` works

1. Query `driver_state_snapshot` for `target_date` → base driver list
2. LEFT JOIN `program_eligibility_daily` on `(target_date, driver_profile_id)` → program data
3. LEFT JOIN `rna_priority_fact` on `driver_profile_id` (latest scored_at) → RNA data
4. LEFT JOIN `assignment_queue` on `driver_profile_id` (latest status) → driver_name, campaign
5. LEFT JOIN `loopcontrol_result_sync` on `driver_id` (latest synced_at) → contact history
6. LEFT JOIN `impact_tracking` on `driver_id` (latest measured_at) → impact data
7. LEFT JOIN `driver_lifecycle_daily` on `(target_date, driver_profile_id)` → trips_30d, anchor
8. INSERT INTO `growth.yego_lima_driver_explorer_fact` ON CONFLICT (target_date, driver_profile_id) DO UPDATE
9. Compute `activity_trend` (compare trips_7d vs previous period)
10. Compute `data_quality` flag (COMPLETE if all sources joined; PARTIAL if gaps)

### Flow Compliance

```
RAW TABLES (raw_yango.orders_raw, public.trips_unified)
    ↓
SNAPSHOT TABLES (growth.yango_lima_driver_state_snapshot, program_eligibility_daily, rna_priority_fact)
    ↓
SERVING FACT (growth.yego_lima_driver_explorer_fact)          ← LG-EXP-1C creates this
    ↓
SERVING ENDPOINT (GET /yego-lima-growth/driver-explorer)      ← LG-EXP-1D creates this
    ↓
UI (DriverExplorerTab.jsx)                                     ← LG-EXP-1E wires this
```

**Compliance:** YES. Full chain from RAW → SNAPSHOT → SERVING FACT → ENDPOINT → UI. No heavy runtime joins in the endpoint. The endpoint reads pre-joined rows from the serving fact with simple WHERE filters.

---

## TASK 5 — UI CONTRACT AUDIT

### Current State of DriverExplorerTab.jsx

**File:** `frontend/src/pages/lima-growth-ui1a/sections/DriverExplorerTab.jsx` (246 lines)

**Current endpoint consumed:** `GET /drivers/activity-summary` (WRONG — serves activity metrics, not operational data)

**Current columns displayed (lines 186-228):**

| # | Column Header | Expected Field | Actual Source | Status |
|---|--------------|----------------|---------------|--------|
| 1 | Driver ID | `d.driver_id \|\| d.driver_profile_id \|\| '—'` | `activity-summary` ✅ | **OK** |
| 2 | Lifecycle | `d.lifecycle \|\| d.lifecycle_stage \|\| '—'` | `'—'` ❌ | **EMPTY** |
| 3 | Segment | `d.segment \|\| d.driver_segment \|\| '—'` | `'—'` ❌ | **EMPTY** |
| 4 | Program | `d.program \|\| d.program_code \|\| '—'` | `'—'` ❌ | **EMPTY** |
| 5 | Movement | `d.movement_status \|\| d.movement \|\| '—'` | `'—'` ❌ | **EMPTY** |
| 6 | RNA | `d.rna_status \|\| (d.is_rna ? 'RNA' : 'Active')` | `'—'` ❌ | **EMPTY** |
| 7 | Last Activity | `d.last_activity \|\| d.last_trip_date \|\| d.last_active \|\| '—'` | `latest_trip_at` ✅ | **OK** (via `latest_trip_at` from activity-summary) |
| 8 | Why | Explainability button → `ExplainabilityPanel` | — | **OK** (separate component, not endpoint-dependent) |

**Current filters (lines 106-156):**

| Filter | Source | Sent to Backend? | Used by Backend? | Status |
|--------|--------|------------------|-----------------|--------|
| Search (text input) | `filters.search` | `search=value` | ✅ (LG-PERF-1A fix) | **OK** (prefix match on driver_id) |
| Program (dropdown) | `filters.program` | `program=value` | ❌ | **BROKEN** |
| Lifecycle (dropdown) | `filters.lifecycle` | `lifecycle=value` | ❌ | **BROKEN** |
| Segment (not in UI) | — | — | — | **MISSING** |

### MUST HAVE Columns (for operational ficha)

| # | Column | Rationale |
|---|--------|-----------|
| 1 | `driver_id` | Primary identifier — non-negotiable |
| 2 | `driver_name` | Human-readable identity |
| 3 | `lifecycle` | Core operational state (ACTIVE, AT_RISK, CHURNED, etc.) |
| 4 | `program` | What program is the driver in? |
| 5 | `rna_priority_band` | Is this driver in RNA priority? (HOT/WARM/COLD) |
| 6 | `last_trip_at` | When was their last activity? |
| 7 | `trips_7d` | Recent activity metric |

### SHOULD HAVE Columns (enrich the ficha)

| # | Column | Rationale |
|---|--------|-----------|
| 8 | `phone` | For operator contact |
| 9 | `segment` | Value segment classification |
| 10 | `contactable` | Can we reach this driver? |
| 11 | `movement_type` | Recent state change indicator |
| 12 | `days_since_last_trip` | Churn proximity |
| 13 | `activity_trend` | Growing / stable / declining |
| 14 | `last_contact_disposition` | What happened last time we contacted? |

### NICE TO HAVE Columns (optional depth)

| # | Column | Rationale |
|---|--------|-----------|
| 15 | `sub_segment` | Granular segmentation |
| 16 | `rna_score` | Numeric RNA priority score |
| 17 | `cancelled_signal` | Cancellation signal flag |
| 18 | `impact_status` | Did our action change behavior? |
| 19 | `trips_30d` | Broader activity window |
| 20 | `queue_status` | Is driver in export queue? |

---

## TASK 6 — GAP ANALYSIS

### EXPLORER_GAP_MATRIX

| # | Campo | Disponible | Fuente | Gap | Acción | Clasificación |
|---|-------|-----------|--------|-----|--------|-------------|
| 1 | `driver_id` | ✅ | `driver_state_snapshot` | Ninguno | Direct mapping | **READY** |
| 2 | `driver_name` | ⚠️ | `assignment_queue` (solo exportados) | No hay source para TODOS los drivers | Agregar campo a `driver_state_snapshot` o leer de `raw_yango.mv_driver_profiles_snapshot` | **NEEDS_MAPPING** |
| 3 | `phone` | ⚠️ | `loopcontrol_result_sync` (solo contactados) | No hay source universal | Leer de `public.drivers` como fallback | **NEEDS_MAPPING** |
| 4 | `lifecycle` | ✅ | `driver_state_snapshot.lifecycle_state` | Ninguno | Direct mapping | **READY** |
| 5 | `performance_state` | ✅ | `driver_state_snapshot.performance_state` | Ninguno | Direct mapping | **READY** |
| 6 | `retention_state` | ✅ | `driver_state_snapshot.retention_state` | Ninguno | Direct mapping | **READY** |
| 7 | `historical_band` | ✅ | `driver_state_snapshot.historical_band` | Ninguno | Direct mapping (usar como fallback de segment) | **READY** |
| 8 | `segment` | ⚠️ | `rna_priority_fact.value_tier` o `historical_band` | V1 no tiene segmentación canónica | Backfill desde `historical_band` o agregar a snapshot | **NEEDS_MAPPING** |
| 9 | `sub_segment` | ❌ | Solo en V2 shadow | V1 no produce sub-segmentación | Crear derivación en V1 o aceptar NULL | **NEEDS_SERVING** |
| 10 | `program_code` | ✅ | `program_eligibility_daily` | Ninguno | Direct mapping | **READY** |
| 11 | `program_priority` | ✅ | `program_eligibility_daily.priority` | Ninguno | Direct mapping | **READY** |
| 12 | `rna_priority_band` | ✅ | `rna_priority_fact.priority_band` | Ninguno | Direct mapping | **READY** |
| 13 | `rna_score` | ✅ | `rna_priority_fact.rna_score` | Ninguno | Direct mapping | **READY** |
| 14 | `contactable` | ✅ | `rna_priority_fact.contactable` | Ninguno | Direct mapping | **READY** |
| 15 | `cancelled_signal` | ✅ | `rna_priority_fact.cancelled_signal` | Ninguno | Direct mapping | **READY** |
| 16 | `rna_value_tier` | ✅ | `rna_priority_fact.value_tier` | Ninguno | Direct mapping | **READY** |
| 17 | `rna_momentum` | ✅ | `rna_priority_fact.momentum` | Ninguno | Direct mapping | **READY** |
| 18 | `movement_type` | ⚠️ | `state_transition_trace` o diff entre fechas | V1 no tiene movement fact canónico | Derivar de diff de lifecycle_state entre target_date y día anterior | **NEEDS_MAPPING** |
| 19 | `last_contact_at` | ✅ | `loopcontrol_result_sync.last_call_at` | Ninguno | Direct mapping (latest per driver) | **READY** |
| 20 | `last_contact_disposition` | ✅ | `loopcontrol_result_sync.disposition` | Ninguno | Direct mapping | **READY** |
| 21 | `last_contact_agent` | ✅ | `loopcontrol_result_sync.agent` | Ninguno | Direct mapping | **READY** |
| 22 | `contact_attempts` | ✅ | `loopcontrol_result_sync.attempts` | Ninguno | Direct mapping | **READY** |
| 23 | `assigned_campaign_id` | ✅ | `assignment_queue.campaign_id_external` | Ninguno | Direct mapping (latest per driver) | **READY** |
| 24 | `queue_status` | ✅ | `assignment_queue.status` | Ninguno | Direct mapping | **READY** |
| 25 | `trips_7d` | ✅ | `driver_state_snapshot.completed_orders_week` | Ninguno | Direct mapping | **READY** |
| 26 | `trips_30d` | ✅ | `rna_priority_fact.trips_30d` o `driver_lifecycle_daily` | Ninguno | Direct mapping con fallback | **READY** |
| 27 | `first_trip_at` | ✅ | `driver_state_snapshot.first_trip_at` | Ninguno | Direct mapping | **READY** |
| 28 | `last_trip_at` | ✅ | `driver_state_snapshot.last_trip_at` | Ninguno | Direct mapping | **READY** |
| 29 | `days_since_last_trip` | ✅ | `rna_priority_fact.days_since_last_trip` | Ninguno | Direct mapping | **READY** |
| 30 | `activity_trend` | ✅ | Derivado (trips_7d vs periodo anterior) | Requiere cómputo | Computar durante el build de serving fact | **READY** |
| 31 | `impact_status` | ✅ | `impact_tracking.impact_status` | Ninguno | Direct mapping | **READY** |

### Summary

| Clasificación | Count | % |
|--------------|-------|---|
| **READY** | 23 | 74% |
| **NEEDS_MAPPING** | 4 | 13% |
| **NEEDS_SERVING** | 1 | 3% |
| **BLOCKED** | 0 | 0% |

**No fields are BLOCKED.** All gaps are addressable with mapping logic or accepting NULL for shadow-only fields.

---

## TASK 7 — GO / NO-GO

### Can the serving fact be built today?

**YES.** All required source tables exist and are populated by `autonomous_tick()`.

### Missing upstream sources?

| Field | Gap | Impact | Mitigation |
|-------|-----|--------|------------|
| `driver_name` | No universal source in `growth.*` | 1 field NULL for non-exported drivers | Accept NULL in MVP; backfill from `raw_yango.mv_driver_profiles_snapshot` or `public.drivers` in LG-EXP-1D |
| `segment` | No V1 taxonomy table | Uses `historical_band` as fallback | Accept fallback semantics in MVP; V2 taxonomy migration tracked separately |
| `sub_segment` | Only in V2 shadow | Always NULL in V1 | Accept NULL in MVP; field is NICE TO HAVE |
| `movement_type` | No V1 movement fact | Derived from day-over-day lifecycle_state diff | Derive during serving fact build (simple, deterministic) |
| `phone` | Only for contacted drivers in `loopcontrol_result_sync` | NULL for non-contacted | Fallback to `public.drivers.phone` during serving fact build |

### Prerequisites Checklist

| # | Prerequisite | Status |
|---|-------------|--------|
| 1 | `driver_state_snapshot` populated for target_date | ✅ `autonomous_tick` runs every 5 min |
| 2 | `program_eligibility_daily` populated | ✅ Same cascade |
| 3 | `rna_priority_fact` has latest scores | ✅ Scored on demand / daily |
| 4 | `loopcontrol_result_sync` has contact data | ✅ Synced on export |
| 5 | `impact_tracking` has measurement data | ✅ Populated on measurement window close |
| 6 | `assignment_queue` has latest queue state | ✅ Rebuilt every 5 min |
| 7 | `driver_lifecycle_daily` has 30d/90d metrics | ✅ Built by migration 214 (LG-ACT-1A) |
| 8 | Migration 219 (LG-PERF-1A indexes) applied | ⚠️ Pending `alembic upgrade head` |

### GO / NO-GO Verdict

**GO — The serving fact can be built today.**

All source tables exist. All fields have a source (with acceptable fallbacks). No fields are truly blocked. The gaps (driver_name, segment, sub_segment) can be addressed with fallback logic or accepted as NULL in MVP.

**Conditions for LG-EXP-1C (implementation):**
1. Migration 219 must be applied (`alembic upgrade head`)
2. `build_driver_explorer_fact()` must be registered in `autonomous_tick` cascade after `generate_all_serving_facts()`
3. The driver_name gap should be addressed by reading from `raw_yango.mv_driver_profiles_snapshot` or `public.drivers`

---

## TASK 8 — IMPLEMENTATION PLAN

### Phase Roadmap

```
LG-EXP-1C: SERVING FACT CREATION
    Create migration + writer + integrate into autonomous_tick
    ↓
LG-EXP-1D: ENDPOINT CREATION
    Create router + service + wire to DriverExplorerTab
    ↓
LG-EXP-1E: UI WIRING & CERTIFICATION
    Update DriverExplorerTab to consume new endpoint + columns
```

---

### LG-EXP-1C: SERVING FACT CREATION

| Aspect | Detail |
|--------|--------|
| **Objective** | Create `growth.yego_lima_driver_explorer_fact` table and populate it within the autonomous_tick cascade |
| **Scope** | Alembic migration + `build_driver_explorer_fact()` function + integration into autonomous_tick |
| **No touch** | No UI. No endpoints. No frontend. |
| **Risks** | (a) `rna_priority_fact` may not have latest scores at time of serving fact build → accept NULL. (b) `driver_lifecycle_daily` may not exist for all dates → fallback to `driver_state_snapshot.completed_orders_week`. |
| **Dependencies** | Migration 219 applied. `driver_lifecycle_daily` table created (migration 214). |
| **GO Criteria** | (1) Table exists in DB. (2) `build_driver_explorer_fact()` runs without error for a target_date. (3) Row count > 0. (4) `data_quality` column populated. |
| **Files to create** | `backend/alembic/versions/220_lg_exp_1c_driver_explorer_fact.py` |
| **Files to modify** | `backend/app/services/yego_lima_scheduler_service.py` (add step to autonomous_tick), new file `backend/app/services/driver_explorer_fact_service.py` |

### LG-EXP-1D: ENDPOINT CREATION

| Aspect | Detail |
|--------|--------|
| **Objective** | Create `GET /yego-lima-growth/driver-explorer` endpoint that reads from the serving fact |
| **Scope** | Router + service + contract validation |
| **No touch** | No UI. No serving fact builder changes. |
| **Risks** | (a) Serving fact may be stale if autonomous_tick hasn't run → endpoint returns `serving_or_missing()` pattern. (b) Filter parameters may not match serving fact indexes → test with EXPLAIN ANALYZE. |
| **Dependencies** | LG-EXP-1C completed (serving fact populated). |
| **GO Criteria** | (1) Endpoint returns valid JSON for target_date with drivers. (2) Filters (lifecycle, program, rna_band, search) work. (3) Response time <2s with filters. (4) Empty state when no drivers match. (5) Export endpoint works. |
| **Files to create** | `backend/app/services/yego_lima_driver_explorer_service.py`, new or extended router |
| **Files to modify** | `backend/app/routers/yego_lima_*.py` (add explorer route) |

### LG-EXP-1E: UI WIRING & CERTIFICATION

| Aspect | Detail |
|--------|--------|
| **Objective** | Wire DriverExplorerTab.jsx to the new endpoint. Populate real data in all columns. Certify. |
| **Scope** | Frontend only. DriverExplorerTab.jsx and SharedComponents. |
| **No touch** | No backend. No serving fact. No other tabs. |
| **Risks** | (a) Column names in serving fact may differ from expected field names → update fallback chain in JSX. (b) Date format differences → normalize in endpoint response. |
| **Dependencies** | LG-EXP-1D completed (endpoint live). |
| **GO Criteria** | (1) All MUST HAVE columns show real data (not '—'). (2) Filters work end-to-end. (3) Search works. (4) Export works. (5) No regressions in other tabs. (6) Build PASS. |
| **Files to modify** | `frontend/src/pages/lima-growth-ui1a/sections/DriverExplorerTab.jsx` |

---

### Execution Order & Parallelization

```
LG-EXP-1C ──→ LG-EXP-1D ──→ LG-EXP-1E
   (backend)     (backend)     (frontend)

Sequential: each phase depends on the previous.
No parallel work possible due to serving fact → endpoint → UI dependency chain.
```

### Total Estimated Scope

| Phase | Migrations | Backend Files | Frontend Files | Risk |
|-------|-----------|---------------|----------------|------|
| LG-EXP-1C | 1 new | 2 (1 new + 1 modified) | 0 | Low |
| LG-EXP-1D | 0 | 2 new | 0 | Low |
| LG-EXP-1E | 0 | 0 | 1 modified | Low |
| **Total** | **1** | **4** | **1** | **Low** |

---

## TASK 9 — CERTIFICATION

### LG_EXP_1B_DRIVER_EXPLORER_CANONICAL_CONTRACT

| Criterion | Status | Evidence |
|-----------|--------|----------|
| **TASK 0** — Governance validated | PASS | Control Foundation scope confirmed. No engine activation required. |
| **TASK 1** — Contract audit complete | PASS | 24-field canonical attribute matrix with source mapping for each field. |
| **TASK 2** — Source of truth matrix | PASS | 13 tables audited. 31 fields mapped to source columns. 5 gaps identified (all addressable). |
| **TASK 3** — Serving fact designed | PASS | `growth.yego_lima_driver_explorer_fact` defined. Grain: `(target_date, driver_profile_id)`. 55 columns across 10 layers. DDL provided. |
| **TASK 4** — Writer recommended | PASS | Option A: `autonomous_tick` cascade. Justified by V1 table coverage (74% READY), existing pattern compliance, governance alignment. |
| **TASK 5** — UI contract audited | PASS | 8 displayed columns classified (2 OK, 5 EMPTY, 1 OK). 20-field MUST/SHOULD/NICE classification. |
| **TASK 6** — Gap analysis | PASS | 31-field gap matrix: 23 READY (74%), 4 NEEDS_MAPPING, 1 NEEDS_SERVING, 0 BLOCKED. |
| **TASK 7** — GO / NO-GO | GO | All source tables exist. All fields have sources (with acceptable fallbacks). No blockers. |
| **TASK 8** — Implementation plan | PASS | 3-phase plan: LG-EXP-1C (serving fact), LG-EXP-1D (endpoint), LG-EXP-1E (UI). 6 files total. |
| **Contract canonical defined** | YES | `driver_id`, `lifecycle`, `program`, `rna_priority_band` as core. `segment`, `movement` with fallbacks. |
| **Grain defined** | YES | `(target_date, driver_profile_id)` |
| **Ownership defined** | YES | Control Foundation — Lima Growth Machine. Writer: autonomous_tick. Reader: explorer service. |

### Veredicto

**LG_EXP_1B_CERTIFIED — READY FOR IMPLEMENTATION**

Driver Explorer contract is canonically defined. The serving fact design is complete with sources, columns, grain, and ownership. The writer is selected and justified. The gap analysis shows 74% of fields are READY, 0% BLOCKED. The 3-phase implementation roadmap is defined with GO criteria for each phase.

**Next Phase:** LG-EXP-1C — Create `growth.yego_lima_driver_explorer_fact` migration and writer, integrate into autonomous_tick.

---

## APPENDIX A: KEY FILE PATHS REFERENCED

| File | Role |
|------|------|
| `ai_operating_system.md` | Governance rules |
| `ai_current_phase.md` | Current phase status |
| `backend/app/services/yego_lima_scheduler_service.py` | autonomous_tick() — lines 537-996 |
| `backend/app/services/yego_lima_v2_daily_pipeline_service.py` | V2 shadow pipeline — 1066 lines |
| `backend/app/services/yego_lima_serving_facts_service.py` | generate_all_serving_facts() — 223 lines |
| `backend/alembic/versions/170_yego_lima_state_based_loyalty_architecture.py` | driver_state_snapshot DDL |
| `backend/alembic/versions/214_yego_lima_driver_lifecycle.py` | driver_lifecycle_daily DDL |
| `backend/alembic/versions/217_yego_lima_rna_priority.py` | rna_priority_fact DDL |
| `backend/alembic/versions/184_yego_lima_loopcontrol_result_sync.py` | loopcontrol_result_sync DDL |
| `backend/alembic/versions/185_yego_lima_impact_tracking.py` | impact_tracking DDL |
| `backend/alembic/versions/219_lg_perf_1a_driver_explorer_index.py` | LG-PERF-1A indexes (pending) |
| `frontend/src/pages/lima-growth-ui1a/sections/DriverExplorerTab.jsx` | Current UI (broken contract) |
| `docs/lima_growth/LG_PERF_1A_DRIVER_EXPLORER_PERFORMANCE_CERTIFICATION.md` | Performance phase (completed) |

## APPENDIX B: GRAIN COMPARISON — V1 vs V2

| Attribute | V1 (production) | V2 (shadow) |
|-----------|----------------|-------------|
| Table prefix | `growth.yango_lima_*` | `growth.yego_lima_v2_*` |
| Driver ID column | `driver_profile_id` | `driver_id` |
| Date column | `snapshot_date` / `eligibility_date` | `target_date` |
| Populated by | `autonomous_tick()` | `run_lima_growth_v2_daily_pipeline()` |
| Frequency | Every 5 min (detects raw ahead) | Manual / on-demand |
| Lifecycle data | ✅ `lifecycle_state` | ✅ `lifecycle_stage` |
| Segment data | ❌ (only `historical_band`) | ✅ `segment`, `sub_segment` |
| Program data | ✅ `program_code`, `priority` | ✅ `program_code`, `priority_score` |
| Movement data | ⚠️ (trace tables) | ✅ `movement_type`, `from_state`, `to_state` |
| RNA data | ✅ (separate `rna_priority_fact`) | ❌ |
| Activity data | ✅ `completed_orders_week` | ✅ `trips`, `orders` |
| Contact data | ✅ (separate `loopcontrol_result_sync`) | ❌ |
| Impact data | ✅ (separate `impact_tracking`) | ❌ |

**Decision:** Use V1 as primary source (it's the production system). V2 segment/movement data can be NULL until V2 is promoted from shadow mode, or until equivalent columns are added to V1 tables.
