-- PASO 3 E2E: Plan canónico en DB + Plan vs Real por LOB
-- Ejecutar en orden. Staging usa lob_name (mapeo desde CSV lob_base).

-- A) Tabla canónica del plan
CREATE SCHEMA IF NOT EXISTS plan;

CREATE TABLE IF NOT EXISTS plan.plan_lob_long (
  country TEXT NOT NULL,
  city TEXT,
  plan_lob_base TEXT NOT NULL,
  segment TEXT,
  period_date DATE NOT NULL,
  trips_plan NUMERIC,
  active_drivers_plan NUMERIC,
  avg_ticket_plan NUMERIC,
  revenue_plan NUMERIC,
  trips_per_driver_plan NUMERIC,
  created_at TIMESTAMP DEFAULT now()
);

-- B) Rebuild idempotente desde staging (lob_name en staging = lob_base del CSV)
TRUNCATE plan.plan_lob_long;

INSERT INTO plan.plan_lob_long (
  country, city, plan_lob_base, segment, period_date,
  trips_plan, active_drivers_plan, avg_ticket_plan, revenue_plan, trips_per_driver_plan
)
SELECT
  country,
  city,
  TRIM(LOWER(COALESCE(lob_name, ''))) AS plan_lob_base,
  NULLIF(TRIM(raw_row->>'segment'), '') AS segment,
  period_date,
  trips_plan,
  NULLIF(TRIM(raw_row->>'active_drivers_plan'), '')::NUMERIC AS active_drivers_plan,
  NULLIF(TRIM(raw_row->>'avg_ticket_plan'), '')::NUMERIC AS avg_ticket_plan,
  revenue_plan,
  NULLIF(TRIM(raw_row->>'trips_per_driver_plan'), '')::NUMERIC AS trips_per_driver_plan
FROM staging.plan_projection_raw
WHERE lob_name IS NOT NULL AND TRIM(lob_name) <> '' AND period_date IS NOT NULL;

-- C) Poblar ops.lob_catalog desde plan.plan_lob_long (source='plan')
INSERT INTO ops.lob_catalog (lob_name, country, city, description, status, source)
SELECT
  plan_lob_base AS lob_name,
  country,
  city,
  NULL AS description,
  'active' AS status,
  'plan' AS source
FROM plan.plan_lob_long
GROUP BY plan_lob_base, country, city
ON CONFLICT (lob_name, country, city) DO NOTHING;

-- D) Vista Plan vs Real: match directo + fallback homologación
DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check CASCADE;

CREATE OR REPLACE VIEW ops.v_plan_vs_real_lob_check AS
WITH real AS (
  SELECT
    r.country,
    r.city,
    TRIM(LOWER(r.real_tipo_servicio)) AS real_tipo_servicio_norm,
    SUM(r.trips_count) AS real_trips
  FROM ops.v_real_tipo_servicio_universe r
  GROUP BY r.country, r.city, TRIM(LOWER(r.real_tipo_servicio))
),
plan AS (
  SELECT
    p.country,
    p.city,
    TRIM(LOWER(p.plan_lob_base)) AS plan_lob_base_norm,
    SUM(p.trips_plan) AS plan_trips,
    SUM(p.revenue_plan) AS plan_revenue
  FROM plan.plan_lob_long p
  GROUP BY p.country, p.city, TRIM(LOWER(p.plan_lob_base))
),
real_to_planname AS (
  SELECT
    country,
    city,
    TRIM(LOWER(real_tipo_servicio)) AS real_tipo_servicio_norm,
    TRIM(LOWER(plan_lob_name)) AS plan_lob_name_norm
  FROM ops.lob_homologation
),
real_resolved AS (
  SELECT
    r.country,
    r.city,
    COALESCE(rtp.plan_lob_name_norm, r.real_tipo_servicio_norm) AS resolved_plan_norm,
    SUM(r.real_trips) AS real_trips
  FROM real r
  LEFT JOIN real_to_planname rtp
    ON rtp.country = r.country
   AND (rtp.city IS NOT DISTINCT FROM r.city)
   AND rtp.real_tipo_servicio_norm = r.real_tipo_servicio_norm
  GROUP BY r.country, r.city, COALESCE(rtp.plan_lob_name_norm, r.real_tipo_servicio_norm)
)
SELECT
  COALESCE(pl.country, rl.country) AS country,
  COALESCE(pl.city, rl.city) AS city,
  COALESCE(pl.plan_lob_base_norm, rl.resolved_plan_norm) AS lob_name_norm,
  CASE WHEN pl.plan_lob_base_norm IS NOT NULL THEN true ELSE false END AS exists_in_plan,
  CASE WHEN rl.resolved_plan_norm IS NOT NULL THEN true ELSE false END AS exists_in_real,
  COALESCE(pl.plan_trips, 0) AS plan_trips,
  COALESCE(rl.real_trips, 0) AS real_trips,
  COALESCE(pl.plan_revenue, 0) AS plan_revenue,
  CASE
    WHEN pl.plan_lob_base_norm IS NOT NULL AND rl.resolved_plan_norm IS NOT NULL THEN 'OK'
    WHEN pl.plan_lob_base_norm IS NOT NULL AND rl.resolved_plan_norm IS NULL THEN 'PLAN_ONLY'
    WHEN pl.plan_lob_base_norm IS NULL AND rl.resolved_plan_norm IS NOT NULL THEN 'REAL_ONLY'
    ELSE 'UNKNOWN'
  END AS coverage_status
FROM plan pl
FULL OUTER JOIN real_resolved rl
  ON rl.country = pl.country
 AND (rl.city IS NOT DISTINCT FROM pl.city)
 AND rl.resolved_plan_norm = pl.plan_lob_base_norm;
