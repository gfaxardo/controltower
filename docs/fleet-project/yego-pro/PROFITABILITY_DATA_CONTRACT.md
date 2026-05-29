# PROFITABILITY DATA CONTRACT — Yego Pro
## API Contract for Fleet Project / Yego Pro / Profitability
## Phase 1 Foundation

---

## BASE PATH
```
/fleet-project/yego-pro/profitability
```

## DEFAULT PARK
```
park_id = 64085dd85e124e2c808806f70d527ea8
```

---

## RESPONSE ENVELOPE

All endpoints return:
```json
{
  "status": "OK | NO_DATA | MISSING_SOURCE | LIMITED | ERROR",
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  ...endpoint-specific data...,
  "source": "table_name",
  "metric_type": "REAL | DERIVED",
  "confidence": "HIGH | MEDIUM | LOW"
}
```

Failure modes:
- `MISSING_SOURCE`: Serving view not created yet
- `NO_DATA`: View exists but empty
- `LIMITED`: Partial data (e.g., vehicle without assignment)
- `ERROR`: Database/connection error

---

## ENDPOINT: /overview

**Query Params**: `park_id` (default: Lima park)

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "park_name": "Yego Lima",
  "kpis": {
    "trips_completed_30d": {"value": 13951, "source": "trips_2026", "metric_type": "REAL", "confidence": "HIGH", "notes": ""},
    "revenue_gross_30d": {"value": 142474.0, "source": "trips_2026", "metric_type": "REAL", "confidence": "HIGH", "notes": ""},
    "profit_weekly": {"value": -5509.9, "source": "module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "notes": ""},
    "profit_per_trip": {"value": -2.17, "source": "module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "notes": ""}
  },
  "health": {
    "profit_status": "LOSS | PROFIT",
    "billing_weeks_available": 1,
    "data_confidence": "HIGH | MEDIUM | LOW",
    "days_with_trips": 30
  },
  "metadata": {
    "sources": ["trips_2026", "module_weekly_billing"],
    "last_billing_week": "2026-05-18",
    "last_trip_date": "2026-05-27"
  }
}
```

---

## ENDPOINT: /weekly

**Query Params**: `park_id`, `weeks` (default 12, max 52)

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "weeks": [
    {
      "week_start": "2026-05-18",
      "week_end": "2026-05-24",
      "active_drivers": 26,
      "trips_completed": 3200,
      "work_hours": 1361.36,
      "revenue_gross": 35280.0,
      "revenue_net": 29400.0,
      "platform_commission": 5880.0,
      "km_total": 29440.0,
      "fuel_cost": 4893.0,
      "maintenance_cost": 4770.0,
      "driver_payment": 10180.0,
      "profit": -5509.9,
      "bono_yango": 5126.57,
      "bono_additional": 2125.0,
      "ticket_avg": 11.03,
      "km_per_trip": 9.2,
      "revenue_per_hour": 25.92,
      "trips_per_hour": 2.35,
      "profit_per_trip": -1.72,
      "margin_pct": -0.156
    }
  ],
  "total_weeks": 1,
  "source": "module_weekly_billing",
  "metric_type": "REAL",
  "confidence": "MEDIUM"
}
```

---

## ENDPOINT: /daily

**Query Params**: `park_id`, `days` (default 30, max 90)

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "days": [
    {
      "date": "2026-05-27",
      "trips_completed": 478,
      "trips_cancelled": 445,
      "active_drivers": 22,
      "revenue_gross": 4882.0,
      "ticket_avg": 10.21,
      "km_total_passenger": 1791.0,
      "km_per_trip_passenger": 3.75,
      "duration_avg_min": 12.7,
      "trips_day_shift": 191,
      "trips_night_shift": 287,
      "revenue_day_shift": 2038.0,
      "revenue_night_shift": 2844.0
    }
  ],
  "total_days": 30,
  "source": "trips_2026",
  "metric_type": "REAL",
  "confidence": "HIGH",
  "notes": "km_per_trip_passenger is passenger-only distance"
}
```

---

## ENDPOINT: /drivers

**Query Params**: `park_id`, `week_start` (ISO date, default: latest)

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "drivers": [
    {
      "driver_id": "abc123",
      "driver_name": "Carrasco Medina Jorge",
      "week_start": "2026-05-18",
      "trips_completed": 172,
      "work_hours": 58.3,
      "revenue_gross": 1756.12,
      "revenue_per_hour": 30.12,
      "trips_per_hour": 2.95,
      "km_total": 1582.4,
      "km_per_trip": 9.2,
      "fuel_cost": 236.0,
      "maintenance_cost": 230.0,
      "driver_pct": 60.0,
      "driver_payment": 1053.67,
      "profit": 45.23,
      "profit_per_trip": 0.26,
      "margin_pct": 0.026,
      "bono_yango": 197.18,
      "is_profitable": true
    }
  ],
  "summary": {
    "total_drivers": 26,
    "profitable_count": 1,
    "loss_count": 25,
    "pct_profitable": 0.038
  },
  "source": "module_weekly_billing",
  "metric_type": "REAL",
  "confidence": "HIGH"
}
```

