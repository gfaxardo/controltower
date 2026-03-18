-- Validación segmentación conductores REAL (mig 106).
-- Ejecutar tras aplicar 106 y (opcional) populate_real_drill_from_hourly_chain + UPDATE segmentación.
--
-- 1) Conductor con completed > 0 → is_active = true en v_real_driver_segment_driver_period
-- 2) Conductor con cancelled > 0 y completed = 0 → is_cancel_only = true
-- 3) activity_drivers = activos + solo_cancelan (sin doble conteo por periodo)
-- 4) cancel_only_pct = cancel_only_drivers / activity_drivers

-- 1) Muestra: drivers activos (completed_cnt > 0) deben tener is_active = true
SELECT '1) Muestra activos (is_active=true)' AS check_name;
SELECT driver_key, period_grain, period_start, country, segment_tag,
       completed_cnt, cancelled_cnt, is_active, is_cancel_only, is_activity
FROM ops.v_real_driver_segment_driver_period
WHERE completed_cnt > 0
LIMIT 5;

-- 2) Muestra: drivers solo_cancelan (completed=0, cancelled>0) deben tener is_cancel_only = true
SELECT '2) Muestra solo_cancelan (is_cancel_only=true)' AS check_name;
SELECT driver_key, period_grain, period_start, country, segment_tag,
       completed_cnt, cancelled_cnt, is_active, is_cancel_only, is_activity
FROM ops.v_real_driver_segment_driver_period
WHERE completed_cnt = 0 AND cancelled_cnt > 0
LIMIT 5;

-- 3) Por un periodo: activity_drivers = COUNT(DISTINCT driver) con (completed>0 OR cancelled>0)
SELECT '3) Conteo por periodo (ej. un mes)' AS check_name;
WITH one_period AS (
  SELECT period_grain, period_start, country
  FROM ops.v_real_driver_segment_driver_period
  WHERE period_grain = 'month'
  LIMIT 1
)
SELECT
  p.period_grain,
  p.period_start,
  p.country,
  COUNT(DISTINCT d.driver_key) FILTER (WHERE d.is_active) AS active_drivers,
  COUNT(DISTINCT d.driver_key) FILTER (WHERE d.is_cancel_only) AS cancel_only_drivers,
  COUNT(DISTINCT d.driver_key) FILTER (WHERE d.is_activity) AS activity_drivers
FROM one_period p
JOIN ops.v_real_driver_segment_driver_period d
  ON d.period_grain = p.period_grain AND d.period_start = p.period_start AND d.country = p.country
GROUP BY p.period_grain, p.period_start, p.country;

-- 4) Reconciliación: suma por LOB = suma por Park (mismo total activos por país+periodo)
SELECT '4) Reconciliación tajadas (activos por país+periodo)' AS check_name;
SELECT period_grain, period_start, country,
       SUM(active_drivers) AS sum_active_by_row,
       (SELECT COUNT(DISTINCT driver_key) FROM ops.v_real_driver_segment_driver_period d2
        WHERE d2.period_grain = a.period_grain AND d2.period_start = a.period_start AND d2.country = a.country AND d2.is_active) AS distinct_active
FROM ops.v_real_driver_segment_agg a
WHERE period_grain = 'month'
GROUP BY period_grain, period_start, country
ORDER BY period_start DESC, country
LIMIT 6;
