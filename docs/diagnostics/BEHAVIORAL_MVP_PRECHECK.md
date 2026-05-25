# BEHAVIORAL DIAGNOSIS MVP — PRECHECK

**Date**: 2025-05-25
**Motor**: Diagnostic Engine 2A.3
**Status**: GO

---

## 1. PHASE CONFIRMATION

| Item | Value |
|---|---|
| Active Engine | Control Foundation (GO) + Diagnostic (ACTIVE 2A.3) |
| Behavioral Pattern Diagnosis | READY NEXT (per Diagnostic Layer Closure) |
| MVP scope | Only signals available in fact table |

---

## 2. SIGNAL CONSTRAINT CHECK

| Signal | Available? | Used in MVP? |
|---|---|---|
| trips | ✅ fact col `completed_trips` | ✅ activity_volume |
| active_days | ✅ computed from `activity_date` | ✅ consistency |
| days_since_last | ✅ computed | ✅ recency/inactive_risk |
| country | ✅ | ✅ filter |
| city | ✅ | ✅ filter |
| park_id | ✅ | ✅ filter |
| weekend_share | ✅ computed | ✅ weekday_weekend |
| revenue | ❌ | ❌ NOT used |
| avg_ticket | ❌ | ❌ NOT used |
| trip_hour | ❌ | ❌ NOT used |
| distance | ❌ | ❌ NOT used |
| duration | ❌ | ❌ NOT used |
| online_hours | ❌ | ❌ NOT used |
| acceptance | ❌ | ❌ NOT used |
| cancellation | ❌ | ❌ NOT used |
| zone | ❌ | ❌ NOT used |

---

## 3. MVP DIMENSIONS (5 of 12)

| # | Dimension | Metric | Status |
|---|---|---|---|
| 1 | `activity_volume` | avg_trips_per_driver | ✅ |
| 2 | `consistency` | active_days / period_days | ✅ |
| 3 | `productivity` | trips_per_active_day | ✅ |
| 4 | `weekday_weekend` | weekend_share | ✅ |
| 5 | `recency` | days_since_last | ✅ |

---

## 4. WHAT MVP WILL NOT DO

- No revenue analysis
- No time efficiency
- No distance analysis
- No cancellation analysis
- No acceptance analysis
- No zone analysis
- No recommendations
- No "call driver" actions
- No campaigns
- No AI
- No forecast

---

## 5. THRESHOLDS (reuse existing)

| Threshold | Value | Source |
|---|---|---|
| TOP trip volume | 80th percentile | `driver_behavior_benchmarking` |
| TOP active days | ≥ 30% of period | `driver_behavior_benchmarking` |
| GROWING delta | ≥ +25% | Existing classification |
| DECLINING delta | ≤ -25% | Existing classification |
| AT_RISK delta | ≤ -40% | Existing classification |
| INACTIVE_RISK days | ≥ 14 | Existing DORMANT threshold |
| CHURNED days | ≥ 30 | Existing threshold |

---

## VERDICT: GO

Honest MVP with only available signals. Gaps documented. Deterministic only. No invented metrics.
