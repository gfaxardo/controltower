# Entregables: trips_2026 + Driver Lifecycle PRO

Resumen de lo implementado por fases.

## FASE 0 — SCAN

- **Script:** `backend/scripts/scan_trips_drivers_parks_schema.py`
- **Uso:** `cd backend && python -m scripts.scan_trips_drivers_parks_schema`
- Inspecciona columnas y tipos de `public.trips_all`, `public.trips_2026`, `public.drivers`, `dim.dim_park`. Detecta candidatos driver_id, park_id, timestamp, condicion. Comprueba si `trips_all` tiene datos 2026 (MAX(fecha)).

## FASE 1 — VIEW unificada

- **Migración:** `backend/alembic/versions/054_trips_unified_view_and_indexes.py`
- Si existe `trips_2026`: VIEW con corte por fecha (trips_all &lt; 2026-01-01, trips_2026 ≥ 2026-01-01).
- Si no existe: VIEW = `SELECT * FROM public.trips_all`.
- **SQL directo (si no usas Alembic):** ver comentarios en la migración 054.

## FASE 2 — Índices mínimos

- Incluidos en la misma migración 054 (en ambas tablas cuando aplica):
  - `(fecha_inicio_viaje)`
  - `(condicion, fecha_inicio_viaje) WHERE condicion = 'Completado'`
  - `(park_id, fecha_inicio_viaje)`
  - `(conductor_id, fecha_inicio_viaje)`
- Para índices CONCURRENTLY en tablas muy grandes, ejecutar a mano fuera de la transacción de la migración (ver `docs/TRIPS_2026_IMPLEMENTACION_MINIMA.md`).

## FASE 3 — Driver Lifecycle → trips_unified

- **Migración:** `backend/alembic/versions/055_driver_lifecycle_use_trips_unified.py`
- Recrea `ops.v_driver_lifecycle_trips_completed` para que lea de `public.trips_unified` en lugar de `public.trips_all`.
- Las MVs (base, weekly_stats, monthly_stats) no se tocan; siguen leyendo de esa vista. Tras la migración, ejecutar `ops.refresh_driver_lifecycle_mvs()`.

## FASE 4 — Park Analysis UI (PRO)

- **Backend**
  - `GET /ops/driver-lifecycle/parks` → `[{ park_id, park_name }]` desde `dim.dim_park` (fallback: distinct park_id de MVs + lookup).
  - `GET /ops/driver-lifecycle/park/series?park_id=&from=&to=&grain=` → serie por periodo del park (alias de `/series` con park_id obligatorio).
  - `GET /ops/driver-lifecycle/series?from=&to=&grain=&park_id=` (park_id opcional; en UI PRO se envía siempre).
- **Frontend**
  - Selector de park obligatorio: sin "Todos"; opción "— Selecciona park —". No se cargan summary/series hasta elegir un park.
  - Lista de parks desde `getDriverLifecycleParksList()` (dim.dim_park).
  - Tabla principal: "Serie por periodo" del park seleccionado, orden desc. Cards responden al rango visible.
  - "Desglose por Park" solo al hacer clic en el botón (no por defecto).

## FASE 5 — Analítica PRO

- **Migraciones:** `backend/alembic/versions/056_driver_lifecycle_pro_mvs.py`
  - `ops.mv_driver_weekly_behavior`: driver_key, week_start, park_id_dominante, trips_completed_week, active_days_week, work_mode_week (FT/PT/casual).
  - `ops.mv_driver_churn_segments_weekly`: power/mid/light/newbie por actividad previa 4w.
  - `ops.mv_driver_behavior_shifts_weekly`: drop/spike/stable vs media 4w previas.
  - `ops.mv_driver_park_shock_weekly`: shock (cambio de park dominante: últimas 8w vs baseline 12-5).
- **Endpoints**
  - `GET /ops/driver-lifecycle/pro/churn-segments` (filtros: week_start, segment, park_id; `format=csv`).
  - `GET /ops/driver-lifecycle/pro/park-shock` (week_start; `format=csv`).
  - `GET /ops/driver-lifecycle/pro/behavior-shifts` (week_start, shift, park_id; `format=csv`).
  - `GET /ops/driver-lifecycle/pro/drivers-at-risk` (week_start, park_id; `format=csv`).
- **Export CSV:** añadir `?format=csv` a cualquiera de los anteriores.

## Comandos de verificación

- Ver `docs/DRIVER_LIFECYCLE_PRO_VERIFICACION.md`: counts, freshness, no duplicados, parks coverage, refresh orden.
- Script FASE 0 para validar columnas antes de desplegar.

## Orden de aplicación

1. Asegurar que `public.trips_2026` exista (misma estructura que `trips_all`) si se quiere unión 2026.
2. `alembic upgrade head` (054 → 055 → 056).
3. `SELECT ops.refresh_driver_lifecycle_mvs();`
4. Refrescar MVs PRO (véase doc de verificación).
5. Probar frontend: selector park obligatorio y serie por park.
