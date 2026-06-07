# LG-INFRA-R1.2 — Daily Closed Lists + Live Monitoring Contract

**Date:** 2026-06-06
**Phase:** LG-INFRA-R1.2 Daily Closed Lists + 5-Min Live Result Monitoring

---

## 1. EXECUTIVE SUMMARY

**REFRESH CONTRACT CORRECTED.**

The operational contract now separates two distinct cycles:

- **A) DAILY CLOSED PIPELINE:** Once per day. Builds all operational layers from Yango API. Produces today's action plan.
- **B) LIVE 5-MIN MONITORING:** Every 5 minutes. Maintains API freshness. Monitors results. Does NOT rebuild lists.

This prevents the anti-pattern of "rebuild everything every 5 minutes" while keeping freshness and results visible.

---

## 2. WHAT CHANGED

| Before (incorrect) | After (correct) |
|-------------------|-----------------|
| "Scheduler rebuilds full pipeline every 5 min" | Scheduler only live-monitors every 5 min |
| "refresh/run recalculates everything" | refresh/run is the daily closed pipeline |
| No separation of concerns | Two distinct cycles with clear responsibilities |
| No midnight behavior defined | Midnight+1 contract with pre-warming |

---

## 3. DAILY CLOSED PIPELINE CONTRACT

See: `docs/lima_growth/LG_OPERATIONAL_REFRESH_CONTRACT.md`

- Trigger: POST /scheduler/run-daily-closed
- Input: Yango API closed operational date
- Output: 8 serving facts, Today Action Plan ready
- Idempotent, never mutates exported records

---

## 4. LIVE 5-MIN MONITORING CONTRACT

See: `docs/lima_growth/LG_OPERATIONAL_REFRESH_CONTRACT.md`

- Trigger: POST /scheduler/tick (every 5 min via cron)
- Maintains: Yango API ingestion, MV freshness, governance
- Monitors: Action results (backlog), campaign status
- Does NOT: rebuild eligibility, prioritization, queue

---

## 5. SCHEDULER CORRECTION

| Endpoint | Mode | Purpose |
|----------|------|---------|
| POST /tick | Live Monitoring | 5-min maintenance tick |
| POST /run-daily-closed | Daily Pipeline | Full daily rebuild |
| POST /run-live-monitoring | Live Monitoring | Explicit monitoring run |

The old `scheduler_tick()` (which ran refresh) is deprecated. Tick now runs `run_live_monitoring()`.

---

## 6. BACKLOG CREATED

`docs/backlog/BACKLOG_CONTROL_LOOP_LIVE_RESULT_MONITORING.md`

- Result signal table design (`yego_lima_action_result_signal`)
- Live monitoring of contacted drivers (trips, supply after action)
- Reactivation detection
- Blocked until R3.x Impact + Attribution foundation

---

## 7. PRE-WARM CONTRACT

The 5-min loop keeps Yango API data fresh. At midnight:
- raw_yango is already current (< 5 min old)
- MVs are already refreshed
- Daily Closed Pipeline only needs to build operational layers
- No re-ingestion of history that was already maintained

---

## 8. DOCUMENTS CREATED / MODIFIED

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `docs/lima_growth/LG_OPERATIONAL_REFRESH_CONTRACT.md` | Canonical refresh contract |
| `docs/lima_growth/LG_INFRA_R1_2_DAILY_CLOSED_LISTS_LIVE_MONITORING_CONTRACT.md` | Este documento |
| `docs/backlog/BACKLOG_CONTROL_LOOP_LIVE_RESULT_MONITORING.md` | Live result monitoring backlog |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/services/yego_lima_scheduler_service.py` | +run_daily_closed_pipeline, +run_live_monitoring |
| `backend/app/routers/yego_lima_scheduler.py` | +2 new endpoints (run-daily-closed, run-live-monitoring) |

---

## 9. QA

| Check | Resultado |
|-------|:---------:|
| Corrected contract documented | YES |
| Scheduler dual-mode implemented | YES |
| Daily closed pipeline separate from live monitoring | YES |
| 5-min tick does NOT rebuild lists | YES |
| Backlog created | YES |
| Pre-warm contract documented | YES |
| Midnight+1 contract documented | YES |
| Backend compile | OK |
| Frontend build | PASS |

---

## 10. VEREDICTO

```
REFRESH CONTRACT CORRECTED
```

**Dual-cycle architecture:**
- **Daily (00:01):** Pipeline builds operational layers → Today Action Plan ready
- **5-min:** Live monitoring maintains API freshness → governance updated → results tracked
- **Pre-warmed:** Yango API stays fresh all day → midnight rebuild is fast
