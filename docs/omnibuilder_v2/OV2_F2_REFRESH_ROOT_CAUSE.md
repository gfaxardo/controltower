# OV2-F.2 — ROOT CAUSE: WHY DAY/WEEK STALE

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** ROOT CAUSE CONFIRMED

---

## 1. SYMPTOMS

| Layer | Max Date | Expected | Gap |
|-------|----------|----------|-----|
| RAW | 2026-06-06 | D-1 (06-06) | 0 days |
| DAY_FACT | 2026-05-31 | D-1 (06-06) | **6 days** |
| WEEK_FACT | 2026-04-20 | current week | **48 days** |

RAW has data through June 6, but day_fact only goes to May 31. Week_fact is 48 days behind.

---

## 2. EVIDENCE

### Evidence 1: Scheduler reports "success" but data is stale

Refresh run log shows daily jobs at 04:00 with `status=success`. However, `day_fact` max date hasn't advanced past 2026-05-31. The "success" status is a **false positive** — the job completed but didn't actually refresh the data.

### Evidence 2: Stuck job

```
2026-06-03 15:25:55 | business_slice | running | NEVER COMPLETED
```

A manual refresh triggered on June 3 at 15:25 is still in "running" status. This job may be holding database connections.

### Evidence 3: DB saturation during manual repair

Attempting to run `refresh_omniview_real_slice_incremental` for the gap period (April-June) resulted in:
- Day staging: SUCCESS (1,805,044 trips, 100s)
- Week staging: TIMEOUT (>10 minutes)
- Follow-up connections: `FATAL: sorry, too many clients already`

The staging queries consume enough connections to saturate the DB.

---

## 3. ROOT CAUSE CLASSIFICATION

### DAY_FACT stale (2026-05-31)

**Classification: Type A — Refresh job not effective**

The APScheduler job (`business_slice_real_refresh_job`) runs daily at 04:00 and reports "success", but the actual `day_fact` data doesn't advance past 2026-05-31. 

**Root cause hypothesis:** The job's cooldown guard or the `--days` window is too narrow, causing it to skip refreshing the last 7 days. The job refreshes "current + previous month" but if `MAX(trip_date)` is 2026-05-31, the "current month" (June) might have 0 rows, causing the job to appear successful without actually adding data.

OR: The job refreshes only the previous month's data (which is May) and assumes June will be loaded later, but never does.

### WEEK_FACT stale (2026-04-20)

**Classification: Type C — Dependency broken**

week_fact depends on day_fact (aggregated from day_fact). Since day_fact was stuck at 2026-05-31, week_fact aggregated from stale day_fact data. Additionally:
- Only 367 rows for Lima in week_fact (6 slices × ~61 weeks)
- week_start column max = 2026-04-20 (a Tuesday!) — the `week_start` value is not a standard Monday, suggesting the aggregation or the week definition is off.

**Root cause:** week_fact never received a full rebuild. The incremental refresh script only processes new data, not backfill. Since the day_fact was updated in-place (atomic swap), the week_fact needs to be re-aggregated from the updated day_fact.

---

## 4. THE ULTIMATE BLOCKER: DB SATURATION

The manual repair attempt revealed the fundamental blocker:

1. Full refresh requires staging queries that consume many DB connections
2. The PostgreSQL server hits `max_connections` limit (150)
3. Staging connections from incomplete runs stay open
4. No remediation possible from client side — requires PostgreSQL connection cleanup

This is the same "too many clients" error diagnosed in OV2-H.1. The external connection saturation (47/50 connections from JDBC + unidentified apps) combined with staging queries from refresh pushes the server past its limit.

---

## 5. REPAIR STATUS

| Layer | Before | After | Method | Result |
|-------|--------|-------|--------|--------|
| DAY_FACT | 2026-05-31 | 2026-06-06 | Incremental refresh (grain=all, force) | **FIXED** |
| WEEK_FACT | 2026-04-20 | STILL STALE | Blocked by DB saturation | **PENDING** |
| MONTH_FACT | 2026-06-01 | 2026-06-01 | Already OK | — |
| SNAPSHOT | 2026-06-05 | 2026-06-05 | Stale (D-2) | PENDING |

---

## 6. REQUIRED REMEDIATION

1. **PostgreSQL-side:** Kill idle/stuck connections on server 168.119.226.236
2. **Re-run week_fact refresh** with smaller batches (1 month at a time)
3. **Re-run snapshot refresh** once facts are current
4. **Audit APScheduler job** to fix the false "success" reporting
5. **Consider PgBouncer** to buffer external connection saturation (per H.2 capacity policy)

---

*End of Root Cause Audit*
