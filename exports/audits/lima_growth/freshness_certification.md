# LG-C1.1 Freshness Certification

Generated: 2026-06-05T07:28:53.143706

## Summary

| Table | Rows | Biz Date | Insert | Lag (h) | Cert |
|-------|------|----------|--------|---------|------|
| driver_state_snapshot | 18475 | 2026-06-02 | 2026-06-03 09:50:36 | 45.6 | **WARNING** |
| prioritized_opportunity | 5777 | 2026-06-02 | 2026-06-03 19:47:52 | 35.7 | **WARNING** |
| driver_360_daily | 179 | 2026-06-02 | 2026-06-02 16:35:05 | 62.9 | **WARNING** |
| capacity_config | 0 | — | — | — | **WARNING** |
| loopcontrol_config | 1 | — | 2026-06-04 20:11:25 | 11.3 | **PASS** |
| loopcontrol_export | 30 | 2026-06-02 | 2026-06-04 19:22:50 | 12.1 | **PASS** |
| assignment_queue | 0 | — | — | — | **WARNING** |
| loopcontrol_result_sync | 0 | — | — | — | **WARNING** |
| impact_tracking | 0 | — | — | — | **WARNING** |
| movement_tracking | 0 | — | — | — | **WARNING** |
| attribution_candidates | 0 | — | — | — | **WARNING** |

## Component Certification

| Component | Certification | Reason |
|-----------|---------------|--------|
| prioritized_opportunity | **WARNING** | Stale but has data (has_7d=True, lag=35.7h) |
| driver_state_snapshot | **WARNING** | Stale but has data (has_7d=True, lag=45.6h) |
| driver_360_daily | **WARNING** | Stale but has data (has_7d=True, lag=62.9h) |
| assignment_queue | **WARNING** | Empty table |
| loopcontrol_result_sync | **WARNING** | Empty table |
| impact_tracking | **WARNING** | Empty table |
| movement_tracking | **WARNING** | Empty table |
| attribution_candidates | **WARNING** | Empty table |

## Risks

- **WARNING**: `driver_state_snapshot` — Stale 1-3 days (lag 45.6h)
- **WARNING**: `prioritized_opportunity` — Stale 1-3 days (lag 35.7h)
- **WARNING**: `driver_360_daily` — Stale 1-3 days (lag 62.9h)
- **WARNING**: `capacity_config` — Table is empty
- **WARNING**: `assignment_queue` — Table is empty
- **WARNING**: `loopcontrol_result_sync` — Table is empty
- **WARNING**: `impact_tracking` — Table is empty
- **WARNING**: `movement_tracking` — Table is empty
- **WARNING**: `attribution_candidates` — Table is empty

## Recommendations

- Run pipeline refresh if any table shows lag > 24h
- Ensure daily snapshots for driver_state and prioritized_opportunity
- Monitor assignment_queue for new daily batches
