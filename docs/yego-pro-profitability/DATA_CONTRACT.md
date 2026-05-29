# DATA CONTRACT — Yego Pro Profitability Intelligence
## API Endpoints Proposal
## Fecha: 28 mayo 2026

---

## BASE PATH

```
/api/profitability/yego-pro
```

## FILTROS GLOBALES

Todos los endpoints aceptan:
- `park_id` (required): `64085dd85e124e2c808806f70d527ea8`
- `period_type` (optional): `week` | `month` | `day` (default: `week`)
- `date_from` (optional): ISO date
- `date_to` (optional): ISO date

---

## ENDPOINT 1: Overview

### URL
```
GET /api/profitability/yego-pro/overview
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| period | string | `last_30d` | `last_7d`, `last_30d`, `last_week_closed`, `custom` |
| date_from | date | null | Solo si period=custom |
| date_to | date | null | Solo si period=custom |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "park_name": "Yego Lima",
  "period": { "from": "2026-04-28", "to": "2026-05-27", "type": "last_30d" },
  "kpis": {
    "trips_completed": 13951,
    "trips_cancelled": 13647,
    "cancellation_rate": 0.495,
    "revenue_gross": 142474.00,
    "ticket_avg": 10.21,
    "ticket_median": 9.00,
    "km_per_trip_passenger": 3.75,
    "km_per_trip_total": 9.20,
    "active_drivers": 34,
    "active_drivers_daily_avg": 21.8,
    "work_hours_weekly_avg": 52.36,
    "revenue_per_hour": 28.97,
    "trips_per_hour": 2.32,
    "profit_per_trip": -2.17,
    "weekly_profit_fleet": -5509.90,
    "pct_drivers_profitable": 0.038,
    "breakeven_trips_weekly": 172
  },
  "health": {
    "status": "LOSS",
    "trend": "stable",
    "billing_weeks_available": 1,
    "data_confidence": "MEDIUM"
  },
  "metadata": {
    "sources": ["trips_2026", "module_weekly_billing", "module_weekly_income"],
    "last_trip_date": "2026-05-27",
    "last_billing_week": "2026-05-18/2026-05-24",
    "generated_at": "2026-05-28T14:30:00Z"
  }
}
```

### KPIs Incluidos
trips_completed, trips_cancelled, cancellation_rate, revenue_gross, ticket_avg, ticket_median, km_per_trip (2 tipos), active_drivers, work_hours, revenue_per_hour, trips_per_hour, profit_per_trip, weekly_profit, breakeven

### Fuentes
- `public.trips_2026` (operativos)
- `public.module_weekly_billing` (financieros)
- `public.drivers` (conteo activos)

### Limitaciones
- `profit_per_trip` y `weekly_profit` solo disponibles para semanas con billing
- `data_confidence` será "LOW" si billing < 2 semanas

---

## ENDPOINT 2: Weekly Closed

### URL
```
GET /api/profitability/yego-pro/weekly-closed
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| weeks | int | 8 | Últimas N semanas |
| include_trips_only | bool | false | Incluir semanas sin billing (solo datos de trips) |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "weeks": [
    {
      "week_start": "2026-05-18",
      "week_end": "2026-05-24",
      "iso_week": "S21-2026",
      "has_billing": true,
      "trips_completed": 3456,
      "trips_cancelled": 3200,
      "revenue_gross": 35280.00,
      "ticket_avg": 10.21,
      "active_drivers": 26,
      "work_hours_total": 1361.36,
      "revenue_per_hour": 25.92,
      "trips_per_hour": 2.54,
      "costs": {
        "fuel": 4893.00,
        "maintenance": 4770.00,
        "platform_commission": 5880.00,
        "driver_payment": 10180.00,
        "vehicle_quota": 13000.00,
        "total_variable": 9663.00,
        "total_fixed": 13000.00
      },
      "income": {
        "revenue_net": 29400.00,
        "bono_yango": 5126.57,
        "bono_additional": 2125.00,
        "total_income": 36651.57
      },
      "profit": {
        "per_trip": -2.17,
        "weekly_total": -5509.90,
        "margin_pct": -15.6,
        "drivers_profitable": 1,
        "drivers_loss": 25
      }
    }
  ],
  "summary": {
    "avg_weekly_profit": -5509.90,
    "trend": "stable",
    "worst_week": "S21-2026",
    "best_week": "S21-2026"
  }
}
```

