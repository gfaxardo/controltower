-- PASO 3D E2E: Plan vs Real por LOB con match directo + homologación + trazabilidad

-- A) Agregación PLAN (plan_lob_name_norm; requiere DROP por cambio de nombre de columna)
DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check CASCADE;
DROP VIEW IF EXISTS ops.v_plan_lob_agg CASCADE;

CREATE OR REPLACE VIEW ops.v_plan_lob_agg AS
SELECT
  country,
  city,
  TRIM(LOWER(plan_lob_base)) AS plan_lob_name_norm,
  SUM(trips_plan) AS plan_trips,
  SUM(revenue_plan) AS plan_revenue
FROM plan.plan_lob_long
GROUP BY country, city, TRIM(LOWER(plan_lob_base));

-- A.1) Mantener v_plan_vs_real_lob_check compatible (usa plan_lob_name_norm; expone lob_name_norm)
DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check CASCADE;
CREATE OR REPLACE VIEW ops.v_plan_vs_real_lob_check AS
SELECT
  COALESCE(p.country, r.country) AS country,
  COALESCE(p.city, r.city) AS city,
  COALESCE(p.plan_lob_name_norm, r.real_tipo_servicio) AS lob_name_norm,
  (p.plan_lob_name_norm IS NOT NULL) AS exists_in_plan,
  (r.real_tipo_servicio IS NOT NULL) AS exists_in_real,
  COALESCE(p.plan_trips, 0) AS plan_trips,
  COALESCE(r.trips_count, 0) AS real_trips,
  COALESCE(p.plan_revenue, 0) AS plan_revenue,
  CASE
    WHEN p.plan_lob_name_norm IS NOT NULL AND r.real_tipo_servicio IS NOT NULL THEN 'OK'
    WHEN p.plan_lob_name_norm IS NOT NULL AND r.real_tipo_servicio IS NULL THEN 'PLAN_ONLY'
    WHEN p.plan_lob_name_norm IS NULL AND r.real_tipo_servicio IS NOT NULL THEN 'REAL_ONLY'
    ELSE 'UNKNOWN'
  END AS coverage_status
FROM ops.v_plan_lob_agg p
FULL OUTER JOIN ops.mv_real_tipo_servicio_universe_fast r
  ON LOWER(TRIM(COALESCE(r.country,''))) = LOWER(TRIM(COALESCE(p.country,'')))
 AND LOWER(TRIM(COALESCE(r.city,''))) = LOWER(TRIM(COALESCE(p.city,'')))
 AND r.real_tipo_servicio = p.plan_lob_name_norm;

-- B) REAL traducido a PLAN vía homologación (prioridad country+city > country > global)
CREATE OR REPLACE VIEW ops.v_real_to_plan_lob_resolved AS
WITH real AS (
  SELECT country, city, real_tipo_servicio, trips_count
  FROM ops.mv_real_tipo_servicio_universe_fast
),
h_ranked AS (
  SELECT
    h.*,
    CASE
      WHEN h.country IS NOT NULL AND h.city IS NOT NULL THEN 1
      WHEN h.country IS NOT NULL AND h.city IS NULL THEN 2
      WHEN h.country IS NULL AND h.city IS NULL THEN 3
      ELSE 4
    END AS specificity_rank
  FROM ops.lob_homologation h
),
real_join AS (
  SELECT
    r.country,
    r.city,
    r.real_tipo_servicio,
    r.trips_count,
    hh.plan_lob_name,
    hh.confidence,
    hh.specificity_rank,
    ROW_NUMBER() OVER (
      PARTITION BY r.country, r.city, r.real_tipo_servicio
      ORDER BY hh.specificity_rank ASC, hh.created_at DESC NULLS LAST
    ) AS rn
  FROM real r
  LEFT JOIN h_ranked hh
    ON (hh.country IS NULL OR LOWER(TRIM(COALESCE(hh.country,''))) = LOWER(TRIM(COALESCE(r.country,''))))
   AND (hh.city IS NULL OR LOWER(TRIM(COALESCE(hh.city,''))) = LOWER(TRIM(COALESCE(r.city,''))))
   AND TRIM(LOWER(hh.real_tipo_servicio)) = TRIM(LOWER(r.real_tipo_servicio))
)
SELECT
  country,
  city,
  real_tipo_servicio,
  trips_count,
  CASE WHEN rn = 1 THEN TRIM(LOWER(plan_lob_name)) END AS plan_lob_name_norm,
  CASE WHEN rn = 1 THEN confidence END AS homologation_confidence
FROM real_join
WHERE rn = 1;

-- C) Vista final: directo + homologación + REAL_ONLY + PLAN_ONLY (UNION ALL)
DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check_resolved CASCADE;

