-- ============================================================
-- YEGO PRO PROFITABILITY — SERVING VIEWS
-- Phase 1 Foundation | Control Foundation (serving layer)
-- Park: 64085dd85e124e2c808806f70d527ea8 (Lima)
-- ============================================================

-- 1. WEEKLY PROFITABILITY (park-level, from billing)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_profitability_week AS
WITH park_drivers AS (
    SELECT driver_id
    FROM public.drivers
    WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
),
billing_agg AS (
    SELECT
        b.fecha_inicio AS week_start,
        b.fecha_fin AS week_end,
        COUNT(DISTINCT b.driver_id) AS active_drivers,
        SUM(b.total_viajes) AS trips_completed,
        SUM(b.horas_trabajo) AS work_hours,
        SUM(b.monto_total_producido) AS revenue_gross,
        SUM(b.comision_app) AS platform_commission,
        SUM(b.monto_neto) AS revenue_net,
        SUM(b.km_recorrido) AS km_total,
        SUM(b.gasto_combustible) AS fuel_cost,
        SUM(b.gasto_mantenimiento) AS maintenance_cost,
        SUM(b.pago_total) AS driver_payment,
        SUM(b.utilidad) AS profit,
        SUM(b.bono_yango) AS bono_yango,
        SUM(b.bono_adic_viajes) AS bono_additional,
        AVG(b.porcentaje_pago) AS avg_driver_pct
    FROM public.module_weekly_billing b
    WHERE b.driver_id IN (SELECT driver_id FROM park_drivers)
    GROUP BY b.fecha_inicio, b.fecha_fin
)
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    week_start,
    week_end,
    active_drivers,
    trips_completed,
    work_hours,
    revenue_gross,
    platform_commission,
    revenue_net,
    km_total,
    fuel_cost,
    maintenance_cost,
    driver_payment,
    profit,
    bono_yango,
    bono_additional,
    avg_driver_pct,
    CASE WHEN trips_completed > 0 THEN revenue_gross / trips_completed ELSE NULL END AS ticket_avg,
    CASE WHEN trips_completed > 0 THEN km_total / trips_completed ELSE NULL END AS km_per_trip,
    CASE WHEN work_hours > 0 THEN revenue_gross / work_hours ELSE NULL END AS revenue_per_hour,
    CASE WHEN work_hours > 0 THEN trips_completed::numeric / work_hours ELSE NULL END AS trips_per_hour,
    CASE WHEN km_total > 0 THEN fuel_cost / km_total ELSE NULL END AS fuel_per_km,
    CASE WHEN km_total > 0 THEN maintenance_cost / km_total ELSE NULL END AS maintenance_per_km,
    CASE WHEN trips_completed > 0 THEN profit / trips_completed ELSE NULL END AS profit_per_trip,
    CASE WHEN revenue_gross > 0 THEN profit / revenue_gross ELSE NULL END AS margin_pct,
    NOW() AS refreshed_at
FROM billing_agg
ORDER BY week_start DESC;

-- 2. DAILY PROFITABILITY (park-level, from trips only)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_profitability_day AS
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    DATE(t.fecha_inicio_viaje) AS date,
    COUNT(*) FILTER (WHERE t.condicion = 'Completado') AS trips_completed,
    COUNT(*) FILTER (WHERE t.condicion <> 'Completado') AS trips_cancelled,
    COUNT(DISTINCT t.conductor_id) FILTER (WHERE t.condicion = 'Completado') AS active_drivers,
    SUM(t.precio_yango_pro) FILTER (WHERE t.condicion = 'Completado') AS revenue_gross,
    AVG(t.precio_yango_pro) FILTER (WHERE t.condicion = 'Completado') AS ticket_avg,
    SUM(t.distancia_km) FILTER (WHERE t.condicion = 'Completado') / 1000.0 AS km_total_passenger,
    AVG(t.distancia_km) FILTER (WHERE t.condicion = 'Completado') / 1000.0 AS km_per_trip_passenger,
    AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) / 60.0)
        FILTER (WHERE t.condicion = 'Completado' AND t.fecha_finalizacion > t.fecha_inicio_viaje)
        AS duration_avg_min,
    COUNT(*) FILTER (WHERE t.condicion = 'Completado' AND EXTRACT(HOUR FROM t.fecha_inicio_viaje) BETWEEN 6 AND 17) AS trips_day_shift,
    COUNT(*) FILTER (WHERE t.condicion = 'Completado' AND (EXTRACT(HOUR FROM t.fecha_inicio_viaje) >= 18 OR EXTRACT(HOUR FROM t.fecha_inicio_viaje) < 6)) AS trips_night_shift,
    SUM(t.precio_yango_pro) FILTER (WHERE t.condicion = 'Completado' AND EXTRACT(HOUR FROM t.fecha_inicio_viaje) BETWEEN 6 AND 17) AS revenue_day_shift,
    SUM(t.precio_yango_pro) FILTER (WHERE t.condicion = 'Completado' AND (EXTRACT(HOUR FROM t.fecha_inicio_viaje) >= 18 OR EXTRACT(HOUR FROM t.fecha_inicio_viaje) < 6)) AS revenue_night_shift,
    NOW() AS refreshed_at
FROM public.trips_2026 t
WHERE t.park_id = '64085dd85e124e2c808806f70d527ea8'
GROUP BY DATE(t.fecha_inicio_viaje)
ORDER BY date DESC;

