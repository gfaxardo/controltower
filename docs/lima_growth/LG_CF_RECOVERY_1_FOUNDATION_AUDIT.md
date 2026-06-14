# LG_CF_RECOVERY_1_FOUNDATION_AUDIT

**Phase:** LG-CF-RECOVERY-1 — Control Foundation Hardening  
**Generated:** 2026-06-12  
**Scope:** Full freshness + lineage audit of all tables feeding Intelligence Dashboard  
**Verdict:** `LG_CF_RECOVERY_1_NOGO — Control Foundation NO puede considerarse cerrada`

---

## 0. FRESHNESS MATRIX

### 9 Tables — Bottom-Line Health

| # | Table | Rows Total | Max Date | Gap (days) | Writer | Scheduler | Consumer | Health |
|---|-------|-----------|----------|------------|--------|-----------|----------|--------|
| 1 | `growth.yango_lima_driver_state_snapshot` | 166,712 | **2026-06-12** | 0 | `build_driver_state_snapshot()` | `autonomous_tick()` | Overview, DriverState, Explorer | **HEALTHY** |
| 2 | `growth.yango_lima_program_eligibility_daily` | 254,560 | **2026-06-12** | 0 | `build_program_eligibility()` | `autonomous_tick()` | Programs, Overview, Explorer | **HEALTHY** |
| 3 | `growth.yego_lima_driver_lifecycle_daily` | 273,908 | **2026-06-10** | **2** | `build_lifecycle_daily()` in lifecycle_service | ❌ **Manual only** (`POST /lifecycle/build`) | Overview, Explorer | **DEGRADED** |
| 4 | `growth.yego_lima_v2_taxonomy_daily` | 273,908 | **2026-06-10** | **2** | ❌ **ORPHAN — no writer in code** | ❌ None | Segments, Explorer (COALESCE) | **BROKEN** |
| 5 | `growth.yego_lima_v2_program_daily` | 273,908 | **2026-06-10** | **2** | `_build_program_v2_daily()` | V2 cron 04:45 (failing) | Programs | **DEGRADED** |
| 6 | `growth.yego_lima_v2_movement_fact` | **0** | NULL | ∞ | `_build_movement_fact()` | V2 cron 04:45 (failing) | Movement Analytics | **BROKEN** |
| 7 | `growth.rna_priority_fact` | 888 | 2026-06-12 | 0 | `build_rna_priority()` | Manual (recovered LG-RNA-1B) | RNA Tab, Explorer | **HEALTHY** |
| 8 | `growth.program_effectiveness_fact` | 34 | 2026-06-12 | 0 | `_build_effectiveness_facts()` | Recovered (LG-IMP-1C) | Effectiveness Tab | **HEALTHY** |
| 9 | `growth.yego_lima_driver_explorer_fact` | 0 (not yet built) | — | — | `build_driver_explorer_fact()` | Not activated (LG-EXP-1D) | Driver Explorer | **NOT DEPLOYED** |

### Summary

| Health | Count | Tables |
|--------|-------|--------|
| **HEALTHY** | 4 | `driver_state_snapshot`, `program_eligibility_daily`, `rna_priority_fact`, `program_effectiveness_fact` |
| **DEGRADED** | 2 | `driver_lifecycle_daily` (2d stale), `v2_program_daily` (2d stale) |
| **BROKEN** | 2 | `v2_taxonomy_daily` (orphan), `v2_movement_fact` (0 rows) |
| **NOT DEPLOYED** | 1 | `driver_explorer_fact` (migration created, not populated) |

---

## 1. DRIVER LIFECYCLE — ROOT CAUSE ANALYSIS

### Diagnosis: **D — Cron desconectado** (primary) + **E — Pipeline desacoplado** (secondary)

### Evidence

