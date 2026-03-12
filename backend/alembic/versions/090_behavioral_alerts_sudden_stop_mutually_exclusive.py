"""
Behavioral Alerts Enterprise — Sudden Stop + precedencia estricta (mutuamente excluyentes).
Adds is_sudden_stop: conductor con actividad en baseline que en la semana analizada pasa a 0 viajes.
Precedence: 1) Sudden Stop 2) Critical Drop 3) Moderate Drop 4) Silent Erosion 5) High Volatility 6) Strong Recovery 7) Stable Performer.
Replaces v_driver_behavior_alerts_weekly and recreates mv_driver_behavior_alerts_weekly.
"""
from alembic import op

revision = "090_behavioral_alerts_sudden_stop"
down_revision = "089_driver_behavior_deviation_last_trip"
branch_labels = None
depends_on = None

_SEG_ORD = """
    CASE c.segment_current
        WHEN 'LEGEND' THEN 7 WHEN 'ELITE' THEN 6 WHEN 'FT' THEN 5 WHEN 'PT' THEN 4
        WHEN 'CASUAL' THEN 3 WHEN 'OCCASIONAL' THEN 2 WHEN 'DORMANT' THEN 1 ELSE 0 END
"""


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_alerts_weekly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE")

    # Sudden Stop: had recent/baseline activity (avg_trips_baseline > 0), current week = 0 trips.
    # Precedence: Sudden Stop first, then existing order (Critical -> Moderate -> Silent Erosion -> High Volatility -> Strong Recovery -> Stable).
    op.execute(f"""
        CREATE VIEW ops.v_driver_behavior_alerts_weekly AS
        WITH base AS (
            SELECT * FROM ops.v_driver_behavior_baseline_weekly
        ),
        with_flags AS (
            SELECT
                b.*,
                (b.trips_current_week = 0 AND b.avg_trips_baseline IS NOT NULL AND b.avg_trips_baseline > 0) AS is_sudden_stop,
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
                    WHEN w.is_sudden_stop THEN 'Sudden Stop'
                    WHEN w.is_critical_drop THEN 'Critical Drop'
                    WHEN w.is_moderate_drop THEN 'Moderate Drop'
                    WHEN w.is_silent_erosion AND NOT w.is_critical_drop AND NOT w.is_moderate_drop THEN 'Silent Erosion'
                    WHEN w.is_high_volatility AND NOT w.is_critical_drop AND NOT w.is_moderate_drop AND NOT w.is_silent_erosion THEN 'High Volatility'
                    WHEN w.is_strong_recovery THEN 'Strong Recovery'
                    ELSE 'Stable Performer'
                END AS alert_type,
                CASE
                    WHEN w.is_sudden_stop OR w.is_critical_drop THEN 'critical'
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
                LEAST(40, GREATEST(0,
                    COALESCE(CASE WHEN c.delta_pct < 0 THEN LEAST(20, (-c.delta_pct) * 20) ELSE 0 END, 0) +
                    COALESCE(LEAST(10, c.weeks_declining_consecutively * 3), 0) +
                    COALESCE(CASE WHEN c.z_score_simple < 0 THEN LEAST(10, (-c.z_score_simple) * 2) ELSE 0 END, 0)
                ))::numeric(5,2) AS risk_score_behavior,
                LEAST(30, GREATEST(0,
                    CASE WHEN c.movement_type = 'drop' THEN 25 WHEN c.movement_type = 'downshift' THEN 15 ELSE 0 END +
                    CASE WHEN c.segment_previous IN ('FT', 'ELITE', 'LEGEND') AND c.movement_type IN ('downshift', 'drop') THEN 5 ELSE 0 END
                ))::numeric(5,2) AS risk_score_migration,
                LEAST(20, GREATEST(0,
                    CASE WHEN c.active_weeks_in_window < 3 THEN 10 ELSE 0 END +
                    CASE WHEN c.avg_trips_baseline IS NOT NULL AND c.avg_trips_baseline > 0 AND c.stddev_trips_baseline IS NOT NULL
                         AND (c.stddev_trips_baseline / c.avg_trips_baseline) > 0.5 THEN 10 ELSE 0 END
                ))::numeric(5,2) AS risk_score_fragility,
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
        'Behavioral Alerts: mutually exclusive. Precedence: Sudden Stop, Critical Drop, Moderate Drop, Silent Erosion, High Volatility, Strong Recovery, Stable Performer. risk_score 0-100. See docs/behavioral_alerts_logic.md.'
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
    # Revert to 085 view (no Sudden Stop; original CASE order).
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_alerts_weekly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_driver_behavior_alerts_weekly CASCADE")
    op.execute(f"""
        CREATE VIEW ops.v_driver_behavior_alerts_weekly AS
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
        ),
        risk_components AS (
            SELECT c.*,
                LEAST(40, GREATEST(0, COALESCE(CASE WHEN c.delta_pct < 0 THEN LEAST(20, (-c.delta_pct) * 20) ELSE 0 END, 0) + COALESCE(LEAST(10, c.weeks_declining_consecutively * 3), 0) + COALESCE(CASE WHEN c.z_score_simple < 0 THEN LEAST(10, (-c.z_score_simple) * 2) ELSE 0 END, 0)))::numeric(5,2) AS risk_score_behavior,
                LEAST(30, GREATEST(0, CASE WHEN c.movement_type = 'drop' THEN 25 WHEN c.movement_type = 'downshift' THEN 15 ELSE 0 END + CASE WHEN c.segment_previous IN ('FT', 'ELITE', 'LEGEND') AND c.movement_type IN ('downshift', 'drop') THEN 5 ELSE 0 END))::numeric(5,2) AS risk_score_migration,
                LEAST(20, GREATEST(0, CASE WHEN c.active_weeks_in_window < 3 THEN 10 ELSE 0 END + CASE WHEN c.avg_trips_baseline IS NOT NULL AND c.avg_trips_baseline > 0 AND c.stddev_trips_baseline IS NOT NULL AND (c.stddev_trips_baseline / c.avg_trips_baseline) > 0.5 THEN 10 ELSE 0 END))::numeric(5,2) AS risk_score_fragility,
                LEAST(10, GREATEST(0, LEAST(5, COALESCE(c.avg_trips_baseline, 0) / 20) + ({_SEG_ORD}) * 0.7))::numeric(5,2) AS risk_score_value
            FROM classified c
        ),
        with_risk AS (
            SELECT r.*,
                (LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0)))::int) AS risk_score,
                CASE WHEN LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0))) <= 24 THEN 'stable'
                    WHEN LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0))) <= 49 THEN 'monitor'
                    WHEN LEAST(100, GREATEST(0, COALESCE(r.risk_score_behavior, 0) + COALESCE(r.risk_score_migration, 0) + COALESCE(r.risk_score_fragility, 0) + COALESCE(r.risk_score_value, 0))) <= 74 THEN 'medium risk' ELSE 'high risk' END AS risk_band
            FROM risk_components r
        )
        SELECT driver_key, driver_name, week_start, week_label, country, city, park_id, park_name, trips_current_week, segment_current, segment_previous, movement_type,
            avg_trips_baseline, median_trips_baseline, stddev_trips_baseline, min_trips_baseline, max_trips_baseline, active_weeks_in_window,
            delta_abs, delta_pct, z_score_simple, weeks_declining_consecutively, weeks_rising_consecutively,
            alert_type, severity, risk_score_behavior, risk_score_migration, risk_score_fragility, risk_score_value, risk_score, risk_band
        FROM with_risk
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
    op.execute("CREATE INDEX ix_mv_driver_behavior_alerts_risk_band ON ops.mv_driver_behavior_alerts_weekly (risk_band)")
