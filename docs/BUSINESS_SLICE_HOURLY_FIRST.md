# BUSINESS_SLICE — contrato hourly-first (Control Tower)

## Principio

La **fuente analítica canónica** de BUSINESS_SLICE sigue el patrón **hourly-first** alineado con el resto de REAL en Control Tower (p. ej. cadena `mv_real_lob_hour_v2` → día / semana / mes):

1. **Grano mínimo temporal**: **`trip_hour_start`** = `date_trunc('hour', fecha_inicio_viaje)` en `ops.v_real_trips_enriched_base` (también expuesto en `ops.v_real_trips_business_slice_resolved` para auditoría).
2. **Agregado horario persistido**: `ops.real_business_slice_hour_fact`, cargado por **bloques temporales** (`DELETE` + `INSERT…SELECT` acotado a `[hour_from, hour_to)` sobre la vista resolved, filtrada por rango de `trip_hour_start`). Incluye `total_fare_completed_positive_sum` para poder recomponer `commission_pct` al subir de grano.
3. **Agregado mensual operativo (transición)**: `ops.real_business_slice_month_fact` se carga **por mes** con `DELETE` del mes + **chunks** con `COMMIT` por chunk. La resolución de `business_slice` **no** lee la vista global `ops.v_real_trips_business_slice_resolved` como fuente principal: usa **`ops.fn_real_trips_business_slice_resolved_subset`**, que filtra primero en `ops.v_real_trips_enriched_base` y aplica las mismas reglas que la vista (prioridad `works_terms` > `tipo_servicio` > `park_only`). Esto reduce el riesgo de temporales enormes en `pgsql_tmp` frente al patrón “evaluar resolved completo y filtrar después”.
4. **Estado objetivo (consolidación futura)**: pipeline oficial **enriched (subconjunto) → resolved (subconjunto) → hour_fact → rollup** `ops.v_real_business_slice_month_from_hour` → alineación de `month_fact` con el rollup horario cuando `hour_fact` cubra el histórico con la densidad deseada. Hoy, **`month_fact` no deriva obligatoriamente de `hour_fact`**; es una **transición incremental válida** que mantiene la API/UI actuales.

## Compatibilidad

- `ops.mv_real_business_slice_monthly` es una **vista** con las **mismas columnas** que la antigua MV, leyendo desde `real_business_slice_month_fact`. No es fuente principal ni admite `REFRESH MATERIALIZED VIEW`.
- La API de backend usa **`ops.real_business_slice_month_fact`** como tabla de lectura (constante `FACT_MONTHLY` / `MV_MONTHLY` en `business_slice_service`).

## Operación

- Cargar un mes: `python -m scripts.refresh_business_slice_mvs --month YYYY-MM` o `--month YYYY-MM-DD` (mismo mes civil).
- Grano de chunk (opcional): `--chunk-grain city` (defecto vía env), `country`, `city_week`, `city_day`. `city_week` / `city_day` reparten por ciudad en semanas ISO (`trip_week`) o días (`trip_date`), acumulan en una tabla temporal de sesión y agregan una vez por ciudad (métricas correctas, p. ej. `active_drivers`).
- Backfill por rango: `--backfill-from YYYY-MM --backfill-to YYYY-MM` (acepta `--chunk-grain`).
- Bloque horario: `--hour-from "…" --hour-to "…"`

**Migraciones:** hace falta **116** (facts) y **117** (`ops.fn_real_trips_business_slice_resolved_subset`).

Tras migración **116**, hay que **poblar** `month_fact` (backfill o mes a mes); hasta entonces la vista `mv_real_business_slice_monthly` y la UI pueden mostrar conjunto vacío.

## Alcance explícito

- **No** incluye Plan, targets ni `plan_vs_real` (fuera de alcance).
- `ops.v_real_trips_business_slice_resolved` y `ops.v_real_trips_business_slice_resolved_mv12` siguen existiendo para **auditoría**, cobertura, unmatched/conflicts y carga horaria; la carga mensual **canónica** evita depender de ellas como fuente principal del agregado.

## Entorno

- El venv del proyecto suele estar en **`backend\venv`**: activar desde la carpeta `backend`, no desde la raíz del repo.
- Pasar el mes en **una sola línea**: `--month 2026-03-01` (si PowerShell parte el comando en dos líneas, falla el parseo).

## Problemas frecuentes

| Síntoma | Acción |
|--------|--------|
| `relation "ops.real_business_slice_month_fact" does not exist` | En `backend`: `alembic upgrade head` (116+). |
| `fn_real_trips_business_slice_resolved_subset` no existe | `alembic upgrade head` (117). |
| `No space left on device` / `base/pgsql_tmp/...` | Espacio en el **disco del servidor PostgreSQL** (donde está el `data_directory`), no en el PC del cliente. Liberar espacio o ampliar volumen. Mitigaciones: `BUSINESS_SLICE_LOAD_WORK_MEM` (p. ej. `512MB`); carga **por ciudad** por defecto; si una ciudad sigue pesada, `--chunk-grain city_week` o `city_day`. |
| Carga “larga” sin salida / `connection already closed` | El script hace **COMMIT tras cada chunk** (y tras el `DELETE` inicial del mes) e imprime progreso. Si falla, el mensaje indica **mes / país / ciudad / grano**. Reintente el mismo `--month`. |
| Reintentos con disco lleno | **No sirven** hasta liberar espacio en el volumen de PostgreSQL. Salida **3** del script `refresh_business_slice_mvs` = `DiskFull`. |

## Validación estática del loader

```text
python -m scripts.validate_business_slice_refresh --check-loader-contract
```

Comprueba que el SQL del camino mensual usa la función subset y no referencia la vista `v_real_trips_business_slice_resolved` en ese tramo (el bloque horario sigue usando la vista acotada por rango).