| Hypothesis | Evidence | Verdict |
|-----------|----------|---------|
| A) Scheduler no ejecuta | `autonomous_tick()` runs every 5 min, 718 ticks, 710 success. Last: 2026-06-12 14:55. Scheduler IS alive. | **REFUTED** |
| B) Writer roto | `build_lifecycle_daily()` in `yego_lima_lifecycle_service.py:394` compiles and runs. Only error is stale source data. Writer IS functional. | **REFUTED** |
| C) Fuente insuficiente | Source is `growth.yego_lima_driver_activity_event` (migration 214). 273,908 rows up to 06-10. Source HAS data. | **REFUTED** |
| **D) Cron desconectado** | `_build_lifecycle_daily()` (V2 step 4) is scheduled via cron at 04:45 AM. Generated **0 log entries** for 06-11/12. APScheduler job `lima_growth_v2_daily_pipeline` exists but did not fire. | **CONFIRMED** |
| **E) Pipeline desacoplado** | `autonomous_tick()` cascade includes 4 builders + `run_daily_refresh()`. `build_lifecycle_daily()` is NOT in the cascade. It is ONLY triggered by the separate 04:45 cron job, which failed silently. | **CONFIRMED** |

### RCA Summary

```
build_lifecycle_daily()  ── written in lifecycle_service.py:394
                               ↓
                          Triggered ONLY via: POST /yego-lima-growth/lifecycle/build
                                               OR
                                               V2 cron job at 04:45 AM
                               ↓
                          autonomous_tick() ← DOES NOT CALL IT
                          run_daily_refresh() ← DOES NOT CALL IT
                               ↓
                          RESULT: stale since 2026-06-10
```

---

## 2. TAXONOMY V2 — LINEAGE

### Table: `growth.yego_lima_v2_taxonomy_daily`

### Writer Status: **ORPHAN** (LG_GOV_1A_ORPHAN_WRITER_AUDIT confirmed)

| Aspect | Finding |
|--------|---------|
| Writer in code | **NONE** — zero `INSERT INTO yego_lima_v2_taxonomy_daily` in entire repo |
| External writer | One-shot SQL/ETL executed 2026-06-10 for dates 06-07 to 06-10 |
| V2 shadow builder | `_build_taxonomy_v2_daily()` writes to `yego_lima_v2_taxonomy_daily` (SHADOW) — NOT the production table |
| Scheduler | V2 cron 04:45 AM — did NOT execute for 06-11/12 |
| Consumer | `yego_lima_export_service.py:43` — COALESCE enrichment for Driver Explorer export |

### Lineage (actual, not designed)

```
driver_lifecycle_daily ── (STALE at 06-10)
       ↓
EXTERNAL ETL (unversioned, one-shot SQL script)
       ↓
yego_lima_v2_taxonomy_daily ── (STALE at 06-10)
       ↓
Consumers:
  ├── yego_lima_export_service (COALESCE)
  ├── yego_lima_explainability_service
  └── yego_lima_rna_priority_service
```

### Dependency on Lifecycle

YES. The taxonomy table mirrors lifecycle_daily row counts exactly (68,479/68,479/68,477/68,473 for 06-07/08/09/10). When lifecycle_daily is stale, taxonomy is stale by definition — the external ETL reads from lifecycle_daily.

---

## 3. MOVEMENT FACT — AUDIT

### Table: `growth.yego_lima_v2_movement_fact`

| Aspect | Finding |
|--------|---------|
| Writer (V2 shadow) | `_build_movement_fact()` in `yego_lima_v2_daily_pipeline_service.py:663` — writes to shadow table, reads from `state_transition_trace` + `program_decision_trace` |
| Writer (production) | **NONE** — `growth.driver_movement_fact` is a SEPARATE orphan table (68,473 rows, external writer) |
| Frequency | V2 cron 04:45 AM — did NOT execute for 06-11/12 |
| Coverage | 0 rows in `yego_lima_v2_movement_fact` (never populated). `driver_movement_fact` has 68,473 rows but is orphan. |
| Consumers | `yego_lima_movement_analytics_service.py` (stats, matrix, winners/losers) |
| Fallback | `build_driver_explorer_fact()` derives movement from day-over-day lifecycle_state diff |

### Why 0 rows?