-- 3. DRIVER PROFITABILITY WEEKLY (from billing)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_driver_profitability_week AS
WITH park_drivers AS (
    SELECT d.driver_id, d.full_name AS driver_name
    FROM public.drivers d
    WHERE d.park_id = '64085dd85e124e2c808806f70d527ea8'
)
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    b.driver_id,
    pd.driver_name,
    b.fecha_inicio AS week_start,
    b.fecha_fin AS week_end,
    b.total_viajes AS trips_completed,
    b.horas_trabajo AS work_hours,
    b.monto_total_producido AS revenue_gross,
    b.comision_app AS platform_commission,
    b.monto_neto AS revenue_net,
    b.km_recorrido AS km_total,
    b.gasto_combustible AS fuel_cost,
    b.gasto_mantenimiento AS maintenance_cost,
    b.porcentaje_pago AS driver_pct,
    b.pago_total AS driver_payment,
    b.utilidad AS profit,
    b.bono_yango,
    b.bono_adic_viajes AS bono_additional,
    CASE WHEN b.total_viajes > 0 THEN b.monto_total_producido / b.total_viajes ELSE NULL END AS ticket_avg,
    CASE WHEN b.total_viajes > 0 THEN b.km_recorrido / b.total_viajes ELSE NULL END AS km_per_trip,
    CASE WHEN b.horas_trabajo > 0 THEN b.monto_total_producido / b.horas_trabajo ELSE NULL END AS revenue_per_hour,
    CASE WHEN b.horas_trabajo > 0 THEN b.total_viajes::numeric / b.horas_trabajo ELSE NULL END AS trips_per_hour,
    CASE WHEN b.total_viajes > 0 THEN b.utilidad / b.total_viajes ELSE NULL END AS profit_per_trip,
    CASE WHEN b.monto_total_producido > 0 THEN b.utilidad / b.monto_total_producido ELSE NULL END AS margin_pct,
    (b.utilidad > 0) AS is_profitable,
    NOW() AS refreshed_at
FROM public.module_weekly_billing b
JOIN park_drivers pd ON pd.driver_id = b.driver_id
ORDER BY b.fecha_inicio DESC, b.utilidad DESC;

-- 4. VEHICLE PROFITABILITY WEEKLY (from cronograma config — limited)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_vehicle_profitability_week AS
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    cr.id AS cronograma_id,
    cr.name AS cronograma_name,
    cv.name AS vehicle_name,
    cv.cuotas_semanales AS total_weekly_quotas,
    r.cuotas_por_vehiculo AS weekly_quota,
    r.viajes AS min_trips_for_bono,
    r.bono_auto AS bono_reduction,
    r.orden AS tier_order,
    NOW() AS refreshed_at
FROM public.module_miauto_cronograma cr
JOIN public.module_miauto_cronograma_vehiculo cv ON cv.cronograma_id = cr.id
JOIN public.module_miauto_cronograma_rule r ON r.cronograma_id = cr.id
WHERE cr.country = 'PE' AND cr.active = true
ORDER BY cr.name, cv.name, r.orden;

-- 5. SHIFT PROFITABILITY (from trips, aggregated weekly)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_shift_profitability_week AS
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    DATE_TRUNC('week', t.fecha_inicio_viaje)::date AS week_start,
    CASE
        WHEN EXTRACT(HOUR FROM t.fecha_inicio_viaje) BETWEEN 6 AND 17 THEN 'DAY'
        ELSE 'NIGHT'
    END AS shift,
    COUNT(*) AS trips_completed,
    COUNT(DISTINCT t.conductor_id) AS active_drivers,
    SUM(t.precio_yango_pro) AS revenue_gross,
    AVG(t.precio_yango_pro) AS ticket_avg,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.precio_yango_pro) AS ticket_median,
    SUM(t.distancia_km) / 1000.0 AS km_total,
    AVG(t.distancia_km) / 1000.0 AS km_per_trip,
    AVG(EXTRACT(EPOCH FROM (t.fecha_finalizacion - t.fecha_inicio_viaje)) / 60.0)
        FILTER (WHERE t.fecha_finalizacion > t.fecha_inicio_viaje)
        AS duration_avg_min,
    NOW() AS refreshed_at
FROM public.trips_2026 t
WHERE t.park_id = '64085dd85e124e2c808806f70d527ea8'
  AND t.condicion = 'Completado'
  AND t.precio_yango_pro IS NOT NULL
GROUP BY DATE_TRUNC('week', t.fecha_inicio_viaje)::date,
         CASE WHEN EXTRACT(HOUR FROM t.fecha_inicio_viaje) BETWEEN 6 AND 17 THEN 'DAY' ELSE 'NIGHT' END
ORDER BY week_start DESC, shift;

-- INDEXES for performance
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_week_pk
    ON ops.mv_yego_pro_profitability_week (week_start);
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_day_pk
    ON ops.mv_yego_pro_profitability_day (date);
CREATE INDEX IF NOT EXISTS idx_yego_pro_driver_week_pk
    ON ops.mv_yego_pro_driver_profitability_week (week_start, driver_id);
CREATE INDEX IF NOT EXISTS idx_yego_pro_shift_week_pk
    ON ops.mv_yego_pro_shift_profitability_week (week_start, shift);
