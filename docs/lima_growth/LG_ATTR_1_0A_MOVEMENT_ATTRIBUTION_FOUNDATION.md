# LG-ATTR-1.0A — Movement Attribution Foundation

**Date:** 2026-06-09
**Motor:** Attribution Foundation
**Phase:** LG-ATTR-1.0A
**Status:** MOVEMENT ATTRIBUTION FOUNDATION CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**MOVEMENT FOUNDATION: CERTIFIED.**

Movements are now traceable from existing persisted traces. Daily movement summary aggregates program decisions + state changes. Driver movement history reconstructs full timeline. No new tables needed — built on R1.3A persistence (state_transition_trace + program_decision_trace).

---

## 2. MOVEMENT DEFINITION

| Movement Type | Source | Example |
|--------------|--------|---------|
| **STATE_CHANGE** | state_transition_trace | HEALTHY → CHURN_RISK |
| **PROGRAM_CHANGE** | program_decision_trace | ACTIVE_GROWTH → CHURN_PREVENTION |
| **PROGRAM_ENTRY** | program_decision_trace | ENTERED: CHURN_PREVENTION |

---

## 3. MOVEMENTS FOR 06-05

| Metric | Count |
|--------|:---:|
| Program decisions | 5,558 |
| State changes | 1,205 |
| Total movements | 6,763 |
| Membership records | 500 |

---

## 4. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/movement/summary?date=` | Daily movement summary |
| GET | `/yego-lima-growth/movement/driver/{id}` | Full movement history |
| GET | `/yego-lima-growth/movement/list?date=&driver=` | Paginated movement list |

---

## 5. DRIVER MOVEMENT EXAMPLE

```
Driver: 87035c62...

06-05: PROGRAM_ENTRY: CHURN_PREVENTION
06-05: STATE_CHANGE: HEALTHY → CHURN_RISK (trigger: churn_risk_flag)
06-04: PROGRAM_CONTINUED: CHURN_PREVENTION
06-02: PROGRAM_ENTRY: ACTIVE_GROWTH
```

---

## 6. FILES CREATED

| File | Purpose |
|------|---------|
| `backend/app/services/yego_lima_movement_service.py` | Movement aggregation service |
| `backend/app/routers/yego_lima_movement_router.py` | Movement endpoints |
| `docs/...LG_ATTR_1_0A_MOVEMENT_ATTRIBUTION_FOUNDATION.md` | This document |

---

## 7. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS (6.89s) |
| python -m compileall | OK |
| Daily summary | YES |
| Driver history | YES |
| Movement list | YES |
| Built on existing persistence | YES |

---

## 8. BOUNDARY

```
WHAT WE KNOW NOW (1.0A):
  WHAT movement occurred ✓
  WHEN it occurred ✓
  Which PROGRAM changed ✓
  Which STATE changed ✓

WHAT WE DON'T KNOW YET (future):
  WHO caused it (action attribution)
  WHICH channel (channel attribution)
  WHICH program produced impact (program impact)
```

---

## 9. FINAL VERDICT

```
MOVEMENT ATTRIBUTION FOUNDATION CERTIFIED
```