```
state_transition_trace  ── EMPTY (no trace data generated)
program_decision_trace  ── EMPTY (no decision trace data)
       ↓
_build_movement_fact()  ── reads from traces → finds 0 rows
       ↓                          fallback to taxonomy/program diff → taxonomy also stale
yego_lima_v2_movement_fact  ── 0 rows
```

The dependency chain is: `driver_activity_event → lifecycle_daily → taxonomy_daily → program_daily → movement_fact`. Every link is broken.

---

## 4. DATA QUALITY GOVERNANCE

### Current State in `build_driver_explorer_fact()` (LG-EXP-1D)

```python
available_count = sum([1 for x in [rna_ok, lf_ok, tax_ok, mov_ok, lc_ok, imp_ok, aq_ok] if x])
data_quality = "COMPLETE" if available_count >= 7 else "PARTIAL"
```

### Problem

`data_quality` checks **table existence** (`information_schema.tables`) — NOT row freshness, NOT data recency, NOT row counts per target_date.

In current production:
- All 7 supplementary tables **exist** → `available_count = 7` → `data_quality = "COMPLETE"`
- But 3 of those tables are **stale** (2d gap) and 2 are **empty** (0 rows)

### Correct Contract Design

```python
def _compute_data_quality(cur, target_date):
    checks = {
        "rna_priority_fact": "SELECT COUNT(*) FROM growth.rna_priority_fact",
        "lifecycle_daily": f"SELECT COUNT(*) FROM growth.yego_lima_driver_lifecycle_daily WHERE snapshot_date = %(d)s",
        "taxonomy_v2": f"SELECT COUNT(*) FROM growth.yego_lima_v2_taxonomy_daily WHERE target_date = %(d)s",
        "movement_fact": f"SELECT COUNT(*) FROM growth.yego_lima_v2_movement_fact WHERE target_date = %(d)s",
        "loopcontrol": "SELECT COUNT(*) FROM growth.yego_lima_loopcontrol_result_sync",
        "impact_tracking": "SELECT COUNT(*) FROM growth.yego_lima_impact_tracking",
        "assignment_queue": "SELECT COUNT(*) FROM growth.yango_lima_assignment_queue",
    }

    sources_fresh = 0
    sources_total = 0
    for name, sql in checks.items():
        try:
            cur.execute(sql, {"d": target_date})
            count = cur.fetchone()[0] or 0
            if count > 0:
                sources_fresh += 1
            sources_total += 1
        except Exception:
            pass

    if sources_fresh == sources_total and sources_total >= 5:
        return "COMPLETE"
    elif sources_fresh >= 3:
        return "DEGRADED"
    elif sources_fresh >= 1:
        return "STALE"
    else:
        return "BROKEN"
```

### New Classification

| Quality | Meaning | Condition |
|---------|---------|-----------|
| `COMPLETE` | All 5+ sources have data for target_date | sources_fresh = sources_total ≥ 5 |
| `DEGRADED` | 3+ sources have data | sources_fresh ≥ 3 |
| `STALE` | 1-2 sources have data | sources_fresh ≥ 1 |
| `BROKEN` | 0 sources have data | sources_fresh = 0 |

**This is a contractual change — NOT implemented yet. Part of LG-CF-RECOVERY-2.**

---

## 5. HEALTH REGISTRY AUDIT

### Why `/growth/health` returns CRITICAL

The health endpoint checks `growth.yego_lima_v2_freshness_registry` which tracks 9 shadow components. Any component with `freshness = "BROKEN"` or `"STALE" for >72h` triggers CRITICAL.

In current state:
- `v2_movement_fact` = BROKEN (0 rows, never populated) → **CRITICAL**
- `v2_taxonomy_daily` = STALE since 06-10 (likely >72h threshold hit) → **CRITICAL**
- `v2_lifecycle_daily` = STALE → DEGRADED

### Classification

| Diagnosis | Verdict |
|-----------|---------|
| Falso positivo | **REFUTED** — the health system is CORRECT. Tables are genuinely broken/stale. |
| Stale registry | **PARTIAL** — the freshness_registry V2 is correct but reflects shadow tables, not production tables. |
| Writer roto | **CONFIRMED** — the V2 cron job failed to execute. |
| Consumer roto | **NOT APPLICABLE** — consumers are correct; the issue is upstream. |

