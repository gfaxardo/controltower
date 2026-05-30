-- =============================================================================
-- DRIVERS SERVING FACTS — SH2 (FIXED)
-- Real columns from ops.driver_daily_activity_fact:
--   driver_id, activity_date, country, city, park_id, completed_trips, source_year, last_refreshed_at
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS ops;

-- =============================================================================
-- 1. Weekly Segment Fact (driver x week_start)
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS ops.driver_weekly_segment_fact CASCADE;
CREATE MATERIALIZED VIEW ops.driver_weekly_segment_fact AS
SELECT
    adf.driver_id,
    date_trunc('week', adf.activity_date)::date AS week_start,
    COALESCE(NULLIF(MAX(adf.country), ''), MAX(p.country)) AS country,
    COALESCE(NULLIF(MAX(adf.city), ''), MAX(p.city)) AS city,
    MAX(adf.park_id) AS park_id,
    MAX(p.park_name) AS park_name,
    COALESCE(SUM(adf.completed_trips), 0) AS trips_completed,
    CASE
        WHEN COALESCE(SUM(adf.completed_trips), 0) = 0 THEN 'DORMANT'
        WHEN COALESCE(SUM(adf.completed_trips), 0) BETWEEN 1 AND 4 THEN 'OCCASIONAL'
        WHEN COALESCE(SUM(adf.completed_trips), 0) BETWEEN 5 AND 29 THEN 'CASUAL'
        WHEN COALESCE(SUM(adf.completed_trips), 0) BETWEEN 30 AND 59 THEN 'PT'
        WHEN COALESCE(SUM(adf.completed_trips), 0) BETWEEN 60 AND 119 THEN 'FT'
        WHEN COALESCE(SUM(adf.completed_trips), 0) BETWEEN 120 AND 179 THEN 'ELITE'
        WHEN COALESCE(SUM(adf.completed_trips), 0) >= 180 THEN 'LEGEND'
        ELSE 'DORMANT'
    END AS segment,
    NOW() AS refreshed_at
FROM ops.driver_daily_activity_fact adf
LEFT JOIN dim.dim_park p ON adf.park_id = p.park_id
GROUP BY adf.driver_id, date_trunc('week', adf.activity_date)::date;

-- =============================================================================
-- 2. Segment Migration Fact (driver x current_week_start)
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS ops.driver_segment_migration_fact CASCADE;
CREATE MATERIALIZED VIEW ops.driver_segment_migration_fact AS
SELECT
    curr.driver_id,
    curr.country,
    curr.city,
    curr.park_id,
    curr.park_name,
    prev.week_start AS previous_week_start,
    curr.week_start AS current_week_start,
    COALESCE(prev.segment, 'DORMANT') AS from_segment,
    curr.segment AS to_segment,
    COALESCE(prev.trips_completed, 0) AS trips_previous,
    curr.trips_completed AS trips_current,
    CASE
        WHEN prev.week_start IS NULL AND curr.trips_completed > 0 THEN 'NEW_ACTIVE'
        WHEN COALESCE(prev.trips_completed, 0) = 0 AND curr.trips_completed = 0 THEN 'CHURNED'
        WHEN COALESCE(prev.trips_completed, 0) = 0 AND curr.trips_completed > 0 THEN 'REACTIVATED'
        WHEN COALESCE(prev.trips_completed, 0) > 0 AND curr.trips_completed = 0 THEN 'BECAME_DORMANT'
        WHEN prev.segment = curr.segment THEN 'SAME_SEGMENT'
        WHEN ARRAY_POSITION(ARRAY['DORMANT','OCCASIONAL','CASUAL','PT','FT','ELITE','LEGEND'], COALESCE(prev.segment, 'DORMANT'))
           < ARRAY_POSITION(ARRAY['DORMANT','OCCASIONAL','CASUAL','PT','FT','ELITE','LEGEND'], curr.segment) THEN 'DOWNGRADE'
        ELSE 'UPGRADE'
    END AS movement_type,
    NOW() AS refreshed_at
FROM ops.driver_weekly_segment_fact curr
LEFT JOIN ops.driver_weekly_segment_fact prev
    ON curr.driver_id = prev.driver_id
    AND prev.week_start = curr.week_start - INTERVAL '7 days';

