# BUSINESS_SLICE — Fase 1

## Rol

Capa ejecutiva de clasificación y agregación sobre **REAL** (PostgreSQL). No sustituye Real LOB ni mezcla Plan.

## Pipeline REAL (orden)

`trips_all` ∪ `trips_2026` (canon) → **`ops.v_real_trips_enriched_base`** (join `dim.dim_park` + `drivers`) → **`ops.v_real_trips_business_slice_base`** (alias `SELECT *` desde enriched) → **`ops.v_real_trips_business_slice_resolved`** (reglas) → **`ops.mv_real_business_slice_monthly`** (agregado; **ventana 36 meses** en el `REFRESH`).

La MV no vuelve a hacer joins raw: consume **`ops.v_real_trips_business_slice_resolved_mv12`** (misma lógica que `resolved`, con **base limitada a 12 meses** para reducir temporales en `REFRESH`). La vista **`v_real_trips_business_slice_resolved`** sigue siendo la referencia completa para auditoría/coverage.

## Flujo operativo

1. Migraciones Alembic: hasta **`115_business_slice_mv_feed_resolved_12m`** (ventana 12m + vista `v_real_trips_business_slice_resolved_mv12` que acota la CTE base antes de clasificar, para aliviar temporales en `REFRESH`).
2. Importar reglas: `python -m scripts.import_business_slice_mapping_from_xlsx --replace` (Excel en `backend/exports/Plantillas_Control_Tower_Simplificadas_final.xlsx`).
3. Refrescar agregado: `python -m scripts.refresh_business_slice_mvs` (timeout de sesión 2h; no ejecutar otro `REFRESH`/`DROP` concurrente sobre la misma MV).
4. Validación opcional: `python -m scripts.validate_business_slice_refresh` (tiempo de refresh, tamaño MV, muestra de `works_terms`). Con disco o temp limitado: `--skip-refresh --light`.

**Disco en el servidor PostgreSQL:** si `REFRESH` falla con `No space left on device`, hay que **liberar espacio** en el volumen de datos/temp de Postgres; no lo resuelve solo el código.

La MV se crea con `WITH NO DATA`; hasta hacer `REFRESH` los endpoints mensuales pueden devolver lista vacía.

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
