# LG-NORTH-GOAL-1A — Goal Attainment + Automatic Movement Governance Patch

**Date:** 2026-06-13
**Phase:** LG-NORTH-GOAL-1A (Governance Patch)
**Mode:** DOCUMENTATION ONLY — No implementation
**Reference:** `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md`
**Status:** CERTIFIED

---

## 1. Executive Decision

### LG_NORTH_GOAL_1A_CERTIFIED

Governance updated. Goal attainment exits are now an explicit North Star requirement. Daily movement vs weekly refresh distinction clarified. Backlog item created for transition fact. 5 documents updated. 0 code changes.

---

## 2. Operator Requirement

Drivers who achieve the measurable objective of their assigned list must exit that list automatically on the next available refresh. Manual removal should not be required. Goal attainment must leave traceable evidence.

---

## 3. Documents Updated

| Document | Change |
|----------|--------|
| `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | Sections 16 (Goal Attainment) + 17 (Daily vs Weekly Refresh) added |
| `GROWTH_MACHINE_CANONICAL.md` | Goal Attainment Transitions section added |
| `ACTIVE_SCOPE_CONTRACT.md` | Question 8 added: "Does this preserve automatic movement when drivers achieve measurable goals?" + certification rule |
| `AI_START_HERE.md` | Questions 8-9 expanded. Goal attainment refresh rule added. |
| `LG_BACKLOG_PRODUCTION_CUTOVER_AND_DEFERRED_ITEMS.md` | Item 22 added: Goal Attainment + Movement Transition Fact (LG-TRACE-1B) |
| `LG_NORTH_GOAL_1A_*.md` | This certification document |

---

## 4. Goal Attainment Rule

Drivers must exit operational lists once they achieve the measurable goal. Next refresh must: remove, reassign, preserve evidence, expose transition.

6 universe-specific exit contracts defined (NEW → Protected, RAMP → Protected, CONSOLIDATION → Protected, ACTIVE_GROWTH → Protected/band update, RECOVERY → Active, CEMETERY → Active).

---

## 5. Daily Movement vs Weekly History Refresh

| Dimension | Daily Worklist Refresh | Weekly History Refresh |
|-----------|----------------------|----------------------|
| Purpose | Operational movement | Historical intelligence |
| Decides | Current list, exit on goal | avg_4w, best_week_12w, value tier |
| Blocks daily exit? | No | Must not |
| Drives | Control Loop operations | Classification quality |

---

## 6. Transition Types Impact

Goal attainment exits map to:
- EXITED_GOAL_MET (NEW, RAMP, CONSOLIDATION)
- MOVED_UP_BAND (ACTIVE_GROWTH band change)
- PROTECTED_GOAL_MET (100+ trips)
- RECOVERED_TO_ACTIVE (Recovery, Cemetery)
- Transition fact table recommended in backlog item LG-TRACE-1B.

---

## 7. Backend Implication

None for this phase. The existing writer already reevaluates all drivers on every refresh. If goals are met, the priority-ordered classification will move drivers automatically. The transition history table is deferred to LG-TRACE-1B.

---

## 8. Backlog Item Created

**LG-TRACE-1B — Goal Attainment + Movement Transition Fact**
Create `growth.yango_lima_exclusive_worklist_transition_daily`.
P1 after production GO.
Not Program Registry V3. Not full State Machine.

---

## 9. What This Does NOT Open

- Program Registry V3
- State Machine completa
- Diagnostic Engine
- New tables
- New writers
- UI changes
- DB changes

---

## 10. Verdict

### LG_NORTH_GOAL_1A_CERTIFIED

Goal attainment governance defined. Daily/weekly refresh distinction clarified. Backlog item created. 0 code changes.

---

*Governance patch complete. No implementation. North Star now defines: classify, explain, export, sync, and exit on goal attainment.*