-- =============================================================================
-- 3. Operational Priority Fact (driver x week_start)
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS ops.driver_operational_priority_fact CASCADE;
CREATE MATERIALIZED VIEW ops.driver_operational_priority_fact AS
SELECT
    m.driver_id,
    m.current_week_start AS week_start,
    m.country,
    m.city,
    m.park_id,
    m.from_segment,
    m.to_segment,
    m.movement_type,
    (m.trips_current - m.trips_previous) AS delta_trips,
    CASE
        WHEN m.from_segment IN ('LEGEND','ELITE','FT') AND m.to_segment = 'DORMANT' THEN 'P0_CRITICAL'
        WHEN m.from_segment IN ('LEGEND','ELITE') AND m.movement_type = 'DOWNGRADE' THEN 'P0_CRITICAL'
        WHEN m.from_segment = 'FT' AND m.to_segment IN ('OCCASIONAL','CASUAL') THEN 'P1_HIGH'
        WHEN m.from_segment IN ('PT','CASUAL') AND m.to_segment = 'DORMANT' THEN 'P1_HIGH'
        WHEN m.movement_type = 'DOWNGRADE' THEN 'P2_MEDIUM'
        WHEN m.movement_type = 'BECAME_DORMANT' AND m.from_segment IN ('PT','FT','ELITE','LEGEND') THEN 'P1_HIGH'
        WHEN m.movement_type = 'BECAME_DORMANT' THEN 'P2_MEDIUM'
        WHEN m.movement_type IN ('UPGRADE','REACTIVATED','NEW_ACTIVE') THEN 'SUCCESS_TRACKING'
        WHEN m.from_segment IN ('FT','ELITE','LEGEND') AND m.movement_type = 'SAME_SEGMENT' THEN 'MONITOR'
        WHEN m.movement_type = 'SAME_SEGMENT' THEN 'P3_LOW'
        WHEN m.movement_type = 'CHURNED' THEN 'P3_LOW'
        ELSE 'P3_LOW'
    END AS operational_priority,
    CASE
        WHEN m.from_segment IN ('LEGEND','ELITE','FT') AND m.to_segment = 'DORMANT'
            THEN m.from_segment || ' became dormant. Severe loss.'
        WHEN m.from_segment IN ('LEGEND','ELITE') AND m.movement_type = 'DOWNGRADE'
            THEN 'Elite/' || m.from_segment || ' downgraded to ' || m.to_segment || '. Critical.'
        WHEN m.from_segment = 'FT' AND m.to_segment IN ('OCCASIONAL','CASUAL')
            THEN 'FT downgraded to ' || m.to_segment || '. High priority.'
        WHEN m.movement_type = 'DOWNGRADE'
            THEN m.from_segment || ' -> ' || m.to_segment || '. Decline detected.'
        WHEN m.movement_type = 'UPGRADE'
            THEN m.from_segment || ' -> ' || m.to_segment || '. Positive momentum.'
        WHEN m.movement_type = 'REACTIVATED'
            THEN 'Reactivated to ' || m.to_segment || '. Success.'
        WHEN m.movement_type = 'SAME_SEGMENT' AND m.from_segment IN ('FT','ELITE','LEGEND')
            THEN 'Stable ' || m.from_segment || '. Monitor.'
        ELSE m.movement_type || ': ' || m.from_segment || ' -> ' || m.to_segment
    END AS operational_reason,
    CASE
        WHEN m.from_segment IN ('LEGEND','ELITE','FT') AND m.movement_type IN ('DOWNGRADE','BECAME_DORMANT') THEN 'HIGH'
        WHEN m.movement_type IN ('UPGRADE','REACTIVATED') THEN 'HIGH'
        WHEN m.movement_type = 'DOWNGRADE' THEN 'MEDIUM'
        WHEN m.movement_type = 'BECAME_DORMANT' THEN 'MEDIUM'
        WHEN m.movement_type = 'CHURNED' THEN 'LOW'
        ELSE 'UNKNOWN'
    END AS recoverability_band,
    CASE
        WHEN m.movement_type IN ('DOWNGRADE','BECAME_DORMANT') AND m.from_segment IN ('LEGEND','ELITE','FT')
            THEN 'RECOVERY_P0'
        WHEN m.movement_type = 'DOWNGRADE' THEN 'HIGH_VALUE_RECOVERY'
        WHEN m.movement_type = 'BECAME_DORMANT' THEN 'REACTIVATION_STANDARD'
        WHEN m.movement_type IN ('UPGRADE','REACTIVATED') THEN 'SUCCESS_NURTURING'
        WHEN m.movement_type = 'SAME_SEGMENT' AND m.from_segment IN ('FT','ELITE','LEGEND') THEN 'MONITOR_ONLY'
        ELSE 'MONITOR_ONLY'
    END AS recommended_queue,
    '24h' AS recommended_contact_window,
    NOW() AS refreshed_at
FROM ops.driver_segment_migration_fact m;

