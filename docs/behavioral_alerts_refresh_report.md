# Behavioral Alerts — Refresh Report

**Date:** 2026-03-11  
**Phase:** 3 — Refresh data objects

---

## Objects used by Behavioral Alerts

| Object | Type | Refresh |
|--------|------|--------|
| ops.v_driver_behavior_baseline_weekly | VIEW | No (always current from underlying tables/MVs) |
| ops.v_driver_behavior_alerts_weekly | VIEW | No (always current) |
| ops.mv_driver_behavior_alerts_weekly | MATERIALIZED VIEW | Yes, via `ops.refresh_driver_behavior_alerts()` |

---

## When refresh is needed

- After **supply / driver lifecycle** data is refreshed (e.g. `mv_driver_segments_weekly`, `mv_driver_weekly_stats` updated).
- So that Behavioral Alerts (and risk score) reflect the latest segments and trips.

---

## Service source

- `behavior_alerts_service` reads from **ops.v_driver_behavior_alerts_weekly** (the view), not directly from the MV.
- The view is always computed from the baseline view and underlying data; the MV is an optional performance cache. If the MV is used by the database for the view (it isn’t — the view is defined over the baseline view), or if the app were switched to query the MV, then refreshing the MV would be required for fresh data. As implemented, **querying the view** always uses current data; the **MV** is for performance (e.g. if the app were later pointed at the MV). Refreshing the MV is still recommended after upstream refreshes so that any future use of the MV or dependent objects sees up-to-date data.

---

## Refresh function

- **Function:** `ops.refresh_driver_behavior_alerts()`
- **Action:** `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_behavior_alerts_weekly;`
- **Created in:** Migration 083; recreated in 085 (after MV recreation).

---

## Execution during closure

- Migrations 081–085 were not fully confirmed at head (085 hit timeout; DB may still be at 080). Therefore **refresh was not run** in this closure.
- Once `alembic upgrade head` completes successfully, the MV will have been created and populated by migration 085. For ongoing use, run refresh after supply/lifecycle refresh:
  ```sql
  SELECT ops.refresh_driver_behavior_alerts();
  ```

---

## Conclusion

- **Refresh needed for Behavioral Alerts to work?** No — the app reads the **view**, which is always current.
- **Refresh needed for MV to be up to date?** Yes — after upstream data refreshes, run `ops.refresh_driver_behavior_alerts()`.
- **Refresh run in this closure?** No — migrations not confirmed at 085; user should run refresh after confirming migrations and after any supply/lifecycle refresh.
