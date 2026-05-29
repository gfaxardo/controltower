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

-- ============================================================
-- P2.4 DATA HARDENING — NEW SERVING VIEWS
-- ============================================================

-- 6. SHIFT DAILY PROFITABILITY (from module_calculated_shifts — native shifts)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_shift_daily AS
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    s.fecha AS date,
    s.tipo_turno AS shift_type,
    s.driver_id,
    s.placa AS vehicle_plate,
    SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
    SUM(COALESCE(s.produccion_total, 0)) AS revenue,
    SUM(COALESCE(s.monto_total, 0)) AS shift_amount,
    SUM(COALESCE(s.comisiones_servicio, 0)) AS service_commission,
    SUM(COALESCE(s.duracion_minutos, 0)) AS total_minutes,
    COUNT(*) AS shift_count,
    COUNT(*) FILTER (WHERE s.pagado) AS paid_shifts,
    COUNT(*) FILTER (WHERE s.es_manual) AS manual_shifts,
    COUNT(*) FILTER (WHERE s.placa IS NOT NULL) AS shifts_with_plate,
    AVG(COALESCE(s.duracion_minutos, 0)) FILTER (WHERE s.duracion_minutos > 0) AS avg_duration_min,
    CASE WHEN SUM(COALESCE(s.cantidad_viajes, 0)) > 0
         THEN SUM(COALESCE(s.produccion_total, 0)) / SUM(COALESCE(s.cantidad_viajes, 0))
         ELSE NULL END AS revenue_per_trip,
    'module_calculated_shifts'::text AS data_source,
    'REAL'::text AS metric_type,
    CASE WHEN s.placa IS NOT NULL THEN 'HIGH' ELSE 'MEDIUM' END::text AS confidence,
    NOW() AS refreshed_at
FROM public.module_calculated_shifts s
WHERE s.driver_id IN (
    SELECT driver_id FROM public.drivers
    WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
)
GROUP BY s.fecha, s.tipo_turno, s.driver_id, s.placa
ORDER BY s.fecha DESC, s.tipo_turno;

-- 7. DRIVER CLOSE WEEKLY (from module_driver_closes — settlement validation)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_driver_close_week AS
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    c.driver_id,
    DATE_TRUNC('week', c.fecha)::date AS week_start,
    COUNT(*) AS close_days,
    MIN(c.fecha)::text AS first_close_date,
    MAX(c.fecha)::text AS last_close_date,
    SUM(COALESCE(c.total_ingresos, 0)) AS close_income,
    SUM(COALESCE(c.total_gastos, 0)) AS close_expenses,
    SUM(COALESCE(c.resta, 0)) AS close_remainder,
    SUM(COALESCE(c.gnv_soles, 0)) AS gnv_cost,
    SUM(COALESCE(c.gasolina_soles, 0)) AS gasoline_cost,
    SUM(COALESCE(c.gnv_soles, 0) + COALESCE(c.gasolina_soles, 0)) AS total_fuel_cost,
    SUM(COALESCE(c.liquida_efectivo, 0)) AS cash_settlement,
    SUM(COALESCE(c.liquida_yape, 0)) AS digital_settlement,
    SUM(COALESCE(c.otros_gastos, 0)) AS other_expenses,
    MAX(c.diferencia_odometro) AS max_odometer_km,
    SUM(COALESCE(c.diferencia_odometro, 0)) AS total_odometer_km,
    STRING_AGG(DISTINCT c.placa, ', ') FILTER (WHERE c.placa IS NOT NULL) AS plates_used,
    'module_driver_closes'::text AS data_source,
    'REAL'::text AS metric_type,
    'MEDIUM'::text AS confidence,
    NOW() AS refreshed_at
FROM public.module_driver_closes c
WHERE c.driver_id IN (
    SELECT driver_id FROM public.drivers
    WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
)
GROUP BY c.driver_id, DATE_TRUNC('week', c.fecha)::date
ORDER BY week_start DESC, c.driver_id;