CREATE OR REPLACE VIEW ops.v_plan_vs_real_lob_check_resolved AS
WITH plan AS (
  SELECT country, city, plan_lob_name_norm, plan_trips, plan_revenue
  FROM ops.v_plan_lob_agg
),
real_raw AS (
  SELECT country, city, real_tipo_servicio, trips_count
  FROM ops.mv_real_tipo_servicio_universe_fast
),
norm_plan AS (
  SELECT
    LOWER(TRIM(COALESCE(country,''))) AS country_norm,
    LOWER(TRIM(COALESCE(city,''))) AS city_norm,
    country,
    city,
    plan_lob_name_norm,
    plan_trips,
    plan_revenue
  FROM plan
),
norm_real AS (
  SELECT
    LOWER(TRIM(COALESCE(country,''))) AS country_norm,
    LOWER(TRIM(COALESCE(city,''))) AS city_norm,
    country,
    city,
    real_tipo_servicio,
    trips_count
  FROM real_raw
),
direct_match AS (
  SELECT
    p.country,
    p.city,
    p.plan_lob_name_norm,
    p.plan_trips,
    p.plan_revenue,
    r.real_tipo_servicio,
    r.trips_count AS real_trips,
    'DIRECT' AS resolution_method
  FROM norm_plan p
  JOIN norm_real r
    ON r.country_norm = p.country_norm
   AND r.city_norm = p.city_norm
   AND TRIM(LOWER(r.real_tipo_servicio)) = p.plan_lob_name_norm
),
plan_direct_miss AS (
  SELECT p.country, p.city, p.plan_lob_name_norm, p.plan_trips, p.plan_revenue
  FROM norm_plan p
  LEFT JOIN direct_match d
    ON d.country = p.country AND (d.city IS NOT DISTINCT FROM p.city)
   AND d.plan_lob_name_norm = p.plan_lob_name_norm
  WHERE d.plan_lob_name_norm IS NULL
),
real_to_plan AS (
  SELECT country, city, real_tipo_servicio, trips_count, plan_lob_name_norm
  FROM ops.v_real_to_plan_lob_resolved
  WHERE plan_lob_name_norm IS NOT NULL
),
homologation_match AS (
  SELECT
    p.country,
    p.city,
    p.plan_lob_name_norm,
    p.plan_trips,
    p.plan_revenue,
    rtp.real_tipo_servicio,
    rtp.trips_count AS real_trips,
    'HOMOLOGATION' AS resolution_method
  FROM plan_direct_miss p
  JOIN real_to_plan rtp
    ON LOWER(TRIM(COALESCE(rtp.country,''))) = LOWER(TRIM(COALESCE(p.country,'')))
   AND LOWER(TRIM(COALESCE(rtp.city,''))) = LOWER(TRIM(COALESCE(p.city,'')))
   AND rtp.plan_lob_name_norm = p.plan_lob_name_norm
),
plan_side AS (
  SELECT * FROM direct_match
  UNION ALL
  SELECT * FROM homologation_match
),
real_mapped AS (
  SELECT country, city, real_tipo_servicio FROM plan_side
),
real_only AS (
  SELECT
    r.country,
    r.city,
    NULL::TEXT AS plan_lob_name_norm,
    0::NUMERIC AS plan_trips,
    0::NUMERIC AS plan_revenue,
    r.real_tipo_servicio,
    r.trips_count AS real_trips,
    'NONE' AS resolution_method
  FROM real_raw r
  LEFT JOIN real_mapped m
    ON LOWER(TRIM(COALESCE(m.country,''))) = LOWER(TRIM(COALESCE(r.country,'')))
   AND LOWER(TRIM(COALESCE(m.city,''))) = LOWER(TRIM(COALESCE(r.city,'')))
   AND m.real_tipo_servicio = r.real_tipo_servicio
  WHERE m.real_tipo_servicio IS NULL
),
plan_mapped AS (
  SELECT country, city, plan_lob_name_norm FROM plan_side
),
plan_only AS (
  SELECT
    p.country,
    p.city,
    p.plan_lob_name_norm,
    p.plan_trips,
    p.plan_revenue,
    NULL::TEXT AS real_tipo_servicio,
    0::NUMERIC AS real_trips,
    'NONE' AS resolution_method
  FROM plan p
  LEFT JOIN plan_mapped pm
    ON LOWER(TRIM(COALESCE(pm.country,''))) = LOWER(TRIM(COALESCE(p.country,'')))
   AND LOWER(TRIM(COALESCE(pm.city,''))) = LOWER(TRIM(COALESCE(p.city,'')))
   AND pm.plan_lob_name_norm = p.plan_lob_name_norm
  WHERE pm.plan_lob_name_norm IS NULL
),
combined AS (
  SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips, resolution_method FROM plan_side
  UNION ALL
  SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips, resolution_method FROM real_only
  UNION ALL
  SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips, resolution_method FROM plan_only
)
SELECT
  country,
  city,
  plan_lob_name_norm,
  real_tipo_servicio,
  plan_trips,
  plan_revenue,
  real_trips,
  CASE
    WHEN plan_lob_name_norm IS NOT NULL AND real_tipo_servicio IS NOT NULL THEN 'OK'
    WHEN plan_lob_name_norm IS NOT NULL AND real_tipo_servicio IS NULL THEN 'PLAN_ONLY'
    WHEN plan_lob_name_norm IS NULL AND real_tipo_servicio IS NOT NULL THEN 'REAL_ONLY'
    ELSE 'UNKNOWN'
  END AS coverage_status,
  resolution_method
FROM combined;
