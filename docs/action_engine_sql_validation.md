# Action Engine — SQL Object Validation (Phase 3)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Method:** information_schema.views query (script: backend/scripts/check_action_engine_views.py)

---

## Result

| Object | Type | Exists? | Notes |
|--------|------|---------|--------|
| ops.v_action_engine_driver_base | VIEW | Yes | Driver-week with cohort_type; reads from ops.mv_driver_behavior_alerts_weekly |
| ops.v_action_engine_cohorts_weekly | VIEW | Yes | Aggregates by week_start, cohort_type |
| ops.v_action_engine_recommendations_weekly | VIEW | Yes | Cohorts + priority_score |
| ops.v_top_driver_behavior_weekly | VIEW | Yes | ELITE/LEGEND/FT from alerts MV |
| ops.v_top_driver_behavior_benchmarks | VIEW | Yes | Aggregate by segment_current |
| ops.v_top_driver_behavior_patterns | VIEW | Yes | By segment, city, park |

---

## Dependency

- All six are **VIEWs** (not materialized views). They do not require a dedicated refresh.
- They depend on **ops.mv_driver_behavior_alerts_weekly**. If that MV is refreshed (e.g. via ops.refresh_driver_behavior_alerts or equivalent), the views will return up-to-date data on next query.

---

## Conclusion

- All expected SQL objects exist in the target database.
- No dedicated refresh for Action Engine / Top Driver Behavior views; refresh of the underlying behavioral alerts MV is the only dependency.