-- =============================================================================
-- 4. Supply Overview Weekly Fact (week_start x country x city x park_id)
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS ops.driver_supply_overview_weekly_fact CASCADE;
CREATE MATERIALIZED VIEW ops.driver_supply_overview_weekly_fact AS
WITH weekly_stats AS (
    SELECT
        week_start,
        COALESCE(country, 'Unknown') AS country,
        COALESCE(city, 'Unknown') AS city,
        COALESCE(park_id, 'Unknown') AS park_id,
        MAX(park_name) AS park_name,
        COUNT(DISTINCT driver_id) AS active_drivers,
        SUM(trips_completed) AS trips
    FROM ops.driver_weekly_segment_fact
    WHERE trips_completed > 0
    GROUP BY week_start, country, city, park_id
)
SELECT
    ws.week_start,
    ws.country,
    ws.city,
    ws.park_id,
    ws.park_name,
    ws.active_drivers,
    ws.trips,
    COALESCE(ch.churned, 0) AS churned,
    COALESCE(rea.reactivated, 0) AS reactivated,
    NULL::integer AS activations,
    (COALESCE(rea.reactivated, 0) - COALESCE(ch.churned, 0)) AS net_growth,
    NOW() AS refreshed_at
FROM weekly_stats ws
LEFT JOIN (
    SELECT week_start, country, city, park_id, COUNT(DISTINCT driver_id) AS churned
    FROM ops.driver_weekly_segment_fact WHERE trips_completed = 0
    GROUP BY week_start, country, city, park_id
) ch ON ws.week_start = ch.week_start AND ws.country = ch.country AND ws.city = ch.city AND ws.park_id = ch.park_id
LEFT JOIN (
    SELECT current_week_start AS week_start, country, city, park_id, COUNT(DISTINCT driver_id) AS reactivated
    FROM ops.driver_segment_migration_fact WHERE movement_type IN ('REACTIVATED','NEW_ACTIVE')
    GROUP BY current_week_start, country, city, park_id
) rea ON ws.week_start = rea.week_start AND ws.country = rea.country AND ws.city = rea.city AND ws.park_id = rea.park_id;

-- =============================================================================
-- 5. Serving Freshness Fact
-- =============================================================================
DROP MATERIALIZED VIEW IF EXISTS ops.driver_serving_freshness_fact CASCADE;
CREATE MATERIALIZED VIEW ops.driver_serving_freshness_fact AS
SELECT 'driver_weekly_segment_fact' AS fact_name, MAX(week_start) AS max_operational_period,
    COUNT(*) AS row_count, MAX(refreshed_at) AS refreshed_at,
    CASE WHEN MAX(refreshed_at) IS NULL THEN 'blocked'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '7 days' THEN 'stale'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '2 days' THEN 'warning'
         ELSE 'fresh' END AS freshness_status,
    'From driver_weekly_segment_fact' AS freshness_reason
FROM ops.driver_weekly_segment_fact
UNION ALL
SELECT 'driver_segment_migration_fact', MAX(current_week_start), COUNT(*), MAX(refreshed_at),
    CASE WHEN MAX(refreshed_at) IS NULL THEN 'blocked'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '7 days' THEN 'stale'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '2 days' THEN 'warning'
         ELSE 'fresh' END, 'From migration_fact'
FROM ops.driver_segment_migration_fact
UNION ALL
SELECT 'driver_operational_priority_fact', MAX(week_start), COUNT(*), MAX(refreshed_at),
    CASE WHEN MAX(refreshed_at) IS NULL THEN 'blocked'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '7 days' THEN 'stale'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '2 days' THEN 'warning'
         ELSE 'fresh' END, 'From priority_fact'
FROM ops.driver_operational_priority_fact
UNION ALL
SELECT 'driver_supply_overview_weekly_fact', MAX(week_start), COUNT(*), MAX(refreshed_at),
    CASE WHEN MAX(refreshed_at) IS NULL THEN 'blocked'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '7 days' THEN 'stale'
         WHEN MAX(refreshed_at) < NOW() - INTERVAL '2 days' THEN 'warning'
         ELSE 'fresh' END, 'From supply_overview_fact'
FROM ops.driver_supply_overview_weekly_fact;

-- =============================================================================
-- INDEXES
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_wsf_driver_week ON ops.driver_weekly_segment_fact(driver_id, week_start);
CREATE INDEX IF NOT EXISTS idx_wsf_geo_week ON ops.driver_weekly_segment_fact(country, city, park_id, week_start);
CREATE INDEX IF NOT EXISTS idx_smf_week_movement ON ops.driver_segment_migration_fact(current_week_start, movement_type);
CREATE INDEX IF NOT EXISTS idx_smf_driver_week ON ops.driver_segment_migration_fact(driver_id, current_week_start);
CREATE INDEX IF NOT EXISTS idx_opf_week_priority ON ops.driver_operational_priority_fact(week_start, operational_priority);
CREATE INDEX IF NOT EXISTS idx_opf_driver_week ON ops.driver_operational_priority_fact(driver_id, week_start);
CREATE INDEX IF NOT EXISTS idx_sof_week_geo ON ops.driver_supply_overview_weekly_fact(week_start, country, city, park_id);
