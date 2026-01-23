-- Fase 2B - Validaciones semanales

-- 8.1 Unicidad MV semanal
SELECT week_start, country, city_norm, lob_base, segment, COUNT(*) AS cnt
FROM ops.mv_real_trips_weekly
GROUP BY 1,2,3,4,5
HAVING COUNT(*) > 1;

-- 8.2 Reconciliacion semanal vs trips_all (ultima semana cerrada por pais)
WITH last_closed_week AS (
    SELECT DATE_TRUNC('week', NOW())::DATE - INTERVAL '1 week' AS week_start
),
direct_sum AS (
    SELECT
        DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE as week_start,
        COALESCE(dp.country, '') as country,
        -1 * SUM(NULLIF(t.comision_empresa_asociada, 0)) as revenue_real_yego_direct
    FROM public.trips_all t
    LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
    WHERE t.condicion = 'Completado'
      AND DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE = (SELECT week_start FROM last_closed_week)
    GROUP BY 1,2
),
mv_sum AS (
    SELECT
        week_start,
        country,
        SUM(revenue_real_yego) as revenue_real_yego_mv
    FROM ops.mv_real_trips_weekly
    WHERE week_start = (SELECT week_start FROM last_closed_week)
    GROUP BY 1,2
)
SELECT
    COALESCE(d.week_start, m.week_start) as week_start,
    COALESCE(d.country, m.country) as country,
    COALESCE(d.revenue_real_yego_direct, 0) as revenue_real_yego_direct,
    COALESCE(m.revenue_real_yego_mv, 0) as revenue_real_yego_mv,
    ABS(COALESCE(d.revenue_real_yego_direct, 0) - COALESCE(m.revenue_real_yego_mv, 0)) as diff
FROM direct_sum d
FULL OUTER JOIN mv_sum m
  ON d.week_start = m.week_start AND d.country = m.country
ORDER BY country;

-- 8.3 Sanity
-- revenue_real_yego >= 0
SELECT COUNT(*) AS negative_revenue_count
FROM ops.mv_real_trips_weekly
WHERE revenue_real_yego < 0;

-- commission_yego_signed <= 0 (loggear positivos)
SELECT *
FROM ops.mv_real_trips_weekly
WHERE commission_yego_signed > 0
ORDER BY week_start DESC
LIMIT 20;

-- 8.4 Plan semanal suma al plan mensual (por pais/ciudad/lob/segment/mes)
WITH plan_weekly AS (
    SELECT
        DATE_TRUNC('month', week_start)::DATE as month,
        country,
        city_norm,
        lob_base,
        segment,
        SUM(trips_plan_week) as trips_plan_week_sum,
        SUM(drivers_plan_week) as drivers_plan_week_sum,
        SUM(revenue_plan_week) as revenue_plan_week_sum
    FROM ops.v_plan_trips_weekly_from_monthly
    GROUP BY 1,2,3,4,5
),
plan_monthly AS (
    SELECT
        month,
        country,
        COALESCE(plan_city_resolved_norm, city_norm) as city_norm,
        lob_base,
        segment,
        SUM(projected_trips) as trips_plan_month,
        SUM(projected_drivers) as drivers_plan_month,
        SUM(projected_revenue) as revenue_plan_month
    FROM ops.v_plan_trips_monthly_latest
    GROUP BY 1,2,3,4,5
)
SELECT
    COALESCE(w.month, m.month) as month,
    COALESCE(w.country, m.country) as country,
    COALESCE(w.city_norm, m.city_norm) as city_norm,
    COALESCE(w.lob_base, m.lob_base) as lob_base,
    COALESCE(w.segment, m.segment) as segment,
    COALESCE(w.trips_plan_week_sum, 0) as trips_plan_week_sum,
    COALESCE(m.trips_plan_month, 0) as trips_plan_month,
    COALESCE(w.drivers_plan_week_sum, 0) as drivers_plan_week_sum,
    COALESCE(m.drivers_plan_month, 0) as drivers_plan_month,
    COALESCE(w.revenue_plan_week_sum, 0) as revenue_plan_week_sum,
    COALESCE(m.revenue_plan_month, 0) as revenue_plan_month,
    ABS(COALESCE(w.trips_plan_week_sum, 0) - COALESCE(m.trips_plan_month, 0)) as diff_trips,
    ABS(COALESCE(w.drivers_plan_week_sum, 0) - COALESCE(m.drivers_plan_month, 0)) as diff_drivers,
    ABS(COALESCE(w.revenue_plan_week_sum, 0) - COALESCE(m.revenue_plan_month, 0)) as diff_revenue
FROM plan_weekly w
FULL OUTER JOIN plan_monthly m
  ON w.month = m.month
 AND w.country = m.country
 AND w.city_norm = m.city_norm
 AND w.lob_base = m.lob_base
 AND w.segment = m.segment
ORDER BY month DESC, country, city_norm, lob_base, segment;
