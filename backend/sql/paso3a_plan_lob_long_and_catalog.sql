-- PASO 3A E2E: plan.plan_lob_long + ops.lob_catalog desde staging

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

INSERT INTO ops.lob_catalog (lob_name, country, city, description, status, source)
SELECT
  plan_lob_base AS lob_name,
  country,
  city,
  NULL,
  'active',
  'plan'
FROM plan.plan_lob_long
GROUP BY plan_lob_base, country, city
ON CONFLICT (lob_name, country, city) DO NOTHING;
