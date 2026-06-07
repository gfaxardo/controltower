# BACKLOG — Lima Growth Daily Refresh Scheduler

**Date:** 2026-06-06
**Phase:** BACKLOG (NO IMPLEMENTAR)
**Registry:** LG-UX-R2.9G.3 — Part B

---

## NEED

Today the Lima Growth daily pipeline exists (`POST /yego-lima-growth/pipeline/run-daily` runs 15 build steps) but is triggered only manually. The APScheduler in `main.py` has no Lima Growth jobs — only Omniview.

Data becomes stale within hours of the last manual run. For 2026-06-06, data exists only for 2026-06-02.

---

## SCHEDULED JOB CONTRACT

```json
{
  "job_id": "lima_growth_daily_pipeline",
  "schedule": "cron: hour=3, minute=0",
  "timezone": "America/Lima",
  "function": "run_daily_pipeline_for_most_recent_closed_date",
  "enabled_by": "LIMA_GROWTH_DAILY_REFRESH_ENABLED",
  "retry_policy": {
    "max_retries": 2,
    "retry_delay_minutes": 30
  },
  "alerting": {
    "on_failure": "log + operational banner in UI",
    "on_success": "silent"
  }
}
```

---

## SLA

| Metric | Target |
|--------|:---:|
| Data freshness for operational date | <= 6 hours after close |
| Pipeline duration | <= 15 minutes |
| Max consecutive failures before alert | 2 |

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| APScheduler installed | YES |
| APScheduler available in main.py | YES (Omniview jobs) |
| Lima Growth pipeline service | EXISTS (15 steps) |
| Refresh orchestrator | EXISTS (R2.9G.3) |
| Refresh run log table | EXISTS |

---

## IMPLEMENTATION PLAN

1. Add `LIMA_GROWTH_DAILY_REFRESH_ENABLED` setting (default: `False`)
2. Add `LIMA_GROWTH_DAILY_REFRESH_HOUR` setting (default: `3`)
3. Wire `run_daily_refresh()` into APScheduler in `main.py` startup
4. Add freshness gate (don't re-run if < 6h old)
5. Add status visible in `/refresh/status`

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Lima Growth Daily Refresh Scheduler
Registered: 2026-06-06
Phase: LG-UX-R2.9G.3 — Part B
Status: BACKLOG — NO IMPLEMENTAR
Next review: Post R3.1 Program Registry Foundation
```
