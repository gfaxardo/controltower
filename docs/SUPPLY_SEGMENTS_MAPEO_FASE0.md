# FASE 0 — Mapeo columnas ops.mv_driver_weekly_stats

Inspección sobre la definición en `backend/sql/driver_lifecycle_build.sql` y uso en Supply.

## Columnas reales (mv_driver_weekly_stats)

| Columna espec | Nombre real | Tipo / notas |
|---------------|-------------|--------------|
| driver_key | `driver_key` | conductor_id en origen |
| week_start | `week_start` | date (lunes, DATE_TRUNC('week', completion_ts)::date) |
| park_id | `park_id` | text (en build = park_id_mode, MIN(park_id) por driver+week) |
| trips_completed_week | `trips_completed_week` | bigint (COUNT(*) por conductor_id, week_start) |
| active_days_week | **no existe** | — |
| last_completed_ts | **no existe** (está en mv_driver_lifecycle_base) | — |

Otras columnas presentes (no usadas para segmentación PRO):  
`work_mode_week` (FT/PT por >=20), `tipo_servicio`, `segment` (b2b/b2c), `is_active_week`.

## Uso en motor PRO

- **Segmento semanal**: se calcula desde `trips_completed_week` con umbrales FT≥60, PT 20–59, CASUAL 5–19, OCCASIONAL 1–4, DORMANT 0.
- **Dominant park**: se usa `park_id` de la fila (una fila por driver_key, week_start en la fuente).
- **DORMANT**: la MV solo contiene filas con al menos 1 viaje; los drivers con 0 viajes en la semana no tienen fila. El agregado por segmento (mv_supply_segments_weekly) incluye solo segmentos con datos (FT/PT/CASUAL/OCCASIONAL). Anomalías y alertas se calculan sobre esos segmentos; DORMANT puede añadirse en el futuro vía universo de drivers si se requiere.

## Índices existentes

- `ux_mv_driver_weekly_stats_driver_week` UNIQUE (driver_key, week_start)

---

## Refresh de MVs de Supply Alerting

Después de aplicar la migración `063_supply_segments_alerts_weekly`:

```sql
SELECT ops.refresh_supply_alerting_mvs();
```

Refresca CONCURRENTLY: `mv_driver_segments_weekly`, `mv_supply_segments_weekly`, `mv_supply_segment_anomalies_weekly`, `mv_supply_alerts_weekly`.
