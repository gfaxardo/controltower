# Action Engine — API Validation (Phase 5)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11  
**Base URL:** http://127.0.0.1:8000 (backend running)

---

## Routes tested

| Route | Params | Status | Response shape | Pass |
|-------|--------|--------|----------------|------|
| GET /ops/action-engine/summary | (none) | 200 | actionable_drivers, cohorts_detected, high_priority_cohorts, recoverable_drivers, high_value_at_risk, near_upgrade_opportunities | Yes |
| GET /ops/action-engine/cohorts | limit=2 | 200 | data[], total, limit, offset; items: week_start, cohort_type, cohort_size, avg_risk_score, suggested_priority, suggested_channel, action_name, action_objective | Yes |
| GET /ops/action-engine/recommendations | top_n=2 | 200 | data[] with priority_score, action_name, cohort_type, cohort_size, suggested_channel | Yes |
| GET /ops/top-driver-behavior/summary | (none) | 200 | elite_drivers, legend_drivers, ft_drivers | Yes |
| GET /ops/top-driver-behavior/benchmarks | (none) | 200 | data[] with segment_current, driver_count, avg_weekly_trips, consistency_score_avg, active_weeks_avg | Yes |

---

## Sample responses (excerpts)

**action-engine/summary:**
```json
{
  "actionable_drivers": 18421,
  "cohorts_detected": 298,
  "high_priority_cohorts": 175,
  "recoverable_drivers": 59972,
  "high_value_at_risk": 2926,
  "near_upgrade_opportunities": 0
}
```

**action-engine/cohorts (first item):**
```json
{
  "week_start": "2025-12-22",
  "cohort_type": "near_drop_risk",
  "cohort_size": 509,
  "suggested_priority": "high",
  "suggested_channel": "outbound_call",
  "action_name": "Contain FT at risk of downgrade",
  "action_objective": "Prevent collapse to lower segment"
}
```

**top-driver-behavior/benchmarks:**
```json
{
  "data": [
    {"segment_current": "LEGEND", "driver_count": 243, "avg_weekly_trips": 198.6, "consistency_score_avg": 0.746},
    {"segment_current": "ELITE", "driver_count": 2867, "avg_weekly_trips": 138.27, "consistency_score_avg": 0.7618},
    {"segment_current": "FT", "driver_count": 8132, "avg_weekly_trips": 85.5, "consistency_score_avg": 0.724}
  ]
}
```

---

## Expected fields (all present)

- **Cohorts:** cohort_type, cohort_size, suggested_priority, suggested_channel, action_name, action_objective, dominant_segment, avg_risk_score, avg_delta_pct.
- **Recommendations:** priority_score, action_name, cohort_type, cohort_size, suggested_channel.
- **Benchmarks:** segment_current, driver_count, avg_weekly_trips, consistency_score_avg.

---

## Conclusion

- All tested endpoints respond with HTTP 200.
- Response shapes and expected fields match. No missing fields observed.
- **Pass:** Yes for summary, cohorts, recommendations, top-driver summary, benchmarks.
