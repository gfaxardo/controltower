# LG-DIAG-R1.6A — Why Button UI

**Date:** 2026-06-08
**Motor:** Control Foundation / Diagnostic Hardening
**Phase:** LG-DIAG-R1.6A
**Status:** WHY BUTTON UI CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**WHY BUTTON: VISIBLE.**

Every driver in the Execution Queue table now has a [Why?] button. One click opens a modal showing: WHY THIS PROGRAM? (selected program, eligible alternatives, selection reason, score, rank), WHY DID I MOVE? (transition type, trigger, before/after states), and WHAT RULE CHANGED? (rule deltas with MATCH/FAIL visualization). All data from persisted diagnostic traces. No recalculation.

---

## 2. UI ELEMENTS

### Why? Button

- Location: Execution Queue table, last column per row
- Style: Small purple button `[Why?]`
- Loading state: Shows `...` while fetching
- Error state: Shows "Unable to load diagnostic trace"

### Diagnostic Trace Modal

Opens on click. Shows 3-4 blocks:

| Block | Content |
|-------|---------|
| **WHY THIS PROGRAM?** | Selected program, eligible alternatives, selection_reason, score, rank |
| **WHY DID I MOVE?** | transition_type, trigger_reason, state_before → state_after |
| **WHAT RULE CHANGED?** | rule_deltas: rule name, FAIL→MATCH or MATCH→FAIL |
| **Metadata** | policy_version, run_id |

---

## 3. DATA SOURCE

```
GET /yego-lima-growth/diagnostic-trace/{driver_id}
  → growth.yego_lima_program_decision_trace
  → growth.yego_lima_state_transition_trace
```

Zero recalculation. Pure read from persisted tables.

---

## 4. FILES MODIFIED

| File | Change |
|------|--------|
| `ExecutionQueueSection.jsx` | +WhyButton, +WhyModal components, +Why? column in table |

---

## 5. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (10.36s) |
| Why? button per row | YES |
| Modal with 3 blocks | YES |
| Data from persisted traces | YES |
| Loading state | YES |
| Error state | YES |
| No recalculation | YES |

---

## 6. FINAL VERDICT

```
WHY BUTTON UI CERTIFIED
```

**First visible element of operational explainability in Lima Growth. One click from queue to full diagnostic trace.**

### Diagnostic Engine — 9/9 CERTIFIED

```
R1.0B  Explainability
R1.1A  Decision Trace
R1.2A  Transition Detection
R1.2B.1 Production Rules
R1.3A  Persistence
R1.3A.1 Backfill
R1.4A  Serving API
R1.5A  Frontend Integration
R1.6A  Why Button UI        ← NEW
```
