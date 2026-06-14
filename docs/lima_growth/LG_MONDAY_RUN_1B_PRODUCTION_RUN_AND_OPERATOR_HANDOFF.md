# LG-MONDAY-RUN-1B — Production Run + Operator Handoff

**Date:** 2026-06-14 (Sunday — ready for Monday 06-15)
**Operational Date:** 2026-06-14 (worklist) / Monday batch
**Phase:** LG-MONDAY-RUN-1B (Production Run)
**Mode:** PRODUCTION OPERATION
**Predecessor:** `LG_MONDAY_PREFLIGHT_1A_PRODUCTION_OPERATIONAL_START.md`
**Status:** CERTIFIED

---

## 1. Executive Decision

### LIMA_GROWTH_MONDAY_RUN_GO

Monday production run complete. Worklist refreshed (18,545 drivers, 6,113 exportable). Goal attainment 0 violations. Control Loop has 6,113 READY records (batch `lg-prog-excl-prod-20260614`). Operator handoff ready.

**The Lima Growth Machine is ready for agent assignment on Monday.**

---

## 2. Backend Restart

Backend operational. Writer executed (55s). Sync function loaded. All 4 endpoints responding.

---

## 3. Worklist Refresh

| Metric | Value |
|--------|-------|
| generated_date | 2026-06-14 |
| Total drivers | 18,545 |
| Distinct | 18,545 |
| Duplicates | 0 |

---

## 4. Counts

| Universe | Drivers | Export | Exportable? |
|----------|---------|--------|-------------|
| CEMETERY | 12,403 | false | NO |
| RECOVERY_LOW | 2,989 | true | YES |
| ACTIVE_GROWTH | 1,641 | true | YES |
| RECOVERY_HIGH | 877 | true | YES |
| CONSOLIDATION | 348 | true | YES |
| RAMP_UP | 210 | true | YES |
| NEW_REACTIVATED | 48 | true | YES |
| PROTECTED | 29 | false | NO |
| **TOTAL** | **18,545** | 6,113 true | |

---

## 5. Explainability

| Check | Result |
|-------|--------|
| null reason_text | 0 |
| null evidence_json | 0 |
| recovered_threshold_days | 45 |

---

## 6. Goal Attainment Sanity

| Check | Violations |
|-------|-----------|
| NEW (trips >= 50) | **0** |
| RAMP (weekly >= 100) | **0** |
| CONSOLIDATION (weekly >= 100) | **0** |
| ACTIVE_GROWTH (weekly >= 100) | **0** |

**ALL PASS.** No driver stuck in a list after achieving the goal.

---

## 7. CSV/API Smoke

4/4 endpoints working. CSV exports 6,113 rows. Cemetery/Protected excluded.

---

## 8. Control Loop Dry-run

6,113 candidates. 0 violations. 6,113 already existing (from preflight batch). NOT EXISTS guard working.

---

## 9. Control Loop Write Batch

| Metric | Value |
|--------|-------|
| Batch ID | `lg-prog-excl-prod-20260614` |
| Status | Already synced (preflight) |
| Rows in Control Loop | 6,113 |
| New inserts | 0 (NOT EXISTS prevented dups) |
| Duplicates | 0 |
| No-export violations | 0 |
| Missing notes | 0 |

**Batch `lg-prog-excl-prod-20260614` is the canonical Monday batch.** On Monday morning, refresh and generate new batch `lg-prog-excl-prod-20260615`.

---

## 10. Post-write Validation

| Check | Value |
|-------|-------|
| Batch rows in CL | 6,113 |
| All states | READY |
| Duplicate drivers | 0 |
| Cemetery/Protected/NoData | 0 |
| Notes (reason_text) present | 6,113 |

---

## 11. CSV Fallback

`GET /yego-lima-growth/exclusive-worklist/export.csv` → 6,113 rows, 19 headers. Cemetery excluded. Reason_text, gap_to_target, recommended_action_category included.

