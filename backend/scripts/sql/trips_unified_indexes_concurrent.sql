-- Índices para trips_all y trips_2026 (fuente de public.trips_unified).
-- Ejecutar FUERA de transacción, con statement_timeout alto (ej. 1h).
-- Ejemplo: psql ... -v statement_timeout=3600000 -f trips_unified_indexes_concurrent.sql
-- O en psql: SET statement_timeout = '1h'; luego ejecutar cada bloque.

-- trips_all (tabla grande: puede tardar varios minutos)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_fecha_inicio
ON public.trips_all (fecha_inicio_viaje);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_condicion_fecha
ON public.trips_all (condicion, fecha_inicio_viaje)
WHERE condicion = 'Completado';

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_park_fecha
ON public.trips_all (park_id, fecha_inicio_viaje);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_all_conductor_fecha
ON public.trips_all (conductor_id, fecha_inicio_viaje);

-- trips_2026 (solo si existe la tabla)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_fecha_inicio
ON public.trips_2026 (fecha_inicio_viaje);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_condicion_fecha
ON public.trips_2026 (condicion, fecha_inicio_viaje)
WHERE condicion = 'Completado';

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_park_fecha
ON public.trips_2026 (park_id, fecha_inicio_viaje);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_trips_2026_conductor_fecha
ON public.trips_2026 (conductor_id, fecha_inicio_viaje);
