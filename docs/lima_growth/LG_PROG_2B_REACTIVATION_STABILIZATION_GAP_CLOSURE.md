# LG-PROG-2B — REACTIVATION STABILIZATION PROGRAM GAP CLOSURE

**Ticket:** LG-PROG-2B  
**Date:** 2026-06-11  
**Phase:** Lima Growth Foundation — Program Layer  
**Status:** GAP CLOSED — 0 UNASSIGNED  

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Shadow mode. Zero production impact.

---

## TASK 1 — AUDIT RESULTS

All 593 unassigned confirmed as `REACTIVATED_ACTIVE` segment with `lifecycle_status = REACTIVATED`. They are drivers who returned after 90+ days of inactivity and are now taking trips again. They fell through the gap because no program in the original registry targeted this segment.

---

## TASK 2 — NEW PROGRAM

| Field | Value |
|-------|-------|
| Program Code | `REACTIVATION_STABILIZATION` |
| Program Name | Reactivation Stabilization |
| Family | REACTIVATION |
| Priority Order | 4 |
| Target Segment | `REACTIVATED_ACTIVE` |

### Priority Order (Final)

| Order | Program | Segment |
|-------|---------|---------|
| 1 | HVR | HVR_CANDIDATE |
| 2 | FIFTY_14 | NEW_ACTIVE |
| 3 | NINETY_300 | NEW_ACTIVE |
| **4** | **REACTIVATION_STABILIZATION** | **REACTIVATED_ACTIVE** |
| 5 | ACTIVE_GROWTH | ACTIVE_GROWTH |
| 6 | TOP_RETENTION | TOP_PERFORMER |
| 7 | STABLE_MONITOR | STABLE |
| 8 | CHURN_RECOVERY | CHURNED |
| 9 | RNA_ONBOARDING | REGISTERED_NOT_ACTIVATED |
| 10 | ARCHIVED_REACTIVATION | ARCHIVED |

---

## TASK 3 — RULES

| Rule | Operator | Value |
|------|----------|-------|
| segment | = | REACTIVATED_ACTIVE |
| activity_status | IN | ACTIVE_7D, ACTIVE_30D, RECENTLY_INACTIVE |
| lifecycle | = | REACTIVATED |

---

## TASK 4 — PRIORITY SCORING

Score = `1000 - days_since_last_trip` — drivers closer to their reactivation event get higher priority.

---

## TASK 5 — REBUILD RESULT

| Metric | Before | After |
|--------|--------|-------|
| Programs | 9 | **10** |
| Eligibility rows | 68,004 | **68,597** |
| Assignment rows | 68,473 | 68,473 |
| UNASSIGNED | 593 | **0** |
| REACTIVATION_STABILIZATION | — | **593** |

### Final Distribution

| Program | Drivers |
|---------|---------|
| RNA_ONBOARDING | 50,181 |
| ARCHIVED_REACTIVATION | 10,743 |
| CHURN_RECOVERY | 3,486 |
| ACTIVE_GROWTH | 2,594 |
| **REACTIVATION_STABILIZATION** | **593** |
| TOP_RETENTION | 495 |
| HVR | 166 |
| FIFTY_14 | 124 |
| STABLE_MONITOR | 91 |
| **UNASSIGNED** | **0** |

---

## TASK 8 — GO / NO-GO

### Veredicto: **A) PROGRAM_ENGINE_V2_ZERO_UNASSIGNED**

| Criterion | Status |
|-----------|--------|
| UNASSIGNED = 0 | PASS |
| 1 driver = 1 program | PASS |
| REACTIVATION_STABILIZATION populated | PASS (593) |
| Priorities adjusted | PASS |
| No production impact | PASS |

---

**LG-PROG-2B — GAP CLOSED**

*593 REACTIVATED_ACTIVE drivers now assigned to REACTIVATION_STABILIZATION.*  
*10 programs, 68,473 drivers, 0 unassigned.*  
*Program Engine V2 shadow is complete with full universe coverage.*
