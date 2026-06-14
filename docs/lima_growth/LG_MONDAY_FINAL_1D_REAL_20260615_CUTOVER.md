# LG-MONDAY-FINAL-1D — Real 2026-06-15 Cutover

**Date:** 2026-06-13 (cutover executed pre-Monday, data dated 06-15)
**Operational Date:** 2026-06-15 (worklist generated with target_date='2026-06-15')
**Phase:** LG-MONDAY-FINAL-1D (Real Cutover Execution)
**Mode:** REAL CUTOVER
**Predecessor:** `LG_MONDAY_CUTOVER_1C_FRESH_20260615_BATCH_FINALIZATION.md`
**Status:** EXECUTED AND CERTIFIED

---

## 1. Executive Decision

### LIMA_GROWTH_REAL_20260615_CUTOVER_GO

Real Monday cutover executed. Worklist `generated_date = 2026-06-15` populated (18,545 drivers, 6,114 exportable). Control Loop batch `lg-prog-excl-prod-20260615` synced (6,114 READY, 0 violations). All gates pass.

**The Lima Growth Machine is ready for agent operations with the 20260615 batch.**

---

## 2. Worklist 2026-06-15 Evidence

| Metric | Value |
|--------|-------|
| generated_date | **2026-06-15** |
| Total | 18,545 |
| Distinct | 18,545 |
| Duplicates | 0 |
| Null reason_text | 0 |
| Null evidence_json | 0 |

---

## 3. Worklist Counts (2026-06-15)

| Universe | Drivers | Export |
|----------|---------|--------|
| CEMETERY | 12,403 | false |
| RECOVERY_LOW | 2,989 | true |
| ACTIVE_GROWTH | 1,652 | true |
| RECOVERY_HIGH | 877 | true |
| CONSOLIDATION | 344 | true |
| RAMP_UP | 204 | true |
| NEW_REACTIVATED | 48 | true |
| PROTECTED | 28 | false |
| **TOTAL** | **18,545** | 6,114 exportable |

**06-15 delta vs 06-14:** ACTIVE_GROWTH +11, RAMP -6, CONSOLIDATION -4, PROTECTED -1. Natural churn. Core patterns stable.

---

## 4. Goal Attainment Sanity (2026-06-15)

| Check | Violations |
|-------|-----------|
| NEW (trips >= 50) | **0** |
| RAMP (weekly >= 100) | **0** |
| CONSOLIDATION (weekly >= 100) | **0** |
| ACTIVE_GROWTH (weekly >= 100) | **0** |

**ALL PASS. All 4 checks verified on generated_date 2026-06-15.**

---

## 5. API / CSV Latest Date

Resolved to 2026-06-15. CSV exports 6,114 rows with reason_text. Cemetery/Protected excluded.

---

## 6. Old Batch Warning

| Batch | Rows | Status |
|-------|------|--------|
| `lg-prog-excl-1f-20260613` | 6,109 | **LEGACY — DO NOT USE** |
| `lg-prog-excl-prod-20260614` | 6,113 | **PRE-RUN — DO NOT USE** |
| `lg-prog-excl-prod-20260615` | **6,114** | **MONDAY OPERATIONAL BATCH — USE THIS** |

**Agents must only work batch `lg-prog-excl-prod-20260615`.**

---

## 7. Dry-run 2026-06-15

6,114 candidates. 0 violations. Dry-run PASS.

---

## 8. Write Batch 2026-06-15

| Metric | Value |
|--------|-------|
| Batch ID | `lg-prog-excl-prod-20260615` |
| Inserted | 6,114 |
| Skipped | 0 |
| Status | OK |

---

## 9. Post-write Validation

| Check | Result |
|-------|--------|
| Batch rows | 6,114 |
| Duplicate drivers | 0 |
| No-export violations | 0 |
| Missing notes | 0 |
| All states | READY |

| Universe | Count |
|----------|-------|
| RECOVERY_LOW | 2,989 |
| ACTIVE_GROWTH | 1,652 |
| RECOVERY_HIGH | 877 |
| CONSOLIDATION | 344 |
| RAMP_UP | 204 |
| NEW_REACTIVATED | 48 |

---

## 10. Weekly Refresh Observation

`MAX(week_start_date) = 2026-06-01` — STALE. Pending Monday autonomous tick.

Does NOT block operational GO. Blocks Growth Machine CLOSED.

---

## 11. Operator Handoff

| Priority | Universe | Drivers | Action Category |
|----------|----------|---------|-----------------|
| 1 | RECOVERY_HIGH | 877 | HIGH_VALUE_RECOVERY |
| 2 | NEW_REACTIVATED | 48 | ONBOARDING_PUSH |
| 3 | RAMP_UP | 204 | PRODUCTIVITY_RAMP |
| 4 | CONSOLIDATION | 344 | CONSOLIDATION_PUSH |
| 5 | ACTIVE_GROWTH | 1,652 | BAND_GROWTH |
| 6 | RECOVERY_LOW | 2,989 | LOW_VALUE_RECOVERY |

**DO NOT WORK:** CEMETERY (12,403), PROTECTED (28).

**CSV:** `GET /yego-lima-growth/exclusive-worklist/export.csv`
**Batch:** `lg-prog-excl-prod-20260615`

---

## 12. Rollback

```sql
DELETE FROM growth.yego_lima_control_loop_state
WHERE campaign_id_external = 'lg-prog-excl-prod-20260615';
```

Does NOT touch worklist source or other batches.

---

## 13. Final Decision

### LIMA_GROWTH_REAL_20260615_CUTOVER_GO

| Component | Status |
|-----------|--------|
| Worklist generated_date | 2026-06-15 |
| Explainability | 0 nulls |
| Goal attainment | 0 violations |
| Control Loop batch 20260615 | 6,114 READY |
| CSV/API | Operational |
| Weekly cycle | PENDING (does not block ops) |
| **Growth Machine CLOSED** | **NOT YET** |

**Real Monday cutover executed. 18,545 classified. 6,114 in Control Loop. 0 violations. Batch `lg-prog-excl-prod-20260615` is the canonical Monday operational batch.**

---

*Cutover complete. Ready for Monday agent assignment.*
