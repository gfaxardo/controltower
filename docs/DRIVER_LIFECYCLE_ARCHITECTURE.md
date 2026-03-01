# Driver Lifecycle — Arquitectura productizada (drilldown por PARK)

## Resumen

- **Fuentes:** Solo datos reales: `public.trips_all`, `public.drivers`. Plan y Real no se mezclan.
- **MVs:** `ops.mv_driver_lifecycle_base`, `ops.mv_driver_weekly_stats`, `ops.mv_driver_monthly_stats`, `ops.mv_driver_lifecycle_weekly_kpis`, `ops.mv_driver_lifecycle_monthly_kpis`, `ops.mv_driver_cohorts_weekly`, `ops.mv_driver_cohort_kpis`.
- **Park:** Se deriva en **una sola MV**: `mv_driver_weekly_stats`. Definición oficial: **park_dominante_semana** = `park_id` con mayor `trips_completed_week` por (driver, week). Desempate: menor `park_id` (determinístico). No se usa "primer trip".
- **Activations por park:** Join `mv_driver_lifecycle_base` con `mv_driver_weekly_stats` en `driver_key` y `week_start = DATE_TRUNC('week', activation_ts)::date`; el `park_id` de esa fila asigna el park de activación.

## Diagrama de flujo (una sola fuente)

```
trips_all (condicion, conductor_id, fecha_inicio_viaje, fecha_finalizacion, park_id, ...)
    │
    ▼
v_driver_lifecycle_trips_completed
    │
    ├──────────────────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          ▼
mv_driver_lifecycle_base (MIN/MAX completion_ts por driver)   mv_driver_weekly_stats (driver, week, park_dominante, trips_completed_week)
    │                                                          │
    │                                                          ├──► v_driver_weekly_churn_reactivation
    │                                                          │
    └──────────────┬──────────────────────────────────────────┘
                   │
                   ▼
         mv_driver_lifecycle_weekly_kpis (activations desde base; active_drivers, churn_flow, reactivated desde weekly_stats)
                   │
                   ▼
         mv_driver_cohorts_weekly (cohort_week, park_id, active_w1/w4/w8/w12)
                   │
                   ▼
         mv_driver_cohort_kpis (cohort_size, retention_w1/w4/w8/w12)
```

## Garantía matemática Σ park = global

- **Activations:** Cada driver que activa en semana W tiene exactamente una fila en `mv_driver_weekly_stats` para (driver_key, W). El `park_id` de esa fila es el park_dominante. Por tanto Σ activations por park = activations global.
- **Active drivers:** Cada fila en weekly_stats es (driver_key, week_start, park_id). Suma por (week_start, park_id) = total por week_start (incluyendo park_id NULL si aplica).
- **Churn flow / Reactivated:** Definidos sobre weekly_stats; una fila por (driver, week) → Σ por park = global.
- Validación automática: `backend/sql/driver_lifecycle_consistency_validation.sql` (A, B, C, D). Si hay diff, no continuar; investigar causa.

## Definición formal park_dominante_semana

- **Fuente:** `ops.v_driver_lifecycle_trips_completed` (trips completados con conductor_id, completion_ts, park_id).
- **Agregación por (conductor_id, week_start, park_id):** `trips_in_park = COUNT(*)`.
- **Park dominante:** Para cada (conductor_id, week_start), el `park_id` tal que `trips_in_park` es máximo. **Desempate:** `ORDER BY trips_in_park DESC, park_id ASC` → se toma el primero (menor park_id).
- La lógica vive **solo** en `ops.mv_driver_weekly_stats`. No hay derivación implícita en otras MVs.

## Definición formal churn

- **Churn flow (semana W):** Driver que tiene fila en `mv_driver_weekly_stats` para (driver_key, week_start=W) y **no** tiene fila para (driver_key, week_start=W+7).
- **Reactivated (semana W):** Driver que no tenía trips en W-1 (`prev_week_trips = 0` o NULL) y tiene `trips_completed_week > 0` en W. Definido en `v_driver_weekly_churn_reactivation`.

## Definición cohort_week

- **cohort_week:** `DATE_TRUNC('week', activation_ts)::date` (lunes de la semana de activación).
- **park_id de cohorte:** park_dominante en la semana de activación (desde `mv_driver_weekly_stats`).
- **Activo en W+n:** Driver tiene fila en `mv_driver_weekly_stats` para `week_start = cohort_week + n*7`.

## Garantía Σ park = global

- **Activations:** Cada driver que activa en semana W tiene exactamente una fila en `mv_driver_weekly_stats` para (driver_key, W). El `park_id` de esa fila es el park_dominante. Por tanto **Σ activations por park = activations global**.
- **Active drivers:** Cada fila en weekly_stats es (driver_key, week_start, park_id). Suma por (week_start, park_id) = total por week_start.
- **Churn flow / Reactivated:** Definidos sobre weekly_stats; una fila por (driver, week) → **Σ por park = global**.

## Umbral calidad park

- **null_share:** `COUNT(*) FILTER (WHERE park_id IS NULL) / COUNT(*)` en `mv_driver_weekly_stats`.
- **Umbral:** null_share ≤ 5% (0.05). Si > 5%: **WARNING** (no bloquea deploy).

## Flujo final (apply_driver_lifecycle_v2.py)

