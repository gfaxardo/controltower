# LG-UI-NORTH-1A — Growth Machine UI Operational North Star

**Date:** 2026-06-14
**Phase:** LG-UI-NORTH-1A (UI Governance Patch)
**Mode:** DOCUMENTATION ONLY
**Status:** CERTIFIED

---

## 1. Executive Decision

### LG_UI_NORTH_1A_CERTIFIED

Growth Machine backend core is CLOSED. UI/Product operational closure is now the active phase. The North Star has been revised: the product is not complete until the operator can see, understand, and act on the exclusive worklists through a UI — without SQL, CSV, or terminal commands.

Diagnostic Engine remains blocked until both OMNI-P0 closure AND Growth Machine UI operational closure.

---

## 2. Why Backend Closure Is Not Product Closure

Backend delivers data. The operator needs visibility. A CSV download is not a product. The operator must be able to:
- See counts by universe at a glance
- Explore driver lists with explainability
- Drill down into individual drivers
- See movement and goal attainment
- Verify Control Loop sync status
- See alerts for stale data or violations

---

## 3. Revised North Star

**New North Star doc:** `LG_NORTH_STAR_UI_OPERATIONAL_CONTRACT.md`

12 requirements across 7 sections: Universe Overview, Actionable Lists, Driver Table, Driver Drilldown, Movement Dashboard, Alerts, Action Evidence Readback.

---

## 4. UI Operational Requirements (Summary)

| # | Requirement | Backend Ready? |
|---|-------------|---------------|
| 1 | Daily universe overview | Yes (summary endpoint) |
| 2 | Actionable list filtering | Yes (rows endpoint) |
| 3 | Driver table with explainability | Yes (reason_text, gap, etc.) |
| 4 | Driver drilldown | Yes (evidence_json, transitions) |
| 5 | Movement dashboard | Yes (transition fact) |
| 6 | Alerts (stale/violations) | Yes (freshness governance) |
| 7 | Control Loop readback | Yes (control_loop_state) |
| 8 | Action evidence | Yes (action_registry/ledger) |

All backend data is ready. UI implementation is the gap.

---

## 5. Files Updated

| File | Change |
|------|--------|
| `TRUTH_MAP_V2.md` | Status: Backend Core CLOSED, UI Operationalization ACTIVE |
| `LG_NORTH_STAR_UI_OPERATIONAL_CONTRACT.md` | New: 12 UI requirements |
| `GROWTH_MACHINE_CANONICAL.md` | Added: UI Operational Closure Requirement |
| `AI_START_HERE.md` | Updated: GM status, Diagnostic pre-req |
| `KNOWN_CONSTRAINTS.md` | Added: UI gap constraint |
| `LG_UI_NORTH_1A_*.md` | This certification |

---

## 6. What Remains Blocked

- Diagnostic Engine (until GM UI closure + OMNI-P0 closure)
- Forecast, Suggestion, Decision, Action, AI, Learning
- Program Registry V3, State Machine

---

## 7. Next Phases (P0)

| Phase | Focus |
|-------|-------|
| LG-UI-AUDIT-1B | Audit current Intelligence tab and route rendering |
| LG-UI-LISTS-1C | Worklist explorer with universe counts and driver table |
| LG-UI-DRILLDOWN-1D | Driver drilldown with reason/evidence/gap/history |
| LG-UI-MOVEMENT-1F | Movement summary and goal attainment dashboard |
| LG-UI-CONTROL-1E | Control Loop batch/status verification in UI |
| LG-UI-ACTIONS-1G | Control Loop action evidence readback |

---

## 8. Verdict

### LG_UI_NORTH_1A_CERTIFIED

North Star revised. UI operational closure is now the active phase. Backend is ready. 6 UI phases defined. 8 docs updated. 0 code changes.

---

*UI is the product. The operator must see the lists. Backend alone is not enough.*
