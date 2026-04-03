# Real Trip Source Contract

**Arquitectura operativa**: Este contrato es la base para la capa operativa REAL (hourly-first). Cumplirlo permite reemplazar la fuente sin tocar agregaciones ni UI.

## Propósito

Define las columnas mínimas que cualquier fuente de viajes debe proveer para alimentar `ops.v_real_trip_fact_v2`. Permite cambiar la fuente base (trips_all, trips_2026, otra tabla, otra flota, otra operación) sin modificar las capas de agregación ni el frontend.

## Fuente actual (actualizado 2026-04-02)

| Tabla | Rango temporal | Estado |
|-------|---------------|--------|
| `public.trips_2025` | 2025-01-01 a 2025-12-31 | **OFICIAL** |
| `public.trips_2026` | >= 2026-01-01 | **OFICIAL** |
| `public.trips_all` | Histórico (legacy) | **LEGACY — NO usar para auditoría/reconstrucción** |

**Fuente oficial para nuevos consumidores:** `ops.v_real_trips_enriched_base` (trips_2025 + trips_2026, migración 118).
**Legacy aún en uso:** `ops.v_trips_real_canon_120d` (trips_all + trips_2026), pendiente migración.
Ver `docs/SOURCE_OF_TRUTH_REAL_AUDIT_V2.md` para la definición completa.

## Columnas mínimas requeridas

| Columna | Tipo PostgreSQL | Nullable | Descripción |
|---------|----------------|----------|-------------|
| `id` | TEXT o INT | NO | Identificador único del viaje |
| `park_id` | TEXT | NO | Identificador del parque/flota |
| `tipo_servicio` | TEXT | SÍ | Tipo de servicio raw (se normaliza) |
| `fecha_inicio_viaje` | TIMESTAMP | SÍ | Fecha/hora de inicio del viaje |
| `fecha_finalizacion` | TIMESTAMP | SÍ | Fecha/hora de finalización |
| `comision_empresa_asociada` | NUMERIC | SÍ | Comisión YEGO (revenue/margin) |
| `pago_corporativo` | NUMERIC | SÍ | Si no es NULL → B2B |
| `distancia_km` | NUMERIC | SÍ | Distancia en metros (se divide por 1000) |
| `condicion` | TEXT | SÍ | Estado del viaje: 'Completado', 'Cancelado', etc. |
| `conductor_id` | TEXT | SÍ | ID del conductor |
| `motivo_cancelacion` | TEXT | SÍ | Motivo de cancelación (solo para cancelados) |

## Reglas semánticas

1. **`condicion`**: Debe contener al menos 'Completado' para viajes finalizados exitosamente, y 'Cancelado' para cancelados. Otros valores se clasifican como 'other'.

2. **`fecha_inicio_viaje`**: Es la columna canónica de tiempo. Los viajes con NULL se excluyen.

3. **`fecha_finalizacion`**: Se usa para calcular duración. Solo se considera válida si:
   - Es posterior a `fecha_inicio_viaje`
   - La diferencia está entre 30 segundos y 10 horas (36000 segundos)

4. **`motivo_cancelacion`**: Se normaliza (trim, lowercase, quitar ruido) y se agrupa en categorías de negocio.

5. **`distancia_km`**: Viene en metros desde la fuente, se convierte a km dividiendo por 1000.

6. **`tipo_servicio`**: Se normaliza con `canon.normalize_real_tipo_servicio()` y se mapea a LOB via `canon.dim_service_type` → `canon.dim_lob_group`.

## Cómo onboardear otra fuente

### Paso 1: Verificar columnas

Ejecutar contra la nueva fuente:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'new_schema' AND table_name = 'new_table'
AND column_name IN (
    'id', 'park_id', 'tipo_servicio', 'fecha_inicio_viaje',
    'fecha_finalizacion', 'comision_empresa_asociada', 'pago_corporativo',
    'distancia_km', 'condicion', 'conductor_id', 'motivo_cancelacion'
)
ORDER BY column_name;
```

### Paso 2: Crear vista canónica equivalente

Si la nueva fuente tiene las mismas columnas, reemplazar `ops.v_trips_real_canon_120d`:

```sql
CREATE OR REPLACE VIEW ops.v_trips_real_canon_120d AS
SELECT
    id, park_id, tipo_servicio, fecha_inicio_viaje, fecha_finalizacion,
    comision_empresa_asociada, pago_corporativo, distancia_km,
    condicion, conductor_id,
    'new_source'::text AS source_table
FROM new_schema.new_table
WHERE fecha_inicio_viaje IS NOT NULL
  AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days';
```

Si la nueva fuente tiene columnas con nombres distintos, usar aliases.

### Paso 3: Verificar

```sql
SELECT COUNT(*), MIN(fecha_inicio_viaje), MAX(fecha_inicio_viaje)
FROM ops.v_trips_real_canon_120d;

SELECT trip_outcome_norm, COUNT(*)
FROM ops.v_real_trip_fact_v2
GROUP BY 1;
```

### Paso 4: Re-bootstrap

```bash
cd backend && python scripts/bootstrap_hourly_first.py
```

### Paso 5: Validar

```bash
cd backend && python scripts/governance_hourly_first.py --skip-refresh
```

## Capas que NO se tocan al cambiar la fuente

| Capa | Depende de |
|------|-----------|
| `ops.v_real_trip_fact_v2` | `ops.v_trips_real_canon_120d` (único punto de contacto con raw) |
| `ops.mv_real_lob_hour_v2` | `ops.v_real_trip_fact_v2` |
| `ops.mv_real_lob_day_v2` | `ops.mv_real_lob_hour_v2` |
| `ops.mv_real_lob_week_v3` | `ops.mv_real_lob_hour_v2` |
| `ops.mv_real_lob_month_v3` | `ops.mv_real_lob_hour_v2` |
| Backend services | MVs v3 |
| Frontend | Backend API |
