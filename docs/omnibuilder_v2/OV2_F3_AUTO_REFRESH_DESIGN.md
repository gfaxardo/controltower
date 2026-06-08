# OV2-F.3 — AUTO REFRESH DESIGN

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Status:** DESIGN — NOT IMPLEMENTED

---

## 1. CURRENT STATE: MANUAL

```
[MANUAL] Bridge update → [MANUAL] Week rebuild → [AUTO?] Month refresh → [MANUAL] Snapshot
```

Every layer except the scheduler's daily day_fact job requires manual execution.

## 2. TARGET STATE: AUTOMATIC CASCADE

```
[APScheduler 04:00] → Check RAW
  ↓ RAW has new data
[APScheduler 04:05] → Build bridge for D-1
  ↓ Bridge updated
[APScheduler 04:10] → Refresh day_fact from bridge
  ↓ day_fact updated
[APScheduler 04:15] → Rebuild week_fact from day+bridge
  ↓ week_fact updated
[APScheduler 04:20] → Rebuild month_fact from bridge
  ↓ month_fact updated
[APScheduler 04:25] → Refresh snapshots
  ↓ Snapshots ready
[APScheduler 04:30] → Certification check → LOG result
```

Each step:
1. Checks if upstream has new data
2. If yes: executes refresh
3. If no: skips with `SUCCESS_NO_CHANGE`
4. Logs result to `ops.refresh_run_log`

## 3. NEW SCHEDULER JOBS

| Job | Time | Depends on | Action if stale |
|-----|------|-----------|-----------------|
| `driver_bridge_daily` | 04:05 | RAW D-1 exists | Build bridge for D-1 and D |
| `day_fact_from_bridge` | 04:10 | Bridge has D-1 | Rebuild day_fact from bridge |
| `week_fact_from_day_bridge` | 04:15 | day updated | Rebuild week_fact |
| `month_fact_from_bridge` | 04:20 | week updated | Rebuild month_fact |
| `snapshot_refresh` | 04:25 | All facts fresh | Refresh snapshots |
| `freshness_certification` | 04:30 | All above done | Run certify script, log |

## 4. SAFETY

- Each step validates upstream freshness before executing
- `SUCCESS_NO_CHANGE` if no new data (no unnecessary heavy queries)
- `BLOCKED` if upstream stale > threshold
- Recovery: cascade skips blocked layer, continues with stale data

---

*End of Auto Refresh Design*
