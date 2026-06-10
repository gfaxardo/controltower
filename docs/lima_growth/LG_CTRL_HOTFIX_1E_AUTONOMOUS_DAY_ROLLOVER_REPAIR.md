# LG-CTRL-HOTFIX-1E — Autonomous Day Rollover Repair

**Date**: 2026-06-10  
**Status**: RESOLVED (pending backend restart + 5-min wait)  
**Phase**: Control Foundation / Operational Reliability

---

## TAREA 0 — Phase Confirmation

Control Foundation. No new engines.

---

## TAREA 1 — Root Cause Analysis

**Why zero runs with `triggered_by='autonomous_tick'`?**

| Cause | Detail |
|---|---|
| **A. Scheduler row never created** | `growth.yego_lima_scheduler_status` had no row for `lima_growth_refresh`. `start_scheduler()` only does `UPDATE`, never `INSERT`. `autonomous_tick` returned `SKIPPED` silently. |
| **B. autonomous_tick never wrote to refresh_run_log** | Only updated internal `scheduler_status` table. Zero visibility. |
| **C. No daily cascade** | `autonomous_tick` was designed as "lightweight monitoring" only — governance, signals, history. Never rebuilt lists. |
| **D. Silent failure** | When `enabled=false` or row missing, `autonomous_tick` returned without writing to `tick_log`. Zero traces. |

**Classification: A + B + C + D (multiple)**

---

## TAREA 2-6 — Fixes Applied

### 1. Scheduler initialization (`yego_lima_scheduler_service.py`)

```python
def _ensure_scheduler_row(conn):
    INSERT INTO growth.yego_lima_scheduler_status (...)
    ON CONFLICT (scheduler_name) DO NOTHING
```

Called at every `autonomous_tick` invocation.

### 2. Full daily cascade in autonomous_tick

```
autonomous_tick():
  1. Ensure scheduler row
  2. Acquire advisory lock (anti-overlap)
  3. Detect latest operational date
  4. If new day detected:
       run_daily_refresh(target_date, triggered_by="autonomous_tick")
  5. sync_assignment_queue_to_control_loop(date)
  6. generate_all_serving_facts(date)
  7. refresh_freshness_registry()
  8. build_intraday_signals(date)
  9. snapshot_queue_to_history(date)
 10. Write to refresh_run_log (triggered_by='autonomous_tick')
 11. Write to tick_log (ALWAYS)
```

### 3. Control loop auto-sync (`yego_lima_control_loop_sync_service.py`)

```sql
INSERT INTO growth.yego_lima_control_loop_state
(id, driver_profile_id, current_state, created_at, ...)
SELECT gen_random_uuid(), q.driver_id, 'READY', now(), ...
FROM assignment_queue q
WHERE q.date = :date AND q.status = 'READY'
  AND NOT EXISTS (
    SELECT 1 FROM control_loop_state cl
    WHERE cl.driver_profile_id = q.driver_id
      AND cl.created_at::date = :date
  )
```

Rules:
- Only inserts READY drivers
- Never overwrites ASSIGNED / IN_PROGRESS / CONTACTED / DONE / CLOSED
- No duplicates (NOT EXISTS clause)

### 4. Governance visibility (`yego_lima_refresh_governance_service.py`)

Added to governance-status response:
```json
{
  "last_autonomous_tick": {
    "last_autonomous_tick_at": "2026-06-10T...",
    "last_autonomous_tick_status": "SUCCESS",
    "last_autonomous_run_id": "tick-20260610-...",
    "last_autonomous_tick_reason": null
  }
}
```

### 5. Observable states

| Status | When |
|---|---|
| `SUCCESS` | Full cascade + sync completed |
| `SUCCESS_NO_CASCADE` | Already caught up, lightweight monitoring only |
| `NOOP_NO_DATA` | No operational data available |
| `PARTIAL_CASCADE_FAILED` | Some steps failed |
| `FAILED` | Exception during tick |
| `SKIPPED_OVERLAP` | Previous tick still running |
| `SKIPPED` | Scheduler not enabled |

### 6. Manual vs auto separation

refresh_run_log.triggered_by now supports:
- `autonomous_tick` — APScheduler interval
- `system` — manual run via API
- `manual` — explicit POST call
- `startup_self_heal` — startup cascade

---

## Files Changed

| File | Change |
|---|---|
| `backend/app/services/yego_lima_scheduler_service.py` | `_ensure_scheduler_row`, full cascade `autonomous_tick`, tick_log always, refresh_run_log writes |
| `backend/app/services/yego_lima_control_loop_sync_service.py` | NEW — sync queue→control_loop |
| `backend/app/services/yego_lima_refresh_governance_service.py` | `last_autonomous_tick` in governance response |

---

## TAREA 7-8 — Verification Checklist

| Check | How to verify |
|---|---|
| Scheduler row exists | `SELECT * FROM growth.yego_lima_scheduler_status WHERE scheduler_name='lima_growth_refresh'` |
| Tick runs | Wait 5 min after restart, check `refresh_run_log WHERE triggered_by='autonomous_tick'` |
| Tick visible in governance | `GET /yego-lima-growth/refresh/governance-status` → `last_autonomous_tick` |
| Control loop populated | `SELECT COUNT(*) FROM growth.yego_lima_control_loop_state WHERE created_at::date='2026-06-09'` |
| No silent failures | All tick outcomes written to `growth.yego_lima_scheduler_tick_log` |
| No queue→CL duplicates | `NOT EXISTS` guard in sync |

---

## GO / NO-GO

**GO** — Autonomous rollover repaired.

Next step: restart backend, wait 5 minutes, verify autonomous_tick appears in refresh_run_log and governance.
