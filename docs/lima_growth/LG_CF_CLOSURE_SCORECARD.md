# LG_CF_CLOSURE_SCORECARD

**Phase:** LG-CF-RECOVERY-2A — Control Foundation Closure  
**Generated:** 2026-06-12  
**Criteria:** C1-C12 from LG_GOV_2A_GOVERNANCE_HARDENING_REPORT  

---

## MINIMUM VIABLE CLOSURE (C1-C7)

| # | Criterion | Status | Evidence | Score |
|---|-----------|--------|----------|-------|
| **C1** | All 7 Intelligence Dashboard tabs show fresh data (≤1 day stale) | **PASS** | All tabs confirmed fresh 06-12 in LG-CF-RECOVERY-1B real DB audit. | ✅ 1/1 |
| **C2** | No orphan tables with active consumers | **FAIL** | 2 orphans (`v2_taxonomy_daily`, `driver_movement_fact`) with 3+ active consumers. Taxonomía is populated externally but has no versioned writer. | ❌ 0/1 |
| **C3** | V2 pipeline integrated into automated scheduler | **FAIL** | V2 pipeline cron at 04:45 AM is failing silently. All 17 runs triggered manually via POST endpoint. Not in autonomous_tick. | ❌ 0/1 |
| **C4** | `data_quality` reflects actual row freshness (not table existence) | **FAIL** | `build_driver_explorer_fact()` checks `information_schema.tables` (table exists?), not `COUNT(*) WHERE date = target_date` (data exists?). | ❌ 0/1 |
| **C5** | `driver_explorer_fact` populated and serving UI | **FAIL** | Table does not exist in production (migration 220 not applied). Writer never executed. Endpoint returns `NO_SERVING_DATA`. | ❌ 0/1 |
| **C6** | Health endpoint returns HEALTHY/DEGRADED when data is fresh | **FAIL** | `/growth/health` returns CRITICAL (SLA violations in serving_freshness_fact) even though all tables have 06-12 data. | ❌ 0/1 |
| **C7** | 0 false-positive freshness signals | **FAIL** | `operational-date` reports `is_fresh: true` but ignores intelligence tables. `driver_state_snapshot` marked BROKEN in health but has 06-12 data. | ❌ 0/1 |

**Minimum Viable Closure: 1/7 (14%)**

---

## FULL CLOSURE (C8-C12)

| # | Criterion | Status | Evidence | Score |
|---|-----------|--------|----------|-------|
| **C8** | All writers versioned and in repository | **FAIL** | `v2_taxonomy_daily` populated by external process. `driver_movement_fact` populated by one-shot SQL. Both have NO versioned writer in the repository. | ❌ 0/1 |
| **C9** | All writers integrated into automated scheduler (≥80%) | **FAIL** | 18/42 (43%) auto-scheduled. Target: ≥80% (34/42). Gap: 16 writers. | ❌ 0/1 |
| **C10** | 90-day retention pruning active | **FAIL** | Not implemented. Explorer fact does not exist. No pruning strategy for any growth.* table. | ❌ 0/1 |
| **C11** | Legacy tables fully deprecated (no consumers) | **FAIL** | `driver_taxonomy_daily` still read by legacy Segments path. `driver_segment_snapshot` still read by actionable lists. | ❌ 0/1 |
| **C12** | DATA HEALTH + SLA HEALTH endpoints live | **FAIL** | Designed in LG_GOV_2A_HEALTH_CONTRACT_V2. Not implemented. | ❌ 0/1 |

**Full Closure: 0/5 (0%)**

---

## OVERALL SCORECARD

| Tier | Criteria | Passed | Total | Percentage |
|------|----------|--------|-------|------------|
| Minimum Viable | C1-C7 | 1 | 7 | **14%** |
| Full Closure | C8-C12 | 0 | 5 | **0%** |
| **Combined** | **C1-C12** | **1** | **12** | **8%** |

---

## CLOSURE GAP ANALYSIS

### What Is Already Closed (1/12)

| # | Criterion | Why It Passes |
|---|-----------|---------------|
| C1 | Tabs show fresh data | Confirmed by real DB audit: all 9/10 source tables have 06-12 data. V2 pipeline runs manually and successfully. |

### What Is Close to Closure (work started, LG-EXP phases completed)

