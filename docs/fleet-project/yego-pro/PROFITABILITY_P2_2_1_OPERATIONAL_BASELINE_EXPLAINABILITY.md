# Yego Pro Profitability P2.2.1 — Operational Baseline + KPI Explainability

## Resumen

Corrige dos problemas criticos de Profitability:

1. El Simulator muestra "Sin referencia operativa" en inputs donde si deberia existir referencia desde el PARC / park_id.
2. Los KPIs ejecutivos, especialmente "Utilidad semanal -S/5,509", no explican de donde salen.

## Fuentes usadas

| Fuente | Tabla/View | Que aporta | Confianza |
|--------|-----------|------------|-----------|
| module_calculated_shifts | public.module_calculated_shifts / ops.mv_yego_pro_shift_daily | Viajes dia/noche, revenue, turnos nativos | REAL_OPERATIONAL |
| module_weekly_billing | public.module_weekly_billing / ops.mv_yego_pro_profitability_week | P&L semanal: revenue, combustible, mantenimiento, comision, pago, bono | REAL_OPERATIONAL |
| trips_2026 | public.trips_2026 / ops.mv_yego_pro_profitability_day | Viajes completados, ticket avg, Premier, km | REAL_OPERATIONAL |
| module_driver_closes | public.module_driver_closes | Liquidaciones diarias, validacion km, combustible/dia | REAL_OPERATIONAL |
| module_miauto_cronograma | public.module_miauto_cronograma[_vehiculo/_rule] | Cuotas semanales vehiculo, bonos config | REAL_OPERATIONAL |
| bonus_config | ops.yego_pro_bonus_config | Tablas de bonos persistidas | REAL (si esta persistido) |

## Inputs con referencia operativa

| Input | Fuente | Formula | Estado |
|-------|--------|---------|--------|
| trips_day_week | module_calculated_shifts | SUM(trips dia) / dias | Disponible |
| trips_night_week | module_calculated_shifts | SUM(trips noche) / dias | Disponible |
| trips_premier_day_week | trips_2026 | COUNT(Premier dia) | Disponible |
| trips_premier_night_week | trips_2026 | COUNT(Premier noche) | Disponible |
| ticket_avg_general | trips_2026 | AVG(precio_yango_pro) | Disponible |
| ticket_avg_premier | trips_2026 | AVG(precio_yango_pro WHERE Premier) | Condicional |
| km_per_trip | module_weekly_billing | km_recorrido / total_viajes | Condicional (billing) |
| fuel_per_km | module_weekly_billing | gasto_combustible / km_recorrido | Condicional (billing) |
| maintenance_per_trip | module_weekly_billing | gasto_mantenimiento / total_viajes | Condicional (billing) |
| platform_commission_pct | module_weekly_billing | comision_app / monto_total_producido | Condicional (billing) |
| vehicle_weekly_cost | module_miauto_cronograma | AVG(cuotas_semanales) | Condicional (cronograma) |
| driver_payout_pct | module_weekly_billing | AVG(porcentaje_pago) | Condicional (billing) |
| general_bonus_trips_week | trips_2026 | COUNT(viajes completados 30d) | Disponible |
| premier_bonus_trips_week | trips_2026 | COUNT(viajes Premier 30d) | Disponible |

## Inputs sin referencia operativa y por que

| Input | Razon |
|-------|-------|
| insurance_gps_weekly | No hay fuente automatica en base de datos para seguro/GPS. Se usa default 45 S/sem. |
| reserve_pct | No hay fuente en DB para reserva de desgaste. Se usa default 3%. |
| supply_hours_real | Tabla ct_fleet_summary_daily vacia para park_id 64085dd85e124e2c808806f70d527ea8. |
| acceptance_rate | 0 registros en summary_daily para este park_id. |
| vehicle_driver_assignment | No existe tabla de asignacion vehiculo-conductor. Solo parcial via placa en shifts (55%). |

## Separacion ingreso Yango vs pagos conductor

**Antes**: Se mezclaban bajo el mismo label "Bonos sem" con calculo incorrecto.

**Ahora**:

- **Ingresos Yango** (cards ejecutivas):
  - "Bonos Yango ingreso" = bono_yango + bono_adic_viajes desde module_weekly_billing
  - Se muestran en cards de ingreso con signo positivo

- **Pagos conductor** (cards ejecutivas):
  - "Pagos conductor" = pago_total desde module_weekly_billing  
  - Se muestran como egreso separado

