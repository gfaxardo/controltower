# OV2-F.5 — DRIVER TRACEABILITY AUDIT

> **Date:** 2026-06-08
> **Status:** **READY**

---

## 1. CAN WE REACH DRIVER_ID WITHOUT 68M RAW TRIPS?

**YES.** `ops.driver_day_slice_fact` has:
- `driver_id` per row
- `activity_date` (day grain)
- `business_slice_name`
- `completed_trips`
- `country`, `city`, `park_id`

Row count (Lima): **162,486** (vs 6.8M raw trips)

## 2. DRILL PATH

```
Cell (month_fact, Auto regular, May 2026, trips=373,681)
  ↓
Driver bridge WHERE activity_date IN (May 2026)
  AND business_slice_name = 'Auto regular'
  ↓
SELECT driver_id, SUM(completed_trips) AS trips
FROM ops.driver_day_slice_fact
WHERE country='peru' AND city='lima'
  AND date_trunc('month', activity_date) = '2026-05-01'
  AND business_slice_name = 'Auto regular'
GROUP BY driver_id
ORDER BY trips DESC
  ↓
Returns: ~5,000-6,000 driver rows (monthly distinct)
```

## 3. VERDICT

**READY** — Driver-level breakdown is reconstructable from the bridge at day, week, or month grain. No raw trip scanning required.

## 4. SUPPORTING FACTS

- `ops.driver_daily_activity_fact` — has driver_id + activity_date + park_id (no slice)
- `ops.driver_day_slice_fact` (bridge) — has driver_id + activity_date + slice + park

Bridge is the primary source for driver drill.