-- 8. WEEKLY FINANCIAL TRUTH (from module_weekly_billing — consolidated P&L)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_weekly_financial_truth AS
WITH park_drivers AS (
    SELECT driver_id, full_name FROM public.drivers
    WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
),
billing_agg AS (
    SELECT
        b.fecha_inicio AS week_start,
        b.fecha_fin AS week_end,
        COUNT(DISTINCT b.driver_id) AS active_drivers,
        SUM(b.total_viajes) AS trips,
        SUM(b.monto_total_producido) AS revenue_gross,
        SUM(b.comision_app) AS platform_commission,
        SUM(b.monto_neto) AS revenue_net,
        SUM(b.gasto_combustible) AS fuel_cost,
        SUM(b.gasto_mantenimiento) AS maintenance_cost,
        SUM(b.pago_total) AS driver_payout,
        SUM(b.bono_yango) AS bonus_yango,
        SUM(b.bono_adic_viajes) AS bonus_additional,
        SUM(COALESCE(b.bonificacion, 0)) AS bonification,
        SUM(COALESCE(b.garantia, 0)) AS guarantee,
        SUM(COALESCE(b.descuento, 0)) AS discount,
        SUM(b.utilidad) AS net_profit,
        SUM(b.km_recorrido) AS km_total,
        SUM(b.horas_trabajo) AS work_hours,
        STRING_AGG(DISTINCT b.turno, ', ') FILTER (WHERE b.turno IS NOT NULL) AS shift_types,
        STRING_AGG(DISTINCT b.estado, ', ') FILTER (WHERE b.estado IS NOT NULL) AS billing_statuses
    FROM public.module_weekly_billing b
    WHERE b.driver_id IN (SELECT driver_id FROM park_drivers)
    GROUP BY b.fecha_inicio, b.fecha_fin
)
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    week_start,
    week_end,
    active_drivers,
    trips,
    revenue_gross,
    platform_commission,
    revenue_net,
    fuel_cost,
    maintenance_cost,
    driver_payout,
    bonus_yango,
    bonus_additional,
    bonification,
    guarantee,
    discount,
    net_profit,
    km_total,
    work_hours,
    CASE WHEN trips > 0 THEN revenue_gross / trips ELSE NULL END AS ticket_avg,
    CASE WHEN trips > 0 THEN km_total / trips ELSE NULL END AS km_per_trip,
    CASE WHEN work_hours > 0 THEN revenue_gross / work_hours ELSE NULL END AS revenue_per_hour,
    CASE WHEN revenue_gross > 0 THEN net_profit / revenue_gross ELSE NULL END AS margin_pct,
    CASE WHEN revenue_gross > 0 THEN fuel_cost / revenue_gross ELSE NULL END AS fuel_pct,
    CASE WHEN revenue_gross > 0 THEN maintenance_cost / revenue_gross ELSE NULL END AS maintenance_pct,
    CASE WHEN revenue_gross > 0 THEN driver_payout / revenue_gross ELSE NULL END AS payout_pct,
    CASE WHEN net_profit >= 0 THEN 'PROFIT' ELSE 'LOSS' END AS result,
    shift_types,
    billing_statuses,
    'module_weekly_billing'::text AS data_source,
    'REAL'::text AS metric_type,
    'HIGH'::text AS confidence,
    NOW() AS refreshed_at
FROM billing_agg
ORDER BY week_start DESC;

