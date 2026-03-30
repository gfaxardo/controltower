# BUSINESS_SLICE — Fase 1

## Rol

Capa ejecutiva de clasificación y agregación sobre **REAL** (PostgreSQL). No sustituye Real LOB ni mezcla Plan.

## Pipeline REAL (orden)

`trips_all` ∪ `trips_2026` (canon) → **`ops.v_real_trips_enriched_base`** (join `dim.dim_park` + `drivers`) → **`ops.v_real_trips_business_slice_base`** (alias `SELECT *` desde enriched) → **`ops.v_real_trips_business_slice_resolved`** (reglas; auditoría y vistas de cobertura) → **`ops.mv_real_business_slice_monthly`** (hoy: **vista** sobre **`ops.real_business_slice_month_fact`**, no MV refrescable).

**Carga mensual canónica (post-117):** `enriched` (subconjunto por mes / país / ciudad / subchunk temporal) → **`ops.fn_real_trips_business_slice_resolved_subset`** (misma lógica de reglas que la vista resolved, pero **filtrando la CTE `base` antes** de unir mapping) → agregación → **`ops.real_business_slice_month_fact`**. Así se evita el patrón costoso “materializar/evaluar `resolved` global y filtrar al final”.

La vista **`ops.v_real_trips_business_slice_resolved_mv12`** sigue siendo útil para auditoría en ventana 12m (misma lógica con base acotada). La vista global **`v_real_trips_business_slice_resolved`** permanece como referencia para unmatched/conflicts/coverage.

## Flujo operativo

1. Migraciones Alembic: **116** (`real_business_slice_month_fact` / `hour_fact` + vistas) y **117** (`ops.fn_real_trips_business_slice_resolved_subset` para carga mensual incremental).
2. Importar reglas: `python -m scripts.import_business_slice_mapping_from_xlsx --replace` (Excel en `backend/exports/Plantillas_Control_Tower_Simplificadas_final.xlsx`).
3. Poblar / actualizar agregado mensual: `python -m scripts.refresh_business_slice_mvs --month YYYY-MM` (opcional `--chunk-grain city|country|city_week|city_day`). Timeout de sesión largo en el script de carga.
4. Validación opcional: `python -m scripts.validate_business_slice_refresh` (tamaño `month_fact`, muestra `works_terms` vía `resolved_mv12` si no es `--light`). Contrato del loader: `--check-loader-contract`.

**Disco en el servidor PostgreSQL:** si la carga falla con `No space left on device` en `pgsql_tmp`, hay que **liberar espacio** en el volumen de datos/temp de Postgres; además usar chunks más finos (`city_week` / `city_day`) y/o más `work_mem` de sesión (`BUSINESS_SLICE_LOAD_WORK_MEM`).

Hasta poblar `month_fact`, la vista `mv_real_business_slice_monthly` puede devolver conjunto vacío.

## Métricas (MV mensual)

- **commission_pct**: `SUM(revenue_yego_net) / SUM(total_fare)` sobre viajes **completados** con `total_fare > 0` (mismo filtro en numerador y denominador). `total_fare` = efectivo + tarjeta + pago_corporativo. Si no hay base, **NULL** (no promedio de ratios).
- **connected_only_drivers**: columna numérica reservada (NULL); estado explícito en **`connected_only_drivers_status` = `'NOT_IMPLEMENTED'`**.

## Contrato futuro Plan vs Real

Clave documentada: `country + city + business_slice_name + month`. Vista stub: `ops.v_plan_business_slice_join_stub`. Endpoint: `GET /ops/business-slice/plan-join-stub`.

## Revenue / impuestos

`revenue_yego_net` en base = `comision_empresa_asociada` canónica (misma línea que el resto del Control Tower). Ajustes explícitos IGV/IVA no se aplican en esta fase si no hay columna bruta trazable.

## Auditoría

- `ops.v_business_slice_unmatched_trips`
- `ops.v_business_slice_conflict_trips`
- `ops.v_business_slice_coverage_month`

## API

Prefijo `GET /ops/business-slice/*`: `filters`, `monthly`, `coverage`, `unmatched`, `conflicts`, `subfleets`, `weekly`, `daily`, `plan-join-stub`.
