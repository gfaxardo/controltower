# BUSINESS_SLICE — contrato hourly-first (Control Tower)

## Principio

La **fuente analítica canónica** de BUSINESS_SLICE sigue el patrón **hourly-first** alineado con el resto de REAL en Control Tower (p. ej. cadena `mv_real_lob_hour_v2` → día / semana / mes):

1. **Grano mínimo**: viaje clasificado con **`trip_hour_start`** = `date_trunc('hour', fecha_inicio_viaje)` en `ops.v_real_trips_enriched_base` (expuesto en `ops.v_real_trips_business_slice_resolved`).
2. **Agregado horario persistido**: `ops.real_business_slice_hour_fact`, cargado por **bloques temporales** (`DELETE` + `INSERT…SELECT` acotado a `[hour_from, hour_to)`). Incluye `total_fare_completed_positive_sum` para poder recomponer `commission_pct` al subir de grano.
3. **Agregado mensual operativo**: `ops.real_business_slice_month_fact`, cargado **por mes** (`DELETE` + `INSERT…SELECT` solo para `trip_month = mes objetivo`), sin depender de un refresh monolítico de toda la historia.
4. **Rollup mensual desde hora (preparado)**: `ops.v_real_business_slice_month_from_hour` agrega `hour_fact` a mes. Algunas métricas (p. ej. `active_drivers`, ratios por km/tiempo) no son suma fiel en ese rollup; `commission_pct` se deriva de sumas de revenue y total_fare a nivel horario.

## Compatibilidad

- `ops.mv_real_business_slice_monthly` es una **vista** con las **mismas columnas** que la antigua MV, leyendo desde `real_business_slice_month_fact`. No es fuente principal ni admite `REFRESH MATERIALIZED VIEW`.
- La API de backend usa **`ops.real_business_slice_month_fact`** como tabla de lectura (constante `FACT_MONTHLY` / `MV_MONTHLY` en `business_slice_service`).

## Operación

- Cargar un mes: `python -m scripts.refresh_business_slice_mvs --month YYYY-MM` o `--month YYYY-MM-DD` (mismo mes civil)
- Backfill por rango: `--backfill-from YYYY-MM --backfill-to YYYY-MM`
- Bloque horario: `--hour-from "…" --hour-to "…"`

Tras migración **116**, hay que **poblar** `month_fact` (backfill o mes a mes); hasta entonces la vista `mv_real_business_slice_monthly` y la UI pueden mostrar conjunto vacío.

## Alcance explícito

- **No** incluye Plan, targets ni `plan_vs_real` (fuera de alcance).
- `ops.v_real_trips_business_slice_resolved_mv12` sigue existiendo para auditoría en ventana 12m; la carga mensual usa la vista **resolved completa** para no perder histórico fuera de esa ventana.

## Entorno

- El venv del proyecto suele estar en **`backend\venv`**: activar desde la carpeta `backend`, no desde la raíz del repo.
- Pasar el mes en **una sola línea**: `--month 2026-03-01` (si PowerShell parte el comando en dos líneas, falla el parseo).

## Problemas frecuentes

| Síntoma | Acción |
|--------|--------|
| `relation "ops.real_business_slice_month_fact" does not exist` | En `backend`: `alembic upgrade head` (revisión 116). |
| `No space left on device` / `base/pgsql_tmp/...` | Espacio en el **disco del servidor PostgreSQL** (donde está el `data_directory`), no en el PC del cliente. Liberar espacio o mover/ampliar volumen. Mitigaciones en carga: `BUSINESS_SLICE_LOAD_WORK_MEM` (p. ej. `512MB`); la carga mensual va **por país** por defecto (`BUSINESS_SLICE_MONTH_LOAD_CHUNK_BY_COUNTRY=1`) para bajar el pico de temporales. `=0` vuelve a un solo `INSERT` grande. |
| Carga “larga” sin salida / `connection already closed` | Desde el script CLI se hace **COMMIT tras cada chunk** y se imprime progreso en consola. Por defecto el grano es **país+ciudad** (`BUSINESS_SLICE_MONTH_CHUNK_GRAIN=city`); `=country` usa menos commits pero más pico en temporales. Si falla a mitad, vuelva a lanzar el mismo `--month`. El prompt `>>` en PowerShell indica línea incompleta: Ctrl+C y un solo renglón con el comando. |
| Reintentos con disco lleno | **No sirven** hasta liberar espacio en el volumen de PostgreSQL. Salida **3** del script `refresh_business_slice_mvs` = `DiskFull`. |
