"""
Driver Behavioral Deviation Engine — Additive.
Creates ops.v_driver_last_trip for days_since_last_trip and inactivity_status.
Source: ops.v_driver_lifecycle_trips_completed. No changes to existing views/MVs.
"""
from alembic import op

revision = "089_driver_behavior_deviation_last_trip"
down_revision = "088_action_engine_driver_base_weeks_rising"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_last_trip AS
        SELECT
            conductor_id AS driver_key,
            MAX(completion_ts)::date AS last_trip_date
        FROM ops.v_driver_lifecycle_trips_completed
        WHERE completion_ts IS NOT NULL
        GROUP BY conductor_id
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_driver_last_trip IS
        'Driver-level last trip date for Behavioral Deviation Engine. Source: v_driver_lifecycle_trips_completed. Used for days_since_last_trip and inactivity_status.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_driver_last_trip CASCADE")
