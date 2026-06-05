"""
186 — Raw Yango operational_date hardening (OV2-B.1.1)

Adds operational_date column to each raw table for date-based coverage/reconciliation.

orders_raw:
  - operational_date DATE (derived from order_ended_at or order_created_at)

transactions_raw:
  - operational_date DATE (derived from event_at / transaction_created_at)

driver_profiles_raw:
  - operational_date DATE (derived from api_fetched_at temporarily)

Additive. No backfill of existing rows — new rows populated by ingestion.

down_revision: 185_yego_lima_impact_tracking
"""

from alembic import op

revision = "186_raw_yango_operational_date"
down_revision = "185_yego_lima_impact_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE raw_yango.orders_raw
        ADD COLUMN IF NOT EXISTS operational_date DATE;
    """)
    op.execute("""
        ALTER TABLE raw_yango.transactions_raw
        ADD COLUMN IF NOT EXISTS operational_date DATE;
    """)
    op.execute("""
        ALTER TABLE raw_yango.driver_profiles_raw
        ADD COLUMN IF NOT EXISTS operational_date DATE;
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_orders_operational_date
        ON raw_yango.orders_raw (park_id, operational_date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_txn_operational_date
        ON raw_yango.transactions_raw (park_id, operational_date);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_yango_drivers_operational_date
        ON raw_yango.driver_profiles_raw (park_id, operational_date);
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS raw_yango.ix_yango_drivers_operational_date;")
    op.execute("DROP INDEX IF EXISTS raw_yango.ix_yango_txn_operational_date;")
    op.execute("DROP INDEX IF EXISTS raw_yango.ix_yango_orders_operational_date;")
    op.execute("ALTER TABLE raw_yango.driver_profiles_raw DROP COLUMN IF EXISTS operational_date;")
    op.execute("ALTER TABLE raw_yango.transactions_raw DROP COLUMN IF EXISTS operational_date;")
    op.execute("ALTER TABLE raw_yango.orders_raw DROP COLUMN IF EXISTS operational_date;")