---

## 12. Weekly Refresh Observation

| Metric | Value |
|--------|-------|
| MAX(week_start_date) | 2026-06-01 |
| Expected closed week | 2026-06-08 |
| Status | Stale (pending Monday 06-15 autonomous tick) |

**Does NOT block Monday operational GO.** Daily worklist + Control Loop are fresh.

---

## 13. Tests

25/25 pass. compileall clean.

---

## 14. Operator Handoff

### What to Work (Priority Order)

| Priority | Universe | Objective | Action Category |
|----------|----------|-----------|-----------------|
| 1 | RECOVERY_HIGH (877) | Reactivate high-value drivers | HIGH_VALUE_RECOVERY |
| 2 | NEW_REACTIVATED (48) | Reach 50 trips in 14 days | ONBOARDING_PUSH |
| 3 | RAMP_UP (210) | Reach 100 trips/week | PRODUCTIVITY_RAMP |
| 4 | CONSOLIDATION (348) | Sustain 100 trips/week | CONSOLIDATION_PUSH |
| 5 | ACTIVE_GROWTH (1,641) | Move up productivity band | BAND_GROWTH |
| 6 | RECOVERY_LOW (2,989) | Reactivate low-value drivers | LOW_VALUE_RECOVERY |

### What NOT to Work

| Universe | Drivers | Why |
|----------|---------|-----|
| CEMETERY | 12,403 | Not in daily Control Loop. Inactive >60 days. |
| PROTECTED | 29 | Already meeting goal. No action needed. |

### How to Read a Row

Each row tells you:
- **reason_text**: Why the driver is here (human-readable)
- **gap_to_target**: How many trips/week are needed to reach goal
- **objective**: The operational objective for this driver
- **exit_condition**: What must happen to exit this list

### How to Track

- **CSV**: `GET /yego-lima-growth/exclusive-worklist/export.csv`
- **API**: `GET /yego-lima-growth/exclusive-worklist/summary`
- **Per driver**: `GET /yego-lima-growth/exclusive-worklist/rows?search=<driver_id>`

### End of Day

1. Autonomous tick will refresh worklist automatically (every 5 min)
2. Next business day: generate new batch with `sync_exclusive_worklist_to_control_loop(dry_run=False, export_batch_id='lg-prog-excl-prod-YYYYMMDD')`
3. Download new CSV for the day

---

## 15. Rollback

```sql
-- Remove Monday batches from Control Loop:
DELETE FROM growth.yego_lima_control_loop_state WHERE campaign_id_external = 'lg-prog-excl-prod-20260614';
DELETE FROM growth.yego_lima_control_loop_state WHERE campaign_id_external = 'lg-prog-excl-1f-20260613';
-- DOES NOT touch exclusive_driver_worklist_daily or any source table
```

---

## 16. Final Decision

### LIMA_GROWTH_MONDAY_RUN_GO

All 14 gates pass. Worklist fresh. Explainability complete. Goal attainment 0 violations. Control Loop synced (6,113 READY). Operator handoff documented.

**Growth Machine operational MVP is production-ready for Monday.**

| Component | Status |
|-----------|--------|
| Exclusive worklist | OPERATIONAL (18,545 drivers) |
| Explainability | COMPLETE (0 nulls) |
| Goal attainment | VERIFIED (0 violations) |
| CSV/API | OPERATIONAL (4 endpoints) |
| Control Loop sync | OPERATIONAL (6,113 READY) |
| Freshness | GOVERNED (3 layers) |
| Weekly cycle | PENDING (Mon 06-15 observation) |
| **Growth Machine CLOSED** | **NOT YET** |

Growth Machine overall CLOSED requires weekly cycle observation: `MAX(week_start_date)` must advance to 2026-06-08 after Monday's autonomous tick runs.

---

*Monday production run complete. 18,545 classified. 6,113 in Control Loop. 0 violations. Ready for agent assignment.*
