-- =============================================================================
-- DRIVER LIFECYCLE — Diagnóstico timeout / locks (ejecutar antes o durante refresh)
-- =============================================================================

-- 1) Timeouts y settings de sesión
SHOW statement_timeout;
SHOW lock_timeout;
SHOW maintenance_work_mem;

-- 2) Refresh en curso / consultas relacionadas
SELECT now() AS at_time,
       pid,
       usename,
       state,
       wait_event_type,
       wait_event,
       left(query, 120) AS query
FROM pg_stat_activity
WHERE query ILIKE '%REFRESH MATERIALIZED VIEW%'
  AND state <> 'idle';

-- 3) Locks bloqueados (quién bloquea a quién)
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       left(blocked_activity.query, 80) AS blocked_query,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       left(blocking_activity.query, 80) AS blocking_query,
       age(now(), blocking_activity.query_start) AS blocking_duration
FROM pg_locks blocked_locks
JOIN pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
 AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
 AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
 AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
 AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
 AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
 AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
 AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
 AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
 AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
 AND blocking_locks.pid != blocked_locks.pid
JOIN pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- 4) Resumen: ¿es timeout o lock? (interpretar según resultado)
-- Si (2) muestra REFRESH en state 'active' y wait_event_type = 'Lock' -> esperando lock.
-- Si la sesión desaparece tras un tiempo y el error es "statement timeout" -> timeout.

-- -----------------------------------------------------------------------------
-- ÍNDICES SUGERIDOS: SOLO tras confirmar columnas reales vía pg_get_viewdef
-- -----------------------------------------------------------------------------
-- Ejecutar primero para inspeccionar definición:
--   SELECT pg_get_viewdef('ops.mv_driver_lifecycle_base'::regclass, true);
--   SELECT pg_get_viewdef('ops.v_driver_lifecycle_trips_completed'::regclass, true);
-- Columnas reales en trips_all: conductor_id, condicion, fecha_inicio_viaje, fecha_finalizacion, park_id
-- Índices recomendados (driver_lifecycle_indexes_and_analyze.sql):
--   idx_trips_all_conductor_completion, idx_trips_all_condicion_fecha, idx_trips_all_conductor_week_park
-- Ejecutar CONCURRENTLY en ventana de bajo uso.
