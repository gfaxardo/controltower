-- PASO 3C E2E: Vista Plan vs Real por LOB (match directo lob_base = tipo_servicio)
-- Usa plan.plan_lob_long y ops.mv_real_tipo_servicio_universe_fast.

CREATE OR REPLACE VIEW ops.v_plan_lob_agg AS
SELECT
  country,
  city,
  TRIM(LOWER(plan_lob_base)) AS lob_name_norm,
  SUM(trips_plan) AS plan_trips,
  SUM(revenue_plan) AS plan_revenue
FROM plan.plan_lob_long
GROUP BY country, city, TRIM(LOWER(plan_lob_base));

DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check CASCADE;

CREATE OR REPLACE VIEW ops.v_plan_vs_real_lob_check AS
SELECT
  COALESCE(p.country, r.country) AS country,
  COALESCE(p.city, r.city) AS city,
  COALESCE(p.lob_name_norm, r.real_tipo_servicio) AS lob_name_norm,
  (p.lob_name_norm IS NOT NULL) AS exists_in_plan,
  (r.real_tipo_servicio IS NOT NULL) AS exists_in_real,
  COALESCE(p.plan_trips, 0) AS plan_trips,
  COALESCE(r.trips_count, 0) AS real_trips,
  COALESCE(p.plan_revenue, 0) AS plan_revenue,
  CASE
    WHEN p.lob_name_norm IS NOT NULL AND r.real_tipo_servicio IS NOT NULL THEN 'OK'
    WHEN p.lob_name_norm IS NOT NULL AND r.real_tipo_servicio IS NULL THEN 'PLAN_ONLY'
    WHEN p.lob_name_norm IS NULL AND r.real_tipo_servicio IS NOT NULL THEN 'REAL_ONLY'
    ELSE 'UNKNOWN'
  END AS coverage_status
FROM ops.v_plan_lob_agg p
FULL OUTER JOIN ops.mv_real_tipo_servicio_universe_fast r
  ON LOWER(TRIM(COALESCE(r.country,''))) = LOWER(TRIM(COALESCE(p.country,'')))
 AND LOWER(TRIM(COALESCE(r.city,''))) = LOWER(TRIM(COALESCE(p.city,'')))
 AND r.real_tipo_servicio = p.lob_name_norm;
