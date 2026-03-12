"""
Top Driver Behavior — Additive views for Elite/Legend (and FT) benchmarks and patterns.
Reads from ops.mv_driver_behavior_alerts_weekly. Does not modify existing modules.
Creates: ops.v_top_driver_behavior_weekly, ops.v_top_driver_behavior_benchmarks, ops.v_top_driver_behavior_patterns.
"""
from alembic import op

revision = "087_top_driver_behavior_views"
down_revision = "086_action_engine_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Driver-week for ELITE, LEGEND, FT only; consistency_score = 1 - CV when baseline available
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_top_driver_behavior_weekly AS
        SELECT
            driver_key,
            driver_name,
            week_start,
            week_label,
            country,
            city,
            park_id,
            park_name,
            segment_current,
            segment_previous,
            movement_type,
            trips_current_week,
            avg_trips_baseline,
            stddev_trips_baseline,
            active_weeks_in_window,
            delta_pct,
            risk_score,
            risk_band,
            CASE
                WHEN avg_trips_baseline IS NOT NULL AND avg_trips_baseline > 0 AND stddev_trips_baseline IS NOT NULL
                THEN ROUND(GREATEST(0, 1 - (stddev_trips_baseline / avg_trips_baseline))::numeric, 4)
                ELSE NULL
            END AS consistency_score
        FROM ops.mv_driver_behavior_alerts_weekly
        WHERE segment_current IN ('ELITE', 'LEGEND', 'FT')
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_top_driver_behavior_weekly IS
        'Top Driver Behavior: driver-week for ELITE, LEGEND, FT. consistency_score = 1 - CV. See docs/top_driver_behavior_logic.md.'
    """)

    # Benchmarks by segment_current
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_top_driver_behavior_benchmarks AS
        SELECT
            segment_current,
            COUNT(DISTINCT driver_key) AS driver_count,
            ROUND(AVG(trips_current_week)::numeric, 2) AS avg_weekly_trips,
            ROUND(AVG(
                CASE WHEN avg_trips_baseline > 0 AND stddev_trips_baseline IS NOT NULL
                     THEN GREATEST(0, 1 - (stddev_trips_baseline / avg_trips_baseline)) ELSE NULL END
            )::numeric, 4) AS consistency_score_avg,
            ROUND(AVG(active_weeks_in_window)::numeric, 2) AS active_weeks_avg
        FROM ops.v_top_driver_behavior_weekly
        GROUP BY segment_current
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_top_driver_behavior_benchmarks IS
        'Top Driver Behavior: aggregate benchmarks by segment (ELITE, LEGEND, FT). See docs/top_driver_behavior_logic.md.'
    """)

    # Patterns by segment, city, park
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_top_driver_behavior_patterns AS
        SELECT
            segment_current,
            country,
            city,
            park_id,
            park_name,
            COUNT(DISTINCT driver_key) AS driver_count,
            ROUND(AVG(trips_current_week)::numeric, 2) AS avg_trips,
            ROUND(100.0 * COUNT(DISTINCT driver_key) / NULLIF(SUM(COUNT(DISTINCT driver_key)) OVER (PARTITION BY segment_current), 0), 2) AS pct_of_segment
        FROM ops.v_top_driver_behavior_weekly
        GROUP BY segment_current, country, city, park_id, park_name
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_top_driver_behavior_patterns IS
        'Top Driver Behavior: concentration by segment, city, park. See docs/top_driver_behavior_logic.md.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_top_driver_behavior_patterns CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_top_driver_behavior_benchmarks CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_top_driver_behavior_weekly CASCADE")
