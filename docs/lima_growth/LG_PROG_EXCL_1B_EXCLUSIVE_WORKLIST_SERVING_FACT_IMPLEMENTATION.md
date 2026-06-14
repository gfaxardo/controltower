# LG-PROG-EXCL-1B — Exclusive Worklist Serving Fact Implementation

**Date:** 2026-06-13
**Phase:** LG-PROG-EXCL-1B (Serving Fact + Canonical Writer)
**Mode:** IMPLEMENTATION
**Predecessor:** `LG_PROG_EXCL_1A1_OPERATOR_DECISIONS_CONTRACT_PATCH.md`
**Status:** IMPLEMENTED — 25/25 tests pass

---

## 1. Executive Decision

### LG_PROG_EXCL_1B_PASS

**Serving fact created. Canonical writer implemented. Freshness registered. Tick cascade integrated.**

The `growth.yango_lima_exclusive_driver_worklist_daily` table materializes the V1 exclusive universe contract. Every driver gets exactly 1 `assigned_universe_v1` per `generated_date`. Cemetery is not exported to daily Control Loop. Productivity bands use `weekly_trips` (current), not `best_week_12w` (historical).

---

## 2. Pre-check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation |
| 2 | Fase | LG-PROG-EXCL-1B |
| 3 | Contrato | Exclusive Dynamic Lists V1, Production Cutover, North Star |
| 4 | Tablas | New: `growth.yango_lima_exclusive_driver_worklist_daily`. Read sources: driver_state_snapshot, driver_explorer_fact, driver_history_daily. |
| 5 | Writer | New canonical: `refresh_exclusive_driver_worklist_daily()` |
| 6 | Freshness | Registered in chain + registry + serving_freshness_fact. SLA: 24h. |
| 7 | Endpoint/UI | None yet. Read-only summary + rows functions created. |
| 8 | Legacy | No activation. |
| 9 | Riesgos | See Section 11. |
| 10 | Rollback | DROP table. Revert writer. Remove registrations. |
| 11 | ACTIVE_SCOPE_CONTRACT | IN SCOPE. |
| 12 | North Star Test | PASS. |
| 13 | Scope Escalation | IMPLEMENTATION AUTHORIZED. |

---

## 3. Migration

**File:** `backend/alembic/versions/222_lg_prog_excl_1b_exclusive_worklist.py`
**Down revision:** `221_ov2_d1_serving_registry`

**Table:** `growth.yango_lima_exclusive_driver_worklist_daily`

| Feature | Detail |
|---------|--------|
| PK | (generated_date, driver_profile_id) |
| Columns | 23 |
| CHECK constraint | `assigned_universe_v1` IN (9 universe codes) |
| Indexes | 7 (date, universe, program, export, priority, driver, date+universe) |
| Additive | CREATE TABLE IF NOT EXISTS. No DROP. |

---

## 4. Canonical Writer

**File:** `backend/app/services/yego_lima_exclusive_worklist_service.py`

**Function:** `refresh_exclusive_driver_worklist_daily(target_date=None)`

| Feature | Detail |
|---------|--------|
| Input | target_date (str or None → today) |
| Output | dict with total_drivers, exportable_drivers, universe_counts |
| Lock | `pg_try_advisory_lock(9010)` |
| Sources | driver_state_snapshot (latest), driver_explorer_fact (latest), driver_history_daily (MIN(date)) |
| Operation | UPSERT `ON CONFLICT (generated_date, driver_profile_id) DO UPDATE` |
| Transaction | Explicit BEGIN/COMMIT. Rollback on error. |
| No DELETE | Only UPSERT. Historical rows preserved. |

**Helper functions:**
- `_compute_productivity_band(weekly_trips)` — 9 bands (0, 1-10 through 100+)
- `_compute_weekly_trips(snapshot, explorer)` — max of both sources
- `_compute_inactivity_days(explorer, snapshot, target_date)` — days_since_last_trip first, then last_trip_at fallback
- `_compute_value_tier(snapshot, explorer)` — HIGH/DEFAULT/LOW from historical_band + best_week_12w + rna_value_tier

---

## 5. V1 Rules Implemented

### 5.1 Priority Order (deterministic first-match)