### The CRITICAL status is REAL and CORRECT.

The fact that operational tabs show data doesn't mean the system is healthy — it means the tabs are reading from cached/serving data while the underlying intelligence pipeline is broken. This is exactly what the health endpoint is designed to detect.

---

## 6. END-TO-END LINEAGE

### Complete Chain (all tables)

```
RAW INGESTION
  │
  ├── raw_yango.orders_raw        ← ingest_recent_orders()  [autonomous_tick, every 5 min]
  │
  ▼
OPERATIONAL LAYER (autonomous_tick cascade)
  │
  ├── driver_state_snapshot        ← build_driver_state_snapshot()       [HEALTHY, 06-12]
  ├── program_eligibility_daily    ← build_program_eligibility()          [HEALTHY, 06-12]
  ├── daily_opportunity_list       ← build_daily_opportunity_lists()     [HEALTHY]
  ├── prioritized_opportunity      ← build_prioritized_opportunities()   [HEALTHY]
  ├── assignment_queue             ← run_daily_refresh()                 [HEALTHY]
  ├── loopcontrol_result_sync      ← sync_assignment_queue_to_control()  [STALE, 10 rows]
  └── serving_fact (8 types)       ← generate_all_serving_facts()        [HEALTHY, 06-12]
  │
  ▼ ── GAP: NO BUILDER HERE ──
  │
INTELLIGENCE LAYER (NOT in autonomous_tick)
  │
  ├── driver_activity_event        ← migration 214 (table exists, populated by V1?)    [?]
  ├── driver_lifecycle_daily       ← build_lifecycle_daily() [MANUAL ONLY]              [DEGRADED, 06-10]
  ├── driver_activity_daily        ← _build_activity_daily() [V2 cron 04:45, FAILING]  [STALE]
  ├── driver_activity_weekly       ← _build_activity_weekly() [V2 cron 04:45, FAILING]  [STALE]
  ├── driver_activity_monthly      ← _build_activity_monthly() [V2 cron, FAILING]      [STALE]
  ├── v2_lifecycle_daily           ← _build_lifecycle_daily() [V2 cron, FAILING]       [STALE]
  ├── v2_taxonomy_daily            ← EXTERNAL ETL (ORPHAN)                             [BROKEN, 06-10]
  ├── v2_program_daily             ← _build_program_v2_daily() [V2 cron, FAILING]      [DEGRADED, 06-10]
  ├── v2_movement_fact             ← _build_movement_fact() [V2 cron, FAILING]         [BROKEN, 0 rows]
  └── v2_effectiveness_fact        ← _build_effectiveness_facts() [V2 cron, FAILING]   [EMPTY, 0 rows]
  │
  ▼
SPECIAL LAYER (recovered / manual)
  │
  ├── rna_priority_fact            ← build_rna_priority() [RECOVERED LG-RNA-1B]         [HEALTHY, 888 rows]
  ├── program_effectiveness_fact   ← _build_effectiveness_facts() [RECOVERED LG-IMP-1C] [HEALTHY, 34 rows]
  └── rna_pilot_measurement_fact   ← migration 218 (exists, populated?)                [?]
  │
  ▼
SERVING LAYER
  │
  └── driver_explorer_fact         ← build_driver_explorer_fact() [LG-EXP-1D, NOT ACTIVATED]
  │
  ▼
UI
  ├── Overview                     ← driver_state_snapshot + serving_fact               [HEALTHY]
  ├── Programs                     ← program_eligibility_daily + serving_fact            [HEALTHY]
  ├── Segments                     ← v2_taxonomy_daily [BROKEN — reads orphan]           [DEGRADED]
  ├── Movement                     ← driver_movement_fact [ORPHAN] + movement_analytics  [DEGRADED]
  ├── RNA                          ← rna_priority_fact [RECOVERED] + yango_loyalty      [DEGRADED]
  ├── Effectiveness                ← program_effectiveness_fact [RECOVERED]              [HEALTHY]
  └── Driver Explorer              ← /drivers/activity-summary (legacy) or explorer_fact [TRANSITIONING]
```

