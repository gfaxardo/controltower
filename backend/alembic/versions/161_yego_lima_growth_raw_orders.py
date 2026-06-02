"""
161 — YEGO Lima Fleet Growth Tower: Raw Orders Capture

Creates:
- growth schema
- growth.yango_lima_orders_raw: raw orders from Yango Fleet API

Additive only. No DROP on raw. No impact on production serving facts.

down_revision: 160_yego_historical_presence_operational_flow_v2
"""

from alembic import op

revision = "161_yego_lima_growth_raw_orders"
down_revision = "160_yego_historical_presence_operational_flow_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_orders_raw (
            order_id TEXT PRIMARY KEY,
            order_short_id BIGINT,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ,
            booked_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ NOT NULL,
            provider TEXT,
            category TEXT,
            payment_method TEXT,
            price NUMERIC(18,4),
            mileage NUMERIC(18,4),

            driver_profile_id TEXT,
            driver_profile_name TEXT,

            car_id TEXT,
            car_callsign TEXT,
            car_brand_model TEXT,
            car_license_number TEXT,

            driver_work_rule_id TEXT,
            driver_work_rule_name TEXT,

            raw_payload JSONB NOT NULL,

            first_fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            fetch_count INTEGER NOT NULL DEFAULT 1,

            source TEXT NOT NULL DEFAULT 'yango_orders_api_lima'
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_orders_raw_ended_at
        ON growth.yango_lima_orders_raw (ended_at);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_orders_raw_driver_profile_id
        ON growth.yango_lima_orders_raw (driver_profile_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_orders_raw_car_id
        ON growth.yango_lima_orders_raw (car_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_orders_raw_category
        ON growth.yango_lima_orders_raw (category);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_orders_raw_last_fetched_at
        ON growth.yango_lima_orders_raw (last_fetched_at);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_yango_lima_orders_raw_status_ended_at
        ON growth.yango_lima_orders_raw (status, ended_at);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_orders_raw;")