| # | Criterion | Progress | Remaining Work |
|---|-----------|----------|---------------|
| C5 | Explorer fact populated | LG-EXP-1B (contract), LG-EXP-1C (governance), LG-EXP-1D (writer), LG-EXP-1E (endpoint + UI) — ALL COMPLETE. | Apply migration 220. Run first build. Enable feature flag. |
| C2 | No orphan tables | Orphan audit complete (LG_GOV_2A_ORPHAN_REGISTRY). Writers exist for V2 shadow equivalents. | Create versioned writer for `v2_taxonomy_daily`. Migrate `driver_movement_fact` consumers to `v2_movement_fact`. |
| C3 | V2 pipeline automated | V2 pipeline functional (17 manual runs, all SUCCESS). Code ready. | Fix 04:45 cron or add to autonomous_tick. |
| C6 | Health endpoint honest | Contract designed (DATA HEALTH vs SLA HEALTH). | Implement DATA HEALTH endpoint. |
| C7 | No false positives | Contradictions documented (LG_HEALTH_V2_RECONCILIATION). | Extend `detect_latest_closed_data_date()` to intelligence tables. |

### What Needs Full Implementation

| # | Criterion | Gap |
|---|-----------|-----|
| C4 | data_quality contract | Writer uses table existence check. Needs row count check. Simple fix (<10 lines). |
| C8 | 100% versioned writers | 2 writers missing. Need to create them. |
| C9 | 80% automated scheduling | 16 manual writers. Must integrate V2 pipeline (covers 9). RNA, effectiveness, explorer = 3 more. |
| C10 | Retention pruning | Not started. Simple DELETE query per table. |
| C11 | Legacy deprecation | 2 legacy tables. Migrate consumers, then DROP. |
| C12 | Health V2 endpoints | Spec complete. 3 new read-only endpoints. |

---

## ESTIMATED EFFORT TO CLOSE

### LG-CF-RECOVERY-2 (Minimum Viable Closure → C1-C7 all PASS)

| Step | Criterion | Effort | Type |
|------|-----------|--------|------|
| Create versioned taxonomy writer | C2 | 1 new service file | Backend |
| Migrate movement_fact consumers | C2 | 1 modified service | Backend |
| Add V2 pipeline to autonomous_tick | C3 | 5 lines in scheduler | Backend |
| Fix data_quality check | C4 | 10 lines in writer | Backend |
| Apply migration 220 + build fact | C5 | 1 alembic command + 1 script run | Ops |
| Enable feature flag | C5 | 1 env var | Ops |
| Implement DATA HEALTH endpoint | C6, C7 | 1 new service + 1 new endpoint | Backend |
| Extend freshness detection | C7 | 5 lines in refresh service | Backend |

**Total LG-CF-RECOVERY-2: ~3 new files, ~5 modified files, 2 ops commands.**

### LG-CF-RECOVERY-3 (Full Closure → C8-C12 all PASS)

| Step | Criterion | Effort | Type |
|------|-----------|--------|------|
| Create missing versioned writers | C8 | 2 new services | Backend |
| Integrate remaining writers into scheduler | C9 | Modify scheduler cascade | Backend |
| Implement retention pruning | C10 | 1 new maintenance script | Backend |
| Migrate legacy consumers | C11 | 2 modified services | Backend |
| Implement SLA HEALTH + SYSTEM HEALTH | C12 | 2 new endpoints | Backend |

**Total LG-CF-RECOVERY-3: ~5 new files, ~4 modified files.**

---

## CLOSURE PERCENTAGE TODAY

**8% (1/12 criteria passed)**

After LG-CF-RECOVERY-2: **58% (7/12)** — minimum viable closure achieved.
After LG-CF-RECOVERY-3: **100% (12/12)** — full closure achieved.

---

## DECISION GATE

**Question:** Can Control Foundation be declared closed today?

**Answer:** NO. 1/12 criteria passed (8%). 6 of 7 minimum viable criteria fail.

**Question:** What is the single largest gap?

**Answer:** C5 — `driver_explorer_fact` not deployed. This blocks the canonical Explorer serving chain and requires the simplest fix (apply migration + run script). But it depends on C2-C4 being addressed first (writers, scheduler, quality).

**Question:** What can be closed with zero code changes?

**Answer:** Only C1 (tabs show fresh data). Everything else requires code changes or operations work.
