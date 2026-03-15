# Estrategia para datasets DERIVED_STALE (hourly-first closure)

## Objetivo

Hacer que real_lob, real_lob_drill, driver_lifecycle y driver_lifecycle_weekly dejen de ser DERIVED_STALE alineándolos con la cadena hourly-first o con pipelines refrescados en el orden correcto.

## real_lob (real_rollup_day_fact) — cerrado

- **Implementado**: real_rollup_day_fact es **vista** sobre v_real_rollup_day_from_day_v2 (agregado de mv_real_lob_day_v2). Migración 101. No hay backfill; max(derived) == max(day_v2) por definición.

## real_lob_drill (real_drill_dim_fact) — cerrado

- **Implementado**: real_drill_dim_fact se puebla desde **mv_real_lob_day_v2** (period_grain=day) y **mv_real_lob_week_v3** (period_grain=week) mediante **scripts.populate_real_drill_from_hourly_chain**. Se ejecuta tras refresh de la cadena hourly-first en run_pipeline_refresh_and_audit. backfill_real_lob_mvs ya no forma parte del camino principal (deprecated).

## driver_lifecycle / driver_lifecycle_weekly

- **Fuente actual**: v_driver_lifecycle_trips_completed (trips_unified) → mv_driver_lifecycle_base → mv_driver_weekly_stats. Pipeline propio (refresh_driver_lifecycle_mvs).
- **Objetivo**: No derivan de la cadena REAL hourly-first; son un dominio distinto (conductores, no viajes por LOB). El DERIVED_STALE se resuelve asegurando que el refresh driver se ejecute con frecuencia y que trips_unified tenga datos recientes (trips_2026).
- **Acción**: Mantener pipeline driver; incluir en run_pipeline_refresh_and_audit después de hourly-first y backfill REAL. No reescribir driver_lifecycle para que lea de hourly (no es la misma semántica).

## Validación

- Tras cualquier cambio: `max(source) == max(derived)` para cada dataset.
- Ejecutar `run_data_freshness_audit` y comprobar que real_operational, real_lob, real_lob_drill pasen a OK cuando sus fuentes y refrescos estén al día.
