/*
 * FASE 2B — Operational Behavioral Intelligence: SQL Facts
 * Crea capas operacionales para inteligencia de comportamiento.
 * Fuentes: ops.v_real_trips_enriched_base, ops.driver_daily_activity_fact, public.trips_2026
 *
 * Objetos creados:
 *   1. ops.driver_trip_behavior_fact  (VIEW)      — driver + trip grain
 *   2. ops.driver_session_fact        (MVIEW)     — session grain (gap > 90 min)
 *   3. ops.driver_zone_behavior_fact  (VIEW)      — driver + zone + date grain
 *
 * Reglas:
 *   - Todo determinístico.
 *   - Columnas inexistentes devuelven NULL con alias documentado.
 *   - No inventar datos.
 *   - Indexes optimizados para queries del servicio.
 */

BEGIN;

-- ═══════════════════════════════════════════════════════════════════
-- 1. ops.driver_trip_behavior_fact (VIEW)
-- Grano: driver + trip
-- Envuelve v_real_trips_enriched_base añadiendo columnas derivadas.
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW ops.driver_trip_behavior_fact AS
SELECT
    driver_id,
    trip_date,
    EXTRACT(HOUR FROM trip_hour_start)::int AS trip_hour,
    EXTRACT(DOW FROM trip_date)::int AS day_of_week,  -- 0=Sun .. 6=Sat
    country,
    city,
    park_id,
    CASE WHEN completed_flag THEN 1 ELSE 0 END AS completed_trips,
    CASE WHEN cancelled_flag THEN 1 ELSE 0 END AS cancelled_trips,
    revenue_yego_net::numeric AS revenue,
    km::numeric AS distance_km,
    duration_minutes::numeric AS duration_min,
    gmv_passenger_paid::numeric AS gmv,
    ticket::numeric AS ticket,
    park_id AS origin_zone,          -- proxy: park_id es nuestra mejor aproximación a zona
    NULL::text AS destination_zone,  -- NO disponible en datos fuente
    tipo_servicio AS lob,            -- proxy: tipo_servicio como línea de negocio
    NULL::numeric AS surge,          -- NO disponible
    NULL::numeric AS idle_before_trip_min, -- NO disponible (se calcula en session_fact)
    condicion AS trip_status,
    trip_hour_start,
    source_table
FROM ops.v_real_trips_enriched_base;

COMMENT ON VIEW ops.driver_trip_behavior_fact IS
'Fase 2B: Vista operacional a nivel driver+trip. Basada en ops.v_real_trips_enriched_base.
Columnas NO disponibles: destination_zone, surge, idle_before_trip_min (devuelven NULL).';


-- ═══════════════════════════════════════════════════════════════════
-- 2. ops.driver_session_fact (MATERIALIZED VIEW)
-- Grano: driver + session
-- Detecta sesiones operacionales: nueva sesión si gap > 90 min entre viajes.
-- Fuente: public.trips_2026 para timestamps precisos (fecha_inicio_viaje).
-- Ventana: últimos 180 días para rendimiento.
-- ═══════════════════════════════════════════════════════════════════

-- Limpieza previa
DROP MATERIALIZED VIEW IF EXISTS ops.driver_session_fact CASCADE;

