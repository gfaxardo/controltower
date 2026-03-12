"""
Behavioral Alerts — Alert classification view.
Creates ops.v_driver_behavior_alerts_weekly from ops.v_driver_behavior_baseline_weekly.
Alert types: Critical Drop, Moderate Drop, Silent Erosion, Strong Recovery, High Volatility, Stable Performer.
Severity: critical | moderate | positive | neutral.
Additive; no changes to existing objects.
"""
from alembic import op

revision = "082_driver_behavior_alerts_weekly"
down_revision = "081_driver_behavior_baseline_weekly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_behavior_alerts_weekly AS
        WITH base AS (
            SELECT * FROM ops.v_driver_behavior_baseline_weekly
        ),
        with_flags AS (
            SELECT
                b.*,
                (b.avg_trips_baseline IS NOT NULL AND b.avg_trips_baseline >= 40
                 AND b.delta_pct IS NOT NULL AND b.delta_pct <= -0.30
                 AND b.active_weeks_in_window >= 4) AS is_critical_drop,
                (b.delta_pct IS NOT NULL AND b.delta_pct <= -0.15 AND b.delta_pct > -0.30) AS is_moderate_drop,
                (b.weeks_declining_consecutively >= 3) AS is_silent_erosion,
                (b.delta_pct IS NOT NULL AND b.delta_pct >= 0.30 AND b.active_weeks_in_window >= 3) AS is_strong_recovery,
                (b.avg_trips_baseline IS NOT NULL AND b.avg_trips_baseline > 0
                 AND b.stddev_trips_baseline IS NOT NULL
                 AND (b.stddev_trips_baseline / b.avg_trips_baseline) > 0.5) AS is_high_volatility
            FROM base b
        ),
        classified AS (
            SELECT
                w.*,
                CASE
                    WHEN w.is_critical_drop THEN 'Critical Drop'
                    WHEN w.is_moderate_drop AND NOT w.is_critical_drop THEN 'Moderate Drop'
                    WHEN w.is_silent_erosion AND NOT w.is_critical_drop AND NOT w.is_moderate_drop THEN 'Silent Erosion'
                    WHEN w.is_strong_recovery THEN 'Strong Recovery'
                    WHEN w.is_high_volatility AND NOT w.is_critical_drop AND NOT w.is_moderate_drop AND NOT w.is_silent_erosion AND NOT w.is_strong_recovery THEN 'High Volatility'
                    ELSE 'Stable Performer'
                END AS alert_type,
                CASE
                    WHEN w.is_critical_drop THEN 'critical'
                    WHEN w.is_moderate_drop OR w.is_silent_erosion THEN 'moderate'
                    WHEN w.is_strong_recovery THEN 'positive'
                    WHEN w.is_high_volatility THEN 'moderate'
                    ELSE 'neutral'
                END AS severity
            FROM with_flags w
        )
        SELECT
            driver_key,
            driver_name,
            week_start,
            week_label,
            country,
            city,
            park_id,
            park_name,
            trips_current_week,
            segment_current,
            avg_trips_baseline,
            median_trips_baseline,
            stddev_trips_baseline,
            min_trips_baseline,
            max_trips_baseline,
            active_weeks_in_window,
            delta_abs,
            delta_pct,
            z_score_simple,
            weeks_declining_consecutively,
            weeks_rising_consecutively,
            alert_type,
            severity
        FROM classified
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_driver_behavior_alerts_weekly IS
        'Behavioral Alerts: driver-week classified by deviation vs own baseline. Types: Critical Drop, Moderate Drop, Silent Erosion, Strong Recovery, High Volatility, Stable Performer. Severity: critical/moderate/positive/neutral.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE")
