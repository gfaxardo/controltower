# LG-NORTH-TRACE-1A — Assignment Explainability + Movement Traceability Governance Patch

**Date:** 2026-06-13
**Phase:** LG-NORTH-TRACE-1A (Governance Patch)
**Mode:** DOCUMENTATION ONLY — No implementation
**Reference:** `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md`
**Status:** CERTIFIED

---

## 1. Executive Decision

### LG_NORTH_TRACE_1A_CERTIFIED

North Star updated. Assignment explainability and movement traceability are now explicit requirements. No code changes. 4 documents updated. All future Growth Machine tasks must pass the 7-question North Star Test (previously 5 questions).

---

## 2. Operator Requirement

The operator must understand WHY each driver is in their assigned list, WHAT gap exists to the target, and HOW drivers move between lists over time. Lists without evidence are not operationally useful.

---

## 3. Documents Updated

| Document | Change |
|----------|--------|
| `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | Added Section 14 (Assignment Explainability) + Section 15 (Movement Traceability). 10-question explainability contract. 10 transition types defined. |
| `GROWTH_MACHINE_CANONICAL.md` | Added "Exclusive Lists Explainability and Traceability" section. Lists evidence fields and transition types. |
| `ACTIVE_SCOPE_CONTRACT.md` | North Star Test expanded from 5 to 7 questions (+explainability, +traceability). Certification rule added. |
| `AI_START_HERE.md` | North Star Test expanded from 6 to 8 questions. Traceability preservation rule added. |
| `LG_NORTH_TRACE_1A_*.md` | This certification document. |

---

## 4. Assignment Explainability Requirement

Every daily worklist row must be explainable. 10 questions per row define the contract:

1. Why is this driver in this list today?
2. What rule placed the driver here?
3. What metric is below or above target?
4. What is the target?
5. What is the current value?
6. What is the gap?
7. What must happen to exit?
8. What happens if goal is met?
9. What happens if driver becomes inactive?
10. What is the recommended treatment?

V1 implementation already satisfies this via `reason_code`, `objective`, `target_metric`, `baseline_metric`, and `productivity_band` columns in `growth.yango_lima_exclusive_driver_worklist_daily`. A `reason_text` human-readable field is recommended for future phases.

---

## 5. Movement Traceability Requirement

Daily transition tracking between universes. 7 questions per transition:

1. Previous list?
2. Current list?
3. Stay/enter/exit/improve/decline/recover/churn?
4. What metric changed?
5. Objective achieved or missed?
6. Transition date?
7. Action history before movement?

10 transition types V1:
ENTERED_LIST, STAYED_IN_LIST, MOVED_UP_BAND, MOVED_DOWN_BAND, EXITED_GOAL_MET, MOVED_TO_RECOVERY, MOVED_TO_CEMETERY, RECOVERED_TO_ACTIVE, PROTECTED_GOAL_MET, NO_DATA.

Recommended future table: `growth.yango_lima_exclusive_worklist_transition_daily`.

---

## 6. Backend Implication

**None for this phase.** The existing `exclusive_driver_worklist_daily` table already has `reason_code`, `objective`, `target_metric`, `baseline_metric` columns satisfying the explainability requirement. Movement traceability requires a new transition fact table — NOT implemented yet. Deferred to a future phase (recommended: LG-TRACE-1B).

---

## 7. Control Loop Implication

The Control Loop export (endpoint created in LG-PROG-EXCL-1D) already includes `objective`, `reason_code`, `target_metric`, and `baseline_metric`. This satisfies the explainability requirement for export. Movement traceability adds transition history, which enriches but does not block the current export.

---

## 8. What This Does NOT Open

- Program Registry V3
- Lifecycle State Machine
- Full temporal assignment engine
- Diagnostic Engine
- Forecast/Suggestion/Decision/Action/AI/Learning
- New tables (yet)
- New writers
- UI changes
- DB changes

---

## 9. Verdict

### LG_NORTH_TRACE_1A_CERTIFIED

North Star now includes explainability and traceability as explicit product requirements. All canonical governance documents updated. 0 code/DB/scheduler changes.

---

*Governance patch complete. No implementation. North Star now defines: why, what gap, how to exit, and where drivers move.*
