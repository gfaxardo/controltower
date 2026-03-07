# Runbook: Backfill Real Drill (068/069 desacoplado)

## Qué cambió y por qué

- **068:** Antes creaba una MATERIALIZED VIEW y la llenaba dentro de la migración (ETL pesado). Ahora la migración solo crea la **tabla** `ops.real_drill_service_by_park` y la **vista** `ops.mv_real_drill_service_by_park` (mismo nombre y esquema para compatibilidad). El llenado se hace con un script fuera de Alembic.
- **069:** Antes hacía DELETE + INSERT en `real_drill_dim_fact` (breakdown=service_type) dentro de la migración. Ahora la migración es no-op; el dato con `tipo_servicio_norm` se carga con scripts de backfill.

Así, `alembic upgrade head` termina en segundos y el ETL se ejecuta bajo demanda con progreso visible y reintentos seguros.

## Orden de ejecución

1. Aplicar migraciones: `alembic upgrade head`
2. Backfill tabla por park: `python -m scripts.backfill_real_drill_service_by_park ...`
3. Backfill service_type en dim_fact: `python -m scripts.backfill_real_drill_service_type ...` (o usar `backfill_real_lob_mvs` si ya rellena service_type con tipo real)
4. Validar: `python -m scripts.check_real_drill_objects`

## Comandos exactos

```bash
cd backend

# 1. Migraciones (solo DDL)
alembic upgrade head

# 2–4. Backfill completo + validación (un solo comando, ~2–3 h)
python -m scripts.run_real_drill_backfill_e2e --from 2025-12-01 --to 2026-03-31 --chunk weekly
```

O por pasos:

```bash
# 2. Llenar ops.real_drill_service_by_park
python -m scripts.backfill_real_drill_service_by_park --from 2025-12-01 --to 2026-03-31 --chunk weekly --replace

# 3. Llenar filas breakdown='service_type' en real_drill_dim_fact
python -m scripts.backfill_real_drill_service_type --from 2025-12-01 --to 2026-03-31 --chunk weekly --replace

# 4. Validación
python -m scripts.check_real_drill_objects
```

## Ejemplos y opciones

- **Dry-run (solo ver rangos):**  
  `python -m scripts.backfill_real_drill_service_by_park --from 2025-01-01 --to 2025-12-31 --chunk monthly --dry-run`

- **Chunk mensual (menos chunks, más tiempo por chunk):**  
  `--chunk monthly`

- **Sin --replace (idempotente por rango):**  
  Sin `--replace`, el script de service_by_park borra solo el rango de cada chunk y reinserta; el de service_type borra por rango en cada chunk. Con `--replace` en service_by_park se usa staging y al final se reemplaza toda la tabla; en service_type se borran todas las filas service_type al inicio.

- **Un solo país:**  
  `python -m scripts.backfill_real_drill_service_by_park --from 2025-06-01 --to 2026-01-01 --country co`

## Reintentos si falla

- Si falla a mitad de backfill por park: volver a ejecutar con el mismo `--from`/`--to` **sin** `--replace` para rellenar solo los chunks no escritos (o con `--replace` para empezar de cero).
- Si falla el backfill de service_type: igual; con `--replace` se borra todo service_type y se rellena de nuevo; sin `--replace` se borra por rango y se reinserta por chunk.

## Validación

- Ejecutar `python -m scripts.check_real_drill_objects`: comprueba existencia de tabla/vista, conteos, freshness y que service_type no quede solo en "unknown".
- En BD:
  - `SELECT count(*) FROM ops.real_drill_service_by_park;`
  - `SELECT count(*) FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type';`
  - `SELECT dimension_key, count(*) FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type' GROUP BY 1;` (debe haber valores distintos de 'unknown' si hay datos).

## safe_refresh_real_lob

El script `safe_refresh_real_lob.py` ya **no** incluye `ops.mv_real_drill_service_by_park` en la lista de REFRESH (es una vista, no una MV). El llenado de ese objeto se hace con `backfill_real_drill_service_by_park.py` según este runbook.

## Consultas SQL de validación (estado, conteos, sample)

```sql
-- Estado Alembic
SELECT version_num FROM alembic_version;

-- Conteos
SELECT 'real_drill_service_by_park' AS obj, count(*) FROM ops.real_drill_service_by_park
UNION ALL
SELECT 'real_drill_dim_fact_service_type', count(*) FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type';

-- Freshness (últimas fechas)
SELECT max(period_start) AS last_period FROM ops.real_drill_service_by_park;
SELECT max(period_start) AS last_period FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type';

-- Tipos de servicio (no solo unknown)
SELECT dimension_key, count(*) FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type' GROUP BY 1 ORDER BY 2 DESC;

-- Sample drill (parks)
SELECT country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips
FROM ops.mv_real_drill_service_by_park
ORDER BY period_start DESC, trips DESC
LIMIT 10;
```

## Antes / después del cambio

- **Antes:** `alembic upgrade head` ejecutaba 068 y 069 con loops y ETL; podía colgarse o tardar mucho.
- **Después:** `alembic upgrade head` solo crea estructura; los backfills se ejecutan a mano y con progreso por chunk.
