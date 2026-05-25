# BEHAVIORAL MVP — SIGNAL GAPS

**Date**: 2025-05-25
**Data Source**: `ops.driver_daily_activity_fact`

---

## Signals Used (5)

| # | Signal | Column / Computed | Dimension |
|---|---|---|---|
| 1 | Trips | `completed_trips` | activity_volume |
| 2 | Active days | `COUNT DISTINCT activity_date` | consistency |
| 3 | Days since last | `MAX(activity_date)` vs today | recency |
| 4 | Weekend share | `ISODOW IN (6,7)` fraction | weekday_weekend |
| 5 | Trip delta | Current vs previous window trips | trend |

---

## Signals Unavailable (10)

| # | Signal | Why Missing | Impact |
|---|---|---|---|
| 1 | `revenue` | Not in fact table columns | Blocked: revenue_efficiency |
| 2 | `avg_ticket` | Depends on revenue | Blocked: revenue_efficiency |
| 3 | `trip_hour` | Not in fact table columns | Blocked: time_efficiency |
| 4 | `duration` | Not in fact table columns | Blocked: time_efficiency |
| 5 | `distance` | Not in fact table columns | Blocked: distance_efficiency |
| 6 | `online_hours` | Not in fact table columns | Blocked: time_efficiency |
| 7 | `cancellation` | Not in fact table columns | Blocked: cancellation_behavior |
| 8 | `acceptance` | Not in fact table columns | Blocked: cancellation_behavior |
| 9 | `zone` | Not in fact table columns | Blocked: geographic_behavior |
| 10 | `tipo_servicio` | Not in fact table columns | Blocked: lob_mix |

---

## Dimensions Affected

| Dimension | Status | Blocking Signals |
|---|---|---|
| `activity_volume` | ACTIVE | — |
| `consistency` | ACTIVE | — |
| `productivity` | ACTIVE | — |
| `weekday_weekend` | ACTIVE | — |
| `recency` | ACTIVE | — |
| `revenue_efficiency` | **BLOCKED** | revenue, avg_ticket |
| `time_efficiency` | **BLOCKED** | trip_hour, duration, online_hours |
| `distance_efficiency` | **BLOCKED** | distance |
| `cancellation_behavior` | **BLOCKED** | cancellation, acceptance |
| `city_mix` | **PARTIAL** | city available, zone blocked |
| `park_mix` | **ACTIVE** | park_id available |
| `lob_mix` | **BLOCKED** | tipo_servicio |

---

## Unblocking Path

To enable the blocked dimensions, the fact table `ops.driver_daily_activity_fact` needs additional columns. The `trips_2026` fallback table likely has more columns (revenue, trip_hour, distance) but using it would introduce a raw scan performance risk.

**Recommended**: Extend `ops.driver_daily_activity_fact` with pre-aggregated columns for `revenue`, `online_hours`, `cancelled_trips`, `accepted_trips`, and `trip_hour_peak_share`. This keeps serving-fact performance while expanding diagnostic coverage.
