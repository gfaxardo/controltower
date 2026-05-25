# BEHAVIORAL DIAGNOSTIC CONTRACT

**Date**: 2025-05-25
**Motor**: Diagnostic Engine 2A.3
**API Prefix**: `/behavioral-patterns`

---

## 1. OFFICIAL DIMENSIONS

Defined at `behavioral_pattern_diagnosis_service.py:39-44`.

| # | Dimension | Status | Metrics Used |
|---|---|---|---|
| 1 | `activity_volume` | **ACTIVE** | avg_trips_per_driver |
| 2 | `consistency` | **ACTIVE** | avg_active_days, consistency_score |
| 3 | `productivity` | **ACTIVE** | trips_per_active_day |
| 4 | `recency` | PARTIAL | days_since_last (classification only) |
| 5 | `weekday_weekend` | **ACTIVE** | weekend_share |
| 6 | `city_mix` | PARTIAL | top_cities (group profile only) |
| 7 | `park_mix` | PARTIAL | top_parks (group profile only) |
| 8 | `lob_mix` | MISSING | tipo_servicio (not in fact table) |
| 9 | `revenue_efficiency` | MISSING | revenue (not in fact table) |
| 10 | `time_efficiency` | MISSING | trip_hour, duration (not in fact table) |
| 11 | `distance_efficiency` | MISSING | distance (not in fact table) |
| 12 | `cancellation_behavior` | MISSING | cancellation, acceptance (not in fact table) |

---

## 2. OFFICIAL LIFECYCLE GROUPS

Defined at `driver_behavior_benchmarking_service.py:22-31`.

| # | Group | Classification Rule |
|---|---|---|
| 1 | `TOP_PERFORMER` | trips ≥ 80th percentile AND active_days ≥ 30% of period |
| 2 | `STABLE` | Default — none of the other rules apply |
| 3 | `GROWING` | delta_pct ≥ +25% |
| 4 | `DECLINING` | delta_pct ≤ -25% |
| 5 | `AT_RISK` | delta_pct ≤ -40% OR (trips ≤ 3 AND active_days ≤ 3) |
| 6 | `DORMANT` | days_since_last ≥ 14 OR trips == 0 |
| 7 | `CHURNED` | days_since_last ≥ 30 |
| 8 | `REACTIVATED` | Previously inactive, now active |

**Comparison pairings** (used for pattern detection):
```
TOP_PERFORMER vs AT_RISK
TOP_PERFORMER vs DECLINING
TOP_PERFORMER vs STABLE
STABLE vs DECLINING
STABLE vs AT_RISK
GROWING vs DECLINING
DECLINING vs AT_RISK
```

---

## 3. STRENGTH CLASSIFICATION

Defined at `behavioral_pattern_diagnosis_service.py:153-163`.

| Strength | Ratio metrics (consistency_score, weekend_share) | Non-ratio metrics (trips, days, trips/day) |
|---|---|---|
| **HIGH** | gap ≥ 30% | gap ≥ 100% |
| **MEDIUM** | gap ≥ 15% | gap ≥ 50% |
| **LOW** | gap ≥ 5% | gap ≥ 25% |

---

## 4. DECLINE SIGNALS

Defined at `behavioral_pattern_diagnosis_service.py:288-297`.

| Signal | Dimension | Metric |
|---|---|---|
| Disminución de volumen de viajes | activity_volume | avg_trips_per_driver |
| Reducción de días activos | consistency | avg_active_days |
| Caída de productividad diaria | productivity | trips_per_active_day |
| Pérdida de consistencia | consistency | consistency_score |
| Cambio en patrón de fin de semana | weekday_weekend | weekend_share |

---

## 5. API CONTRACTS

### GET `/behavioral-patterns/summary`

```json
{
  "total_patterns_detected": 12,
  "high_strength_patterns": 3,
  "medium_strength_patterns": 5,
  "low_strength_patterns": 4,
  "dimensions_available": ["activity_volume", "consistency", "productivity", "weekday_weekend"],
  "dimensions_missing": ["recency", "city_mix", "park_mix", "lob_mix", ...],
  "available_metrics": ["trips", "country", "city", "park_id", "weekend_share"],
  "missing_metrics": ["revenue", "avg_ticket", "trip_hour", ...],
  "data_source": "ops.driver_daily_activity_fact",
  "source_warning": null,
  "diagnostic_mode": "deterministic",
  "period_days": 28,
  "date_range": {"from": "2025-04-27", "to": "2025-05-25"}
}
```

### GET `/behavioral-patterns/patterns`

```json
{
  "patterns": [
    {
      "pattern_id": "productivity_top_performer_vs_at_risk",
      "dimension": "productivity",
      "title": "Mayor productividad por día en TOP_PERFORMER",
      "strength": "HIGH",
      "comparison_groups": "TOP_PERFORMER vs AT_RISK",
      "metric_name": "trips_per_active_day",
      "top_value": 12.5,
      "comparison_value": 4.2,
      "gap_abs": 8.3,
      "gap_pct": 197.6,
      "sample_size": 450,
      "interpretation": "TOP_PERFORMER concentra más viajes por día activo que AT_RISK.",
      "available": true,
      "source": "ops.driver_daily_activity_fact"
    }
  ],
  "total": 12,
  "diagnostic_mode": "deterministic",
  "period_days": 28,
  "date_range": {"from": "2025-04-27", "to": "2025-05-25"},
  "data_source": "ops.driver_daily_activity_fact",
  "source_warning": null
}
```