CREATE MATERIALIZED VIEW ops.driver_session_fact AS
WITH
-- Paso 1: trips completados ordenados por conductor y timestamp
ordered_trips AS (
    SELECT
        t.conductor_id AS driver_id,
        t.fecha_inicio_viaje AS trip_start,
        t.fecha_finalizacion AS trip_end,
        t.park_id,
        t.precio_yango_pro AS ticket,
        t.comision_empresa_asociada AS revenue,
        ABS(t.distancia_km) / 1000.0 AS distance_km,
        EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) / 60.0 AS duration_min,
        t.condicion,
        t.fecha_inicio_viaje::date AS trip_date,
        LAG(t.fecha_inicio_viaje) OVER (
            PARTITION BY t.conductor_id
            ORDER BY t.fecha_inicio_viaje
        ) AS prev_trip_start,
        LAG(t.fecha_finalizacion) OVER (
            PARTITION BY t.conductor_id
            ORDER BY t.fecha_inicio_viaje
        ) AS prev_trip_end
    FROM public.trips_2026 t
    WHERE t.condicion = 'Completado'
      AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '180 days'
      AND t.conductor_id IS NOT NULL
),
-- Paso 2: calcular gaps y marcar inicios de sesión
trips_with_gaps AS (
    SELECT
        *,
        CASE
            WHEN prev_trip_end IS NULL THEN 1  -- primer viaje del conductor
            WHEN EXTRACT(EPOCH FROM (trip_start - prev_trip_end)) / 60.0 > 90 THEN 1
            ELSE 0
        END AS is_new_session,
        CASE
            WHEN prev_trip_end IS NOT NULL
            THEN EXTRACT(EPOCH FROM (trip_start - prev_trip_end)) / 60.0
            ELSE NULL
        END AS gap_minutes
    FROM ordered_trips
),
-- Paso 3: asignar session_id acumulando is_new_session
sessions_numbered AS (
    SELECT
        *,
        SUM(is_new_session) OVER (
            PARTITION BY driver_id
            ORDER BY trip_start
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS session_id
    FROM trips_with_gaps
),
-- Paso 4: agregar por sesión
session_agg AS (
    SELECT
        driver_id,
        session_id,
        MIN(trip_date) AS session_date,
        MIN(trip_start) AS session_start,
        MAX(trip_end) AS session_end,
        EXTRACT(EPOCH FROM (MAX(trip_end) - MIN(trip_start))) / 60.0 AS session_duration_min,
        COUNT(*) AS session_trips,
        SUM(revenue) AS session_revenue,
        SUM(distance_km) AS session_distance_km,
        AVG(duration_min) AS avg_trip_duration_min,
        SUM(gap_minutes) FILTER (WHERE gap_minutes IS NOT NULL) AS total_idle_time_min,
        COUNT(*) FILTER (WHERE is_new_session = 0) AS internal_gaps_count,
        MIN(ticket) AS min_ticket,
        MAX(ticket) AS max_ticket,
        AVG(ticket) AS avg_ticket
    FROM sessions_numbered
    GROUP BY driver_id, session_id
)
SELECT
    driver_id,
    session_date,
    session_start,
    session_end,
    session_duration_min,
    session_trips,
    session_revenue,
    session_distance_km,
    avg_trip_duration_min,
    total_idle_time_min,
    CASE
        WHEN internal_gaps_count > 0
        THEN total_idle_time_min / internal_gaps_count
        ELSE NULL
    END AS avg_idle_between_trips_min,
    min_ticket,
    max_ticket,
    avg_ticket
FROM session_agg
WHERE session_trips >= 1
ORDER BY driver_id, session_start;

-- Índices para queries del servicio
CREATE INDEX IF NOT EXISTS idx_dsf_driver_date
    ON ops.driver_session_fact (driver_id, session_date);
CREATE INDEX IF NOT EXISTS idx_dsf_session_date
    ON ops.driver_session_fact (session_date);
CREATE INDEX IF NOT EXISTS idx_dsf_driver_id
    ON ops.driver_session_fact (driver_id);

COMMENT ON MATERIALIZED VIEW ops.driver_session_fact IS
'Fase 2B: Sesiones operacionales. Nueva sesión = gap > 90 min entre viajes consecutivos.
Fuente: public.trips_2026 (últimos 180 días). Solo viajes completados.
Columnas NO disponibles: city (requiere JOIN con dim_park).';


-- ═══════════════════════════════════════════════════════════════════
-- 3. ops.driver_zone_behavior_fact (VIEW)
-- Grano: driver + zone(park_id) + date
-- Agrega comportamiento por zona-park desde el trip behavior fact.
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW ops.driver_zone_behavior_fact AS
SELECT
    driver_id,
    park_id AS zone,
    country,
    city,
    trip_date,
    COUNT(*) FILTER (WHERE completed_trips = 1) AS trips_completed,
    COUNT(*) FILTER (WHERE cancelled_trips = 1) AS trips_cancelled,
    COUNT(*) AS total_trips,
    SUM(revenue) AS revenue,
    AVG(revenue) FILTER (WHERE revenue IS NOT NULL AND revenue > 0) AS avg_ticket,
    SUM(distance_km) AS total_distance_km,
    AVG(distance_km) AS avg_distance_km,
    SUM(duration_min) AS total_duration_min,
    AVG(duration_min) AS avg_duration_min,
    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_hour_trips,
    COUNT(*) FILTER (WHERE day_of_week IN (0, 6)) AS weekend_trips,
    COUNT(DISTINCT trip_date) AS active_days
FROM ops.driver_trip_behavior_fact
WHERE completed_trips = 1
GROUP BY driver_id, park_id, country, city, trip_date;

COMMENT ON VIEW ops.driver_zone_behavior_fact IS
'Fase 2B: Comportamiento operacional por driver + zone (park) + día.
Agregado desde ops.driver_trip_behavior_fact. Solo viajes completados.
Zone = park_id (proxy, no hay geozonas reales en los datos).';


-- ═══════════════════════════════════════════════════════════════════
-- 4. Refresh function para el MVIEW de sesiones
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION ops.refresh_driver_session_fact()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW ops.driver_session_fact;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION ops.refresh_driver_session_fact() IS
'Refresca el MVIEW de sesiones operacionales.';

COMMIT;