### Fuentes
- `public.trips_2026` (agrupado por iso_week)
- `public.module_weekly_billing` (costos y utilidad)
- `public.module_weekly_income` (ingresos adicionales)

### Limitaciones
- Solo 1 semana de billing disponible actualmente
- Semanas sin billing tendrán `has_billing: false` y `costs/profit: null`

---

## ENDPOINT 3: Last Closed Day

### URL
```
GET /api/profitability/yego-pro/last-closed-day
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| date | date | null | Día específico (default: último día con data) |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "date": "2026-05-27",
  "day_of_week": "martes",
  "kpis": {
    "trips_completed": 478,
    "trips_cancelled": 445,
    "revenue_gross": 4882.00,
    "ticket_avg": 10.21,
    "active_drivers": 22,
    "trips_per_driver": 21.7,
    "revenue_per_driver": 221.90
  },
  "shifts": {
    "day": { "trips": 191, "revenue": 2038.00, "drivers": 18 },
    "night": { "trips": 287, "revenue": 2844.00, "drivers": 20 }
  },
  "hourly": [
    { "hour": 0, "trips": 45, "revenue": 420.00, "drivers": 8 },
    { "hour": 1, "trips": 38, "revenue": 355.00, "drivers": 7 }
  ],
  "comparison": {
    "vs_prev_day": { "trips_delta_pct": 5.2, "revenue_delta_pct": 3.8 },
    "vs_same_dow_prev_week": { "trips_delta_pct": -2.1, "revenue_delta_pct": -1.5 }
  }
}
```

### Fuentes
- `public.trips_2026` solamente (billing no es diario)

### Limitaciones
- Sin datos financieros diarios (billing es semanal)
- Comparativa solo disponible si hay data del día anterior/semana anterior

---

## ENDPOINT 4: Driver Profitability

### URL
```
GET /api/profitability/yego-pro/driver
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| period | string | `last_week_closed` | Periodo del análisis |
| sort_by | string | `profit` | `profit`, `trips`, `revenue`, `revenue_per_hour` |
| limit | int | 50 | Max drivers |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "period": { "from": "2026-05-18", "to": "2026-05-24" },
  "drivers": [
    {
      "driver_id": "abc123",
      "driver_name": "Carrasco Medina Jorge",
      "shift_type": "NOCHE",
      "trips": 172,
      "revenue_gross": 1756.12,
      "work_hours": 58.3,
      "revenue_per_hour": 30.12,
      "trips_per_hour": 2.95,
      "payment_pct": 60,
      "payment_total": 1053.67,
      "fuel_cost": 236.00,
      "maintenance_cost": 230.00,
      "vehicle_quota": 500.00,
      "bono_yango": 197.18,
      "profit": 45.23,
      "profit_per_trip": 0.26,
      "is_profitable": true,
      "days_worked": 7,
      "consistency": "CONSISTENTE"
    }
  ],
  "summary": {
    "total_drivers": 26,
    "profitable_count": 1,
    "loss_count": 25,
    "avg_profit_per_driver": -212.00,
    "top_performer_trips": 172,
    "bottom_performer_trips": 43
  },
  "percentiles": {
    "p10_trips": 43,
    "p25_trips": 231,
    "p50_trips": 471,
    "p75_trips": 599,
    "p90_trips": 675
  }
}
```

### Fuentes
- `public.module_weekly_billing` (principal)
- `public.trips_2026` (complemento: turno, días)
- `public.drivers` (nombre)
- `public.module_payment_percentages` (escalones)