1. **Preflight:** Guardar viewdefs en `backend/sql/rollback/`; generar `restore_driver_lifecycle_v1.sql`.
2. **Baseline consistency:** Registrar diffs (no bloquea).
3. **Hardening v2:** En transacción (BEGIN/COMMIT); si falla → rollback.
4. **Refresh:** Con benchmark (breakdown por MV).
5. **Post consistency:** Si falla → ejecutar restore automático → exit 1.
6. **Park quality:** null_share; WARNING si > 5%.
7. **Índices:** trips_all + cohort (driver_key+week_start, park_id+week_start).
8. **Cohortes:** Crear MVs si no existen; refresh_with_cohorts.
9. **Refresh final:** Con benchmark.
10. **Cohort validation:** Si retention > 1 o cohort_size no cuadra → exit 1.
11. **Quality gates:** Parks distintos, null_share.

## Estrategia de refresh

1. **Orden obligatorio:** base → weekly_stats → monthly_stats → weekly_kpis → monthly_kpis → cohorts_weekly → cohort_kpis.
2. **Timeouts:** `statement_timeout = 60min`, `lock_timeout = 60s` dentro de la función.
3. **CONCURRENTLY** por defecto (no bloquea lecturas). Fallback: `refresh_driver_lifecycle_mvs_nonc()` en ventana de mantenimiento.
4. Post-refresh: ejecutar validación de consistencia (A–D) y, si existen cohortes, validaciones de cohortes.

## Trazabilidad

| KPI | Origen | Drilldown a driver_key |
|-----|--------|------------------------|
| Activations | base + weekly_stats (semana de activation_ts) | base + weekly_stats filtrado por park_id y week_start |
| Active drivers | weekly_stats / monthly_stats | Filtrar por park_id y period_start |
| Churned | weekly_stats (presente en W, ausente en W+1) | Filtrar por park_id y week_start |
| Reactivated | v_driver_weekly_churn_reactivation | Vista tiene park_id |
| FT/PT | work_mode_week / work_mode_month en stats | Filtrar por park_id y period_start |

## Backend

- **Router:** `app/routers/driver_lifecycle.py` (prefix `/ops/driver-lifecycle`).
- **Service:** `app/services/driver_lifecycle_service.py`.
- **Endpoints:**
  - `GET /ops/driver-lifecycle/weekly?from=&to=&park_id=` — KPIs semanales; sin `park_id` incluye `breakdown_by_park`.
  - `GET /ops/driver-lifecycle/monthly?from=&to=&park_id=` — KPIs mensuales; sin `park_id` incluye `breakdown_by_park`.
  - `GET /ops/driver-lifecycle/drilldown?period_type=&period_start=&metric=&park_id=&page=&page_size=` — Lista paginada de driver_key (metric: activations, churned, reactivated, active, fulltime, parttime).
  - `GET /ops/driver-lifecycle/parks-summary?from=&to=&period_type=` — Ranking parks por activations, churn_rate, net_growth, mix FT/PT.
  - `GET /ops/driver-lifecycle/parks` — Lista de park_id para selector.

## Frontend

- **Pestaña:** "Driver Lifecycle" en la barra principal.
- **Componente:** `DriverLifecycleView.jsx`.
- **Filtros:** From, To, Park (opcional), Semanal/Mensual.
- **Bloque KPI:** Activations (rango), Active drivers (último periodo), Churned/Reactivated (semanal).
- **Tabla:** Desglose por Park (Park, Activations, Active Drivers, Churn Rate, Reactivation Rate, Net Growth, Mix FT/PT). Celdas numéricas clickeables → modal con lista de driver_key y export CSV.

## SQL y validación

- **Mapeo y estrategia park:** `docs/DRIVER_LIFECYCLE_MAPEO_PARK.md`.
- **Validación trazabilidad:** `backend/scripts/sql/driver_lifecycle_trazabilidad_validation.sql` (activations por park = global, churn consistente, parks distintos).
- **Refresh y hardening:** `backend/sql/driver_lifecycle_refresh_hardening.sql`, `backend/scripts/run_driver_lifecycle_hardening.py`, `backend/scripts/check_driver_lifecycle_and_validate.py`.

## Operación

- **Refresh:** `python -m scripts.refresh_driver_lifecycle` o `python -m scripts.check_driver_lifecycle_and_validate`.
- **Post-refresh (FASE E):** El script valida parks distintos, top 5 parks por activations (28 días), total activations (28 días). Si falla drilldown/parks no bloquea; solo loguea.

## Archivos entregados (blindaje v2 + cohortes)

| Tipo | Ruta |
|------|------|
| **Validación consistencia (FASE 1)** | backend/sql/driver_lifecycle_consistency_validation.sql |
| **Hardening v2 (FASE 2–3)** | backend/sql/driver_lifecycle_hardening_v2.sql (park_dominante, weekly_kpis una fuente) |
| **Índices y ANALYZE (FASE 4)** | backend/sql/driver_lifecycle_indexes_and_analyze.sql |
| **Cohortes (FASE 5)** | backend/sql/driver_lifecycle_cohorts.sql |
| **Validación cohortes (FASE 6)** | backend/scripts/sql/driver_lifecycle_cohort_validation.sql |
| **Refresh con cohortes** | backend/sql/driver_lifecycle_refresh_with_cohorts.sql |
| Doc mapeo | docs/DRIVER_LIFECYCLE_MAPEO_PARK.md |
| Doc arquitectura | docs/DRIVER_LIFECYCLE_ARCHITECTURE.md |
| Resumen ejecutivo | docs/DRIVER_LIFECYCLE_RESUMEN_EJECUTIVO.md |
| Service | backend/app/services/driver_lifecycle_service.py |
| Router | backend/app/routers/driver_lifecycle.py |
| Frontend | frontend/src/components/DriverLifecycleView.jsx |
| Validación trazabilidad | backend/scripts/sql/driver_lifecycle_trazabilidad_validation.sql |
| Script refresh | backend/scripts/refresh_driver_lifecycle.py |
