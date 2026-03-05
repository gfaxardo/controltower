# Real LOB: fuente canónica de trips y freshness

## Contexto

Real LOB usaba solo `public.trips_all` para métricas y freshness. `trips_all` tiene datos hasta enero; los de feb/mar 2026 están en `public.trips_2026`. La solución es una **fuente real canónica** que unifica ambas tablas y que usan todas las vistas y MVs de Real LOB.

## Entregables (migración 064)

### 1. `ops.v_trips_real_canon`

- **Qué es**: Vista que une `trips_all` (histórico &lt; 2026-01-01) y `trips_2026` (≥ 2026-01-01) con las columnas necesarias para Real LOB y freshness.
- **Columnas**: `id`, `park_id`, `tipo_servicio`, `fecha_inicio_viaje`, `fecha_finalizacion`, `comision_empresa_asociada`, `pago_corporativo`, `distancia_km`, `condicion`, `conductor_id`, `source_table`.
- **Auditoría**: `source_table` indica el origen de cada fila (`'trips_all'` o `'trips_2026'`).
- **Sin duplicados**: Corte por fecha (como `public.trips_unified`); si no existe `trips_2026`, la vista equivale a `trips_all` con `source_table = 'trips_all'`.

### 2. `ops.v_real_freshness_trips`

- **Qué es**: Freshness de Real LOB por país desde la fuente canónica.
- **Contenido**: `country`, `last_trip_date`, `max_trip_ts` con `condicion = 'Completado'`. País derivado vía `parks` (misma lógica CO/PE que el resto de Real LOB).

### 3. Real LOB usando la canónica

- **`ops.v_real_trips_with_lob_v2`**: deja de leer `public.trips_all` y pasa a leer `ops.v_trips_real_canon`.
- **`ops.mv_real_drill_dim_agg`**: MV dimensional única con breakdown (`lob`|`park`|`service_type`). 1 fila por dimensión por periodo. Fix: drill por LOB ya no duplica (agrupa solo por lob_group). Nuevo desglose: Tipo de servicio (economico, confort, confort_plus, xl, premier, unknown).
- **`ops.v_real_drill_lob`**, **`ops.v_real_drill_park`**, **`ops.v_real_drill_service_type`**: vistas legacy filtradas por breakdown.
- **`ops.mv_real_rollup_day`**: base desde `ops.v_trips_real_canon`.
- **`ops.v_real_data_coverage`**: se recrea y sigue leyendo de `ops.mv_real_rollup_day` (que ya usa la canónica), por lo que `last_trip_date` en la UI refleja feb/mar 2026 si existen en `trips_2026`.

Las vistas de drill (`v_real_drill_country_month/week`, etc.) se recrean igual que en 053 y siguen dependiendo de `mv_real_rollup_day` y `v_real_data_coverage`.

## Validación

Ejecutar:

```bash
cd backend
psql $DATABASE_URL -f scripts/sql/validate_real_lob_canon_freshness.sql
```

Comprobaciones esperadas:

1. **E1**: `MAX(fecha_inicio_viaje)` en `ops.v_trips_real_canon` (Completado) ≥ que el de `trips_all` y ≥ que el de `trips_2026`. Si hay datos en mar 2026 en `trips_2026`, el máximo global debe ser de marzo.
2. **E2**: `ops.v_real_freshness_trips` muestra `last_trip_date` por país (co, pe) acorde a la canónica.
3. **E3**: `ops.v_real_data_coverage` tiene `last_trip_date` / `last_month_with_data` actualizados (marzo si hay data).
4. **E4**: Conteo por `source_table` en la canónica para ver cuántas filas vienen de cada tabla.
5. **E5**: Drill dimensional: breakdown=lob sin duplicados (1 fila por LOB por periodo+segment); breakdown=service_type con dimension_key en {economico, confort, confort_plus, xl, premier, unknown}; SUM(trips) coherente entre breakdowns.

## Frontend

- El header de Real LOB usa la cobertura desde `ops.v_real_data_coverage` (`last_trip_date`).
- Selector Desglose: LOB | Park | Tipo de servicio. Tabla children: viajes, margen total, margen/trip, km prom, b2b_trips, %b2b.

## Trazabilidad opcional

- Para un desglose por fuente en APIs o reportes se puede consultar `ops.v_trips_real_canon` con `GROUP BY source_table` o exponer `last_trip_date` + breakdown por `source_table` si se desea.

## Comandos a ejecutar (tras aplicar cambios)

**NO ejecutar desde el asistente. El usuario ejecutará manualmente:**

1. **Aplicar migración 064** (una sola vez):
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Validación SQL**:
   ```bash
   psql $DATABASE_URL -f scripts/sql/validate_real_lob_canon_freshness.sql
   ```

3. **Smoke test UI**: Abrir Real LOB — Drill por país, verificar:
   - Desglose LOB: 1 fila por LOB (sin duplicados)
   - Desglose Park: columna Park con "nombre — ciudad" (sin park_id)
   - Desglose Tipo de servicio: economico, confort, confort_plus, xl, premier, unknown
   - B2B: formato "N (X.X%)" con 1 decimal
   - Freshness: último día con data actualizado (Feb/Mar si hay datos en trips_2026)
