# Mapa de dependencias — Hourly-first vs Legacy

## Cadena oficial (hourly-first)

```
FACT (ops.v_real_trip_fact_v2 ← ops.v_trips_real_canon_120d)
  ↓
ops.mv_real_lob_hour_v2
  ↓
ops.mv_real_lob_day_v2
  ↓
ops.mv_real_lob_week_v3   (lee de hourly)
ops.mv_real_lob_month_v3  (lee de hourly)
```

## Consumidores de la cadena oficial

| Consumidor | Objeto que lee | Tipo |
|------------|----------------|------|
| real_operational_service | mv_real_lob_day_v2, mv_real_lob_hour_v2 | Backend |
| real_operational_comparatives_service | mv_real_lob_day_v2, mv_real_lob_hour_v2 | Backend |
| RealOperationalView (UI) | API /ops/real-operational/* | Frontend |
| data_freshness_expectations (real_operational) | mv_real_lob_day_v2 (trip_date) | Auditoría |
| bootstrap_hourly_first.py | hour_v2 → day_v2 → week_v3 → month_v3 | Script |
| governance_hourly_first.py | hour_v2, day_v2, week_v3, month_v3 | Script |
| audit_real_aggregation_consistency.py | hour_v2, day_v2, week_v3 | Script |

## real_lob / real_lob_drill (unificados con hourly-first)

Tras la fase CT-HOURLY-FIRST-FINAL-UNIFICATION:

| Objeto | Fuente actual | Usado por |
|--------|----------------|-----------|
| ops.real_rollup_day_fact | **Vista** sobre ops.v_real_rollup_day_from_day_v2 (agregado de mv_real_lob_day_v2) | real_lob_daily_service, comparative_metrics_service, v_real_data_coverage, real_lob_drill_pro_service (coverage) |
| ops.v_real_rollup_day_from_day_v2 | Agregado de mv_real_lob_day_v2 al grano (trip_day, country, city, park_id, lob_group, segment_tag) | real_rollup_day_fact (vista) |
| ops.real_drill_dim_fact | **Tabla** poblada desde mv_real_lob_day_v2 (day) y mv_real_lob_week_v3 (week) por scripts.populate_real_drill_from_hourly_chain | mv_real_drill_dim_agg (vista), real_lob_drill_pro_service, real_lob_filters_service (parks), get_drill_parks |
| ops.mv_real_rollup_day | Vista sobre real_rollup_day_fact | 064 compatibilidad |
| ops.mv_real_drill_dim_agg | Vista SELECT * FROM real_drill_dim_fact | real_lob_drill_pro_service (drill principal) |
| ops.v_real_data_coverage | real_rollup_day_fact (MIN/MAX trip_day) | real_lob_drill_pro_service |

Freshness: real_lob → derived = real_rollup_day_fact (vista → day_v2). real_lob_drill → derived = real_drill_dim_fact (poblado desde day_v2/week_v3).

## Objetos legacy (fuera del camino principal)

| Objeto / script | Rol |
|-----------------|-----|
| scripts.backfill_real_lob_mvs | **Deprecated** para camino principal. Ya no se ejecuta en run_pipeline_refresh_and_audit. Queda para compatibilidad/recuperación si se revierte migración 101. |

### driver_lifecycle (DERIVED_STALE)

| Objeto | Fuente actual | Usado por |
|--------|----------------|-----------|
| ops.v_driver_lifecycle_trips_completed | trips_unified (trips_all + trips_2026) | mv_driver_lifecycle_base |
| ops.mv_driver_lifecycle_base | v_driver_lifecycle_trips_completed | mv_driver_weekly_stats, driver_lifecycle_service, freshness (driver_lifecycle) |
| ops.mv_driver_weekly_stats | mv_driver_lifecycle_base | driver_lifecycle_service, supply, freshness (driver_lifecycle_weekly) |

Pipeline propio: run_driver_lifecycle_build / ops.refresh_driver_lifecycle_mvs(). No deriva de la cadena REAL hourly-first.

### trips_base (SOURCE_STALE)

| Objeto | Rol |
|--------|-----|
| public.trips_all | Tabla histórica; corte &lt; 2026-01-01. Fuente junto con trips_2026 para v_trips_real_canon y v_trips_real_canon_120d. |
| data_freshness_expectations (trips_base) | Expectativa: source = trips_all, sin derived. Marcada legacy en 074. |

trips_2026 es la fuente viva (>= 2026). trips_all deja de recibir datos recientes → SOURCE_STALE esperado si no se backfillea.

## Endpoints y servicios por fuente

### Solo cadena hourly-first (day_v2 / hour_v2)

- GET /ops/real-operational/snapshot
- GET /ops/real-operational/day-view
- GET /ops/real-operational/hourly-view
- GET /ops/real-operational/cancellations
- GET /ops/real-operational/comparatives/*

### REAL LOB / drill (ahora desde cadena hourly-first)

- comparative_metrics_service (real_rollup_day_fact = vista desde day_v2)
- real_lob_daily_service (real_rollup_day_fact)
- real_lob_drill_pro_service (mv_real_drill_dim_agg, v_real_data_coverage, real_drill_dim_fact para parks; drill poblado desde day_v2/week_v3)
- GET /ops/real-lob/drill, /drill/children, /drill/parks
- real_lob_filters_service (fallback parks desde real_drill_dim_fact)

### Driver lifecycle (fuente propia)

- driver_lifecycle_service (mv_driver_lifecycle_base, mv_driver_weekly_stats)
- UI Ciclo de vida
- supply_weekly (mv_driver_weekly_stats → mv_supply_segments_weekly)

## Pipelines de refresh actuales

| Pipeline | Orden | Incluye hourly-first |
|----------|-------|------------------------|
| run_pipeline_refresh_and_audit | hourly-first chain → **populate_real_drill_from_hourly_chain** → refresh driver lifecycle → supply → audit | Sí |
| bootstrap_hourly_first.py | hour_v2 (staging) → day_v2 → week_v3 → month_v3 | Sí |
| populate_real_drill_from_hourly_chain | Pobla real_drill_dim_fact desde day_v2 (day) y week_v3 (week) | Sí (post hourly-first) |
| backfill_real_lob_mvs | **Deprecated** camino principal. Inserta en real_drill_dim_fact y real_rollup_day_fact desde v_trips_real_canon (legacy) | No |
| refresh_driver_lifecycle_mvs | mv_driver_lifecycle_base, mv_driver_weekly_stats, kpis | No |

## Resumen

- **Una sola columna vertebral REAL**: FACT → hourly → day → week → month. real_rollup_day_fact es vista desde day_v2; real_drill_dim_fact se puebla desde day_v2/week_v3. No hay dualidad de fuentes para el universo REAL activo.
- **Driver lifecycle**: Cadena separada (trips_unified → mv_driver_lifecycle_base → mv_driver_weekly_stats); no se deriva de hourly-first.
- **trips_base**: Fuente histórica; SOURCE_STALE esperado; política en source_dataset_policy.md.