### Limitaciones
- Solo disponible para semanas con billing
- 8 drivers de trips pueden no aparecer en billing (sin liquidación)

---

## ENDPOINT 5: Vehicle Profitability

### URL
```
GET /api/profitability/yego-pro/vehicle
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| period | string | `last_month` | Periodo |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "period": { "from": "2026-04-28", "to": "2026-05-27" },
  "status": "LIMITED",
  "reason": "No existe tabla de asignación vehículo→conductor. Solo se muestra agregado por cronograma.",
  "vehicles_configured": 16,
  "vehicle_types": [
    {
      "type": "Kia 0KM",
      "count": 6,
      "weekly_quota": 500.00,
      "monthly_quota_equiv": 2165.00,
      "total_quotas": 261,
      "bono_tiers": [
        { "min_trips": 90, "bono": 10.00 },
        { "min_trips": 120, "bono": 40.00 },
        { "min_trips": 150, "bono": 70.00 }
      ]
    },
    {
      "type": "Kia Seminuevo",
      "count": 5,
      "weekly_quota": 532.50,
      "monthly_quota_equiv": 2306.00,
      "total_quotas": 156
    }
  ],
  "fleet_economics": {
    "total_weekly_quota_cost": 8400.00,
    "total_monthly_quota_cost": 36372.00,
    "quota_per_trip_avg": 4.10,
    "quota_coverage_from_revenue_pct": 59.0
  }
}
```

### Fuentes
- `public.module_miauto_cronograma`
- `public.module_miauto_cronograma_vehiculo`
- `public.module_miauto_cronograma_rule`

### Limitaciones
- **NO se puede reportar por vehículo individual** — sin asignación vehicle→driver
- Solo estructura de costos por tipo de cronograma
- El endpoint se degradará a "fleet economics" agregado

---

## ENDPOINT 6: Shift Profitability

### URL
```
GET /api/profitability/yego-pro/shift
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| period | string | `last_30d` | Periodo |
| shift_definition | string | `default` | `default` (6-18/18-6), `custom` |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "period": { "from": "2026-04-28", "to": "2026-05-27" },
  "shift_definition": { "day": "06:00-17:59", "night": "18:00-05:59" },
  "shifts": {
    "day": {
      "trips": 5563,
      "pct_trips": 0.399,
      "revenue": 59349.00,
      "ticket_avg": 10.67,
      "ticket_median": 9.60,
      "km_avg": 3.89,
      "duration_avg_min": 15.5,
      "drivers": 31,
      "revenue_per_hour_journey": 24.84,
      "trips_per_hour_journey": 2.30,
      "journey_median_hours": 8.1
    },
    "night": {
      "trips": 8388,
      "pct_trips": 0.601,
      "revenue": 83125.00,
      "ticket_avg": 9.91,
      "ticket_median": 8.70,
      "km_avg": 3.66,
      "duration_avg_min": 10.8,
      "drivers": 32,
      "revenue_per_hour_journey": 28.95,
      "trips_per_hour_journey": 2.79,
      "journey_median_hours": 3.4
    }
  },
  "gap_analysis": {
    "revenue_per_hour_gap": 4.11,
    "revenue_per_hour_gap_pct": 16.5,
    "trips_per_hour_gap": 0.49,
    "main_driver": "TRAFFIC",
    "suggested_day_incentive_per_trip": 0.90
  },
  "hourly_bands": [
    { "band": "02-06", "label": "madrugada", "trips": 2605, "revenue": 24264, "ticket": 9.35, "drivers": 22 },
    { "band": "06-10", "label": "mañana", "trips": 1746, "revenue": 19439, "ticket": 11.13, "drivers": 27 },
    { "band": "10-14", "label": "media mañana", "trips": 1866, "revenue": 19151, "ticket": 10.15, "drivers": 27 },
    { "band": "14-18", "label": "tarde", "trips": 1921, "revenue": 20586, "ticket": 10.51, "drivers": 25 },
    { "band": "18-22", "label": "noche temprana", "trips": 2193, "revenue": 23366, "ticket": 10.91, "drivers": 31 },
    { "band": "22-02", "label": "noche core", "trips": 3556, "revenue": 36135, "ticket": 10.14, "drivers": 26 }
  ]
}
```

