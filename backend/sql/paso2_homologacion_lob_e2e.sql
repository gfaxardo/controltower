-- PASO 2 E2E - Homologación LOB PLAN vs REAL
-- Ejecutar con statement_timeout alto si trips_all es grande.
-- SET statement_timeout = '300s';

-- 0) v_real_tipo_servicio_universe ya existe en migración 021 (usa dim_park + fecha_inicio_viaje).
--    Si tu esquema tiene trips_all con country, city, trip_date puedes reemplazar con:
/*
CREATE OR REPLACE VIEW ops.v_real_tipo_servicio_universe AS
SELECT
  country,
  city,
  tipo_servicio AS real_tipo_servicio,
  COUNT(*) AS trips_count,
  MIN(trip_date) AS first_seen_date,
  MAX(trip_date) AS last_seen_date
FROM trips_all
WHERE tipo_servicio IS NOT NULL
GROUP BY 1,2,3;
*/

-- 1) Staging (ya en 021)
CREATE SCHEMA IF NOT EXISTS staging;
CREATE TABLE IF NOT EXISTS staging.plan_projection_raw (
  plan_raw_id SERIAL PRIMARY KEY,
  country TEXT,
  city TEXT,
  lob_name TEXT,
  period_date DATE,
  trips_plan NUMERIC,
  revenue_plan NUMERIC,
  raw_row JSONB,
  loaded_at TIMESTAMP DEFAULT now()
);

-- 2) Vista universo plan (ya en 021)
DROP VIEW IF EXISTS ops.v_plan_lob_universe_raw CASCADE;
CREATE OR REPLACE VIEW ops.v_plan_lob_universe_raw AS
SELECT
  country,
  city,
  TRIM(LOWER(lob_name)) AS plan_lob_name,
  SUM(trips_plan) AS trips_plan,
  SUM(revenue_plan) AS revenue_plan,
  MIN(period_date) AS first_period,
  MAX(period_date) AS last_period
FROM staging.plan_projection_raw
WHERE lob_name IS NOT NULL
GROUP BY 1,2,3;

-- 3) Tabla homologación (ya en 021)
CREATE TABLE IF NOT EXISTS ops.lob_homologation (
  homologation_id SERIAL PRIMARY KEY,
  country TEXT,
  city TEXT,
  real_tipo_servicio TEXT NOT NULL,
  plan_lob_name TEXT NOT NULL,
  confidence TEXT CHECK (confidence IN ('high','medium','low')) DEFAULT 'medium',
  notes TEXT,
  created_at TIMESTAMP DEFAULT now(),
  UNIQUE(country, city, real_tipo_servicio, plan_lob_name)
);

-- 4) Vista sugerencias ya existe en migración 021 (v_lob_homologation_suggestions).

-- 5) Inserción solo matches exactos
INSERT INTO ops.lob_homologation (country, city, real_tipo_servicio, plan_lob_name, confidence, notes)
SELECT s.country, s.city, s.real_tipo_servicio, s.plan_lob_name, 'high', 'auto exact match'
FROM ops.v_lob_homologation_suggestions s
WHERE s.suggested_confidence = 'high'
ON CONFLICT (country, city, real_tipo_servicio, plan_lob_name) DO NOTHING;

-- 6) Gap: Real sin homologación (top 200)
-- SELECT u.* FROM ops.v_real_tipo_servicio_universe u
-- LEFT JOIN ops.lob_homologation h ON (h.country IS NULL OR h.country = u.country) AND (h.city IS NULL OR h.city = u.city) AND TRIM(LOWER(h.real_tipo_servicio)) = TRIM(LOWER(u.real_tipo_servicio))
-- WHERE h.homologation_id IS NULL ORDER BY u.trips_count DESC LIMIT 200;

-- 7) Gap: Plan sin homologación (top 200)
-- SELECT p.* FROM ops.v_plan_lob_universe_raw p
-- LEFT JOIN ops.lob_homologation h ON (h.country IS NULL OR h.country = p.country) AND (h.city IS NULL OR h.city = p.city) AND TRIM(LOWER(h.plan_lob_name)) = TRIM(LOWER(p.plan_lob_name))
-- WHERE h.homologation_id IS NULL ORDER BY p.trips_plan DESC LIMIT 200;
