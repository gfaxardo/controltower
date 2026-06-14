# LG-MONDAY-CUTOVER-1C — Fresh Monday Batch Finalization

**Date:** 2026-06-14 (Sunday) — Cutover ready for Monday 06-15
**Operational Date:** 2026-06-14 (worklist) / 2026-06-15 target
**Phase:** LG-MONDAY-CUTOVER-1C (Final Cutover)
**Mode:** CUTOVER FINALIZATION
**Predecessor:** `LG_MONDAY_RUN_1B_PRODUCTION_RUN_AND_OPERATOR_HANDOFF.md`
**Status:** CERTIFIED

---

## 1. Executive Decision

### LIMA_GROWTH_MONDAY_20260615_CUTOVER_GO

The Lima Growth Machine cutover pipeline is certified. Worklist is fresh as of 2026-06-14. Control Loop batch `lg-prog-excl-prod-20260614` holds 6,113 READY records. On Monday morning, the autonomous tick will regenerate the worklist with `generated_date = 2026-06-15` and a new Control Loop batch `lg-prog-excl-prod-20260615` should be generated.

**All pipelines, validation gates, and rollback mechanisms are verified and documented.**

---

## 2. Backend Restart

Backend operational. Writer runs in 55s. Sync function loaded. 4 endpoints responding.

---

## 3. Worklist 2026-06-14 Evidence (Will auto-refresh to 06-15 on Monday)

| Metric | Value |
|--------|-------|
| generated_date | 2026-06-14 |
| Total | 18,545 |
| Exportable | 6,113 |
| Duplicates | 0 |
| Null reason_text | 0 |
| Null evidence_json | 0 |

| Universe | Drivers |
|----------|---------|
| CEMETERY | 12,403 |
| RECOVERY_LOW | 2,989 |
| ACTIVE_GROWTH | 1,641 |
| RECOVERY_HIGH | 877 |
| CONSOLIDATION | 348 |
| RAMP_UP | 210 |
| NEW_REACTIVATED | 48 |
| PROTECTED | 29 |

---

## 4. Goal Attainment Sanity

| Check | Violations |
|-------|-----------|
| NEW (trips >= 50) | **0** |
| RAMP (weekly >= 100) | **0** |
| CONSOLIDATION (weekly >= 100) | **0** |
| ACTIVE_GROWTH (weekly >= 100) | **0** |

**ALL PASS. All 4 checks verified on generated_date 2026-06-14.**

---

## 5. API / CSV Evidence

| Endpoint | Status |
|----------|--------|
| `/summary` | resolved to 2026-06-14 |
| `/rows` | Working |
| `/export.csv` | 6,113 rows, Cemetery excluded |
| `/control-loop-preview` | Working |

---

## 6. Old Batch Risk

| Batch ID | Rows | Usage |
|----------|------|-------|
| `lg-prog-excl-1f-20260613` | 6,109 | **First sync batch. Do NOT use for Monday ops.** |
| `lg-prog-excl-prod-20260614` | 6,113 | **Pre-run batch. Foundation for Monday. Will be superseded by 20260615.** |
| `lg-prog-excl-prod-20260615` | 0 (pending) | **Monday operational batch. Must be generated on Monday morning.** |

**Agents must work only the 20260615 batch on Monday.**

---

## 7. Control Loop Dry-run

Verified. 6,113 candidates, 0 violations. NOT EXISTS guard working (second dry-run shows 6,113 existing = idempotent).

---

## 8. Control Loop Current State

| Batch | Rows | No-export | Missing Notes | READY |
|-------|------|-----------|---------------|-------|
| 20260613 | 6,109 | 0 | 0 | 6,109 |
| 20260614 | 6,113 | 0 | 0 | 6,113 |
| **Total** | **12,222** | 0 | 0 | 12,222 |

---

## 9. Monday Morning Procedure

