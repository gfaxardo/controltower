# BEHAVIORAL SIGNAL AUDIT

**Date**: 2025-05-25
**Source**: `driver_behavior_benchmarking_service.py`, `behavioral_pattern_diagnosis_service.py`

---

## Data Sources

| Source | Table | Status |
|---|---|---|
| **Primary** | `ops.driver_daily_activity_fact` | Pre-aggregated fact table — 14 columns detected |
| **Fallback** | `public.trips_2026` | Raw trips table — used when fact table is empty/missing |

---

## Signal Inventory

### AVAILABLE NOW (enabled in code)

| Signal | Key | Source | Used By |
|---|---|---|---|
| Total trips (per driver) | `trips` / `completed_trips` | `driver_daily_activity_fact` | Classification, benchmakrs, group profiles |
| Active days | `active_days_from_activity_date` / `activity_date` | Fact table | Classification (TOP requires ≥30% days active) |
| Days since last trip | `days_since_last` | Fact table | CHURN/DORMANT detection |
| Country | `country` | Fact table | Filter + top cities |
| City | `city` | Fact table | Filter + top cities |
| Park ID | `park_id` | Fact table | Top parks per group |
| Weekend share | `weekend_share` | Computed from activity_date | Weekend pattern patterns |

### DERIVABLE (computed from available signals)

| Signal | Formula | Category |
|---|---|---|
| `avg_trips_per_driver` | `total_trips / drivers_count` | Productivity |
| `avg_active_days` | `total_active_days / drivers_count` | Consistency |
| `trips_per_active_day` | `total_trips / total_active_days` | Productivity |
| `consistency_score` | `mean(active_days_i / period_days)` | Stability |
| `delta_pct` | `(current - previous) / previous * 100` | Trend |
| `top_threshold` | 80th percentile of trips | Benchmark |
| `weekend_share` | `weekend_trips / total_trips` | Temporal |

### MISSING (hardcoded False — not yet enabled)

| Signal | Status | Reason |
|---|---|---|
| `revenue` | **False** | Column not in fact table / not yet integrated |
| `avg_ticket` | **False** | Revenue-dependent |
| `trip_hour` | **False** | Column not in fact table |
| `distance` | **False** | Column not in fact table |
| `duration` | **False** | Column not in fact table |
| `tipo_servicio` | **False** | Column not in fact table |
| `cancellation` | **False** | Column not in fact table |
| `online_hours` | **False** | Column not in fact table |
| `zone` | **False** | Column not in fact table |
| `acceptance` | **False** | Column not in fact table |

**Impact**: 8 of 12 behavioral DIMENSIONS cannot be populated because their underlying metrics are missing:
- `recency` — needs date-derived signals (partially available via days_since_last)
- `city_mix` / `park_mix` — needs dimension-aware metrics (currently only used for top-N queries)
- `lob_mix` — needs `tipo_servicio`
- `revenue_efficiency` — needs `revenue`
- `time_efficiency` — needs `trip_hour`, `duration`
- `distance_efficiency` — needs `distance`
- `cancellation_behavior` — needs `cancellation`, `acceptance`

### UNSAFE (not reliable for diagnosis)

| Signal | Risk |
|---|---|
| `peak_hour_share` | Always None in benchmarks — data not available |
| `avg_distance_km` | Always None in benchmarks — data not available |
| `avg_duration_sec` | Always None in benchmarks — data not available |
| `revenue_per_driver` | Always None in benchmarks — data not available |
| `avg_ticket` | Always None in benchmarks — data not available |

---

## Current Classification Thresholds

| Threshold | Value | Controls |
|---|---|---|
| Top performer trips | 80th percentile | `TOP_PERFORMER` |
| Top performer active days | `≥ period_days * 0.3` (≈8.4 for 28d) | `TOP_PERFORMER` |
| Churned days since last | `≥ 30` | `CHURNED` |
| Dormant days since last | `≥ 14` | `DORMANT` |
| AT_RISK low activity | `trips ≤ 3 AND active_days ≤ 3` | `AT_RISK` |
| AT_RISK decline | `delta_pct ≤ -40` | `AT_RISK` |
| DECLINING decline | `delta_pct ≤ -25` | `DECLINING` |
| GROWING growth | `delta_pct ≥ +25` | `GROWING` |
| STABLE | None of the above | `STABLE` |
| REACTIVATED | Previously inactive, now active | `REACTIVATED` |

---

## Gap Analysis

| Desired Signal | Can we compute today? | Gap |
|---|---|---|
| Trips per hour | ❌ | Missing `trip_hour` + `online_hours` |
| Revenue per hour | ❌ | Missing `revenue` + `online_hours` |
| Acceptance rate | ❌ | Missing `acceptance` |
| Cancellation rate | ❌ | Missing `cancellation` |
| Zone coverage | ❌ | Missing `zone` |
| Shift consistency | ❌ | Missing hourly data |
| Bonus dependency | ❌ | No bonus signal in schema |
| Loyalty effect | ❌ | No loyalty segment data |

**Conclusion**: Current system covers basic activity/consistency/productivity. Revenue, efficiency, and discipline metrics require fact table expansion or enrichment from `trips_2026`.
