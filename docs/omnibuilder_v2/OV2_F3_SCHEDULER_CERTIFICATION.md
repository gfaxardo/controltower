# OV2-F.3 — SCHEDULER CERTIFICATION

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Status:** AUDIT COMPLETE

---

## 1. APSCHEDULER STATUS

| Job | Schedule | Status | Evidence |
|-----|----------|--------|----------|
| `omniview_business_slice_real_refresh` | Daily 04:00 | **RUNNING** (false positives) | refresh_run_log shows daily "success" |
| `serving_fact_daily_refresh` | Daily 05:00 | **RUNNING** | Scheduled in main.py |
| `omniview_real_data_watchdog` | Every 15min | **RUNNING** | Scheduled in main.py |

## 2. SCHEDULER ISSUE: FALSE POSITIVE

The daily 04:00 job reports `status=success` even when no new data is loaded. Evidence:
- F.2 audit found day_fact stuck at 2026-05-31 for 7 days despite daily "success" runs
- The job refreshes "current + previous month" but if current month has 0 rows, it reports success without loading

**Fix needed:** Before/after data validation in the job to detect `SUCCESS_NO_CHANGE` vs `SUCCESS_WITH_DATA`.

## 3. WHAT'S MISSING FROM SCHEDULER

| Gap | Impact |
|-----|--------|
| No driver bridge update job | Bridge only built manually |
| No cascade refresh (day→week→month) | Each layer refreshed independently |
| No snapshot auto-refresh after facts update | Snapshots must be triggered manually |
| No staleness alert | Freshness degrades silently |

## 4. VERDICT

**YELLOW** — Scheduler runs but with false positives and no cascade. Bridge update not scheduled.

---

*End of Scheduler Certification*
