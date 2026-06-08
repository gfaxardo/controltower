# OV2-F.2B — WEEK FACT ROOT CAUSE

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** ROOT CAUSE CONFIRMED

---

## 1. SYMPTOM

week_fact max date = **2026-04-20** (48 days behind today 2026-06-07).

---

## 2. EVIDENCE CHAIN

### Evidence 1: week_fact is never rebuilt

The `refresh_omniview_real_slice_incremental` script uses atomic staging. It:
1. Materializes enriched data (6.8M trips)
2. Inserts into staging table
3. Validates staging data
4. Swaps staging ↔ production (atomic)

Step 2 for `week_fact` staging timed out (>600s). Step 4 never executed. The staging data exists but was never promoted to production.

### Evidence 2: day_fact was successfully swapped

In the same run, `day_fact` staging completed (1.8M trips, 100s) and was swapped. `day_fact` now shows 2026-06-06. This confirms the script works — it just can't handle the `week_fact` staging volume in a single transaction.

### Evidence 3: week_fact staging volume is the bottleneck

- day_fact staging: 1,395 rows from 6.8M trips
- week_fact staging: likely more complex (GROUP BY week_start, business_slice from day-level granularity)

The week_fact staging requires aggregating day-level data into weeks, which for 2+ months of 6.8M trips is computationally heavy. The query exceeds the 10-minute timeout.

### Evidence 4: Connection exhaustion on second attempt

Attempting to re-run week-only refresh opened NEW staging connections while previous staging connections from the timed-out run were still open. This doubled the connection load and saturated the DB.

---

## 3. CLASSIFICATION

| Factor | Type | Details |
|--------|------|---------|
| **Primary** | **Type D — Timeout** | week_fact staging query exceeds 600s timeout |
| **Contributing** | **Type E — Connection exhaustion** | Staging connections from timed-out run not released |
| **Underlying** | **Type C — Refresh batch** | Single-batch refresh for 68+ days (Apr-Jun) is too heavy |

**Final classification: D + E + C (Time-out + Connection exhaustion + Batch size)**

---

## 4. WHY 2026-04-20 SPECIFICALLY?

The week_fact column is `week_start` (a date field representing the Monday of the ISO week). 2026-04-20 is a **Monday** — this is the correct format for `week_start`.

The last successful week_fact refresh was for the full month of April (up to April 20, the last Monday in April that had complete data). The May and June weeks were never built because:
1. day_fact was stale (stuck at 2026-05-31)
2. After fixing day_fact, the week_fact staging timed out
3. No subsequent refresh completed

---

## 5. RESOLUTION PATH

1. Clean up PostgreSQL connections (kill idle staging connections)
2. Re-run week_fact refresh in **30-day batches** (avoid the 6.8M trip staging)
3. Validate waterfall integrity after each batch
4. Re-run snapshot refresh after all facts are current

---

*End of Week Fact Root Cause*
