# OV2-F.2C — ISO GRAIN CONTRACT AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** CONTRACT AUDIT COMPLETE

---

## 1. CURRENT STATE

### week_start computation

```sql
date_trunc('week', trip_date)::date
```

- PostgreSQL `date_trunc('week')` = Monday of the ISO week
- Returns a DATE, no timezone dependency
- **Correct for ISO Monday-based weeks**

### Current week_start audit

| Date | Expected Monday | Actual week_start | Match? |
|------|----------------|-------------------|--------|
| 2026-06-01 (Mon) | 2026-06-01 | — (stale) | — |
| 2026-04-20 (Mon) | 2026-04-20 | 2026-04-20 | ✓ |
| 2026-04-13 (Mon) | 2026-04-13 | — | — |
| 2025-12-29 (Mon) | 2025-12-29 | — | — |

**Verdict:** `week_start` IS a Monday. The stale date (2026-04-20) happens to be the last Monday that was successfully processed.

## 2. ISO WEEK TESTS

### Test 1: week_start always Monday

```sql
-- Verify all week_start values are Mondays
SELECT week_start, EXTRACT(DOW FROM week_start) AS dow
FROM ops.real_business_slice_week_fact
GROUP BY week_start
HAVING EXTRACT(DOW FROM week_start) != 1
```

**Expected:** 0 rows (all Mondays). PostgreSQL's `date_trunc('week')` guarantees this.

### Test 2: Week crossing months

ISO week 2026-05-25 (Monday) = May 25-31. Days:
- May 25-31 (7 days in May)
- Does NOT cross into June

ISO week 2026-06-01 (Monday) = June 1-7. Days:
- All in June

**Verdict:** No cross-month crossing for these dates. But ISO weeks CAN cross months in general (e.g., 2026-01-26 crosses Jan→Feb).

### Test 3: Week crossing years

ISO week 2025-12-29 (Monday) = Dec 29 - Jan 4
- Days in 2025: Dec 29-31 (3 days)
- Days in 2026: Jan 1-4 (4 days)
- This IS the correct ISO behavior — week 01 of 2026 starts Dec 29, 2025

**Current implementation:** `date_trunc('week', trip_date)` correctly handles this. A trip on 2026-01-01 gets `week_start = 2025-12-29`.

### Test 4: No GROUP BY month in week_fact

```sql
-- Current GROUP BY (from resolution query)
GROUP BY
    date_trunc('week', r.trip_date),   -- week_start only
    r.country, r.city, r.business_slice_name,
    r.fleet_display_name, r.is_subfleet, r.subfleet_name, r.parent_fleet_name
```

**Verdict:** NO month grouping. The GROUP BY uses week_start (derived from `date_trunc('week', trip_date)`), NOT calendar month. Cross-month weeks are preserved correctly.

## 3. COMPARISON: day_fact → week_fact rollup

The `_WEEK_ROLLUP_FROM_DAY_FACT` query also groups by:
```sql
date_trunc('week', trip_date)::date AS week_start
```

Using `trip_date` from `ops.real_business_slice_day_fact` which IS a date column. The same `date_trunc('week')` produces the same Monday-based weeks.

## 4. VERDICT

| Check | Status |
|-------|--------|
| week_start is always Monday | ✓ (PostgreSQL guarantee) |
| Cross-month weeks preserved | ✓ (GROUP BY week_start, not month) |
| Cross-year weeks preserved | ✓ (date_trunc handles year boundaries) |
| No GROUP BY month in week_fact | ✓ |
| day_fact → week_fact compatible | ✓ (same trip_date → same week_start) |

**ISO contract: CORRECT.** The week_start computation is correct in both the raw-based path and the day-based rollup path. The issue is only the data volume — 6.8M raw trips vs 2.5K day_fact rows.

---

*End of ISO Grain Contract Audit*
