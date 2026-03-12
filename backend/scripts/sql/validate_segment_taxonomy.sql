-- Validaciones post-refactor de segmentación semanal (dormant, casual, pt, ft, elite, legend).
-- Ejecutar contra la BD después de aplicar migración 078 y refrescar MVs.
-- Fuente: ops.mv_driver_segments_weekly (o ops.mv_driver_weekly_stats si se valida pre-MV).

-- 1) Distribución semanal por segmento (nueva taxonomía)
SELECT
  week_start,
  segment_week AS segment_new,
  COUNT(*) AS drivers
FROM ops.mv_driver_segments_weekly
WHERE week_start >= (SELECT MAX(week_start) - 28 FROM ops.mv_driver_segments_weekly)
GROUP BY 1, 2
ORDER BY 1 DESC, 2;

-- 2) Masa de Legend (180+ viajes/semana)
SELECT
  week_start,
  COUNT(*) FILTER (WHERE trips_completed_week >= 180) AS legend_drivers
FROM ops.mv_driver_segments_weekly
WHERE week_start >= (SELECT MAX(week_start) - 56 FROM ops.mv_driver_segments_weekly)
GROUP BY 1
ORDER BY 1 DESC;

-- 3) Masa de Elite (120-179)
SELECT
  week_start,
  COUNT(*) FILTER (WHERE trips_completed_week BETWEEN 120 AND 179) AS elite_drivers
FROM ops.mv_driver_segments_weekly
WHERE week_start >= (SELECT MAX(week_start) - 56 FROM ops.mv_driver_segments_weekly)
GROUP BY 1
ORDER BY 1 DESC;

-- 4) Top transiciones (migración)
SELECT
  week_start,
  prev_segment_week AS segment_prev,
  segment_week AS segment_current,
  segment_change_type,
  COUNT(*) AS drivers
FROM ops.mv_driver_segments_weekly
WHERE park_id IS NOT NULL
  AND week_start >= (SELECT MAX(week_start) - 28 FROM ops.mv_driver_segments_weekly)
GROUP BY 1, 2, 3, 4
ORDER BY week_start DESC, drivers DESC;

-- 5) Same-to-same (stable / lateral)
SELECT
  week_start,
  prev_segment_week AS segment_prev,
  segment_week AS segment_current,
  COUNT(*) AS drivers
FROM ops.mv_driver_segments_weekly
WHERE segment_week = prev_segment_week
  AND week_start >= (SELECT MAX(week_start) - 28 FROM ops.mv_driver_segments_weekly)
GROUP BY 1, 2, 3
ORDER BY week_start DESC, drivers DESC;

-- 6) Presencia Dormant
SELECT
  week_start,
  COUNT(*) FILTER (WHERE segment_week = 'DORMANT') AS dormant_drivers
FROM ops.mv_driver_segments_weekly
WHERE week_start >= (SELECT MAX(week_start) - 56 FROM ops.mv_driver_segments_weekly)
GROUP BY 1
ORDER BY 1 DESC;

-- 7) Config vigente (orden operativo)
SELECT segment_code, segment_name, min_trips_week, max_trips_week, ordering
FROM ops.driver_segment_config
WHERE is_active
  AND effective_from <= CURRENT_DATE
  AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
ORDER BY ordering ASC;