### Markers

| Symbol | Meaning | Count |
|--------|---------|-------|
| `HEALTHY` | Table fresh, writer active, scheduler functional | 6 |
| `DEGRADED` | Table exists with data but stale (1-2 days behind) | 5 |
| `BROKEN` | Table has 0 rows or writer is orphan/unversioned | 4 |
| `EMPTY` | Table exists with 0 rows | 1 |
| `?` | Status unknown | 2 |
| `TRANSITIONING` | Being migrated from legacy to serving fact | 1 |

---

## 7. BUILD

| Build | Result |
|-------|--------|
| `python -m compileall backend\app` | PASS |
| `npm run build` | PASS |

---

## 8. SCHEDULER MATRIX

### Active Schedulers

| Job | Type | Interval | Registered | Last Executed | Status |
|-----|------|----------|------------|---------------|--------|
| `autonomous_tick` | APScheduler | Every 5 min | `main.py:370` | 2026-06-12 14:55 | **ACTIVE** (718 ticks, 710 success) |
| `lima_growth_v2_daily_pipeline` | APScheduler cron | 04:45 AM daily | `main.py:405` | **NOT EXECUTED 06-11/12** | **FAILING SILENTLY** |

### What Each Scheduler Builds

| Job | Tables Built |
|-----|-------------|
| `autonomous_tick` | `driver_state_snapshot`, `program_eligibility_daily`, `daily_opportunity_list`, `prioritized_opportunity`, `assignment_queue`, `loopcontrol_result_sync`, `serving_fact`, `intraday_signals`, `driver_history_daily` |
| `lima_growth_v2_daily_pipeline` | `v2_activity_daily`, `v2_activity_weekly`, `v2_activity_monthly`, `v2_lifecycle_daily`, `v2_taxonomy_daily`, `v2_program_daily`, `v2_movement_fact`, `v2_observability_fact`, `v2_effectiveness_fact` |

### Gap

Tables NOT covered by any scheduler:
- `growth.yego_lima_driver_lifecycle_daily` (production) — only manual via POST endpoint
- `growth.yego_lima_v2_taxonomy_daily` (production/orphan) — NO writer anywhere
- `growth.driver_movement_fact` (production/orphan) — NO writer anywhere

---

## 9. WRITER MATRIX

| Table | Writer Function | File | Trigger | Status |
|-------|----------------|------|---------|--------|
| `yango_lima_driver_state_snapshot` | `build_driver_state_snapshot()` | `yego_lima_driver_state_service.py` | `autonomous_tick` | **ACTIVE** |
| `yango_lima_program_eligibility_daily` | `build_program_eligibility()` | `yego_lima_program_eligibility_service.py` | `autonomous_tick` | **ACTIVE** |
| `yego_lima_driver_lifecycle_daily` | `build_lifecycle_daily()` | `yego_lima_lifecycle_service.py:394` | Manual (POST) only | **MANUAL** |
| `yego_lima_v2_taxonomy_daily` | ❌ **ORPHAN** | — | — | **NONE** |
| `yego_lima_v2_program_daily` | `_build_program_v2_daily()` | `yego_lima_v2_daily_pipeline_service.py:598` | V2 cron 04:45 | **FAILING** |
| `yego_lima_v2_movement_fact` | `_build_movement_fact()` | `yego_lima_v2_daily_pipeline_service.py:663` | V2 cron 04:45 | **FAILING** |
| `rna_priority_fact` | `build_rna_priority()` | `yego_lima_rna_priority_service.py` | Manual (recovered) | **RECOVERED** |
| `program_effectiveness_fact` | `_build_effectiveness_facts()` | `yego_lima_v2_daily_pipeline_service.py` | Recovered LG-IMP-1C | **RECOVERED** |
| `driver_explorer_fact` | `build_driver_explorer_fact()` | `yego_lima_driver_explorer_fact_service.py` | Not activated | **OFF** |

---

## 10. CONSUMER MATRIX

