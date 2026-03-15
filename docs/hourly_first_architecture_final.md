# Arquitectura oficial — Hourly-first (columna vertebral)

## Regla única

Toda la analítica y operativa REAL debe derivar de una sola cadena:

```
FACT CANÓNICA (ops.v_real_trip_fact_v2)
        ↓
ops.mv_real_lob_hour_v2
        ↓
ops.mv_real_lob_day_v2
        ↓
ops.mv_real_lob_week_v3
ops.mv_real_lob_month_v3
```

## Reglas obligatorias

1. **Ninguna capa puede derivar directamente de FACT salvo hourly.**  
   day, week y month se construyen desde hourly (o desde day para week/month si se define así; en 099 week y month leen de hourly).

2. **day debe derivar exclusivamente de hourly.**  
   mv_real_lob_day_v2 = agregado de mv_real_lob_hour_v2 por (trip_date, country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, trip_outcome_norm, cancel_reason_*).

3. **week y month deben derivar de hourly (o de day).**  
   En 099: week_v3 y month_v3 leen de hourly. Alternativa válida: que lean de day_v2 para reducir coste.

4. **Cualquier vista o tabla que rompa esta cadena** (por ejemplo, leer de v_trips_real_canon o fact para agregados día/semana/mes) debe:
   - corregirse para que derive de hourly o day, o
   - marcarse como legacy y dejar de usarse en el camino principal.

## Objetos oficiales

| Capa | Objeto | Granularidad |
|------|--------|--------------|
| FACT | ops.v_real_trip_fact_v2 | 1 fila por viaje |
| Hourly | ops.mv_real_lob_hour_v2 | (trip_date, trip_hour, country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, trip_outcome_norm, cancel_reason_norm, cancel_reason_group) |
| Day | ops.mv_real_lob_day_v2 | (trip_date, country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, trip_outcome_norm, cancel_reason_*) |
| Week | ops.mv_real_lob_week_v3 | (week_start, country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag) |
| Month | ops.mv_real_lob_month_v3 | (month_start, country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag) |

## Refresh

El orden de refresco debe ser:

1. FACT (vista; no se refresca, depende de ingestión).
2. REFRESH mv_real_lob_hour_v2 (desde fact; vía bootstrap o REFRESH MATERIALIZED VIEW).
3. REFRESH mv_real_lob_day_v2 (desde hourly).
4. REFRESH mv_real_lob_week_v3 (desde hourly).
5. REFRESH mv_real_lob_month_v3 (desde hourly).

No debe existir un refresh que construya week o month directamente desde fact sin pasar por hourly/day.

## Derivados desde la cadena (post unificación)

- **real_rollup_day_fact**: vista sobre agregado de mv_real_lob_day_v2 (v_real_rollup_day_from_day_v2). Migración 101.
- **real_drill_dim_fact**: tabla poblada por scripts.populate_real_drill_from_hourly_chain desde mv_real_lob_day_v2 (day) y mv_real_lob_week_v3 (week). No deriva de fact directo.

## Legacy

- **scripts.backfill_real_lob_mvs**: deprecated para camino principal; no se ejecuta en run_pipeline_refresh_and_audit. Pipeline driver_lifecycle sigue con fuente propia (trips_unified); no deriva de hourly-first por diseño.