| Priority | Universe | Condition | Export |
|----------|----------|-----------|--------|
| 1 | CEMETERY | inactivity_days > 60 | false |
| 2 | RECOVERY_HIGH | 7 ≤ inactivity ≤ 60 AND value_tier = HIGH | true |
| 3 | RECOVERY_LOW | 7 ≤ inactivity ≤ 60 AND value_tier != HIGH | true |
| 4 | NEW 0-14 | age 0-14 AND trips_30d < 50 AND active < 7d | true |
| 5 | RAMP_UP 15-45 | age 15-45 AND weekly < 100 AND active < 7d | true |
| 6 | CONSOLIDATION 46-90 | age 46-90 AND weekly < 100 AND active < 7d | true |
| 7 | ACTIVE_GROWTH 90+ | age > 90 AND 1 ≤ weekly < 100 AND active < 7d | true |
| 8 | PROTECTED | weekly ≥ 100 OR (age ≤ 14 AND trips ≥ 50) | false |
| 9 | NO_DATA | None of the above | false |

### 5.2 Key Rules

- Productivity bands: `weekly_trips` (current), NOT `best_week_12w`
- `best_week_12w` reserved for `value_tier` classification
- `first_active_date`: `driver_history_daily.MIN(date)` — documented proxy
- Cemetery and Protected are NOT exported to daily Control Loop

---

## 6. Freshness Governance

### 6.1 Chain (yego_lima_freshness_chain_service.py)

Layer: `exclusive_worklist`
Table: `growth.yango_lima_exclusive_driver_worklist_daily`
Date column: `generated_date`
Lineage: source = `"snapshot"`

### 6.2 Registry (yego_lima_refresh_governance_service.py)

Component: `exclusive_worklist`
Table: `growth.yango_lima_exclusive_driver_worklist_daily`
Date column: `generated_date`

### 6.3 Serving Freshness Fact (serving_freshness_audit_service.py)

Asset: `exclusive_driver_worklist_daily`
Table: `growth.yango_lima_exclusive_driver_worklist_daily`
Date column: `generated_date`
SLA: 24 hours
Criticality: CRITICAL

---

## 7. Autonomous Tick Integration

**File:** `backend/app/services/yego_lima_scheduler_service.py`

Added as cascade step between `driver_state_snapshot` and `program_eligibility`:

```
driver_state_snapshot → exclusive_worklist → eligibility → opportunity_lists
```

Protected by tick-level advisory lock + worklist-level advisory lock (9010).

Fail-closed: if worklist refresh fails, pipeline_failed = True, downstream steps skipped.

---

## 8. Read / Summary Service

**File:** `backend/app/services/yego_lima_exclusive_worklist_service.py`

### 8.1 `get_exclusive_worklist_summary(generated_date=None)`

Returns: resolved_generated_date, total_drivers, exportable_drivers, by_universe counts.

### 8.2 `get_exclusive_worklist_rows(generated_date, assigned_universe, exportable_only, limit, offset)`

Returns: paginated rows with driver details. Ready for Control Loop export endpoint in LG-PROG-EXCL-1C.

---

## 9. Tests

**File:** `backend/tests/test_exclusive_worklist.py`
**Result:** 25/25 PASS

| Coverage Area | Tests |
|---------------|-------|
| Productivity bands | 3 |
| Weekly trips computation | 1 |
| Inactivity days | 2 |
| Value tier | 3 |
| Universe classification | 9 |
| Priority collision resolution | 3 |
| Export flag rules | 4 |

---

## 10. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Table needs migration applied in production | MEDIUM | Migration is additive. Run `alembic upgrade head`. |
| Writer performance on 18K drivers | LOW | Row-by-row UPSERT in transaction. 18K rows ~5-10s. Advisory lock prevents concurrent runs. |
| `first_active_date` proxy may miss very old drivers | LOW | Fallback to NO_DATA. Documented limitation. |
| Tick cascade: worklist step may slow down tick | LOW | Runs only when cascade_required. Statement timeout 300s. |

---

## 11. Rollback

1. Remove cascade step from `yego_lima_scheduler_service.py`
2. Remove freshness registrations (chain, registry, audit)
3. DROP TABLE growth.yango_lima_exclusive_driver_worklist_daily
4. Delete migration file or apply downgrade
5. Revert service file

---

## 12. Verdict

### LG_PROG_EXCL_1B_PASS

| Criterion | Status |
|-----------|--------|
| Migration created | PASS |
| Canonical writer implemented | PASS |
| V1 rules (9 universes, priority order) | PASS |
| Freshness governance registered (3 layers) | PASS |
| Autonomous tick cascade integrated | PASS |
| Read/summary service created | PASS |
| Tests: 25/25 | PASS |
| Compile: clean all services | PASS |
| No DELETE/TRUNCATE | PASS |
| No parallel writers | PASS |
| No UI changes | PASS |
| No Diagnostic Engine activation | PASS |
| Productivity bands use weekly_trips | PASS |
| Cemetery export flag = false | PASS |

**Next phase:** LG-PROG-EXCL-1C — Run writer + validate DB counts + smoke.

---

*Implementation complete. 6 files created/modified. 25 tests. 0 legacy activation.*
