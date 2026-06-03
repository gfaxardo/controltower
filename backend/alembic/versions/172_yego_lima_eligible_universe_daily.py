"""
172 — YEGO Lima Fleet Growth Tower: Eligible Universe Daily

Creates:
- growth.yango_lima_eligible_universe_daily: daily driver eligibility classification

Additive only. No DROP. No impact on production serving facts.

down_revision: 171_yego_lima_driver_360_daily
"""

from alembic import op

revision = "172_yego_lima_eligible_universe_daily"
down_revision = "171_yego_lima_driver_360_daily"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_eligible_universe_daily (
            date DATE NOT NULL,
            driver_profile_id TEXT NOT NULL,

            eligibility_reason TEXT NOT NULL,
            priority_tier TEXT NOT NULL,

            current_status TEXT,
            work_status TEXT,

            completed_orders_today INTEGER NOT NULL DEFAULT 0,
            completed_orders_7d INTEGER NOT NULL DEFAULT 0,
            completed_orders_30d INTEGER NOT NULL DEFAULT 0,

            last_order_at TIMESTAMPTZ,

            included_in_supply_batch BOOLEAN NOT NULL DEFAULT FALSE,

            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            PRIMARY KEY (date, driver_profile_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_eligible_universe_daily_date
        ON growth.yango_lima_eligible_universe_daily (date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_eligible_universe_daily_priority_tier
        ON growth.yango_lima_eligible_universe_daily (priority_tier);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_eligible_universe_daily_eligibility_reason
        ON growth.yango_lima_eligible_universe_daily (eligibility_reason);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_eligible_universe_daily;")
