# OV2-F.2C — DAY→WEEK ROLLUP DESIGN

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** DESIGN COMPLETE — Ready for implementation

---

## 1. SOURCE: ops.real_business_slice_day_fact

Columns available:
- `trip_date` (DATE)
- `business_slice_name`
- `trips_completed`
- `revenue_yego_final`
- `revenue_yego_net`
- `active_drivers` (daily distinct)
- `avg_ticket` (daily)
- `trips_per_driver` (daily)
- `commission_pct` (daily)

Row count (Lima): ~2,500 (vs 6.8M raw trips)

## 2. ISO WEEK GROUPING

```sql
SELECT
    date_trunc('week', trip_date)::date AS week_start,
    (date_trunc('week', trip_date)::date + interval '6 days')::date AS week_end,
    country, city, business_slice_name,
    fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name,
    -- ── ADDITIVE METRICS ──
    SUM(trips_completed) AS trips_completed,
    SUM(trips_cancelled) AS trips_cancelled,
    SUM(COALESCE(revenue_yego_final, 0)) AS revenue_yego_final,
    SUM(COALESCE(revenue_yego_net, 0)) AS revenue_yego_net,
    -- ── DERIVED METRICS (recalculated, not averaged) ──
    CASE WHEN SUM(trips_completed) > 0
         THEN SUM(COALESCE(revenue_yego_final, 0)) / SUM(trips_completed)
    END AS avg_ticket,
    CASE WHEN SUM(active_drivers) > 0
         THEN SUM(trips_completed)::numeric / SUM(active_drivers)
    END AS trips_per_driver,
    -- ── SEMI-ADDITIVE METRICS ──
    SUM(active_drivers) AS active_drivers,  -- UPPER BOUND (see §3)
    -- ── DERIVED RATIOS ──
    CASE WHEN SUM(revenue_yego_net) > 0
         THEN SUM(revenue_yego_net) / NULLIF(SUM(revenue_yego_final), 0)
    END AS commission_pct
FROM ops.real_business_slice_day_fact
WHERE country = 'peru' AND city = 'lima'
  AND trip_date BETWEEN '2026-04-01' AND '2026-06-06'
GROUP BY week_start, week_end, country, city, business_slice_name,
         fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name
```

## 3. ACTIVE_DRIVERS STRATEGY

| Strategy | Accuracy | Complexity | Verdict |
|----------|----------|------------|---------|
| **A) SUM(day_fact.active_drivers)** | Upper bound (overcounts) | Low | Use with warning |
| B) DISTINCT from driver_daily_activity_fact | Exact | Medium (requires cross-table join) | Preferred |
| C) Bridge day→driver→week | Exact | High (new table) | Backlog |
| D) Raw trips (current) | Exact | Very high (6.8M scans) | DEPRECATED |

**Decision:** Use Strategy A with `ACTIVE_DRIVERS_WEEKLY_UPPER_BOUND` warning. Strategy B is the correct long-term fix but requires `driver_daily_activity_fact` to have `business_slice_name` mapping.

If `SUM(daily active_drivers)` for a week = 100 but `COUNT(DISTINCT driver_id)` = 85, the cell gets:
- value = 100
- warning = `ACTIVE_DRIVERS_WEEKLY_UPPER_BOUND`
- message = "Weekly active_drivers is sum of daily counts. True weekly distinct may be lower."

## 4. METRIC CLASSIFICATION

| Metric | Type | Day→Week Method | Accuracy |
|--------|------|----------------|----------|
| trips_completed | Additive | SUM | Exact |
| trips_cancelled | Additive | SUM | Exact |
| revenue_yego_final | Additive | SUM | Exact |
| revenue_yego_net | Additive | SUM | Exact |
| avg_ticket | Derived | SUM(revenue) / SUM(trips) | Recalculated |
| trips_per_driver | Derived | SUM(trips) / SUM(drivers) | Recalculated (upper bound) |
| active_drivers | Semi-additive | SUM (upper bound) | APPROXIMATION |
| commission_pct | Derived | SUM(net) / SUM(final) | Recalculated |

## 5. COMPARISON: CURRENT RAW PATH VS NEW DAY PATH

| Aspect | RAW path (current) | DAY path (new) |
|--------|-------------------|----------------|
| Rows scanned | 6,861,415 | ~2,500 |
| Connections needed | 8-12 | 2-3 |
| Execution time | >600s (timeout) | <5s |
| DB saturation risk | HIGH | NONE |
| active_drivers accuracy | Exact (DISTINCT) | Upper bound |
| Revenue accuracy | Exact | Exact (if day_fact has it) |
| ISO week correct | Yes | Yes |

**Savings:** 99.96% fewer rows scanned. From 600s+ to <5s. From DB-saturating to lightweight.

---

*End of Day→Week Rollup Design*
