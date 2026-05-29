# Profitability P1.4 — Simulator MVP

## Objetivo

Calculadora exploratoria basada en el Excel "Yego Pro Calculo Pagos.xlsx" (MODELO PORCENTAJE + PROPUESTA Final).
Permite simular escenarios de pago, costos, bonos y retorno del vehiculo sin contaminar la verdad historica.

## Ruta

Control Tower > Fleet Project > Yego Pro > Profitability > Simulator

## Inputs del simulador

### A. Inputs desde operacion (si existen)

| Input | Fuente | Confidence |
|-------|--------|------------|
| ticket_avg | module_calculated_shifts (avg produccion/viajes) | REAL |
| trips_per_day | module_calculated_shifts (avg cantidad_viajes) | REAL |
| km_per_trip | module_driver_closes (diferencia_odometro / viajes) | REAL |
| fuel_cost_per_km | module_driver_closes (combustible / km) | REAL |

### B. Inputs derivados

| Input | Formula |
|-------|---------|
| gross_revenue_week | trips_per_day * days_per_week * ticket_avg |
| km_week | trips_per_day * days_per_week * km_per_trip |
| fuel_cost_week | km_week * fuel_cost_per_km |
| maintenance_cost_week | km_week * maintenance_cost_per_km |
| net_revenue_week | gross_revenue * (1 - platform_commission_pct) |
| driver_payout_week | net_revenue * driver_payout_pct |
| revenue_per_km | ticket_avg / km_per_trip |

### C. Inputs manuales / legacy (defaults del Excel)

| Input | Default | Unit |
|-------|---------|------|
| trips_per_day | 15 (o operacion) | viajes/dia |
| days_per_week | 6 | dias |
| ticket_avg | 16.0 (o operacion) | S/ |
| km_per_trip | 9.0 (o operacion) | km |
| fuel_cost_per_km | 0.20 (o operacion) | S//km |
| maintenance_cost_per_km | 0.15 | S//km |
| platform_commission_pct | 25% | % |
| driver_payout_pct | 45% | % |
| fixed_daily_cost | 15 | S//dia |
| vehicle_monthly_quota | 0 (configurable) | S//mes |
| insurance_gps_monthly | 0 (configurable) | S//mes |
| capital_to_recover | 0 (configurable) | S/ |
| payback_target_months | 60 | meses |
| weekly_bonus_day | 0 (configurable) | S//sem |
| weekly_bonus_night | 0 (configurable) | S//sem |
| guarantee_weekly | 0 (configurable) | S//sem |
| wear_reserve_pct | 0 (configurable) | % |

## Formulas

```
trips_week = trips_per_day * days_per_week
gross_revenue_week = trips_week * ticket_avg
km_week = trips_week * km_per_trip

platform_commission = gross_revenue_week * platform_commission_pct
net_revenue = gross_revenue_week - platform_commission

fuel_cost = km_week * fuel_cost_per_km
maintenance_cost = km_week * maintenance_cost_per_km
fixed_cost = fixed_daily_cost * days_per_week
vehicle_weekly = vehicle_monthly_quota / 4.33
insurance_weekly = insurance_gps_monthly / 4.33

driver_payout = net_revenue * driver_payout_pct
bonuses = weekly_bonus_day + weekly_bonus_night
guarantee_adjustment = max(0, guarantee_weekly - driver_payout)
wear_reserve = gross_revenue_week * wear_reserve_pct

total_costs = platform_commission + fuel + maintenance + fixed + driver_payout + bonuses + guarantee + vehicle + insurance + wear
net_profit_week = gross_revenue_week - total_costs
net_profit_month = net_profit_week * 4.33
margin_pct = net_profit_week / gross_revenue_week

driver_income_week = driver_payout + bonuses + guarantee_adjustment
driver_income_month = driver_income_week * 4.33

company_recovery_months = capital_to_recover / net_profit_month  (if > 0)
break_even = fixed_costs / net_per_trip
```

## Endpoints

### GET /fleet-project/yego-pro/profitability/simulator/defaults

Devuelve inputs con source/confidence por input. No modifica datos.

### POST /fleet-project/yego-pro/profitability/simulator/run

Input: todos los parametros del simulador.
Output: resultados deterministicos + explanation + status (VIABLE/RISKY/LOSS).
No persiste en BD.

## Features del frontend

1. Panel de inputs editables agrupados por categoria
2. Resultado calculado (cards con KPIs)
3. Botones rapidos de payout: 40%, 45%, 50%, 55%, 60%
4. Guardar escenarios en memoria (tabla comparativa)
5. Sensibilidad payout (40-60% con impacto)
6. Sensibilidad produccion (actual, +10%, +20%, -10%)
7. UI copy claro: "Esto es simulacion, no modifica pagos reales"

## Limitaciones

- NO persiste escenarios en BD (solo memoria del browser)
- NO genera recomendaciones automaticas
- NO ejecuta acciones operativas
- NO modifica esquemas de pago
- NO tiene IA
- Escenarios se pierden al recargar la pagina
- Costos default son supuestos del Excel, no mediciones reales

## Lo que NO hace todavia

- Persistencia de escenarios favoritos
- Compartir escenarios entre usuarios
- Backtest contra data historica real
- Alertas si un escenario se activa en produccion
- Recomendaciones automaticas de esquema optimo
- Validacion contra cierres reales
- Multi-vehiculo / multi-conductor (simulacion es por unidad)

## GO/NO-GO para uso como calculadora exploratoria

| Criterio | Status |
|----------|--------|
| Calculo determinista correcto | GO |
| Inputs operativos disponibles | GO (parcial) |
| UI clara y funcional | GO |
| No contamina verdad historica | GO |
| No modifica pagos reales | GO |
| Persistencia de escenarios | NO-GO (solo memoria) |
| Validacion contra cierres | NO-GO (pendiente) |
| Multi-conductor | NO-GO (pendiente) |

**Veredicto: GO para uso exploratorio individual por Gonzalo.**

## QA

- `python -m compileall backend/app` — OK
- `cd frontend && npm run build` — OK
- No se tocan modulos fuera del scope
- Waterfall sigue funcionando
- Data Quality sigue funcionando

## Fecha

2026-05-29
