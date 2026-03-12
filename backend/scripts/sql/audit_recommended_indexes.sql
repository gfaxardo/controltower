-- Índices recomendados para el Audit Engine (FASE 6).
-- Reducen tiempo de v_trip_integrity, v_lob_mapping_audit, v_weekly_trip_volume, v_join_integrity.
-- Ejecutar con permisos adecuados (CONCURRENTLY requiere no estar en transacción de escritura).
-- Ajustar si ya existen índices con estos nombres.

-- trips_all: filtros por condicion y fecha (v_trips_real_canon → v_trip_integrity, v_weekly_trip_volume)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_condicion_fecha
ON public.trips_all (condicion, fecha_inicio_viaje)
WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_fecha_inicio
ON public.trips_all (fecha_inicio_viaje)
WHERE fecha_inicio_viaje IS NOT NULL;

-- trips_2026 (si existe)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_condicion_fecha
ON public.trips_2026 (condicion, fecha_inicio_viaje)
WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL;

-- real_rollup_day_fact: agregaciones por mes (v_trip_integrity, v_b2b_integrity)
CREATE INDEX IF NOT EXISTS ix_real_rollup_day_fact_trip_day
ON ops.real_rollup_day_fact (trip_day);