| Table | Consumers | Consumer Health |
|-------|-----------|----------------|
| `driver_state_snapshot` | OverviewTab, DriverStateSummary, Explorer (export), ProgramsTab | OK — reading fresh data |
| `program_eligibility_daily` | ProgramsTab, Overview, Explorer (export) | OK — reading fresh data |
| `driver_lifecycle_daily` | Overview, Explorer (export), v2_lifecycle_daily | DEGRADED — reading stale data (06-10) |
| `v2_taxonomy_daily` | SegmentsTab, Explorer (COALESCE), Explainability, RNA priority | BROKEN — reading stale data + orphan |
| `v2_program_daily` | ProgramsTab | DEGRADED — reading stale data (06-10) |
| `v2_movement_fact` | Movement Analytics (stats, matrix, winners/losers) | BROKEN — reading 0 rows |
| `rna_priority_fact` | RNATab, Explorer | OK — recovered, 888 rows |
| `program_effectiveness_fact` | EffectivenessTab | OK — recovered, 34 rows |
| `driver_explorer_fact` | DriverExplorerTab (future) | NOT YET — endpoint created but serving fact not populated |

---

## 11. RCA — SUMMARY OF ALL ROOT CAUSES

### RCA #1: Intelligence layer decoupled from operational layer

**Root cause:** `autonomous_tick()` builds the operational layer (snapshot → eligibility → queue) but does NOT call lifecycle/taxonomy/movement builders. These are only triggered by a separate cron job that is failing silently.

**Impact:** 5 tables stale/broken. Intelligence Dashboard tabs (Segments, Movement) reading degraded data.

### RCA #2: Two orphan tables with NO writer

**Root cause:** `growth.yego_lima_v2_taxonomy_daily` and `growth.driver_movement_fact` were populated by an external one-shot ETL script (not in the repo). Reader services were written AFTER data existed, assuming the data would continue being generated. The writer never existed in version control.

**Impact:** These tables will NEVER refresh. The taxonomy_daily is frozen at 06-10. The movement_fact will accumulate data only if the external ETL runs again.

### RCA #3: V2 cron job failing silently

**Root cause:** `lima_growth_v2_daily_pipeline` (cron 04:45 AM) generated 0 log entries for 06-11 and 06-12. The job is registered in `main.py:405` but did not execute. No error logs, no alerts. The failure is silent.

**Impact:** The V2 shadow pipeline (which SHOULD populate lifecycle, taxonomy, program, movement, effectiveness) did not run. The production tables that depend on V2 reads are stale.

### RCA #4: data_quality reports false COMPLETE

**Root cause:** `build_driver_explorer_fact()` checks table existence (`information_schema.tables`) instead of row counts per target_date.

**Impact:** The serving fact can report `data_quality = "COMPLETE"` even when source tables are stale/empty. Operators see no degradation signal.

### RCA #5: operational-date freshness is a false positive

**Root cause:** `detect_latest_closed_data_date()` only checks `driver_state_snapshot.snapshot_date` and `program_eligibility_daily.eligibility_date`. Both are fresh (06-12). The system considers itself caught up.

**Impact:** `autonomous_tick()` enters NOOP_CAUGHT_UP state because it doesn't know lifecycle/taxonomy/movement are stale. The system is in false-normal state.

---

## 12. GO / NO-GO

### The Question

**¿Control Foundation de Lima Growth puede considerarse cerrada?**

### Verdict: **NO-GO**

### Evidence

| # | Criterion | Required for Closure | Actual | Gap |
|---|-----------|---------------------|--------|-----|
| 1 | All Intelligence Dashboard tabs reading fresh data | Closure | 2/7 tabs reading stale/broken (Segments, Movement) | **FAIL** |
| 2 | All source-of-truth tables have active writers | Closure | 2 orphan tables, 3 manual-only writers, 1 cron failing silently | **FAIL** |
| 3 | All writers integrated into autonomous_tick cascade | Closure | 0 of 3 intelligence-layer writers in cascade | **FAIL** |
| 4 | No false-positive freshness signals | Closure | `operational_date` reports `is_fresh: true` while 5 tables are stale | **FAIL** |
| 5 | Health endpoint returns HEALTHY or DEGRADED (not CRITICAL) | Closure | `/growth/health` returns CRITICAL | **FAIL** |
| 6 | `data_quality` reflects actual data freshness | Closure | Reports COMPLETE based on table existence, not row counts | **FAIL** |
| 7 | Serving fact chain complete (RAW → SNAPSHOT → SERVING → UI) | Closure | Explorer fact not populated, not integrated into cascade | **FAIL** |
| 8 | No unversioned external dependencies for data generation | Closure | 2 orphan tables populated by external ETL | **FAIL** |

