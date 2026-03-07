# Diagnóstico: corrección estructural migraciones 068 y 069

## Cadena Alembic (confirmada)

| Revisión | Nombre | Descripción |
|----------|--------|-------------|
| 066 | 066_supply_refresh_log | Crea `ops.supply_refresh_log` |
| 066b | 066b_alembic_version_col | Amplía `alembic_version.version_num` a VARCHAR(64) |
| 067 | 067_mv_driver_segments_weekly_join_config | Recrea MVs de driver segments |
| 068 | 068_real_drill_service_by_park_mv | Creaba MV + ETL pesado (staging, loop por semana, INSERT desde v_trips_real_canon) |
| 069 | 069_real_drill_service_type_tipo_norm | ETL pesado (staging, loop, DELETE + INSERT en real_drill_dim_fact con tipo_servicio_norm) |

Cadena: **066 → 066b → 067 → 068 → 069**. No hay down_revision incorrectos. 066b se introdujo para permitir nombres de revisión largos (067 tiene 36 caracteres).

---

## Qué hacía exactamente 068

- **DDL:** Creaba tabla staging `ops._staging_mv_real_drill_service_by_park`, luego DROP MATERIALIZED VIEW existente, CREATE MATERIALIZED VIEW `ops.mv_real_drill_service_by_park` desde staging, índices únicos y de lookup, DROP staging.
- **ETL (mal ubicado):** Loop por semanas (ventana 90 días). Por cada semana ejecutaba INSERT masivo desde `ops.v_trips_real_canon` (JOIN parks, dim_city_country, park_country_fallback; CTEs with_city, with_country, enriched, agg_month, agg_week) hacia la tabla staging. Incluía workarounds: `threading`, `th.join(timeout=...)`, `SET LOCAL statement_timeout`, `print(..., flush=True)`.
- **Objeto final:** `ops.mv_real_drill_service_by_park` (materialized view). Consumido por `real_lob_drill_pro_service.py` cuando desglose=SERVICE_TYPE y hay park_id. Listado en `safe_refresh_real_lob.py` para REFRESH.

---

## Qué hacía exactamente 069

- **DDL:** Creaba tabla staging `ops._staging_069_service_type`.
- **ETL (mal ubicado):** Loop por semanas; por cada semana INSERT desde `v_trips_real_canon` (base, with_city, with_country, enriched, service_agg con tipo_servicio_norm) hacia staging. Luego DELETE FROM real_drill_dim_fact WHERE breakdown = 'service_type' e INSERT desde staging. Usaba `SET LOCAL statement_timeout` y prints.
- **Objetivo funcional:** Que el desglose por tipo de servicio use el valor real (tipo_servicio_norm) en lugar de colapsar a "unknown" (service_type_norm). La tabla `real_drill_dim_fact` ya existe en 064; `mv_real_drill_dim_agg` es vista sobre ella.

---

## Por qué estaban mal ubicadas en Alembic

- Alembic debe usarse para **DDL** (crear/alterar estructura). El procesamiento masivo sobre vistas pesadas (v_trips_real_canon) es **ETL** y provoca:
  - Queries que tardan demasiado o no terminan
  - Timeouts inconsistentes
  - Procesos congelados y Ctrl+C sin respuesta
  - Imposibilidad de saber si avanza
- Los workarounds (hilos, timers, statement_timeout) no resuelven la causa: ETL no debe vivir dentro de migraciones.

---

## Objetos creados vs datos cargados

| Objeto | Creado en | Datos cargados en (antes) | Datos cargados en (después) |
|--------|-----------|---------------------------|-----------------------------|
| ops.mv_real_drill_service_by_park | 068 | 068 (INSERT en staging → MV) | Script backfill_real_drill_service_by_park.py → tabla real_drill_service_by_park; vista MV apunta a tabla |
| ops.real_drill_dim_fact (filas service_type) | 064 | 069 (DELETE + INSERT) | backfill_real_drill_service_type.py o backfill_real_lob_mvs.py |

---

## DDL vs ETL

- **DDL (en Alembic):** Crear tabla `ops.real_drill_service_by_park`, índices, vista `ops.mv_real_drill_service_by_park`. 069 no crea estructura nueva; real_drill_dim_fact ya tiene dimension_key.
- **ETL (en scripts):** Leer desde v_trips_real_canon, normalizar ciudad/país/tipo_servicio, agregar por periodo y dimensiones, escribir en tabla o en real_drill_dim_fact por chunks, con progreso y reemplazo no destructivo.

---

## Dependencias

- **Consumidores de mv_real_drill_service_by_park:** `backend/app/services/real_lob_drill_pro_service.py` (get_drill_children cuando desglose=SERVICE_TYPE y park_id indicado).
- **Consumidores de real_drill_dim_fact / mv_real_drill_dim_agg:** real_lob_drill_pro_service (drill principal y children para LOB/PARK/SERVICE_TYPE sin park), real_lob_filters_service (fallback parks), frontend RealLOBDrillView, api.js.
- **v_trips_real_canon:** Vista (064) sobre trips_all + trips_2026; usada por backfill y por lógica de drill en 064/backfill.

---

## Riesgos al modificar

- Romper contrato: el nombre `ops.mv_real_drill_service_by_park` y el esquema (columnas) deben mantenerse para no romper el servicio de drill. Se mantiene como vista sobre la nueva tabla.
- safe_refresh_real_lob ya no puede hacer REFRESH sobre este objeto (pasa a ser vista sobre tabla); el llenado se hace con el script de backfill (documentado en runbook).

---

## Estrategia aplicada

1. **068:** Solo DDL. Crear tabla `ops.real_drill_service_by_park` (mismo esquema que la MV) y vista `ops.mv_real_drill_service_by_park AS SELECT * FROM ops.real_drill_service_by_park`. Sin INSERT, sin loops, sin threads/timeouts.
2. **069:** Solo DDL. Migración no-op o mínima; el cambio de dato (tipo_servicio_norm) se hace vía backfill/script.
3. **Backfill:** Script `backfill_real_drill_service_by_park.py` para llenar la tabla; script `backfill_real_drill_service_type.py` (o uso de backfill_real_lob_mvs) para filas service_type con tipo real.
4. **safe_refresh_real_lob:** Quitar ops.mv_real_drill_service_by_park de la lista de REFRESH; documentar en runbook.

---

## Workarounds eliminados

- **068:** threading, threading.Event, th.join(timeout=...), SET LOCAL statement_timeout en SQL, print(..., flush=True), loop por semanas con INSERT desde canon, creación de staging dentro de la migración.
- **069:** SET LOCAL statement_timeout, loop por semanas, staging, DELETE + INSERT dentro de la migración, print(..., flush=True).
