# Autodiagnóstico y Auto-fix Real LOB Drill

Script para detectar columnas variables en `trips_all` y aplicar fix a las vistas de drill.

## Uso

```bash
cd backend

# Solo diagnóstico (no modifica DB)
python -m scripts.diagnose_and_fix_real_drill --diagnose-only

# Generar SQL sin aplicar
python -m scripts.diagnose_and_fix_real_drill --no-apply --output-sql exports/fix_real_drill_views.sql

# Aplicar fix (diagnóstico + fix + validación)
python -m scripts.diagnose_and_fix_real_drill
```

## Mapeo de columnas (auto-detectado)

| Canon | Candidatos |
|-------|------------|
| ts_col | trip_ts, fecha_inicio_viaje, start_time, created_at, pickup_datetime |
| country_col | country, pais, country_code |
| city_col | city, ciudad, city_name |
| park_id_col | park_id, id_park, park, parkid |
| park_name_col | park_name, nombre_park, park |
| tipo_servicio_col | tipo_servicio, real_tipo_servicio, service_type, service_class |
| b2b_col | pago_corporativo, corporate_payment, is_corporate, corporativo |
| margin_col | comision_empresa_asociada, commission_partner, partner_commission |
| dist_m_col | distancia_km, distance_meters, distance, trip_distance_m |

## Vistas creadas/reemplazadas (diagnose fix)

- `ops.v_real_trips_base_drill` — Base con park_name_resolved, park_bucket, lob_group, segment_tag
- `ops.v_real_data_coverage` — last_trip_date, min_month, last_week_with_data por país
- `ops.v_real_drill_country_month` / `_week` — Calendario completo, estado CERRADO/ABIERTO/FALTA_DATA/VACIO
- `ops.v_real_drill_lob_month` / `_week` — Drill por LOB
- `ops.v_real_drill_park_month` / `_week` — Drill por park con park_bucket

**Nota**: La migración 051 reemplaza estas vistas por versiones MV-based (`ops.mv_real_rollup_day`). Tras `alembic upgrade head`, los endpoints usan la MV (más rápido).

## Validación post-fix

- El script aplica `SET LOCAL statement_timeout = '120s'` solo a las validaciones.
- Las validaciones A–E usan la MV o vistas drill (rápidas), sin fullscan de `trips_all`.
- A) null park_name_resolved: desde MV con LIMIT
- B) bucket CO: desde MV, últimos 30 días
- C) summary max period: v_real_drill_country_month
- D) estado FALTA_DATA: v_real_drill_country_month
- E) drill park CO: v_real_drill_park_month con LIMIT 50

## Checklist validación (manual)

Ejecutar `backend/scripts/validate_real_drill_post_fix.sql` en psql/pgAdmin.

## Refresh MV (recomendado diario)

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_rollup_day;
```

O vía API: `POST /ops/real-drill/refresh`
