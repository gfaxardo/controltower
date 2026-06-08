# OV2-F.4C — DAY FACT BRIDGE CONTRACT

> **Date:** 2026-06-08
> **Status:** IMPLEMENTED

## SOURCE: `ops.driver_day_slice_fact`

## AGGREGATION

```sql
SELECT activity_date AS trip_date, country, city, business_slice_name,
       SUM(completed_trips) AS trips_completed,
       SUM(cancelled_trips) AS trips_cancelled,
       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS active_drivers,
       COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips = 0 AND total_trips > 0) AS empty_supply_drivers
FROM ops.driver_day_slice_fact
GROUP BY activity_date, country, city, business_slice_name
```

## REVENUE: Hybrid

Bridge has no revenue columns. Revenue preserved from existing `day_fact` via LEFT JOIN on `(trip_date, business_slice_name)`.

## DERIVED METRICS
- avg_ticket = revenue / trips (recalculated)
- trips_per_driver = trips / active_drivers (recalculated)

## SCRIPT
`backend/scripts/rebuild_day_from_bridge.py`
