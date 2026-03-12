"""
Action Engine — Additive views: driver-level cohort tag and cohort/recommendation aggregates.
Reads from ops.mv_driver_behavior_alerts_weekly. Does not modify Behavioral Alerts.
Creates: ops.v_action_engine_driver_base, ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly.
"""
from alembic import op

revision = "086_action_engine_views"
down_revision = "085_behavior_alerts_risk_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Driver-week with primary cohort_type (first match in priority order). Non-matching rows excluded for cohort aggregates.
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_action_engine_driver_base AS
        WITH src AS (
            SELECT * FROM ops.mv_driver_behavior_alerts_weekly
        ),
        tagged AS (
            SELECT
                s.*,
                CASE
                    WHEN s.segment_current IN ('FT', 'ELITE', 'LEGEND')
                         AND s.risk_band IN ('high risk', 'medium risk')
                         AND s.delta_pct IS NOT NULL AND s.delta_pct < -0.15
                    THEN 'high_value_deteriorating'
                    WHEN s.weeks_declining_consecutively >= 3
                         AND s.alert_type NOT IN ('Critical Drop', 'Moderate Drop')
                    THEN 'silent_erosion'
                    WHEN s.segment_current IN ('CASUAL', 'PT')
                         AND (s.alert_type = 'Strong Recovery'
                              OR (s.delta_pct IS NOT NULL AND s.delta_pct > 0 AND s.risk_band IN ('stable', 'monitor')))
                    THEN 'recoverable_mid_performers'
                    WHEN s.segment_current IN ('CASUAL', 'PT')
                         AND s.movement_type = 'upshift'
                         AND s.delta_pct IS NOT NULL AND s.delta_pct > 0
                    THEN 'near_upgrade_opportunity'
                    WHEN (s.segment_current IN ('FT', 'ELITE', 'LEGEND', 'PT') AND s.movement_type IN ('downshift', 'drop'))
                         OR (s.delta_pct IS NOT NULL AND s.delta_pct < -0.10
                             AND s.risk_band IN ('medium risk', 'monitor')
                             AND s.segment_current IN ('FT', 'ELITE', 'LEGEND', 'PT'))
                    THEN 'near_drop_risk'
                    WHEN s.alert_type = 'High Volatility'
                    THEN 'volatile_drivers'
                    WHEN s.avg_trips_baseline >= 40
                         AND s.delta_pct IS NOT NULL AND s.delta_pct < -0.20 AND s.delta_pct > -0.50
                         AND s.segment_current IN ('FT', 'ELITE', 'LEGEND')
                    THEN 'high_value_recovery_candidates'
                    ELSE NULL
                END AS cohort_type
            FROM src s
        )
        SELECT
            driver_key, driver_name, week_start, week_label,
            country, city, park_id, park_name,
            segment_current, segment_previous, movement_type,
            trips_current_week, avg_trips_baseline, delta_abs, delta_pct,
            alert_type, severity, risk_score, risk_band,
            active_weeks_in_window, weeks_declining_consecutively,
            cohort_type
        FROM tagged
        WHERE cohort_type IS NOT NULL
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_action_engine_driver_base IS
        'Action Engine: driver-week rows with primary cohort_type (first match). Source: mv_driver_behavior_alerts_weekly. See docs/action_engine_logic.md.'
    """)

    # Cohort aggregates per week + action metadata
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_action_engine_cohorts_weekly AS
        WITH cohort_meta AS (
            SELECT 'high_value_deteriorating' AS cohort_type, 'high' AS suggested_priority, 'loyalty_call' AS suggested_channel,
                   'Protect Elite/Legend in decline' AS action_name, 'Prevent loss of premium supply' AS action_objective
            UNION ALL SELECT 'silent_erosion', 'high', 'preventive_outreach', 'Stop silent erosion', 'Detect hidden deterioration early'
            UNION ALL SELECT 'recoverable_mid_performers', 'medium', 'whatsapp_coaching', 'Push recovering PT/Casual upward', 'Accelerate conversion to higher productivity'
            UNION ALL SELECT 'near_upgrade_opportunity', 'medium', 'soft_nudge', 'Promote near-upgrade drivers', 'Lock in upward movement'
            UNION ALL SELECT 'near_drop_risk', 'high', 'outbound_call', 'Contain FT at risk of downgrade', 'Prevent collapse to lower segment'
            UNION ALL SELECT 'volatile_drivers', 'medium', 'diagnostic_contact', 'Understand volatile drivers', 'Avoid unreliable supply'
            UNION ALL SELECT 'high_value_recovery_candidates', 'high', 'outbound_call', 'Rescue high-value recoverable', 'High ROI reactivation'
        ),
        agg AS (
            SELECT
                d.week_start,
                d.week_label,
                d.cohort_type,
                COUNT(*)::int AS cohort_size,
                ROUND(AVG(d.risk_score)::numeric, 2) AS avg_risk_score,
                ROUND(AVG(d.delta_pct)::numeric, 4) AS avg_delta_pct,
                ROUND(AVG(d.avg_trips_baseline)::numeric, 2) AS avg_baseline_value,
                MODE() WITHIN GROUP (ORDER BY d.segment_current) AS dominant_segment
            FROM ops.v_action_engine_driver_base d
            GROUP BY d.week_start, d.week_label, d.cohort_type
        )
        SELECT
            a.week_start,
            a.week_label,
            a.cohort_type,
            a.cohort_size,
            a.avg_risk_score,
            a.avg_delta_pct,
            a.avg_baseline_value,
            a.dominant_segment,
            m.suggested_priority,
            m.suggested_channel,
            m.action_name,
            m.action_objective
        FROM agg a
        JOIN cohort_meta m ON m.cohort_type = a.cohort_type
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_action_engine_cohorts_weekly IS
        'Action Engine: cohort aggregates per week with action metadata. See docs/action_engine_logic.md.'
    """)

    # Recommendations: same as cohorts with priority_score for ordering (top actions)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_action_engine_recommendations_weekly AS
        SELECT
            c.*,
            (c.cohort_size * 0.4 + COALESCE(c.avg_risk_score, 0) * 0.4
             + CASE WHEN c.dominant_segment IN ('FT', 'ELITE', 'LEGEND') THEN 20 ELSE 0 END) AS priority_score
        FROM ops.v_action_engine_cohorts_weekly c
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_action_engine_recommendations_weekly IS
        'Action Engine: cohort recommendations with priority_score for panel ordering. See docs/action_engine_logic.md.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_action_engine_recommendations_weekly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_action_engine_cohorts_weekly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_action_engine_driver_base CASCADE")
