"""
173 — YEGO Lima Fleet Growth Tower: Driver 360 Daily Stabilization

Adds:
- productivity_band, eligibility_tier, eligibility_reason
- supply_fetch_status, supply_fetch_error_type, supply_last_attempt_at
- orders_last_seen_at
- Indexes: (date, eligibility_tier), (date, productivity_band), (date, supply_fetch_status)

down_revision: 172_yego_lima_eligible_universe_daily
"""

from alembic import op

revision = "173_yego_lima_driver_360_stabilization"
down_revision = "172_yego_lima_eligible_universe_daily"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS productivity_band TEXT NULL;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS eligibility_tier TEXT NULL;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS eligibility_reason TEXT NULL;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS supply_fetch_status TEXT NULL;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS supply_fetch_error_type TEXT NULL;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS supply_last_attempt_at TIMESTAMPTZ NULL;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily ADD COLUMN IF NOT EXISTS orders_last_seen_at TIMESTAMPTZ NULL;")

    op.execute("CREATE INDEX IF NOT EXISTS idx_yango_lima_360_eligibility_tier ON growth.yango_lima_driver_360_daily (date, eligibility_tier);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_yango_lima_360_productivity_band ON growth.yango_lima_driver_360_daily (date, productivity_band);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_yango_lima_360_supply_fetch_status ON growth.yango_lima_driver_360_daily (date, supply_fetch_status);")


def downgrade():
    op.execute("DROP INDEX IF EXISTS growth.idx_yango_lima_360_supply_fetch_status;")
    op.execute("DROP INDEX IF EXISTS growth.idx_yango_lima_360_productivity_band;")
    op.execute("DROP INDEX IF EXISTS growth.idx_yango_lima_360_eligibility_tier;")

    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS orders_last_seen_at;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS supply_last_attempt_at;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS supply_fetch_error_type;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS supply_fetch_status;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS eligibility_reason;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS eligibility_tier;")
    op.execute("ALTER TABLE growth.yango_lima_driver_360_daily DROP COLUMN IF EXISTS productivity_band;")
