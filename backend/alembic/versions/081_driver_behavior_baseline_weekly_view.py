"""
Behavioral Alerts — Baseline layer: driver-week performance vs own historical baseline.
Creates ops.v_driver_behavior_baseline_weekly.
Source: ops.mv_driver_segments_weekly. Geo: dim.v_geo_park. Driver name: ops.v_dim_driver_resolved.
Baseline window: 6 weeks strictly BEFORE current week (current week excluded).
Additive; no changes to existing MVs or views.
"""
from alembic import op

revision = "081_driver_behavior_baseline_weekly"
down_revision = "080_mv_driver_segment_migrations_weekly_optional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_behavior_baseline_weekly AS
        WITH cur AS (
            SELECT
                d.driver_key,
                d.week_start,
                d.park_id,
                d.trips_completed_week,
                d.segment_week
            FROM ops.mv_driver_segments_weekly d
        ),
        baseline_agg AS (
            SELECT
                c.driver_key,
                c.week_start,
                c.park_id,
                c.trips_completed_week AS trips_current_week,
                c.segment_week AS segment_current,
                COUNT(b.week_start)::int AS active_weeks_in_window,
                AVG(b.trips_completed_week)::numeric(20,4) AS avg_trips_baseline,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY b.trips_completed_week)::numeric(20,4) AS median_trips_baseline,
                STDDEV_POP(b.trips_completed_week)::numeric(20,4) AS stddev_trips_baseline,
                MIN(b.trips_completed_week)::bigint AS min_trips_baseline,
                MAX(b.trips_completed_week)::bigint AS max_trips_baseline
            FROM cur c
            LEFT JOIN ops.mv_driver_segments_weekly b
                ON b.driver_key = c.driver_key
                AND (b.park_id IS NOT DISTINCT FROM c.park_id)
                AND b.week_start >= c.week_start - INTERVAL '6 weeks'
                AND b.week_start < c.week_start
            GROUP BY c.driver_key, c.week_start, c.park_id, c.trips_completed_week, c.segment_week
        ),
        with_deltas AS (
            SELECT
                b.*,
                (b.trips_current_week::numeric - b.avg_trips_baseline) AS delta_abs,
                CASE
                    WHEN b.avg_trips_baseline IS NULL OR b.avg_trips_baseline = 0 THEN NULL
                    ELSE ROUND(((b.trips_current_week::numeric - b.avg_trips_baseline) / b.avg_trips_baseline)::numeric, 6)
                END AS delta_pct,
                CASE
                    WHEN b.stddev_trips_baseline IS NULL OR b.stddev_trips_baseline = 0 THEN NULL
                    ELSE ROUND(((b.trips_current_week::numeric - b.avg_trips_baseline) / b.stddev_trips_baseline)::numeric, 4)
                END AS z_score_simple
            FROM baseline_agg b
        ),
        consec AS (
            SELECT
                c.driver_key,
                c.week_start,
                c.park_id,
                0 AS weeks_declining_consecutively,
                0 AS weeks_rising_consecutively
            FROM (SELECT DISTINCT driver_key, week_start, park_id FROM cur) c
        )
        SELECT
            w.driver_key,
            COALESCE(dr.driver_name, w.driver_key::text) AS driver_name,
            w.week_start,
            'S' || EXTRACT(WEEK FROM w.week_start)::integer || '-' || EXTRACT(ISOYEAR FROM w.week_start)::integer AS week_label,
            COALESCE(g.country, 'UNKNOWN') AS country,
            COALESCE(g.city, 'UNKNOWN') AS city,
            w.park_id,
            COALESCE(g.park_name, w.park_id::text) AS park_name,
            w.trips_current_week,
            w.segment_current,
            w.avg_trips_baseline,
            w.median_trips_baseline,
            w.stddev_trips_baseline,
            w.min_trips_baseline,
            w.max_trips_baseline,
            w.active_weeks_in_window,
            w.delta_abs,
            w.delta_pct,
            w.z_score_simple,
            COALESCE(c.weeks_declining_consecutively, 0)::int AS weeks_declining_consecutively,
            COALESCE(c.weeks_rising_consecutively, 0)::int AS weeks_rising_consecutively
        FROM with_deltas w
        LEFT JOIN dim.v_geo_park g ON g.park_id = w.park_id
        LEFT JOIN ops.v_dim_driver_resolved dr ON dr.driver_id = w.driver_key
        LEFT JOIN consec c ON c.driver_key = w.driver_key AND c.week_start = w.week_start AND (c.park_id IS NOT DISTINCT FROM w.park_id)
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_driver_behavior_baseline_weekly IS
        'Driver-week baseline (6 weeks before current week, excluded). For Behavioral Alerts: compare current vs own history. Baseline excludes current week.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_driver_behavior_baseline_weekly CASCADE")