-- 9. SOURCE COVERAGE (cross-source coverage metrics)
CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_pro_source_coverage AS
WITH park_drivers AS (
    SELECT driver_id FROM public.drivers WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
),
billing_stats AS (
    SELECT
        COUNT(*) AS billing_rows,
        COUNT(DISTINCT fecha_inicio) AS billing_weeks,
        COUNT(DISTINCT driver_id) AS billing_drivers,
        MIN(fecha_inicio)::text AS billing_min_date,
        MAX(fecha_fin)::text AS billing_max_date
    FROM public.module_weekly_billing
    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
),
close_stats AS (
    SELECT
        COUNT(*) AS close_rows,
        COUNT(DISTINCT fecha) AS close_days,
        COUNT(DISTINCT driver_id) AS close_drivers,
        MIN(fecha)::text AS close_min_date,
        MAX(fecha)::text AS close_max_date
    FROM public.module_driver_closes
    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
),
shift_stats AS (
    SELECT
        COUNT(*) AS shift_rows,
        COUNT(DISTINCT fecha) AS shift_days,
        COUNT(DISTINCT driver_id) AS shift_drivers,
        COUNT(*) FILTER (WHERE placa IS NOT NULL) AS shifts_with_plate,
        COUNT(*) FILTER (WHERE placa IS NULL) AS shifts_without_plate,
        MIN(fecha)::text AS shift_min_date,
        MAX(fecha)::text AS shift_max_date
    FROM public.module_calculated_shifts
    WHERE driver_id IN (SELECT driver_id FROM park_drivers)
),
trip_stats AS (
    SELECT
        COUNT(*) AS trip_rows,
        COUNT(DISTINCT conductor_id) AS trip_drivers,
        COUNT(DISTINCT fecha_inicio_viaje::date) AS trip_days,
        MIN(fecha_inicio_viaje::date)::text AS trip_min_date,
        MAX(fecha_inicio_viaje::date)::text AS trip_max_date
    FROM public.trips_2026
    WHERE park_id = '64085dd85e124e2c808806f70d527ea8' AND condicion = 'Completado'
),
total_drivers AS (
    SELECT COUNT(*) AS park_drivers FROM park_drivers
)
SELECT
    '64085dd85e124e2c808806f70d527ea8'::text AS park_id,
    (SELECT park_drivers FROM total_drivers) AS registered_drivers,
    ts.trip_rows,
    ts.trip_days,
    ts.trip_drivers,
    ts.trip_min_date,
    ts.trip_max_date,
    s.shift_rows,
    s.shift_days,
    s.shift_drivers,
    s.shifts_with_plate,
    s.shifts_without_plate,
    CASE WHEN s.shift_rows > 0 THEN ROUND(s.shifts_with_plate::numeric / s.shift_rows * 100, 1) ELSE 0 END AS plate_coverage_pct,
    c.close_rows,
    c.close_days,
    c.close_drivers,
    c.close_min_date,
    c.close_max_date,
    CASE WHEN (SELECT park_drivers FROM total_drivers) > 0
         THEN ROUND(c.close_drivers::numeric / (SELECT park_drivers FROM total_drivers) * 100, 1)
         ELSE 0 END AS close_driver_coverage_pct,
    b.billing_rows,
    b.billing_weeks,
    b.billing_drivers,
    b.billing_min_date,
    b.billing_max_date,
    CASE WHEN b.billing_weeks >= 4 THEN 'HEALTHY'
         WHEN b.billing_weeks >= 1 THEN 'PARTIAL'
         ELSE 'NONE' END AS financial_history_status,
    CASE WHEN s.shift_days >= 7 THEN 'HEALTHY'
         WHEN s.shift_days >= 1 THEN 'PARTIAL'
         ELSE 'NONE' END AS operational_history_status,
    'multi_source'::text AS data_source,
    'DERIVED'::text AS metric_type,
    'HIGH'::text AS confidence,
    NOW() AS refreshed_at
FROM billing_stats b
CROSS JOIN close_stats c
CROSS JOIN shift_stats s
CROSS JOIN trip_stats ts
CROSS JOIN total_drivers;

-- INDEXES for new views
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_shift_daily_pk
    ON ops.mv_yego_pro_shift_daily (date, shift_type, driver_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_driver_close_week_pk
    ON ops.mv_yego_pro_driver_close_week (week_start, driver_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_financial_truth_pk
    ON ops.mv_yego_pro_weekly_financial_truth (week_start);
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_source_coverage_pk
    ON ops.mv_yego_pro_source_coverage (park_id);

-- ============================================================
-- EXISTING INDEXES (kept from Phase 1)
-- ============================================================
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_week_pk
    ON ops.mv_yego_pro_profitability_week (week_start);
CREATE UNIQUE INDEX IF NOT EXISTS idx_yego_pro_day_pk
    ON ops.mv_yego_pro_profitability_day (date);
CREATE INDEX IF NOT EXISTS idx_yego_pro_driver_week_pk
    ON ops.mv_yego_pro_driver_profitability_week (week_start, driver_id);
CREATE INDEX IF NOT EXISTS idx_yego_pro_shift_week_pk
    ON ops.mv_yego_pro_shift_profitability_week (week_start, shift);