### GET `/behavioral-patterns/group-profile?group_name=DECLINING`

```json
{
  "group_name": "DECLINING",
  "drivers_count": 85,
  "total_trips": 2340,
  "avg_trips_per_driver": 27.5,
  "avg_active_days": 12.3,
  "trips_per_active_day": 2.2,
  "consistency_score": 0.44,
  "weekend_share": 0.18,
  "avg_ticket": null,
  "revenue_per_driver": null,
  "peak_hour_share": null,
  "top_cities": [
    {"label": "CALI", "trips": 1200, "driver_count": 45},
    {"label": "BOGOTA", "trips": 800, "driver_count": 30}
  ],
  "top_parks": [
    {"label": "PARK_A", "trips": 500, "driver_count": 20}
  ],
  "available_metrics": ["trips", "country", "city", "park_id", "weekend_share"],
  "missing_metrics": ["revenue", "avg_ticket", "trip_hour", ...],
  "data_source": "ops.driver_daily_activity_fact",
  "source_warning": null
}
```

### GET `/behavioral-patterns/decline-signals`

```json
{
  "signals": [
    {
      "signal_name": "Caída de productividad diaria",
      "dimension": "productivity",
      "metric": "trips_per_active_day",
      "stable_value": 5.8,
      "declining_value": 2.2,
      "at_risk_value": 1.1,
      "max_gap_pct": 81.0,
      "max_gap_vs": "STABLE vs AT_RISK",
      "interpretation": "AT_RISK presenta menos viajes por día activo comparado con STABLE.",
      "strength": "MEDIUM",
      "details": [...]
    }
  ],
  "total": 5,
  "diagnostic_mode": "deterministic",
  "period_days": 28,
  "date_range": {"from": "2025-04-27", "to": "2025-05-25"},
  "data_source": "ops.driver_daily_activity_fact",
  "source_warning": null,
  "note": "Señales de deterioro operativo detectadas comparando STABLE vs DECLINING / AT_RISK. Las interpretaciones son diagnósticas, no recomendaciones."
}
```

---

## 6. ENTITY-LEVEL DIAGNOSTIC CONTRACT (Target for UI Integration)

The next layer (not yet built) should produce per-entity diagnostics:

```json
{
  "entity_id": "driver_123",
  "entity_type": "driver",
  "diagnostic_window": "28d",
  "lifecycle_group": "DECLINING",
  "behavioral_status": "declining",
  "dimensions": {
    "productivity": {
      "status": "critical",
      "metric": "trips_per_active_day",
      "current_value": 2.2,
      "benchmark_value": 5.8,
      "benchmark_group": "STABLE",
      "delta_pct": -62.1,
      "strength": "HIGH",
      "days_active_last_28": 12
    },
    "consistency": {
      "status": "warning",
      "metric": "consistency_score",
      "current_value": 0.44,
      "benchmark_value": 0.72,
      "benchmark_group": "STABLE",
      "delta_pct": -38.9,
      "strength": "MEDIUM"
    },
    "activity_volume": {
      "status": "warning",
      "metric": "avg_trips_per_driver",
      "current_value": 27.5,
      "benchmark_value": 52.0,
      "benchmark_group": "STABLE",
      "delta_pct": -47.1,
      "strength": "MEDIUM"
    }
  },
  "dominant_factor": "trips_per_active_day_decline",
  "dominant_dimension": "productivity",
  "benchmark_group": "STABLE",
  "trend": "declining",
  "signals": [
    {
      "signal_name": "Caída de productividad diaria",
      "dimension": "productivity",
      "gap_pct": -62.1,
      "strength": "HIGH",
      "interpretation": "DECLINING presenta menos viajes por día activo comparado con STABLE."
    }
  ]
}
```

---

## 7. GOVERNANCE RULES (from Diagnostic Layer Closure)

1. **Never add a 7th severity** — only blocked/critical/elevated/warning/normal/unknown
2. **Never duplicate a threshold** — all thresholds in `DECISION_THRESHOLDS`
3. **Never add recommendation text** — explanations must not include "haz", "recommend", "llama"
4. **Normal must produce no visible explanation** — return null from explanation components
5. **Blocked must always rank first** — `getDecisionRank(BLOCKED) === 0`
6. **Never add new API calls** — all signals come from existing data

---

## 8. INTEGRATION PATH TO OMNIVIEW

| Step | Action |
|---|---|
| 1 | Wire `/behavioral-patterns/summary` into Omniview status bar |
| 2 | Render top decline signals in priority strip or new diagnostic strip |
| 3 | Add "Diagnóstico conductual" section to `OmniviewProjectionDrill` |
| 4 | Show group profile popup on entity click |
| 5 | Connect diagnostic factors to cell severity overlays |
