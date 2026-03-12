"""
Segment taxonomy: add ELITE (120-179), LEGEND (180+); cap FT at 60-119.
Recreate mv_driver_segments_weekly (and chain) using ordering from driver_segment_config
instead of hardcoded CASE, so future segments are supported.
Non-destructive: only INSERT and UPDATE config; no DROP of columns/tables.
"""
from alembic import op

revision = "078_segment_taxonomy_elite_legend"
down_revision = "077_audit_views_24month"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add ELITE and LEGEND to config; cap FT at 60-119
    op.execute("""
        INSERT INTO ops.driver_segment_config (segment_code, segment_name, min_trips_week, max_trips_week, ordering, is_active, effective_from, effective_to)
        SELECT 'ELITE', 'Elite', 120, 179, 6, true, '1970-01-01'::date, NULL
        WHERE NOT EXISTS (SELECT 1 FROM ops.driver_segment_config WHERE segment_code = 'ELITE' AND effective_from = '1970-01-01')
    """)
    op.execute("""
        INSERT INTO ops.driver_segment_config (segment_code, segment_name, min_trips_week, max_trips_week, ordering, is_active, effective_from, effective_to)
        SELECT 'LEGEND', 'Legend', 180, NULL, 7, true, '1970-01-01'::date, NULL
        WHERE NOT EXISTS (SELECT 1 FROM ops.driver_segment_config WHERE segment_code = 'LEGEND' AND effective_from = '1970-01-01')
    """)
    op.execute("""
        UPDATE ops.driver_segment_config
        SET max_trips_week = 119, updated_at = now()
        WHERE segment_code = 'FT' AND (effective_to IS NULL OR effective_to >= CURRENT_DATE) AND (max_trips_week IS NULL OR max_trips_week > 119)
    """)

    # 2) Recreate MVs: drop in reverse dependency order
    op.execute("DROP VIEW IF EXISTS ops.v_supply_alert_drilldown CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_alerts_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_segment_anomalies_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_segments_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_segments_weekly CASCADE")

    # 3) mv_driver_segments_weekly: ord/prev_ord from config (no hardcoded CASE)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_segments_weekly AS
        WITH seg AS (
            SELECT DISTINCT ON (s.driver_key, s.week_start)
                s.driver_key,
                s.week_start,
                s.park_id,
                s.trips_completed_week,
                c.segment_code AS segment_week
            FROM ops.mv_driver_weekly_stats s
            JOIN ops.driver_segment_config c ON c.is_active
              AND c.effective_from <= s.week_start
              AND (c.effective_to IS NULL OR c.effective_to >= s.week_start)
              AND s.trips_completed_week >= c.min_trips_week
              AND (c.max_trips_week IS NULL OR s.trips_completed_week <= c.max_trips_week)
            ORDER BY s.driver_key, s.week_start, c.ordering DESC
        ),
        with_prev AS (
            SELECT
                driver_key,
                week_start,
                park_id,
                trips_completed_week,
                segment_week,
                LAG(segment_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS prev_segment_week,
                LAG(trips_completed_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS prev_trips,
                COUNT(*) FILTER (WHERE trips_completed_week > 0) OVER w4 AS weeks_active_rolling_4w,
                AVG(trips_completed_week) OVER w4prev AS baseline_trips_4w_avg
            FROM seg
            WINDOW
                w4 AS (PARTITION BY driver_key ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW),
                w4prev AS (PARTITION BY driver_key ORDER BY week_start ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
        ),
        segment_ord AS (
            SELECT
                wp.*,
                (SELECT c.ordering FROM ops.driver_segment_config c
                 WHERE c.segment_code = wp.segment_week AND c.is_active
                   AND c.effective_from <= wp.week_start
                   AND (c.effective_to IS NULL OR c.effective_to >= wp.week_start)
                 ORDER BY c.ordering DESC LIMIT 1) AS ord,
                (SELECT c.ordering FROM ops.driver_segment_config c
                 WHERE c.segment_code = wp.prev_segment_week AND c.is_active
                   AND c.effective_from <= wp.week_start
                   AND (c.effective_to IS NULL OR c.effective_to >= wp.week_start)
                 ORDER BY c.ordering DESC LIMIT 1) AS prev_ord
            FROM with_prev wp
        )
        SELECT
            driver_key,
            week_start,
            park_id,
            trips_completed_week,
            segment_week,
            prev_segment_week,
            CASE
                WHEN prev_segment_week IS NOT NULL AND segment_week = 'DORMANT' THEN 'drop'
                WHEN prev_segment_week IS NOT NULL AND COALESCE(ord, 0) < COALESCE(prev_ord, 0) THEN 'downshift'
                WHEN prev_segment_week IS NOT NULL AND COALESCE(ord, 0) > COALESCE(prev_ord, 0) THEN 'upshift'
                WHEN prev_segment_week IS NOT NULL AND COALESCE(ord, 0) = COALESCE(prev_ord, 0) THEN 'stable'
                ELSE 'new'
            END AS segment_change_type,
            COALESCE(weeks_active_rolling_4w, 0)::int AS weeks_active_rolling_4w,
            baseline_trips_4w_avg
        FROM segment_ord
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_segments_weekly_driver_week
        ON ops.mv_driver_segments_weekly (driver_key, week_start)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_segments_weekly_park_week
        ON ops.mv_driver_segments_weekly (park_id, week_start)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_segments_weekly AS
        WITH agg AS (
            SELECT
                week_start,
                park_id,
                segment_week,
                COUNT(*)::bigint AS drivers_count,
                SUM(trips_completed_week)::bigint AS trips_sum
            FROM ops.mv_driver_segments_weekly
            WHERE park_id IS NOT NULL
            GROUP BY week_start, park_id, segment_week
        ),
        active_total AS (
            SELECT
                week_start,
                park_id,
                SUM(drivers_count) FILTER (WHERE segment_week != 'DORMANT') AS active_drivers
            FROM agg
            GROUP BY week_start, park_id
        ),
        geo AS (
            SELECT park_id, park_name, city, country FROM dim.v_geo_park
        )
        SELECT
            a.week_start,
            a.park_id,
            COALESCE(g.park_name, a.park_id::text) AS park_name,
            COALESCE(g.city, 'UNKNOWN') AS city,
            COALESCE(g.country, 'UNKNOWN') AS country,
            a.segment_week,
            a.drivers_count,
            a.trips_sum,
            CASE WHEN COALESCE(t.active_drivers, 0) > 0
                THEN ROUND(100.0 * a.drivers_count / NULLIF(t.active_drivers, 0), 4) ELSE NULL END AS share_of_active
        FROM agg a
        LEFT JOIN active_total t ON t.week_start = a.week_start AND t.park_id = a.park_id
        LEFT JOIN geo g ON g.park_id = a.park_id
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_supply_segments_weekly_week_park_segment
        ON ops.mv_supply_segments_weekly (week_start, park_id, segment_week)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segments_weekly_park_week
        ON ops.mv_supply_segments_weekly (park_id, week_start)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segments_weekly_country_city_week
        ON ops.mv_supply_segments_weekly (country, city, week_start)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_segment_anomalies_weekly AS
        WITH base AS (
            SELECT
                week_start,
                park_id,
                park_name,
                city,
                country,
                segment_week,
                drivers_count,
                AVG(drivers_count) OVER w8 AS baseline_avg,
                STDDEV_POP(drivers_count) OVER w8 AS baseline_std
            FROM ops.mv_supply_segments_weekly
            WINDOW w8 AS (
                PARTITION BY park_id, segment_week
                ORDER BY week_start
                ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
            )
        ),
        with_delta AS (
            SELECT
                *,
                drivers_count - baseline_avg AS delta_abs,
                (drivers_count - baseline_avg) / NULLIF(baseline_avg, 0) AS delta_pct,
                (drivers_count - baseline_avg) / NULLIF(baseline_std, 0) AS z_score
            FROM base
            WHERE baseline_avg IS NOT NULL AND baseline_avg >= 30
        ),
        with_flags AS (
            SELECT
                *,
                (delta_pct <= -0.15) AS is_drop,
                (delta_pct >= 0.20) AS is_spike,
                CASE
                    WHEN delta_pct <= -0.30 OR z_score <= -3 THEN 'P0'
                    WHEN delta_pct <= -0.20 OR z_score <= -2 THEN 'P1'
                    WHEN delta_pct <= -0.15 OR z_score <= -1.5 THEN 'P2'
                    WHEN delta_pct >= 0.20 THEN 'P3'
                    ELSE NULL
                END AS severity
            FROM with_delta
        )
        SELECT
            week_start,
            park_id,
            park_name,
            city,
            country,
            segment_week,
            drivers_count AS current_value,
            baseline_avg,
            baseline_std,
            delta_abs,
            delta_pct,
            z_score,
            is_drop,
            is_spike,
            severity
        FROM with_flags
        WHERE is_drop OR is_spike
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_supply_segment_anomalies_week_park_segment
        ON ops.mv_supply_segment_anomalies_weekly (week_start, park_id, segment_week)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segment_anomalies_week_desc
        ON ops.mv_supply_segment_anomalies_weekly (week_start DESC)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segment_anomalies_park_week_desc
        ON ops.mv_supply_segment_anomalies_weekly (park_id, week_start DESC)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_alerts_weekly AS
        SELECT
            md5(week_start::text || COALESCE(park_id::text, '') || segment_week::text || alert_type) AS alert_id,
            week_start,
            park_id,
            park_name,
            city,
            country,
            segment_week,
            alert_type,
            severity,
            baseline_avg,
            current_value,
            delta_pct,
            message_short,
            recommended_action
        FROM (
            SELECT
                week_start,
                park_id,
                park_name,
                city,
                country,
                segment_week,
                'segment_drop' AS alert_type,
                severity,
                baseline_avg,
                current_value,
                delta_pct,
                segment_week || ' cayó ' || ROUND((delta_pct * 100)::numeric, 0)::text || '% vs baseline 8w' AS message_short,
                CASE segment_week
                    WHEN 'FT' THEN 'Revisar tarifas, incentivos, competencia; listar top drivers downshift/dormant'
                    WHEN 'PT' THEN 'Revisar fricción operativa / app / bloqueos'
                    WHEN 'ELITE' THEN 'Revisar retención de conductores elite; incentivos y condiciones'
                    WHEN 'LEGEND' THEN 'Revisar retención de conductores legend (nivel alto); priorizar contacto'
                    ELSE 'Revisar engagement y campañas de reactivación'
                END AS recommended_action
            FROM ops.mv_supply_segment_anomalies_weekly
            WHERE is_drop
            UNION ALL
            SELECT
                week_start,
                park_id,
                park_name,
                city,
                country,
                segment_week,
                'segment_spike' AS alert_type,
                severity,
                baseline_avg,
                current_value,
                delta_pct,
                segment_week || ' subió +' || ROUND((delta_pct * 100)::numeric, 0)::text || '% vs baseline 8w (posible fuga o caída de incentivos)' AS message_short,
                'Activar campaña reactivación + call center' AS recommended_action
            FROM ops.mv_supply_segment_anomalies_weekly
            WHERE is_spike
        ) t
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_supply_alerts_weekly_id
        ON ops.mv_supply_alerts_weekly (week_start, park_id, segment_week, alert_type)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_alerts_weekly_week_desc
        ON ops.mv_supply_alerts_weekly (week_start DESC)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_alerts_weekly_park_week_desc
        ON ops.mv_supply_alerts_weekly (park_id, week_start DESC)
    """)

    op.execute("""
        CREATE VIEW ops.v_supply_alert_drilldown AS
        SELECT
            d.week_start,
            d.park_id,
            d.segment_week,
            d.driver_key,
            d.prev_segment_week,
            d.segment_week AS segment_week_current,
            d.trips_completed_week,
            d.baseline_trips_4w_avg,
            d.segment_change_type
        FROM ops.mv_driver_segments_weekly d
        WHERE d.park_id IS NOT NULL
          AND d.segment_change_type IN ('downshift', 'drop')
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_supply_alert_drilldown CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_alerts_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_segment_anomalies_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_segments_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_segments_weekly CASCADE")

    # Recreate 067-style MVs (hardcoded CASE for 5 segments)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_segments_weekly AS
        WITH seg AS (
            SELECT DISTINCT ON (s.driver_key, s.week_start)
                s.driver_key,
                s.week_start,
                s.park_id,
                s.trips_completed_week,
                c.segment_code AS segment_week
            FROM ops.mv_driver_weekly_stats s
            JOIN ops.driver_segment_config c ON c.is_active
              AND c.effective_from <= s.week_start
              AND (c.effective_to IS NULL OR c.effective_to >= s.week_start)
              AND s.trips_completed_week >= c.min_trips_week
              AND (c.max_trips_week IS NULL OR s.trips_completed_week <= c.max_trips_week)
            ORDER BY s.driver_key, s.week_start, c.ordering DESC
        ),
        with_prev AS (
            SELECT
                driver_key,
                week_start,
                park_id,
                trips_completed_week,
                segment_week,
                LAG(segment_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS prev_segment_week,
                LAG(trips_completed_week) OVER (PARTITION BY driver_key ORDER BY week_start) AS prev_trips,
                COUNT(*) FILTER (WHERE trips_completed_week > 0) OVER w4 AS weeks_active_rolling_4w,
                AVG(trips_completed_week) OVER w4prev AS baseline_trips_4w_avg
            FROM seg
            WINDOW
                w4 AS (PARTITION BY driver_key ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW),
                w4prev AS (PARTITION BY driver_key ORDER BY week_start ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
        ),
        segment_ord AS (
            SELECT
                *,
                CASE segment_week
                    WHEN 'FT' THEN 5 WHEN 'PT' THEN 4 WHEN 'CASUAL' THEN 3 WHEN 'OCCASIONAL' THEN 2 WHEN 'DORMANT' THEN 1 ELSE 0 END AS ord,
                CASE prev_segment_week
                    WHEN 'FT' THEN 5 WHEN 'PT' THEN 4 WHEN 'CASUAL' THEN 3 WHEN 'OCCASIONAL' THEN 2 WHEN 'DORMANT' THEN 1 ELSE 0 END AS prev_ord
            FROM with_prev
        )
        SELECT
            driver_key,
            week_start,
            park_id,
            trips_completed_week,
            segment_week,
            prev_segment_week,
            CASE
                WHEN prev_segment_week IS NOT NULL AND segment_week = 'DORMANT' THEN 'drop'
                WHEN prev_segment_week IS NOT NULL AND ord < prev_ord THEN 'downshift'
                WHEN prev_segment_week IS NOT NULL AND ord > prev_ord THEN 'upshift'
                WHEN prev_segment_week IS NOT NULL AND ord = prev_ord THEN 'stable'
                ELSE 'new'
            END AS segment_change_type,
            COALESCE(weeks_active_rolling_4w, 0)::int AS weeks_active_rolling_4w,
            baseline_trips_4w_avg
        FROM segment_ord
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_segments_weekly_driver_week
        ON ops.mv_driver_segments_weekly (driver_key, week_start)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_segments_weekly_park_week
        ON ops.mv_driver_segments_weekly (park_id, week_start)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_segments_weekly AS
        WITH agg AS (
            SELECT
                week_start,
                park_id,
                segment_week,
                COUNT(*)::bigint AS drivers_count,
                SUM(trips_completed_week)::bigint AS trips_sum
            FROM ops.mv_driver_segments_weekly
            WHERE park_id IS NOT NULL
            GROUP BY week_start, park_id, segment_week
        ),
        active_total AS (
            SELECT
                week_start,
                park_id,
                SUM(drivers_count) FILTER (WHERE segment_week != 'DORMANT') AS active_drivers
            FROM agg
            GROUP BY week_start, park_id
        ),
        geo AS (
            SELECT park_id, park_name, city, country FROM dim.v_geo_park
        )
        SELECT
            a.week_start,
            a.park_id,
            COALESCE(g.park_name, a.park_id::text) AS park_name,
            COALESCE(g.city, 'UNKNOWN') AS city,
            COALESCE(g.country, 'UNKNOWN') AS country,
            a.segment_week,
            a.drivers_count,
            a.trips_sum,
            CASE WHEN COALESCE(t.active_drivers, 0) > 0
                THEN ROUND(100.0 * a.drivers_count / NULLIF(t.active_drivers, 0), 4) ELSE NULL END AS share_of_active
        FROM agg a
        LEFT JOIN active_total t ON t.week_start = a.week_start AND t.park_id = a.park_id
        LEFT JOIN geo g ON g.park_id = a.park_id
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_supply_segments_weekly_week_park_segment
        ON ops.mv_supply_segments_weekly (week_start, park_id, segment_week)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segments_weekly_park_week
        ON ops.mv_supply_segments_weekly (park_id, week_start)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segments_weekly_country_city_week
        ON ops.mv_supply_segments_weekly (country, city, week_start)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_segment_anomalies_weekly AS
        WITH base AS (
            SELECT
                week_start,
                park_id,
                park_name,
                city,
                country,
                segment_week,
                drivers_count,
                AVG(drivers_count) OVER w8 AS baseline_avg,
                STDDEV_POP(drivers_count) OVER w8 AS baseline_std
            FROM ops.mv_supply_segments_weekly
            WINDOW w8 AS (
                PARTITION BY park_id, segment_week
                ORDER BY week_start
                ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
            )
        ),
        with_delta AS (
            SELECT
                *,
                drivers_count - baseline_avg AS delta_abs,
                (drivers_count - baseline_avg) / NULLIF(baseline_avg, 0) AS delta_pct,
                (drivers_count - baseline_avg) / NULLIF(baseline_std, 0) AS z_score
            FROM base
            WHERE baseline_avg IS NOT NULL AND baseline_avg >= 30
        ),
        with_flags AS (
            SELECT
                *,
                (delta_pct <= -0.15) AS is_drop,
                (delta_pct >= 0.20) AS is_spike,
                CASE
                    WHEN delta_pct <= -0.30 OR z_score <= -3 THEN 'P0'
                    WHEN delta_pct <= -0.20 OR z_score <= -2 THEN 'P1'
                    WHEN delta_pct <= -0.15 OR z_score <= -1.5 THEN 'P2'
                    WHEN delta_pct >= 0.20 THEN 'P3'
                    ELSE NULL
                END AS severity
            FROM with_delta
        )
        SELECT
            week_start,
            park_id,
            park_name,
            city,
            country,
            segment_week,
            drivers_count AS current_value,
            baseline_avg,
            baseline_std,
            delta_abs,
            delta_pct,
            z_score,
            is_drop,
            is_spike,
            severity
        FROM with_flags
        WHERE is_drop OR is_spike
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_supply_segment_anomalies_week_park_segment
        ON ops.mv_supply_segment_anomalies_weekly (week_start, park_id, segment_week)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segment_anomalies_week_desc
        ON ops.mv_supply_segment_anomalies_weekly (week_start DESC)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_segment_anomalies_park_week_desc
        ON ops.mv_supply_segment_anomalies_weekly (park_id, week_start DESC)
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_alerts_weekly AS
        SELECT
            md5(week_start::text || COALESCE(park_id::text, '') || segment_week::text || alert_type) AS alert_id,
            week_start,
            park_id,
            park_name,
            city,
            country,
            segment_week,
            alert_type,
            severity,
            baseline_avg,
            current_value,
            delta_pct,
            message_short,
            recommended_action
        FROM (
            SELECT
                week_start,
                park_id,
                park_name,
                city,
                country,
                segment_week,
                'segment_drop' AS alert_type,
                severity,
                baseline_avg,
                current_value,
                delta_pct,
                segment_week || ' cayó ' || ROUND((delta_pct * 100)::numeric, 0)::text || '% vs baseline 8w' AS message_short,
                CASE segment_week
                    WHEN 'FT' THEN 'Revisar tarifas, incentivos, competencia; listar top drivers downshift/dormant'
                    WHEN 'PT' THEN 'Revisar fricción operativa / app / bloqueos'
                    ELSE 'Revisar engagement y campañas de reactivación'
                END AS recommended_action
            FROM ops.mv_supply_segment_anomalies_weekly
            WHERE is_drop
            UNION ALL
            SELECT
                week_start,
                park_id,
                park_name,
                city,
                country,
                segment_week,
                'segment_spike' AS alert_type,
                severity,
                baseline_avg,
                current_value,
                delta_pct,
                segment_week || ' subió +' || ROUND((delta_pct * 100)::numeric, 0)::text || '% vs baseline 8w (posible fuga o caída de incentivos)' AS message_short,
                'Activar campaña reactivación + call center' AS recommended_action
            FROM ops.mv_supply_segment_anomalies_weekly
            WHERE is_spike
        ) t
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_supply_alerts_weekly_id
        ON ops.mv_supply_alerts_weekly (week_start, park_id, segment_week, alert_type)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_alerts_weekly_week_desc
        ON ops.mv_supply_alerts_weekly (week_start DESC)
    """)
    op.execute("""
        CREATE INDEX ix_mv_supply_alerts_weekly_park_week_desc
        ON ops.mv_supply_alerts_weekly (park_id, week_start DESC)
    """)

    op.execute("""
        CREATE VIEW ops.v_supply_alert_drilldown AS
        SELECT
            d.week_start,
            d.park_id,
            d.segment_week,
            d.driver_key,
            d.prev_segment_week,
            d.segment_week AS segment_week_current,
            d.trips_completed_week,
            d.baseline_trips_4w_avg,
            d.segment_change_type
        FROM ops.mv_driver_segments_weekly d
        WHERE d.park_id IS NOT NULL
          AND d.segment_change_type IN ('downshift', 'drop')
    """)

    # Restore FT to 60+ (remove cap) and remove ELITE/LEGEND from config
    op.execute("""
        UPDATE ops.driver_segment_config
        SET max_trips_week = NULL, updated_at = now()
        WHERE segment_code = 'FT' AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
    """)
    op.execute("""
        UPDATE ops.driver_segment_config SET effective_to = CURRENT_DATE, updated_at = now()
        WHERE segment_code IN ('ELITE', 'LEGEND') AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
    """)
