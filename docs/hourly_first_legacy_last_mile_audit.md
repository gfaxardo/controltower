# Auditoría última milla — real_rollup_day_fact y real_drill_dim_fact

## 1. ops.real_rollup_day_fact

### Esquema actual (064)
| Columna | Tipo | Notas |
|---------|------|-------|
| trip_day | date | NOT NULL |
| country | text | NOT NULL |
| city | text | |
| park_id | text | |
| park_name_resolved | text | |
| park_bucket | text | SIN_PARK, OK, etc. |
| lob_group | text | |
| segment_tag | text | B2B / B2C |
| trips | bigint | NOT NULL (solo completados en legacy) |
| b2b_trips | bigint | |
| margin_total_raw | numeric | |
| margin_total_pos | numeric | |
| margin_unit_pos | numeric | |
| distance_total_km | numeric | |
| km_prom | numeric | |
| last_trip_ts | timestamptz | |

**Granularidad**: (trip_day, country, city, park_id, lob_group, segment_tag).  
**UNIQUE**: (trip_day, country, COALESCE(city,''), COALESCE(park_id,''), lob_group, segment_tag).

### Consumidores
- **real_lob_drill_pro_service**: MAX(trip_day), MAX(last_trip_ts) por country para freshness y coverage.
- **real_lob_daily_service**: TABLE = real_rollup_day_fact (lecturas por trip_day, country, city, etc.).
- **comparative_metrics_service**: TABLE_DAY = real_rollup_day_fact (métricas comparativas).
- **v_real_data_coverage**: MIN/MAX trip_day por country (vista que lee de real_rollup_day_fact).
- **v_real_lob_coverage**: min_trip_date_loaded, max_trip_date_loaded desde real_rollup_day_fact.
- **v_trip_integrity, v_b2b_integrity** (075): comparan canonical vs real_rollup_day_fact.

### Scripts que pueblan
- **backfill_real_lob_mvs.py**: INSERT desde v_trips_real_canon (condicion = 'Completado') con JOIN parks y LOB mapping. ON CONFLICT DO UPDATE.

### Fuente natural en cadena nueva
**ops.mv_real_lob_day_v2**: misma granularidad lógica (trip_date, country, city, park_id, lob_group, segment_tag). day_v2 tiene más columnas (real_tipo_servicio_norm, trip_outcome_norm, cancel_reason_*, requested_trips, completed_trips, cancelled_trips). Para compatibilidad: agregar por (trip_date, country, city, park_id, park_name, lob_group, segment_tag) y mapear completed_trips → trips, segment_tag B2B → b2b_trips, margin_total → margin_total_raw/pos, etc.

---

## 2. ops.real_drill_dim_fact

### Esquema actual (064)
| Columna | Tipo | Notas |
|---------|------|-------|
| country | text | NOT NULL |
| period_grain | text | 'day' \| 'week' \| 'month' |
| period_start | date | NOT NULL |
| segment | text | NOT NULL (B2B/B2C) |
| breakdown | text | 'lob' \| 'park' \| 'service_type' |
| dimension_key | text | lob_group, park_name, o real_tipo_servicio_norm |
| dimension_id | text | park_id para breakdown=park |
| city | text | |
| trips | bigint | NOT NULL |
| margin_total | numeric | |
| margin_per_trip | numeric | |
| km_avg | numeric | |
| b2b_trips | bigint | |
| b2b_share | numeric | |
| last_trip_ts | timestamptz | |

**Granularidad**: (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city).  
**UNIQUE**: (country, period_grain, period_start, segment, breakdown, COALESCE(dimension_key,''), COALESCE(dimension_id,''), COALESCE(city,'')).

### Consumidores
- **real_lob_drill_pro_service**: MV_DIM = mv_real_drill_dim_agg (vista SELECT * FROM real_drill_dim_fact). Lecturas por country, period_type (month/week), breakdown (lob/park/service_type), segment. get_drill_parks lee real_drill_dim_fact con breakdown='park' (dimension_id AS park_id, dimension_key AS park_name).
- **real_lob_filters_service**: fallback de parks desde real_drill_dim_fact (breakdown=park).
- **v_observability_* (075)**: MAX(period_start), MAX(last_trip_ts) para status.

### Scripts que pueblan
- **backfill_real_lob_mvs.py**: INSERT desde v_trips_real_canon (enriched con parks, city, country, LOB, tipo_servicio_norm) agrupando por (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city). Incluye day, week, month y breakdown lob, park, service_type.

### Fuente natural en cadena nueva
- **Granularidad diaria**: **ops.mv_real_lob_day_v2**. Agregar por (country, trip_date, segment_tag, breakdown, dimension) → period_grain='day', period_start=trip_date.
- **Granularidad semanal**: **ops.mv_real_lob_week_v3**. Agregar por (country, week_start, segment_tag, breakdown, dimension) → period_grain='week', period_start=week_start.
- **Granularidad mensual**: **ops.mv_real_lob_month_v3** (o agregar week_v3 por mes). period_grain='month', period_start=month_start.

Métricas: trips = completed_trips (o requested_trips; legacy usaba count completados), margin_total, b2b_trips = SUM(completed donde segment=B2B), b2b_share = b2b_trips/trips, km_avg, last_trip_ts = MAX(max_trip_ts).
