# BUSINESS_SLICE — contrato hourly-first (Control Tower)

## Principio

La **fuente analítica canónica** de BUSINESS_SLICE sigue el patrón **hourly-first** alineado con el resto de REAL en Control Tower (p. ej. cadena `mv_real_lob_hour_v2` → día / semana / mes):

1. **Grano mínimo temporal**: **`trip_hour_start`** = `date_trunc('hour', fecha_inicio_viaje)` en `ops.v_real_trips_enriched_base` (también expuesto en `ops.v_real_trips_business_slice_resolved` para auditoría).
2. **Agregado horario persistido**: `ops.real_business_slice_hour_fact`, cargado por **bloques temporales** (`DELETE` + `INSERT…SELECT` acotado a `[hour_from, hour_to)` sobre la vista resolved, filtrada por rango de `trip_hour_start`). Incluye `total_fare_completed_positive_sum` para poder recomponer `commission_pct` al subir de grano.
3. **Agregado mensual operativo (transición)**: `ops.real_business_slice_month_fact` se carga con estrategia **"materializar una vez, agregar N veces"**:
   - **Paso 1**: `DELETE` del mes + `COMMIT`.
   - **Paso 2**: `CREATE TEMP TABLE _bs_enriched_month AS SELECT * FROM ops.v_real_trips_enriched_base WHERE trip_month = mes` — **un solo scan** de la vista pesada (UNION ALL + DISTINCT ON + JOINs). Se indexa `(country, city)` y `(park_id)`. `COMMIT`.
   - **Paso 3**: Descubrir chunks `(country, city)` desde el temp table (rápido).
   - **Paso 4**: Para cada chunk, **resolución inline** (mismas CTEs que la vista resolved: reglas de mapping, prioridad `works_terms` > `tipo_servicio` > `park_only`, tie-break subflotas) **leyendo del temp table**, agregación, `INSERT` en `month_fact`, `COMMIT`, print progreso.
   - **Paso 5**: `DROP` temp table.
   Esto elimina las re-evaluaciones repetidas de la vista pesada que causaban que la carga se quedara colgada o reventara `pgsql_tmp`.
4. **Estado objetivo (consolidación futura)**: pipeline oficial **enriched (subconjunto) → resolved (subconjunto) → hour_fact → rollup** `ops.v_real_business_slice_month_from_hour`. Hoy, **`month_fact` no deriva obligatoriamente de `hour_fact`**; es una **transición incremental válida**.

## Compatibilidad

- `ops.mv_real_business_slice_monthly` es una **vista** con las **mismas columnas** que la antigua MV, leyendo desde `real_business_slice_month_fact`. No es fuente principal ni admite `REFRESH MATERIALIZED VIEW`.
- La API de backend usa **`ops.real_business_slice_month_fact`** como tabla de lectura (constante `FACT_MONTHLY` / `MV_MONTHLY` en `business_slice_service`).

## Operación

- Cargar un mes: `python -m scripts.refresh_business_slice_mvs --month YYYY-MM` o `--month YYYY-MM-DD` (mismo mes civil).
- Grano de chunk (opcional): `--chunk-grain city` (defecto), `country`, `city_week`, `city_day`. Con la materialización, `city_week` / `city_day` se comportan igual que `city` internamente (el cuello de botella ya no está en los subchunks).
- Backfill por rango: `--backfill-from YYYY-MM --backfill-to YYYY-MM` (acepta `--chunk-grain`).
- Bloque horario: `--hour-from "…" --hour-to "…"`

**Migraciones:** hace falta **116** (facts) y **117** (`ops.fn_real_trips_business_slice_resolved_subset` para auditorías; la carga mensual usa resolución inline desde temp table).

Tras migración **116**, hay que **poblar** `month_fact` (backfill o mes a mes); hasta entonces la vista `mv_real_business_slice_monthly` y la UI pueden mostrar conjunto vacío.

## Alcance explícito

- **No** incluye Plan, targets ni `plan_vs_real` (fuera de alcance).
- `ops.v_real_trips_business_slice_resolved` y `ops.v_real_trips_business_slice_resolved_mv12` siguen existiendo para **auditoría**, cobertura, unmatched/conflicts y carga horaria; la carga mensual **canónica** no depende de ellas.

## Entorno

- El venv del proyecto suele estar en **`backend\venv`**: activar desde la carpeta `backend`, no desde la raíz del repo.
- Pasar el mes en **una sola línea**: `--month 2026-03-01` (si PowerShell parte el comando en dos líneas, falla el parseo).

## Problemas frecuentes

| Síntoma | Acción |
|--------|--------|
| `relation "ops.real_business_slice_month_fact" does not exist` | En `backend`: `alembic upgrade head` (116+). |
| `fn_real_trips_business_slice_resolved_subset` no existe | `alembic upgrade head` (117). |
| `No space left on device` / `base/pgsql_tmp/...` | Los temporales suelen ir al disco del **data_directory** (p. ej. `/`), aunque tengas otro volumen montado. Liberar espacio en **ese** disco, o crear un **TABLESPACE** en el volumen grande y usar `BUSINESS_SLICE_LOAD_TEMP_TABLESPACES` (ver abajo). Mitigación adicional: `BUSINESS_SLICE_LOAD_WORK_MEM` (solo si hay RAM). |
| Carga "larga" sin salida / `connection already closed` | El script materializa enriched **una vez** (puede tardar minutos) con print de progreso. Después, cada chunk es rápido con `COMMIT` y print. Si falla, el mensaje indica **mes / país / ciudad / grano**. Reintente el mismo `--month`. |
| Reintentos con disco lleno | **No sirven** hasta liberar espacio en el volumen donde Postgres escribe temporales, o hasta desviar `temp_tablespaces`. Salida **3** del script `refresh_business_slice_mvs` = `DiskFull`. |

## Temporales en un segundo disco (TABLESPACE)

Ejemplo: `/` con ~53 GiB libres y `/mnt/HC_Volume_...` con ~177 GiB libres — sin configuración extra, Postgres **no** usa el segundo disco para `pgsql_tmp`.

1. En el servidor Linux (usuario root), directorio dedicado y permisos:

   ```bash
   install -d -o postgres -g postgres -m 700 /mnt/HC_Volume_105279775/pg_pg_temp
   ```

2. En PostgreSQL (superusuario):

   ```sql
   CREATE TABLESPACE pg_big_tmp OWNER postgres
   LOCATION '/mnt/HC_Volume_105279775/pg_pg_temp';
   ```

3. Opcional global: `temp_tablespaces = 'pg_big_tmp'` en `postgresql.conf`, o solo en la sesión de carga desde el cliente:

   ```powershell
   $env:BUSINESS_SLICE_LOAD_TEMP_TABLESPACES='pg_big_tmp'
   python -m scripts.refresh_business_slice_mvs --month 2026-03 --chunk-grain city
   ```

## Validación estática del loader

```text
python -m scripts.validate_business_slice_refresh --check-loader-contract
```

Comprueba que el SQL del camino mensual usa el temp table `_bs_enriched_month` (resolución inline) y no referencia la vista `v_real_trips_business_slice_resolved` ni la función `fn_real_trips_business_slice_resolved_subset` en ese tramo. El bloque horario sigue usando la vista acotada por rango.
