# Fase 2B - Distribucion semanal de Plan (desde mensual)

## Metodo
- Fuente: `ops.v_plan_trips_monthly_latest` (plan mensual canonico, ultima version).
- Para cada mes, se generan semanas dentro del mes con:
  - `generate_series(date_trunc('month', month)::date,
                     (date_trunc('month', month) + interval '1 month - 1 day')::date,
                     interval '1 week')`
  - `week_start = date_trunc('week', weeks)::date` (semana ISO Postgres, lunes).
- Se calcula `weeks_in_month` como el total de `week_start` distintos por mes.
- La distribucion es uniforme:
  - `trips_plan_week = trips_plan_month / weeks_in_month`
  - `drivers_plan_week = drivers_plan_month / weeks_in_month`
  - `revenue_plan_week = revenue_plan_month / weeks_in_month` (solo si existe)
  - `ingreso_por_viaje_plan_week = revenue_plan_week / trips_plan_week` (si aplica)

## Limitaciones
- La desagregacion es uniforme: no captura estacionalidad intra-mes (picos por semana).
- Semanas que cruzan meses reciben aportes de ambos meses (suma de ambas fracciones).
- Si el plan no incluye `revenue_plan`, se mantiene en `NULL` (no se inventa).