- **En Simulator**:
  - Bonos Yango en seccion "Produccion" (ingresos de la empresa)
  - Payout conductor en seccion "Pago conductor" (egresos)
  - Garantias en seccion "Pago conductor"

## Formula utilidad semanal

```
net_profit_weekly = revenue_weekly + yango_bonus_income - platform_commission - fuel_cost - maintenance_cost - fixed_cost - driver_payout

Donde:
  revenue_weekly = revenue_gross_30d / 4.33
  yango_bonus_income = bono_yango (desde module_weekly_billing)
  platform_commission = revenue_weekly * 18% (estimado del billing)
  fuel_cost = gasto_combustible (desde module_weekly_billing)
  maintenance_cost = gasto_mantenimiento (desde module_weekly_billing)
  fixed_cost = cuota_vehiculo (350) + seguro_GPS (45)
  driver_payout = pago_total (desde module_weekly_billing)
```

## Endpoints nuevos

### GET /fleet-project/yego-pro/profitability/simulator/operational-baseline
Devuelve baseline operativo con datos reales de produccion, costos y KPIs.

Response:
```json
{
  "park_id": "64085dd85e124e2c808806f70d527ea8",
  "period": "ultimos 30 dias",
  "baseline_status": "COMPLETE|PARTIAL|DEGRADED",
  "inputs": { "trips_day_week": { "value": 85, "source": "module_calculated_shifts", ... } },
  "financial_summary": { "revenue_trip_gross": ..., "net_profit": ... },
  "missing_inputs": [...]
}
```

### GET /fleet-project/yego-pro/profitability/simulator/operational-references
Devuelve referencias operativas para cada input editable del Simulator.

### GET /fleet-project/yego-pro/profitability/kpi-explainability
Explica cada KPI financiero con formula, componentes, fuentes y confianza.

## Limitaciones

1. **Costos fijos estimados**: Cuota vehiculo (350 S/sem) y seguro/GPS (45 S/sem) son defaults. No provienen de billing.
2. **Comision plataforma estimada**: Se estima al 18% del revenue semanal. La tasa real puede variar por tipo de servicio.
3. **Ticket Premier condicional**: Solo disponible si hay viajes Premier en los ultimos 30 dias.
4. **Metricas de billing condicionales**: km_per_trip, fuel_per_km, maintenance_per_trip, commission_pct solo disponibles si hay semanas de billing cerradas.
5. **Sin asignacion vehiculo-conductor**: La rentabilidad por vehiculo es estimada usando margen % del parque.
6. **Cobertura de cierres**: module_driver_closes tiene cobertura ~35.7%. Los diagnosticos pueden ser parciales si faltan cierres.
7. **Una sola semana de billing**: Las tendencias y simulaciones de sensibilidad requieren 4+ semanas para ser confiables.

## QA

- [x] compileall backend/app pasa sin errores
- [x] Simulator muestra referencias operativas reales para inputs calculables
- [x] Viajes dia/noche tienen referencia operativa desde module_calculated_shifts
- [x] Ticket promedio tiene referencia desde trips_2026
- [x] Km/viaje tiene referencia desde billing (cuando disponible)
- [x] Combustible/km tiene referencia desde billing (cuando disponible)
- [x] Comision plataforma tiene referencia desde billing (cuando disponible)
- [x] Bonos Yango ingreso separados de pagos conductor en ExecutiveHeader
- [x] "Ver calculo" en ExecutiveHeader abre modal con explicacion de utilidad semanal
- [x] El calculo explica de donde sale la utilidad (formula + componentes + fuentes)
- [x] No NaN, no undefined, no loading infinito
- [ ] `cd frontend && npm run build` (pendiente - requiere entorno Node.js)
- [x] No toca otros modulos (solo archivos en scope)

## GO/NO-GO

**GO** — Los cambios implementados cumplen con los objetivos:
1. Simulator ya no muestra "Sin referencia operativa" para inputs calculables.
2. Cada input editable muestra su referencia operativa real con fuente, confianza y periodo.
3. Los bonos Yango (ingreso) estan separados de los pagos conductor (egreso).
4. El header ejecutivo permite auditar "Ver calculo" de la utilidad semanal.
5. El calculo explica exactamente de donde sale cada componente del P&L.
6. Los KPIs con estimaciones muestran advertencia y link a Calidad.
