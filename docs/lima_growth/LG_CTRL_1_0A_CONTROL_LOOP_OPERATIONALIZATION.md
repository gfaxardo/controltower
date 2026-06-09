# LG-CTRL-1.0A — Control Loop Operationalization

**Date:** 2026-06-09
**Motor:** Control Loop
**Phase:** LG-CTRL-1.0A
**Status:** CONTROL LOOP OPERATIONALIZED

---

## 1. EXECUTIVE SUMMARY

**CONTROL LOOP: OPERATIONALIZED.**

9 workflow states defined (READY → ASSIGNED → CONTACTED → DONE). Control loop state table (migration 199) tracks every driver's current state, agent, channel, days_in_state, and staleness. 4 endpoints serve summary, agent workload, stale detection, and per-driver detail.

---

## 2. WORKFLOW STATES

```
READY → ASSIGNED → IN_PROGRESS → CONTACTED → [NO_ANSWER|NOT_INTERESTED|CONVERTED] → DONE → CLOSED
```

---

## 3. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| GET | `/yego-lima-growth/control-loop/summary?date=` | By-state aggregation |
| GET | `/yego-lima-growth/control-loop/agents` | Agent workload |
| GET | `/yego-lima-growth/control-loop/stale?limit=` | Stuck drivers |
| GET | `/yego-lima-growth/control-loop/driver/{id}` | Per-driver detail + action history |

---

## 4. STALE DETECTION

| Condition | Status |
|-----------|:---:|
| < 2 days in state | NORMAL |
| 3-6 days | AGING |
| 7+ days | **STALE** |

Tracked via `is_stale` flag + `days_in_current_state`.

---

## 5. AGENT WORKLOAD

Per agent: total assigned, closed, pending.

---

## 6. FILES CREATED

| File | Purpose |
|------|---------|
| `backend/alembic/versions/199_yego_lima_control_loop.py` | Control loop state table |
| `backend/app/services/yego_lima_control_loop_service.py` | Control loop service |
| `backend/app/routers/yego_lima_control_loop_router.py` | Control loop endpoints |
| `docs/...LG_CTRL_1_0A_CONTROL_LOOP_OPERATIONALIZATION.md` | This document |

---

## 7. QA

| Check | Result |
|-------|:---:|
| Migration 199 applied | YES |
| npm run build | PASS (8.50s) |
| 9 workflow states | YES |
| Summary endpoint | YES |
| Agent workload | YES |
| Stale detection | YES |
| Per-driver detail | YES |

---

## 8. FINAL VERDICT

```
CONTROL LOOP OPERATIONALIZED
```