```python
# Step 1: Autonomous tick will auto-refresh, or run manually:
refresh_exclusive_driver_worklist_daily()
# Verify:
# SELECT MAX(generated_date) FROM growth.yango_lima_exclusive_driver_worklist_daily;
# → must be 2026-06-15

# Step 2: Validate worklist
# Run Gates 3-5 validations against 2026-06-15

# Step 3: Dry-run sync
sync_exclusive_worklist_to_control_loop(
    generated_date='2026-06-15',
    dry_run=True,
    export_batch_id='lg-prog-excl-prod-20260615'
)
# Verify: candidates match exportable count, violations=0

# Step 4: Write sync
sync_exclusive_worklist_to_control_loop(
    generated_date='2026-06-15',
    dry_run=False,
    export_batch_id='lg-prog-excl-prod-20260615'
)

# Step 5: Download CSV
# GET /yego-lima-growth/exclusive-worklist/export.csv
```

---

## 10. Post-write Validation Template

```sql
-- Batch size
SELECT COUNT(*) FROM growth.yego_lima_control_loop_state
WHERE campaign_id_external = 'lg-prog-excl-prod-20260615';

-- Duplicates (must be 0)
SELECT driver_profile_id, COUNT(*) FROM growth.yego_lima_control_loop_state
WHERE campaign_id_external = 'lg-prog-excl-prod-20260615'
GROUP BY driver_profile_id HAVING COUNT(*) > 1;

-- No-export violations (must be 0)
SELECT COUNT(*) FROM growth.yego_lima_control_loop_state
WHERE campaign_id_external = 'lg-prog-excl-prod-20260615'
AND program_code IN ('CEMETERY_LONG_CHURNED','PROTECTED_ALREADY_MEETING_GOAL','NO_DATA_OR_NO_ACTION');

-- Missing notes (must be 0)
SELECT COUNT(*) FILTER (WHERE notes IS NULL) FROM growth.yego_lima_control_loop_state
WHERE campaign_id_external = 'lg-prog-excl-prod-20260615';
```

---

## 11. Weekly Refresh Observation

| Metric | Value |
|--------|-------|
| MAX(week_start_date) | 2026-06-01 |
| Expected closed week | 2026-06-08 |
| Status | Pending Monday autonomous tick |

Does NOT block operational cutover. Blocks Growth Machine CLOSED declaration.

---

## 12. Tests

25/25 pass. compileall clean.

---

## 13. Operator Handoff

| Priority | Universe | Drivers (expected ~6,113) | Action |
|----------|----------|--------------------------|--------|
| 1 | RECOVERY_HIGH | ~877 | Reactivate high-value |
| 2 | NEW_REACTIVATED | ~48 | Onboard to 50 trips |
| 3 | RAMP_UP | ~210 | Reach 100/wk |
| 4 | CONSOLIDATION | ~348 | Sustain 100/wk |
| 5 | ACTIVE_GROWTH | ~1,641 | Move up band |
| 6 | RECOVERY_LOW | ~2,989 | Low-intensity recovery |

**DO NOT WORK:** CEMETERY (12,403), PROTECTED (29).

---

## 14. Rollback

```sql
DELETE FROM growth.yego_lima_control_loop_state WHERE campaign_id_external = 'lg-prog-excl-prod-20260615';
DELETE FROM growth.yego_lima_control_loop_state WHERE campaign_id_external = 'lg-prog-excl-prod-20260614';
DELETE FROM growth.yego_lima_control_loop_state WHERE campaign_id_external = 'lg-prog-excl-1f-20260613';
```

---

## 15. Final Decision

### LIMA_GROWTH_MONDAY_20260615_CUTOVER_GO

All pipelines verified. All gates documented. Monday morning procedure ready. Rollback by batch documented.

| Component | Status |
|-----------|--------|
| Worklist | 2026-06-14 (→ 06-15 on Monday tick) |
| Explainability | 0 nulls |
| Goal attainment | 0 violations |
| Control Loop (06-13) | 6,109 READY (first sync) |
| Control Loop (06-14) | 6,113 READY (pre-run) |
| Control Loop (06-15) | Pending Monday generation |
| CSV/API | 4/4 operational |
| Weekly cycle | Pending 06-15 tick |
| **Growth Machine CLOSED** | **NOT YET** |

---

*Cutover ready. Monday pipeline: tick → worklist 06-15 → dry-run → batch 20260615 → agents.*
