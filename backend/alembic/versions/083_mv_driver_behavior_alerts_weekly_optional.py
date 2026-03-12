"""
Behavioral Alerts — Optional materialized view and refresh function for performance.
Creates ops.mv_driver_behavior_alerts_weekly (copy of v_driver_behavior_alerts_weekly)
and ops.refresh_driver_behavior_alerts(). Additive and reversible.
"""
from alembic import op

revision = "083_mv_driver_behavior_alerts_weekly_optional"
down_revision = "082_driver_behavior_alerts_weekly"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
        CREATE OR REPLACE FUNCTION ops.refresh_driver_behavior_alerts()
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_behavior_alerts_weekly;
        END;
        $$
    """)
    op.execute("""
        COMMENT ON FUNCTION ops.refresh_driver_behavior_alerts() IS
        'Refreshes ops.mv_driver_behavior_alerts_weekly. Run after supply/driver lifecycle refresh if using the MV for Behavioral Alerts.'
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_driver_behavior_alerts()")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_alerts_weekly")
