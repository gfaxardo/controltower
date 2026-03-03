# Driver Lifecycle PRO — Comandos de verificación

Tras aplicar migraciones 054–056 y refrescar MVs.

## 0) Migración 054 e índices (opcional)

La migración **054** solo crea la VIEW `public.trips_unified` (sin índices) para evitar timeout en tablas grandes. Los índices se crean aparte:

- Ejecutar con **statement_timeout** alto (ej. 1h) y **fuera de transacción**:
  `backend/scripts/sql/trips_unified_indexes_concurrent.sql`
- Ejemplo: `psql $DATABASE_URL -v statement_timeout=3600000 -f backend/scripts/sql/trips_unified_indexes_concurrent.sql`
- Si no existe `trips_2026`, comentar o no ejecutar el bloque de índices de `trips_2026`.

## 1) VIEW y fuentes

```sql
-- Existencia y definición
SELECT definition FROM pg_views WHERE schemaname = 'public' AND viewname = 'trips_unified';

-- Conteo sin duplicados (si hay trips_2026): comparar suma partes vs vista
SELECT (SELECT COUNT(*) FROM public.trips_all WHERE fecha_inicio_viaje IS NULL OR fecha_inicio_viaje < '2026-01-01') AS n_all,
       (SELECT COUNT(*) FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-01-01') AS n_2026,
       (SELECT COUNT(*) FROM public.trips_unified) AS n_unified;
-- n_unified debe ser n_all + n_2026.
```

## 2) Driver Lifecycle usa trips_unified

```sql
SELECT definition FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_driver_lifecycle_trips_completed';
-- Debe contener "FROM public.trips_unified".
```

## 3) Freshness y counts MVs

```sql
SELECT 'mv_driver_lifecycle_base' AS mv, COUNT(*) AS filas FROM ops.mv_driver_lifecycle_base
UNION ALL SELECT 'mv_driver_weekly_stats', COUNT(*) FROM ops.mv_driver_weekly_stats
UNION ALL SELECT 'mv_driver_monthly_stats', COUNT(*) FROM ops.mv_driver_monthly_stats
UNION ALL SELECT 'mv_driver_weekly_behavior', COUNT(*) FROM ops.mv_driver_weekly_behavior
UNION ALL SELECT 'mv_driver_churn_segments_weekly', COUNT(*) FROM ops.mv_driver_churn_segments_weekly
UNION ALL SELECT 'mv_driver_behavior_shifts_weekly', COUNT(*) FROM ops.mv_driver_behavior_shifts_weekly
UNION ALL SELECT 'mv_driver_park_shock_weekly', COUNT(*) FROM ops.mv_driver_park_shock_weekly;
```

```sql
SELECT MAX(last_completed_ts) AS freshness_base FROM ops.mv_driver_lifecycle_base;
SELECT COUNT(DISTINCT park_id) AS parks_coverage FROM ops.mv_driver_weekly_stats WHERE park_id IS NOT NULL;
```

## 4) No duplicados (unicidad)

```sql
SELECT driver_key, week_start, COUNT(*) AS cnt
FROM ops.mv_driver_weekly_stats
GROUP BY driver_key, week_start
HAVING COUNT(*) > 1;
-- Debe devolver 0 filas.
```

## 5) Parks coverage (dim.dim_park)

```sql
SELECT COUNT(*) AS total_parks FROM dim.dim_park;
-- El endpoint GET /ops/driver-lifecycle/parks debe devolver park_id y park_name desde aquí.
```

## 6) Refresh orden recomendado

```sql
SELECT ops.refresh_driver_lifecycle_mvs();
-- Luego, si existen las MVs PRO:
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_weekly_behavior;
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_churn_segments_weekly;
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_behavior_shifts_weekly;
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_park_shock_weekly;
```

## 7) Endpoints PRO y CSV

- `GET /ops/driver-lifecycle/pro/churn-segments?format=csv`
- `GET /ops/driver-lifecycle/pro/park-shock?format=csv`
- `GET /ops/driver-lifecycle/pro/behavior-shifts?format=csv`
- `GET /ops/driver-lifecycle/pro/drivers-at-risk?format=csv`
