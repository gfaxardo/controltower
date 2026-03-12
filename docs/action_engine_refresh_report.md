# Action Engine — Refresh Validation (Phase 4)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## Requirement

- **Action Engine** and **Top Driver Behavior** use only **VIEWs** (no MVs).
- Those views read from **ops.mv_driver_behavior_alerts_weekly** (and for driver_base/cohorts, from that MV via the view definition).
- Therefore there is **no dedicated refresh** for Action Engine or Top Driver Behavior objects.

---

## When data is “fresh”

- **ops.mv_driver_behavior_alerts_weekly** is a materialized view. If your pipeline runs a refresh (e.g. `REFRESH MATERIALIZED VIEW ops.mv_driver_behavior_alerts_weekly` or a function that does so), then the next time the UI or API queries the Action Engine / Top Driver Behavior views, they will see that refreshed data.
- No separate refresh step was run during this preflight because:
  1. The feature uses views, not MVs.
  2. Refreshing the behavioral alerts MV is outside the scope of this verification and is environment-specific.

---

## Conclusion

- **Refresh required for Action Engine / Top Driver Behavior views?** No (they are views).
- **If data appears stale:** Ensure **ops.mv_driver_behavior_alerts_weekly** has been refreshed according to your pipeline; then re-query the UI or API.