---

## ENDPOINT: /vehicles

**Query Params**: `park_id`

**Response**:
```json
{
  "status": "LIMITED",
  "park_id": "...",
  "vehicles": [
    {
      "cronograma_name": "0KM Kia Rio",
      "vehicle_name": "Kia Rio 2025",
      "total_weekly_quotas": 261,
      "weekly_quota": 500.0,
      "min_trips_for_bono": 90,
      "bono_reduction": 10.0,
      "tier_order": 1
    }
  ],
  "limitation": "No vehicle-to-driver assignment table exists.",
  "source": "module_miauto_cronograma",
  "metric_type": "REAL",
  "confidence": "MEDIUM",
  "notes": "Cannot report per-vehicle profitability."
}
```

---

## ENDPOINT: /shifts

**Query Params**: `park_id`, `weeks` (default 8, max 26)

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "shifts": [
    {
      "week_start": "2026-05-19",
      "shift": "DAY",
      "trips_completed": 1400,
      "active_drivers": 28,
      "revenue_gross": 14938.0,
      "ticket_avg": 10.67,
      "ticket_median": 9.60,
      "km_total": 5446.0,
      "km_per_trip": 3.89,
      "duration_avg_min": 15.5
    },
    {
      "week_start": "2026-05-19",
      "shift": "NIGHT",
      "trips_completed": 2100,
      "active_drivers": 30,
      "revenue_gross": 20811.0,
      "ticket_avg": 9.91,
      "ticket_median": 8.70,
      "km_total": 7686.0,
      "km_per_trip": 3.66,
      "duration_avg_min": 10.8
    }
  ],
  "shift_definition": {"DAY": "06:00-17:59", "NIGHT": "18:00-05:59"},
  "source": "trips_2026",
  "metric_type": "DERIVED",
  "confidence": "HIGH"
}
```

---

## ENDPOINT: /input-mapping

**Query Params**: `park_id`

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "inputs_real": [
    {"key": "ticket_avg", "value": 10.21, "unit": "S/", "source": "trips_2026", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": true}
  ],
  "inputs_configurable": [
    {"key": "insurance_gps_monthly", "value": 300.0, "unit": "S/", "metric_type": "ASSUMPTION", "confidence": "LOW", "editable": true}
  ],
  "inputs_not_available": [
    {"key": "supply_hours_real", "source": "module_ct_fleet_summary_daily", "reason": "Table empty for this park", "remediation": "Proxy: use horas_trabajo from billing"}
  ],
  "payment_tiers": [
    {"min_trips_weekly": 90, "driver_pct": 30}
  ]
}
```

---

## ENDPOINT: /quality

**Query Params**: `park_id`

**Response**:
```json
{
  "status": "OK",
  "park_id": "...",
  "serving_views": [
    {"view": "ops.mv_yego_pro_profitability_week", "label": "Weekly Profitability MV", "exists": true, "row_count": 1, "last_refresh": "2026-05-28T14:00:00", "status": "OK"}
  ],
  "raw_sources": {
    "drivers_in_park": 34,
    "trips_completed": 13951,
    "last_trip_date": "2026-05-27",
    "billing_records": 26
  },
  "overall": "HEALTHY | DEGRADED"
}
```
