# OV2-F.5 — PARK TRACEABILITY AUDIT

> **Date:** 2026-06-08
> **Status:** **READY** (day/week/month)

---

## 1. PARK_ID AVAILABILITY

| Table | park_id | Coverage |
|-------|---------|----------|
| `ops.driver_day_slice_fact` | ✅ Yes | 100% (all driver rows) |
| `ops.real_business_slice_day_fact` (bridge rebuilt) | ❌ No | Lost in aggregation |
| `ops.real_business_slice_week_fact` (bridge rebuilt) | ❌ No | Same |
| `ops.real_business_slice_month_fact` (bridge rebuilt) | ❌ No | Same |
| `ops.business_slice_mapping_rules` | ✅ Yes | Mapping key |

## 2. RECONSTRUCTION PATH

```
cell (day_fact) → JOIN driver_day_slice_fact ON (activity_date, business_slice_name)
                → park_id
                → SUM(completed_trips) GROUP BY park_id
```

The bridge has `park_id` per driver-day-slice. To get park-level breakdowns:
1. Query bridge for the same date + slice
2. GROUP BY park_id
3. SUM(completed_trips) per park

## 3. VERDICT

**READY** — park breakdown is reconstructable from the bridge without scanning raw trips. Bridge has 100% park_id coverage.

## 4. SQL EXAMPLE

```sql
SELECT park_id, SUM(completed_trips) AS trips,
       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS drivers
FROM ops.driver_day_slice_fact
WHERE country = 'peru' AND city = 'lima'
  AND activity_date = '2026-06-06'
  AND business_slice_name = 'Auto regular'
GROUP BY park_id
```
