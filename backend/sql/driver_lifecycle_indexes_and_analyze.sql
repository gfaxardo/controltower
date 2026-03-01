-- =============================================================================
-- DRIVER LIFECYCLE — FASE 4: Índices y ANALYZE (solo columnas reales)
--
-- 0) Obtener viewdef real de la MV base (ejecutar para inspección):
--    SELECT pg_get_viewdef('ops.mv_driver_lifecycle_base'::regclass, true);
--    La definición usa v_driver_lifecycle_trips_completed, que lee de trips_all:
--    conductor_id, condicion, fecha_inicio_viaje, fecha_finalizacion, park_id, tipo_servicio, pago_corporativo
-- =============================================================================

-- 1) Índice para agregación por conductor_id (MIN/MAX completion_ts)
--    completion_ts = COALESCE(fecha_finalizacion, fecha_inicio_viaje)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_all_conductor_completion
  ON public.trips_all (conductor_id, (COALESCE(fecha_finalizacion, fecha_inicio_viaje)))
  WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL;

-- 2) Índice para filtro condicion y orden por tiempo (scans por semana/mes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_all_condicion_fecha
  ON public.trips_all (condicion, fecha_inicio_viaje)
  WHERE condicion = 'Completado' AND conductor_id IS NOT NULL;

-- 3) Índice para driver_week_park (conductor_id, week, park_id) en hardening v2
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_all_conductor_week_park
  ON public.trips_all (
    conductor_id,
    (DATE_TRUNC('week', COALESCE(fecha_finalizacion, fecha_inicio_viaje))::date),
    park_id
  )
  WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL;

-- 4) ANALYZE
ANALYZE public.trips_all;
ANALYZE public.drivers;
