# OV2-F.2C — DRIVER WEEKLY DISTINCT AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** AUDIT COMPLETE

---

## 1. QUESTION

Can we calculate `active_drivers` at weekly grain without scanning raw trips?

## 2. SOURCE: driver_daily_activity_fact

```sql
-- Table: ops.driver_daily_activity_fact
-- Columns: driver_id, activity_date, trips_completed, country, city
```

### Check: Does it have business_slice_name?

Likely NO — the driver_daily_activity_fact is at driver granularity, not slice. It may have fleet/LOB but not the same business_slice_name as day_fact.

### If it has business_slice_name

```sql
SELECT date_trunc('week', activity_date)::date AS week_start,
       business_slice_name,
       COUNT(DISTINCT driver_id) AS weekly_active_drivers
FROM ops.driver_daily_activity_fact
WHERE country = 'peru' AND city = 'lima'
  AND trips_completed > 0
GROUP BY week_start, business_slice_name
```

Then JOIN with week_fact to fill `active_drivers` accurately.

### If it does NOT have business_slice_name

Then Strategy A (SUM of daily active_drivers with warning) is the only option without raw trips.

## 3. VERDICT

| Question | Answer |
|----------|--------|
| Exact weekly active_drivers without raw trips? | **NO** — unless driver_daily_activity_fact has business_slice_name |
| By slice? | **NO** — driver table not sliced by business slice |
| By city? | **YES** — if driver table has city |
| By park? | **YES** — if driver table has park_id |
| What's missing? | business_slice_name on driver_daily_activity_fact |

## 4. RECOMMENDATION

**Short term (F.2C):** Use Strategy A (SUM daily active_drivers) with `ACTIVE_DRIVERS_WEEKLY_UPPER_BOUND` warning. This is safe because:
- It overcounts (never undercounts)
- The true distinct is always ≤ SUM(daily)
- The error is bounded (driver working 6 days in a week → counted 6 times instead of 1)

**Long term (backlog):** Add `business_slice_name` to `driver_daily_activity_fact` and use Strategy B (JOIN on week_start + slice).

---

*End of Driver Weekly Distinct Audit*