### Fuentes
- `public.trips_2026` (EXTRACT(HOUR FROM fecha_inicio_viaje))

### Limitaciones
- Revenue/hora calculado desde jornada estimada (primer a último viaje), no de supply hours reales
- No hay costos por turno (billing no distingue día/noche)

---

## ENDPOINT 7: Waterfall (P&L)

### URL
```
GET /api/profitability/yego-pro/waterfall
```

### Filtros
| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| park_id | string | required | ID del park |
| period | string | `last_week_closed` | Periodo |
| view | string | `per_trip` | `per_trip`, `weekly_total`, `monthly_total` |

### Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "period": { "from": "2026-05-18", "to": "2026-05-24" },
  "view": "per_trip",
  "waterfall": [
    { "step": "revenue_gross", "label": "Revenue Bruto (Ticket)", "value": 10.21, "pct": 100.0, "type": "positive" },
    { "step": "platform_commission", "label": "Comisión Plataforma", "value": -1.70, "pct": -16.7, "type": "negative" },
    { "step": "revenue_net", "label": "Revenue Neto", "value": 8.51, "pct": 83.3, "type": "subtotal" },
    { "step": "fuel", "label": "Combustible", "value": -1.41, "pct": -13.8, "type": "negative" },
    { "step": "maintenance", "label": "Mantenimiento", "value": -1.38, "pct": -13.5, "type": "negative" },
    { "step": "margin_pre_driver", "label": "Margen pre-Conductor", "value": 5.72, "pct": 56.0, "type": "subtotal" },
    { "step": "driver_payment", "label": "Pago Conductor", "value": -2.96, "pct": -29.0, "type": "negative" },
    { "step": "margin_pre_vehicle", "label": "Margen pre-Vehículo", "value": 2.76, "pct": 27.0, "type": "subtotal" },
    { "step": "vehicle_quota", "label": "Cuota Vehículo", "value": -4.10, "pct": -40.2, "type": "negative" },
    { "step": "bono_yango", "label": "Bono Yango", "value": 1.62, "pct": 15.9, "type": "positive" },
    { "step": "bono_additional", "label": "Bono Adicional Viajes", "value": 0.67, "pct": 6.6, "type": "positive" },
    { "step": "net_result", "label": "Resultado Neto", "value": 0.95, "pct": 9.3, "type": "result" }
  ],
  "note": "El billing muestra -2.17/viaje promedio porque no todos los drivers reciben bonos completos y las cuotas varían."
}
```

### Fuentes
- `public.module_weekly_billing` (todos los valores reales)
- `public.module_weekly_income` (bonificaciones complementarias)
- `public.module_miauto_cronograma_rule` (cuota base)

### Limitaciones
- Solo disponible para semanas con billing cargado
- El resultado varía significativamente entre drivers de alto y bajo volumen

---

## ENDPOINT 8: Input Mapping (Configuration)

### URL
```
GET /api/profitability/yego-pro/inputs
PUT /api/profitability/yego-pro/inputs
```

### GET Response JSON
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "inputs": {
    "real": [
      { "key": "ticket_avg", "value": 10.21, "unit": "S/", "source": "trips_2026", "auto_refresh": true },
      { "key": "fuel_per_km", "value": 0.1528, "unit": "S/km", "source": "module_weekly_billing", "auto_refresh": true },
      { "key": "maintenance_per_km", "value": 0.1500, "unit": "S/km", "source": "module_weekly_billing", "auto_refresh": true },
      { "key": "platform_commission_pct", "value": 16.66, "unit": "%", "source": "module_weekly_billing", "auto_refresh": true },
      { "key": "avg_driver_payment_pct", "value": 47.69, "unit": "%", "source": "module_weekly_billing", "auto_refresh": true },
      { "key": "vehicle_quota_weekly", "value": 500.00, "unit": "S/", "source": "cronograma_rule", "auto_refresh": false }
    ],
    "configurable": [
      { "key": "insurance_gps_monthly", "value": 300.00, "unit": "S/", "editable": true, "last_updated": "2026-05-28" },
      { "key": "depreciation_reserve_pct", "value": 15.0, "unit": "%", "editable": true, "last_updated": null },
      { "key": "gasoline_price_gallon", "value": 16.50, "unit": "S/gal", "editable": true, "last_updated": null },
      { "key": "wash_weekly", "value": 30.00, "unit": "S/", "editable": true, "last_updated": null },
      { "key": "tolls_daily_avg", "value": 5.00, "unit": "S/", "editable": true, "last_updated": null }
    ],
    "derived": [
      { "key": "km_dead_per_trip", "value": 5.45, "unit": "km", "formula": "km_billing - km_trips" },
      { "key": "dead_km_ratio", "value": 59.2, "unit": "%", "formula": "(km_total - km_passenger) / km_total" },
      { "key": "variable_cost_per_trip", "value": 2.79, "unit": "S/", "formula": "fuel + maintenance per trip" },
      { "key": "monthly_loss_estimated", "value": -22040, "unit": "S/", "formula": "weekly_loss * 4" }
    ]
  },
  "payment_tiers": [
    { "min_trips_weekly": 90, "driver_pct": 30 },
    { "min_trips_weekly": 95, "driver_pct": 35 },
    { "min_trips_weekly": 100, "driver_pct": 40 },
    { "min_trips_weekly": 107, "driver_pct": 45 },
    { "min_trips_weekly": 117, "driver_pct": 50 },
    { "min_trips_weekly": 128, "driver_pct": 55 },
    { "min_trips_weekly": 140, "driver_pct": 60 }
  ]
}
```

