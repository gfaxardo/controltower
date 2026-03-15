# Real LOB — Cierre final (hourly-first)

## Objetivo

Que todo el universo REAL activo (Operacional, LOB, drill, comparativos, freshness) derive de una sola columna vertebral: FACT → hour_v2 → day_v2 → week_v3/month_v3, sin depender de backfill desde fact directo.

## Cambios realizados

### real_rollup_day_fact

- **Antes**: Tabla física poblada por backfill_real_lob_mvs desde v_trips_real_canon.
- **Después**: Vista que hace `SELECT * FROM ops.v_real_rollup_day_from_day_v2`, donde v_real_rollup_day_from_day_v2 es un agregado de **ops.mv_real_lob_day_v2** al grano (trip_day, country, city, park_id, lob_group, segment_tag) con mapeo de columnas (completed_trips→trips, margin_total→margin_total_raw/pos, etc.).
- **Migración**: 101_real_rollup_from_day_v2.py (elimina tabla, crea vista; recrea mv_real_rollup_day, v_real_data_coverage, v_real_lob_coverage).

### real_drill_dim_fact

- **Antes**: Tabla poblada por backfill_real_lob_mvs desde v_trips_real_canon (day/week/month, breakdown lob/park/service_type).
- **Después**: Tabla poblada por **scripts.populate_real_drill_from_hourly_chain** desde:
  - **mv_real_lob_day_v2** para period_grain='day' (ventana configurable, default 120 días),
  - **mv_real_lob_week_v3** para period_grain='week' (ventana default 18 semanas).
- Breakdowns: lob, park, service_type. Métricas: trips, margin_total, margin_per_trip, km_avg, b2b_trips, b2b_share, last_trip_ts.
- **Granularidad month**: No repoblada en el script actual; puede añadirse desde mv_real_lob_month_v3 si se requiere.

### Pipeline principal

- **run_pipeline_refresh_and_audit**:
  1. Refresh cadena hourly-first (hour_v2 → day_v2 → week_v3 → month_v3).
  2. Poblar real_drill_dim_fact desde day_v2/week_v3 (populate_real_drill_from_hourly_chain). real_rollup_day_fact no requiere paso (es vista).
  3. Refresh driver lifecycle.
  4. Refresh supply.
  5. Audit freshness.

- **backfill_real_lob_mvs**: Ya no se ejecuta en el pipeline. Marcado deprecated; queda para legacy/recuperación.

## Consumidores (sin cambios de contrato)

- real_lob_daily_service, comparative_metrics_service, v_real_data_coverage, real_lob_drill_pro_service (coverage): siguen leyendo real_rollup_day_fact (ahora vista sobre day_v2).
- real_lob_drill_pro_service, real_lob_filters_service, get_drill_parks: siguen leyendo real_drill_dim_fact (ahora poblada desde day_v2/week_v3).
- No se modifican endpoints ni contratos API; la UI REAL sigue funcionando igual.

## Freshness y consistencia

- real_lob: derived = real_rollup_day_fact (vista) → source efectivo = day_v2. OK cuando day_v2 esté refrescado.
- real_lob_drill: derived = real_drill_dim_fact → source = day_v2/week_v3. OK cuando el populate se ejecute tras el refresh.
- Auditoría de consistencia: SUM(hourly)==SUM(day), SUM(day)==SUM(week), etc. (audit_hourly_chain_consistency).

## Documentación relacionada

- docs/hourly_first_legacy_last_mile_audit.md — Auditoría detallada rollup y drill.
- docs/hourly_first_dependency_map.md — Mapa de dependencias actualizado.
- docs/hourly_first_architecture_final.md — Reglas de la columna vertebral.
- docs/CT-HOURLY-FIRST-CLOSURE-SALIDA.md — Salida de la fase y secciones A–I.
