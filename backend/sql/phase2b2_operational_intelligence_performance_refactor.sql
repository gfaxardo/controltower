-- ═══════════════════════════════════════════════════════════════════════
-- FASE 2B.2: MATERIALIZED PERFORMANCE REFACTOR
-- Operational Behavioral Intelligence
--
-- Crea 3 facts materializadas para reemplazar VIEWs 64M+ en runtime:
--   A. ops.driver_trip_behavior_daily_fact   (daily grain)
--   B. ops.driver_zone_behavior_daily_fact   (daily × zone grain)
--   C. ops.driver_time_behavior_hourly_fact  (daily × hour grain)
--
-- Aditivo: no dropea views/tablas existentes.
-- Fuente primaria: ops.v_real_trips_enriched_base
-- ═══════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════
-- A. DRIVER TRIP BEHAVIOR DAILY FACT
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS ops.driver_trip_behavior_daily_fact (
    driver_id                VARCHAR NOT NULL,
    activity_date            DATE NOT NULL,
    country                  TEXT,
    city                     TEXT,
    park_id                  VARCHAR,
    trips                    INTEGER DEFAULT 0,
    cancelled_trips          INTEGER DEFAULT 0,
    revenue                  NUMERIC(14,2) DEFAULT 0,
    distance_km              NUMERIC(10,2) DEFAULT 0,
    duration_min             NUMERIC(10,1) DEFAULT 0,
    peak_hour_trips          INTEGER DEFAULT 0,
    weekend_trips            INTEGER DEFAULT 0,
    weekday_trips            INTEGER DEFAULT 0,
    avg_ticket               NUMERIC(10,2),
    revenue_per_trip         NUMERIC(10,2),
    revenue_per_hour_proxy   NUMERIC(10,2),
    revenue_per_km           NUMERIC(10,2),
    trips_per_hour_proxy     NUMERIC(10,4),
    last_refreshed_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (driver_id, activity_date, park_id)
);

-- Indexes for daily fact
CREATE INDEX IF NOT EXISTS idx_dtbdf_activity_date   ON ops.driver_trip_behavior_daily_fact (activity_date);
CREATE INDEX IF NOT EXISTS idx_dtbdf_driver_id       ON ops.driver_trip_behavior_daily_fact (driver_id);
CREATE INDEX IF NOT EXISTS idx_dtbdf_country_city_date ON ops.driver_trip_behavior_daily_fact (country, city, activity_date);
CREATE INDEX IF NOT EXISTS idx_dtbdf_driver_date     ON ops.driver_trip_behavior_daily_fact (driver_id, activity_date);


-- ═══════════════════════════════════════
-- B. DRIVER ZONE BEHAVIOR DAILY FACT
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS ops.driver_zone_behavior_daily_fact (
    driver_id                VARCHAR NOT NULL,
    activity_date            DATE NOT NULL,
    country                  TEXT,
    city                     TEXT,
    zone_key                 VARCHAR NOT NULL,
    zone_type                VARCHAR DEFAULT 'park_id',
    trips                    INTEGER DEFAULT 0,
    cancelled_trips          INTEGER DEFAULT 0,
    revenue                  NUMERIC(14,2) DEFAULT 0,
    distance_km              NUMERIC(10,2) DEFAULT 0,
    duration_min             NUMERIC(10,1) DEFAULT 0,
    peak_hour_trips          INTEGER DEFAULT 0,
    weekend_trips            INTEGER DEFAULT 0,
    weekday_trips            INTEGER DEFAULT 0,
    active_driver_flag       BOOLEAN DEFAULT TRUE,
    last_refreshed_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (driver_id, activity_date, zone_key)
);

-- Indexes for zone daily fact
CREATE INDEX IF NOT EXISTS idx_dzbdf_activity_date   ON ops.driver_zone_behavior_daily_fact (activity_date);
CREATE INDEX IF NOT EXISTS idx_dzbdf_driver_id       ON ops.driver_zone_behavior_daily_fact (driver_id);
CREATE INDEX IF NOT EXISTS idx_dzbdf_zone_date       ON ops.driver_zone_behavior_daily_fact (zone_key, activity_date);
CREATE INDEX IF NOT EXISTS idx_dzbdf_country_city_date ON ops.driver_zone_behavior_daily_fact (country, city, activity_date);
CREATE INDEX IF NOT EXISTS idx_dzbdf_driver_date     ON ops.driver_zone_behavior_daily_fact (driver_id, activity_date);


-- ═══════════════════════════════════════
-- C. DRIVER TIME BEHAVIOR HOURLY FACT
-- ═══════════════════════════════════════

CREATE TABLE IF NOT EXISTS ops.driver_time_behavior_hourly_fact (
    driver_id                VARCHAR NOT NULL,
    activity_date            DATE NOT NULL,
    trip_hour                INTEGER NOT NULL,
    day_of_week              INTEGER NOT NULL,
    country                  TEXT,
    city                     TEXT,
    trips                    INTEGER DEFAULT 0,
    cancelled_trips          INTEGER DEFAULT 0,
    revenue                  NUMERIC(14,2) DEFAULT 0,
    distance_km              NUMERIC(10,2) DEFAULT 0,
    duration_min             NUMERIC(10,1) DEFAULT 0,
    is_peak_hour             BOOLEAN DEFAULT FALSE,
    is_weekend               BOOLEAN DEFAULT FALSE,
    last_refreshed_at        TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (driver_id, activity_date, trip_hour)
);

-- Indexes for hourly fact
CREATE INDEX IF NOT EXISTS idx_dthbf_activity_date   ON ops.driver_time_behavior_hourly_fact (activity_date);
CREATE INDEX IF NOT EXISTS idx_dthbf_driver_id       ON ops.driver_time_behavior_hourly_fact (driver_id);
CREATE INDEX IF NOT EXISTS idx_dthbf_hour_date       ON ops.driver_time_behavior_hourly_fact (trip_hour, activity_date);
CREATE INDEX IF NOT EXISTS idx_dthbf_country_city_date ON ops.driver_time_behavior_hourly_fact (country, city, activity_date);
CREATE INDEX IF NOT EXISTS idx_dthbf_driver_date     ON ops.driver_time_behavior_hourly_fact (driver_id, activity_date);


-- ═══════════════════════════════════════
-- POPULATION (template queries — executed by refresh script)
-- ═══════════════════════════════════════

-- Population query A: daily fact
-- INSERT INTO ops.driver_trip_behavior_daily_fact (...) SELECT ... FROM ops.v_real_trips_enriched_base WHERE trip_date >= ... GROUP BY ...

-- Population query B: zone daily fact
-- INSERT INTO ops.driver_zone_behavior_daily_fact (...) SELECT ... FROM ops.v_real_trips_enriched_base WHERE trip_date >= ... GROUP BY ...

-- Population query C: hourly fact
-- INSERT INTO ops.driver_time_behavior_hourly_fact (...) SELECT ... FROM ops.v_real_trips_enriched_base WHERE trip_date >= ... GROUP BY ...
