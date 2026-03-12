"""
Behavioral Alerts — Add risk_score (0-100) and risk_band. Replace v_driver_behavior_alerts_weekly.
Formula: A Behavior 0-40, B Migration 0-30, C Fragility 0-20, D Value 0-10. Bands: 0-24 stable, 25-49 monitor, 50-74 medium risk, 75-100 high risk.
Recreate mv_driver_behavior_alerts_weekly after view change.
"""
from alembic import op

revision = "085_behavior_alerts_risk_score"
down_revision = "084_behavior_baseline_segment_movement"
branch_labels = None
depends_on = None

# Segment ordering for risk (match ops.driver_segment_config: DORMANT=1 .. LEGEND=7). Use c. in risk_components CTE.
_SEG_ORD = """
    CASE c.segment_current
        WHEN 'LEGEND' THEN 7 WHEN 'ELITE' THEN 6 WHEN 'FT' THEN 5 WHEN 'PT' THEN 4
        WHEN 'CASUAL' THEN 3 WHEN 'OCCASIONAL' THEN 2 WHEN 'DORMANT' THEN 1 ELSE 0 END
"""
_PREV_ORD = """
    CASE c.segment_previous
        WHEN 'LEGEND' THEN 7 WHEN 'ELITE' THEN 6 WHEN 'FT' THEN 5 WHEN 'PT' THEN 4
        WHEN 'CASUAL' THEN 3 WHEN 'OCCASIONAL' THEN 2 WHEN 'DORMANT' THEN 1 ELSE 0 END
"""


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_alerts_weekly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE")

    op.execute(f"""
        CREATE VIEW ops.v_driver_behavior_alerts_weekly AS
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
        ),
        risk_components AS (
            SELECT
                c.*,
                -- A) Behavior Deviation (0-40): delta_pct up to 20, declining weeks up to 10, z_score up to 10
                LEAST(40, GREATEST(0,
                    COALESCE(CASE WHEN c.delta_pct < 0 THEN LEAST(20, (-c.delta_pct) * 20) ELSE 0 END, 0) +
                    COALESCE(LEAST(10, c.weeks_declining_consecutively * 3), 0) +
                    COALESCE(CASE WHEN c.z_score_simple < 0 THEN LEAST(10, (-c.z_score_simple) * 2) ELSE 0 END, 0)
                ))::numeric(5,2) AS risk_score_behavior,
                -- B) Segment Migration Risk (0-30): downshift=15, drop=25, +5 if from FT/ELITE/LEGEND
                LEAST(30, GREATEST(0,
                    CASE WHEN c.movement_type = 'drop' THEN 25 WHEN c.movement_type = 'downshift' THEN 15 ELSE 0 END +
                    CASE WHEN c.segment_previous IN ('FT', 'ELITE', 'LEGEND') AND c.movement_type IN ('downshift', 'drop') THEN 5 ELSE 0 END
                ))::numeric(5,2) AS risk_score_migration,
                -- C) Activity Fragility (0-20): low active_weeks + high volatility
                LEAST(20, GREATEST(0,
                    CASE WHEN c.active_weeks_in_window < 3 THEN 10 ELSE 0 END +
                    CASE WHEN c.avg_trips_baseline IS NOT NULL AND c.avg_trips_baseline > 0 AND c.stddev_trips_baseline IS NOT NULL
                         AND (c.stddev_trips_baseline / c.avg_trips_baseline) > 0.5 THEN 10 ELSE 0 END
                ))::numeric(5,2) AS risk_score_fragility,
                -- D) Value Weight (0-10): higher baseline and segment = higher priority
                LEAST(10, GREATEST(0,
                    LEAST(5, COALESCE(c.avg_trips_baseline, 0) / 20) +
                    ({_SEG_ORD}) * 0.7
                ))::numeric(5,2) AS risk_score_value
            FROM classified c
        ),
        with_risk AS (
            SELECT
                r.*,
                (LEAST(100, GREATEST(0,
                    COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) +
                    COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0)
                ))::int) AS risk_score,
                CASE
                    WHEN LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0))) <= 24 THEN 'stable'
                    WHEN LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0))) <= 49 THEN 'monitor'
                    WHEN LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0))) <= 74 THEN 'medium risk'
                    ELSE 'high risk'
                END AS risk_band
            FROM risk_components r
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
            segment_previous,
            movement_type,
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
            severity,
            risk_score_behavior,
            risk_score_migration,
            risk_score_fragility,
            risk_score_value,
            risk_score,
            risk_band
        FROM with_risk
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_driver_behavior_alerts_weekly IS
        'Behavioral Alerts with risk_score (0-100) and risk_band. Components: behavior, migration, fragility, value. See docs/behavioral_alerts_logic.md.'
    """)

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_behavior_alerts_weekly AS
        SELECT * FROM ops.v_driver_behavior_alerts_weekly
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_behavior_alerts_weekly_driver_week
        ON ops.mv_driver_behavior_alerts_weekly (driver_key, week_start)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_week_start
        ON ops.mv_driver_behavior_alerts_weekly (week_start)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_country
        ON ops.mv_driver_behavior_alerts_weekly (country)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_city
        ON ops.mv_driver_behavior_alerts_weekly (city)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_park_id
        ON ops.mv_driver_behavior_alerts_weekly (park_id)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_alert_type
        ON ops.mv_driver_behavior_alerts_weekly (alert_type)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_severity
        ON ops.mv_driver_behavior_alerts_weekly (severity)
    """)
    op.execute("""
        CREATE INDEX ix_mv_driver_behavior_alerts_risk_band
        ON ops.mv_driver_behavior_alerts_weekly (risk_band)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_alerts_weekly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_behavior_alerts_weekly AS
        WITH base AS (SELECT * FROM ops.v_driver_behavior_baseline_weekly),
        with_flags AS (
            SELECT b.*,
                (b.avg_trips_baseline IS NOT NULL AND b.avg_trips_baseline >= 40 AND b.delta_pct IS NOT NULL AND b.delta_pct <= -0.30 AND b.active_weeks_in_window >= 4) AS is_critical_drop,
                (b.delta_pct IS NOT NULL AND b.delta_pct <= -0.15 AND b.delta_pct > -0.30) AS is_moderate_drop,
                (b.weeks_declining_consecutively >= 3) AS is_silent_erosion,
                (b.delta_pct IS NOT NULL AND b.delta_pct >= 0.30 AND b.active_weeks_in_window >= 3) AS is_strong_recovery,
                (b.avg_trips_baseline IS NOT NULL AND b.avg_trips_baseline > 0 AND b.stddev_trips_baseline IS NOT NULL AND (b.stddev_trips_baseline / b.avg_trips_baseline) > 0.5) AS is_high_volatility
            FROM base b
        ),
        classified AS (
            SELECT w.*,
                CASE WHEN w.is_critical_drop THEN 'Critical Drop' WHEN w.is_moderate_drop AND NOT w.is_critical_drop THEN 'Moderate Drop'
                    WHEN w.is_silent_erosion AND NOT w.is_critical_drop AND NOT w.is_moderate_drop THEN 'Silent Erosion' WHEN w.is_strong_recovery THEN 'Strong Recovery'
                    WHEN w.is_high_volatility AND NOT w.is_critical_drop AND NOT w.is_moderate_drop AND NOT w.is_silent_erosion AND NOT w.is_strong_recovery THEN 'High Volatility' ELSE 'Stable Performer' END AS alert_type,
                CASE WHEN w.is_critical_drop THEN 'critical' WHEN w.is_moderate_drop OR w.is_silent_erosion THEN 'moderate' WHEN w.is_strong_recovery THEN 'positive' WHEN w.is_high_volatility THEN 'moderate' ELSE 'neutral' END AS severity
            FROM with_flags w
        )
        SELECT driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, trips_current_week, segment_current,
            avg_trips_baseline, median_trips_baseline, stddev_trips_baseline, min_trips_baseline, max_trips_baseline, active_weeks_in_window,
            delta_abs, delta_pct, z_score_simple, weeks_declining_consecutively, weeks_rising_consecutively, alert_type, severity
        FROM classified
    """)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_behavior_alerts_weekly AS SELECT * FROM ops.v_driver_behavior_alerts_weekly
    """)
    op.execute("CREATE UNIQUE INDEX ux_mv_driver_behavior_alerts_weekly_driver_week ON ops.mv_driver_behavior_alerts_weekly (driver_key, week_start)")
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_week_start ON ops.mv_driver_behavior_alerts_weekly (week_start)")
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_country ON ops.mv_driver_behavior_alerts_weekly (country)")
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_city ON ops.mv_driver_behavior_alerts_weekly (city)")
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_park_id ON ops.mv_driver_behavior_alerts_weekly (park_id)")
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_alert_type ON ops.mv_driver_behavior_alerts_weekly (alert_type)")
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_severity ON ops.mv_driver_behavior_alerts_weekly (severity)")