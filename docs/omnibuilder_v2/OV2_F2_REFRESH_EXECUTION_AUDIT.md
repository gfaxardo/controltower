# OV2-F.2 — REFRESH EXECUTION AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** AUDIT COMPLETE — 1 layer fixed, 1 blocked by DB saturation

---

## 1. PER-LAYER STATUS

| Layer | Expected | Before Repair | After Repair | Gap | Status |
|-------|----------|---------------|--------------|-----|--------|
| RAW_TRIPS | D-1 | 2026-06-06 | 2026-06-06 | 1 day | **FRESH** |
| RAW_YANGO | D-2 max | 2026-06-05 | 2026-06-05 | 2 days | OK |
| DAY_FACT | D-1 | 2026-05-31 | **2026-06-06** | 1 day | **FIXED** |
| WEEK_FACT | Within 7 days | 2026-04-20 | 2026-04-20 | **48 days** | **BLOCKED** |
| MONTH_FACT | Current month | 2026-06-01 | 2026-06-01 | OK | OK |
| SNAPSHOT | D-2 | 2026-06-05 | 2026-06-05 | 2 days | STALE |
| OPERATING_DATE | D-1 | 2026-05-31 | **2026-06-06** | 1 day | **FIXED** |

---

## 2. REFRESH RUN LOG

| Date | Pipeline | Status | Notes |
|------|----------|--------|-------|
| 2026-06-07 04:00 | business_slice | success | Daily scheduler job |
| 2026-06-06 04:00 | business_slice | success | Daily scheduler job |
| 2026-06-05 04:00 | business_slice | success | Daily scheduler job |
| 2026-06-04 04:00 | business_slice | success | Reports success BUT data wasn't updated past May 31 |
| 2026-06-03 15:36 | business_slice | **skipped** | Cooldown guard |
| 2026-06-03 15:25 | business_slice | **running** | **JOB STUCK — never completed** |
| 2026-06-03 04:00 | business_slice | success | |

**Finding:** The "running" job from June 3 at 15:25 never completed. It may still hold connections.

---

## 3. REPAIR EXECUTED

### Fix 1: day_fact (SUCCESS)

```bash
python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-04-01 --end-date 2026-06-08 --grain all --force
```

- Staging: 1,395 day rows, 1,805,044 trips
- Enriched materialization: 6,861,415 trips in 100.9s
- **Result: day_fact updated from 2026-05-31 to 2026-06-06**

### Fix 2: week_fact (BLOCKED — DB saturation)

- Staging started (6,861,415 trips, 99.5s) but timed out
- Follow-up runs hit `FATAL: sorry, too many clients already`
- Staging connections from the abortive run are still saturating PostgreSQL
- **Requires: manual connection cleanup on PostgreSQL server before retry**

---

## 4. FAILURE CHAIN

```
1. Refresh job reports "success" but data isn't updated
2. day_fact stays at 2026-05-31 for 7+ days
3. week_fact stays at 2026-04-20 (48 days)
4. User triggers manual refresh → staging queries consume DB connections
5. Staging query times out (>10 minutes) → connections are left open
6. "FATAL: too many clients already" — DB saturated
7. No new connections possible → facts stay stale
```

---

*End of Refresh Execution Audit*
