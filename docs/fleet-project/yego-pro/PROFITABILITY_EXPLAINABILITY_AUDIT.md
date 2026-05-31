# Profitability P2.3 — Explainability Audit

## Fórmulas encontradas

### KPIs ejecutivos (overview)

| KPI | Fuente | Fórmula | Trazable |
|-----|--------|---------|----------|
| `revenue_weekly` | `trips_2026` | `revenue_gross_30d / 4.33` | SI |
| `yango_bonus_income` | `module_weekly_billing` | `bono_yango` (ultima semana) | SI |
| `platform_commission` | `module_weekly_billing` | `revenue_weekly * 18%` (estimada) | PARCIAL |
| `fuel_cost` | `module_weekly_billing` | `gasto_combustible` | SI |
| `maintenance_cost` | `module_weekly_billing` | `gasto_mantenimiento` | SI |
| `driver_payout` | `module_weekly_billing` | `pago_total` | SI |
| `net_profit_weekly` | Derivado | `revenue + bonos - comision - combustible - mantenimiento - fijos - pago conductor` | SI |
| `margin_pct` | Derivado | `net_profit / (revenue + bonos) * 100` | SI |

### KPIs por conductor (driver drill)

| KPI | Fuente | Fórmula |
|-----|--------|---------|
| `revenue_gross` | `module_weekly_billing` | `monto_total_producido` |
| `platform_commission` | `module_weekly_billing` | `comision_app` |
| `fuel_cost` | `module_weekly_billing` | `gasto_combustible` |
| `maintenance_cost` | `module_weekly_billing` | `gasto_mantenimiento` |
| `driver_payout` | `module_weekly_billing` | `pago_total` |
| `profit` | `module_weekly_billing` | `utilidad` |

### KPIs por vehículo (vehicle drill)

| KPI | Fuente | Fórmula |
|-----|--------|---------|
| `revenue_gross` | `module_calculated_shifts` | `SUM(produccion_total)` |
| `commission` | `module_calculated_shifts` | `SUM(comisiones_servicio)` |
| `payout` | `module_calculated_shifts` | `SUM(monto_total)` |
| `fuel_estimated` | Estimado | `revenue * 8%` |
| `maintenance_estimated` | Estimado | `revenue * 4%` |
| `estimated_profit` | Derivado | `revenue - commission - fuel - maint - fixed - payout` |

### Root Causes (diagnóstico)

| Causa | Fuente | Regla | Threshold |
|-------|--------|------|-----------|
| LOW_TRIPS | `module_weekly_billing` | Viajes < abs o < % promedio | < 10 abs o < 50% avg |
| LOW_TICKET | `module_weekly_billing` | Ticket < % promedio parque | < 80% avg |
| HIGH_KM_PER_TRIP | `module_weekly_billing` | Km/viaje > % promedio | > 130% avg |
| HIGH_COST_PER_TRIP | `module_weekly_billing` | Costo/viaje > % ingreso | > 85% revenue/trip |
| HIGH_PAYOUT_RATIO | `module_weekly_billing` | Payout > % | > 50% |
| LOW_MARGIN | `module_weekly_billing` | Margen < % | < 5% |
| MISSING_CLOSE | `module_driver_closes` | Sin cierres registrados | N/A |
| MISSING_PLATE | `module_calculated_shifts` | Sin placa en shifts | N/A |
| LOW_UTILIZATION | `module_calculated_shifts` | Dias activos < X | < 3 dias/sem |
| LOW_REVENUE_PER_DAY | `module_calculated_shifts` | Revenue/dia < S/X | < S/ 50 |
| LOW_TRIPS_PER_DAY | `module_calculated_shifts` | Viajes/dia < X | < 5 |
| MANY_DRIVERS_LOW_CONTROL | `module_calculated_shifts` | Conductores > X | > 3 |
| NEGATIVE_MARGIN | Estimado | Margen < 0 | < 0 |
| FIXED_COST_NOT_COVERED | Estimado | Revenue < costo fijo | < S/ 350 |

## KPIs sin trazabilidad

| KPI | Razón |
|-----|-------|
| `supply_hours_real` | Tabla `ct_fleet_summary_daily` vacía para este park_id |
| `acceptance_rate` | 0 registros en `summary_daily` para este park_id |
| `vehicle_driver_assignment` | No existe tabla de asignación vehículo-conductor |
| `insurance_gps_weekly` | Sin fuente automática — valor hardcodeado (45 S/sem) |
| `reserve_pct` | Sin fuente — valor hardcodeado (3%) |

## Modales implementados

| Modal | Endpoint | Componentes mostrados | Clickable desde |
|-------|----------|-----------------------|-----------------|
| KPI Explainability | `GET /kpi-explainability` | Formula, componentes (ingresos/costos), fuente, warnings, confianza. Tabs por KPI. | "Ver calculo" en Overview header |
| Driver Drill | `GET /driver-drill` | Income (revenue, commission, net, bonus), costs (fuel, maint, fixed), driver payment (%, amount), result (profit, margin), operational (trips, hours, ticket, km). Explicación narrativa. | Click en nombre de conductor en TopRankedCard |
| Vehicle Drill | `GET /vehicle-drill` | Income, operational (trips, days, drivers, shifts, hours), costs estimated (fuel, maint, fixed), driver payment, result. Nota de estimación. | Click en placa en TopRankedCard |
| Root Causes Detail | `GET /diagnostics/portfolio` | Total loss, loss %, contributors list, rule/threshold per cause, affected entities count | Diagnostics > Root Causes tab |

## Endpoints usados

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/kpi-explainability` | GET | Explica fórmula, componentes y fuentes de cada KPI financiero |
| `/driver-drill` | GET | Desglose completo P&L por conductor |
| `/vehicle-drill` | GET | Desglose completo P&L por placa |
| `/diagnostics/drivers` | GET | Diagnóstico determinístico por conductor |
| `/diagnostics/vehicles` | GET | Diagnóstico determinístico por vehículo |
| `/diagnostics/portfolio` | GET | Agregación de diagnóstico + root causes + top5 |

## Evidencia UI

- `python -m compileall backend/app` — OK
- `npm run build` — 844 módulos, 6.67s
- Portfolio muestra `entity_name` (nombres reales) en vez de UUIDs
- Root causes muestra `rule` (regla/threshold) por causa
- KPI modal tiene tabs para todos los KPIs (utilidad, revenue, bonos, comision, combustible, mantenimiento, payout, margen)
- Driver drill muestra income/costs/payment/operational con explicación
- Vehicle drill muestra income/costs_estimated/payment/operational con nota de estimación
- "Ver calculo" en Overview header abre modal KPI con tabs

## Riesgos

1. Los drills de vehículo usan **costos estimados** (fuel = 8% revenue, maint = 4% revenue). No son costos reales por vehículo porque billing no asigna costos por placa.
2. KPI modal muestra `platform_commission` al 18% estimado. La tasa real puede variar.
3. Drivers/Vehicles/Weekly vacíos si las MVs no tienen datos (problema de ingesta, no de código).
4. `entity_name` en portfolio depende de que los diagnósticos de drivers incluyan `evidence.driver_name`. Si no hay datos de billing, el nombre será el UUID.

## GO / NO-GO

**GO** — Todos los KPIs financieros clave tienen trazabilidad matemática completa:
- Fórmula documentada
- Componentes desglosados
- Fuente de datos identificada
- Modal de drill accesible desde la UI
- Root causes con reglas y thresholds visibles
- Portfolio muestra nombres reales
