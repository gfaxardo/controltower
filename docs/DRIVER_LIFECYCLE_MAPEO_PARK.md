# Driver Lifecycle — Mapeo estructural (drilldown por PARK)

## FASE A — Resumen

### Columnas reales

| Objeto | Columnas relevantes |
|--------|---------------------|
| **ops.mv_driver_lifecycle_base** | driver_key, activation_ts, last_completed_ts, total_trips_completed, lifetime_days, activation_hour, registered_ts, hire_date, ttf_days_from_registered, **driver_park_id** (de tabla drivers) |
| **ops.mv_driver_lifecycle_weekly_kpis** | week_start, activations, active_drivers, churn_flow, reactivated — **NO park_id** (agregado global) |
| **ops.mv_driver_lifecycle_monthly_kpis** | month_start, activations, active_drivers — **NO park_id** (agregado global) |
| **ops.mv_driver_weekly_stats** | driver_key, **week_start**, trips_completed_week, work_mode_week, **park_id**, tipo_servicio, segment, is_active_week |
| **ops.mv_driver_monthly_stats** | driver_key, **month_start**, trips_completed_month, work_mode_month, **park_id**, tipo_servicio, segment, is_active_month |

### Respuestas obligatorias

- **base_driver_key** = `driver_key`
- **weekly_period_col** = `week_start` (en mv_driver_weekly_stats y mv_driver_lifecycle_weekly_kpis)
- **monthly_period_col** = `month_start` (en mv_driver_monthly_stats y mv_driver_lifecycle_monthly_kpis)
- **park_col_available** en weekly_kpis/monthly_kpis = **no** (solo periodo y KPIs agregados)
- **park_col_available** en mv_driver_weekly_stats / mv_driver_monthly_stats = **sí** (`park_id`)

### Estrategia para park

- **KPIs por park:** No están en weekly_kpis ni monthly_kpis. Se derivan agregando desde **ops.mv_driver_weekly_stats** y **ops.mv_driver_monthly_stats** (que ya tienen `park_id` por driver-periodo).
- **Activations por park:** Un driver “activa” en la semana W. Su park en esa semana es el de su fila en `mv_driver_weekly_stats` para (driver_key, week_start = W). Por tanto:
  - **Activations por (week_start, park_id)** = drivers con `DATE_TRUNC('week', activation_ts)::date = week_start` y que en `mv_driver_weekly_stats` tienen esa misma (driver_key, week_start) con `park_id = P`.
  - Fuente: join `mv_driver_lifecycle_base` con `mv_driver_weekly_stats` en `driver_key` y `week_start = DATE_TRUNC('week', activation_ts)::date`.
- **Park en driver-week/driver-month:** En el build ya se usa **park dominante por periodo** = `MIN(park_id)` por conductor_id + period (primer park por orden, equivalente a “park del primer trip del periodo”). Documentado en SQL como `park_id_mode`.
- **No se crea nueva MV:** Las MVs `mv_driver_weekly_stats` y `mv_driver_monthly_stats` ya existen y tienen `park_id`. Los KPIs por park se calculan en el backend (o en vistas SQL) agregando por `park_id` + periodo desde esas MVs y desde el join base↔weekly_stats para activations.

### Trazabilidad

- Todo KPI por park se puede bajar a driver_key usando:
  - **Activations:** base + weekly_stats (park en semana de activación).
  - **Active / churned / reactivated / FT/PT:** weekly_stats o monthly_stats filtrados por park_id y periodo.