**8 of 8 closure criteria fail. Control Foundation cannot be closed.**

### What's Missing for Closure

| # | Action | Phase |
|---|--------|-------|
| 1 | Add `build_lifecycle_daily()` to `autonomous_tick()` cascade | LG-CF-RECOVERY-2 |
| 2 | Create writer for `v2_taxonomy_daily` (replace orphan ETL with versioned Python builder) and integrate into cascade | LG-CF-RECOVERY-2 |
| 3 | Create writer for `movement_fact` (replace orphan ETL with versioned Python builder) and integrate into cascade | LG-CF-RECOVERY-2 |
| 4 | Fix V2 cron job scheduling (ensure it executes daily) OR merge V2 steps into autonomous_tick | LG-CF-RECOVERY-2 |
| 5 | Fix `data_quality` contract in `build_driver_explorer_fact()` to check row counts | LG-CF-RECOVERY-2 |
| 6 | Backfill lifecycle/taxonomy/movement for 2026-06-11 and 2026-06-12 | LG-CF-RECOVERY-2 |
| 7 | Activate `build_driver_explorer_fact()` in cascade (feature flag → ON) | LG-CF-RECOVERY-2 |
| 8 | Add lifecycle/taxonomy/movement freshness to `detect_latest_closed_data_date()` | LG-CF-RECOVERY-3 |
| 9 | Wire DriverExplorerTab to the new endpoint (already done in LG-EXP-1E, pending deployment) | Deploy |

---

## VEREDICTO FINAL

**LG_CF_RECOVERY_1_NOGO**

Control Foundation de Lima Growth **NO** puede considerarse cerrada. La cadena de inteligencia (lifecycle → taxonomy → movement) está desacoplada del scheduler operacional. Dos tablas son huérfanas (sin writer versionado). La pipeline V2 está fallando silenciosamente. El health endpoint detecta correctamente el estado CRITICAL, pero el operational-date reporta un falso positivo de frescura. La serving fact del Driver Explorer existe pero no está poblada ni integrada.

**La deuda operacional es real y documentada. Se requiere LG-CF-RECOVERY-2 para cerrar los gaps.**

---

## APPENDIX: EVIDENCE REFERENCES

| Evidence | Source |
|----------|--------|
| Freshness rowcounts | `LG_FIX_1A_FACT_ROWCOUNT_AUDIT.md` (2026-06-12T19:36) |
| Pipeline root cause | `LG_FIX_1B1_PIPELINE_ROOT_CAUSE_REPORT.md` (2026-06-12T20:00) |
| Orphan writer confirmation | `LG_GOV_1A_ORPHAN_WRITER_AUDIT.md` |
| Historical ownership timeline | `LG_GOV_1B_HISTORICAL_OWNERSHIP_AUDIT.md` |
| Scheduler status (autonomous_tick) | `yego_lima_scheduler_service.py:537-996` |
| V2 pipeline status | `yego_lima_v2_daily_pipeline_service.py` (1066 lines) |
| Health endpoint implementation | `serving_operability_service.py`, `serving_freshness_audit_service.py` |
| data_quality logic (current) | `yego_lima_driver_explorer_fact_service.py:112-113` |
| Effectiveness recovery | `LG_IMP_1C_PRODUCTION_RECOVERY_CERTIFICATION.md` |
| RNA recovery | `LG_RNA_1B_PRODUCTION_RECOVERY_CERTIFICATION.md` |
| Canonical lineage cert | `LG_LIN_1A_CANONICAL_DATA_CONTRACT.md` |