### PUT Body (para actualizar inputs configurables)
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "inputs": [
    { "key": "insurance_gps_monthly", "value": 320.00 },
    { "key": "gasoline_price_gallon", "value": 17.00 }
  ]
}
```

### Fuentes
- Múltiples tablas (trips_2026, billing, income, cronograma, config)
- Tabla nueva requerida: `profitability_config` (inputs configurables)

### Limitaciones
- Los inputs "real" se recalculan automáticamente; no editables
- Los inputs "configurable" persisten en tabla nueva
- Los inputs "derived" se recalculan on-the-fly

---

## RESUMEN DE ENDPOINTS

| # | Endpoint | Método | Fuente Principal | Disponibilidad |
|---|----------|--------|-----------------|----------------|
| 1 | Overview | GET | trips + billing | ✅ Implementable |
| 2 | Weekly Closed | GET | trips + billing + income | ⚠️ Parcial (1 semana billing) |
| 3 | Last Closed Day | GET | trips only | ✅ Implementable |
| 4 | Driver Profitability | GET | billing + trips | ⚠️ Parcial (1 semana billing) |
| 5 | Vehicle Profitability | GET | cronograma | ⚠️ Limitado (sin asignación) |
| 6 | Shift Profitability | GET | trips | ✅ Implementable |
| 7 | Waterfall | GET | billing + income + cronograma | ⚠️ Parcial (1 semana billing) |
| 8 | Input Mapping | GET/PUT | múltiples + config table | ✅ Implementable |

---

## DEPENDENCIAS TÉCNICAS PARA FASE 1

1. **Nueva tabla**: `public.profitability_config` (park_id, key, value, updated_at)
2. **Nuevo servicio**: `profitability_service.py`
3. **Nuevo router**: `profitability.py`
4. **Migración Alembic**: Para tabla de configuración
5. **NO se requieren MVs** en Fase 1 (queries directas suficientes para 1 park / 34 drivers)
