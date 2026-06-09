"""
192 — LG-INFRA-R1.3: Intraday Driver Signal Table

Creates:
- growth.yego_lima_intraday_driver_signal

Idempotent per (signal_date, driver_profile_id, queue_id).
Non-causal observation layer. Does not alter queue, eligibility, or prioritization.

down_revision: 188_yego_lima_program_capacity_policy
"""

from alembic import op

revision = "192_yego_lima_intraday_driver_signal"
down_revision = "188_yego_lima_program_capacity_policy"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_intraday_driver_signal (
            signal_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            signal_date             date NOT NULL,
            driver_profile_id       text NOT NULL,
            action_date             date,
            queue_id                uuid,
            campaign_id_external    text,
            action_channel          text,
            action_sent_at          timestamptz,
            observed_at             timestamptz NOT NULL DEFAULT now(),
            source_system           text NOT NULL DEFAULT 'YANGO_API_LIVE',
            source_loaded_at        timestamptz NOT NULL DEFAULT now(),
            trips_after_action      integer DEFAULT 0,
            supply_hours_after_action numeric(10,2) DEFAULT 0,
            first_trip_after_action_at timestamptz,
            first_supply_after_action_at timestamptz,
            reactivation_detected   boolean DEFAULT false,
            activity_detected_today boolean DEFAULT false,
            signal_status           text NOT NULL DEFAULT 'OBSERVED'
                CHECK (signal_status IN (
                    'OBSERVED', 'ACTIONED_NO_ACTIVITY', 'TRIP_DETECTED',
                    'SUPPLY_DETECTED', 'REACTIVATED', 'STALE'
                )),
            evidence_json           jsonb DEFAULT '{}'::jsonb,
            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_signal_driver_date_queue
                UNIQUE (signal_date, driver_profile_id, queue_id)
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_isig_date
        ON growth.yego_lima_intraday_driver_signal (signal_date)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_isig_driver
        ON growth.yego_lima_intraday_driver_signal (driver_profile_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_isig_status
        ON growth.yego_lima_intraday_driver_signal (signal_status)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_isig_queue
        ON growth.yego_lima_intraday_driver_signal (queue_id)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_isig_campaign
        ON growth.yego_lima_intraday_driver_signal (campaign_id_external)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_intraday_driver_signal")
