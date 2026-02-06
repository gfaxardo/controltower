-- PASO 3B E2E: MV agregación REAL por tipo_servicio (evitar timeouts)
-- Regla madre: LOB REAL = tipo_servicio. country/city desde dim_park, fecha desde fecha_inicio_viaje.

DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_tipo_servicio_universe_fast;

CREATE MATERIALIZED VIEW ops.mv_real_tipo_servicio_universe_fast AS
SELECT
  COALESCE(d.country, '') AS country,
  COALESCE(d.city, '') AS city,
  TRIM(LOWER(COALESCE(t.tipo_servicio, ''))) AS real_tipo_servicio,
  COUNT(*) AS trips_count,
  MIN(t.fecha_inicio_viaje::DATE) AS first_seen_date,
  MAX(t.fecha_inicio_viaje::DATE) AS last_seen_date
FROM public.trips_all t
LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
WHERE t.tipo_servicio IS NOT NULL
  AND t.condicion = 'Completado'
GROUP BY COALESCE(d.country, ''), COALESCE(d.city, ''), TRIM(LOWER(COALESCE(t.tipo_servicio, '')));

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_real_lob_fast_unique
  ON ops.mv_real_tipo_servicio_universe_fast (country, city, real_tipo_servicio);

CREATE INDEX IF NOT EXISTS ix_mv_real_lob_fast_ccs
  ON ops.mv_real_tipo_servicio_universe_fast (country, city, real_tipo_servicio);

CREATE INDEX IF NOT EXISTS ix_mv_real_lob_fast_trips
  ON ops.mv_real_tipo_servicio_universe_fast (trips_count DESC);

-- Refresh (ejecutar cuando se actualice trips_all):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_tipo_servicio_universe_fast;

-- Si la creación de la MV tarda demasiado, crear índice en trips_all antes de recrear:
-- CREATE INDEX IF NOT EXISTS ix_trips_all_lob_group
--   ON public.trips_all (park_id, tipo_servicio, (fecha_inicio_viaje::DATE))
--   WHERE condicion = 'Completado' AND tipo_servicio IS NOT NULL;
