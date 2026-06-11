"""
202 — CF-H2C: Yango Shadow Reconciliation Day

Creates:
- ops.yango_shadow_reconciliation_day

Compares Yango API raw data vs trips_2026 daily.
Shadow mode: data is ingested but does NOT feed Omniview.
Every row has a reconciliation classification.

down_revision: 201_raw_yango_ingestion_watermark
"""

from alembic import op

revision = "202_yango_shadow_reconciliation_day"
down_revision = "201_raw_yango_ingestion_watermark"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_shadow_reconciliation_day (
            id                      BIGSERIAL PRIMARY KEY,
            source_date             DATE NOT NULL,
            park_id                 TEXT NOT NULL,

            -- Orders / Trips
            trips_ct_completed      BIGINT DEFAULT 0,
            trips_yango_completed   BIGINT DEFAULT 0,
            trips_delta_abs         BIGINT,
            trips_delta_pct         NUMERIC(10,4),
            trips_classification    TEXT,

            trips_ct_cancelled      BIGINT DEFAULT 0,
            trips_yango_cancelled   BIGINT DEFAULT 0,

            -- Revenue
            revenue_ct_total        NUMERIC DEFAULT 0,
            revenue_yango_total     NUMERIC DEFAULT 0,
            revenue_delta_abs       NUMERIC,
            revenue_delta_pct       NUMERIC(10,4),
            revenue_classification  TEXT,

            -- Drivers
            drivers_ct_active       BIGINT DEFAULT 0,
            drivers_yango_unique    BIGINT DEFAULT 0,
            drivers_delta_abs       BIGINT,
            drivers_delta_pct       NUMERIC(10,4),
            drivers_classification  TEXT,

            -- GMV
            gmv_ct_total            NUMERIC DEFAULT 0,
            gmv_yango_total         NUMERIC DEFAULT 0,
            gmv_delta_abs           NUMERIC,
            gmv_delta_pct           NUMERIC(10,4),
            gmv_classification      TEXT,

            -- Audit
            orders_yango_only       INT DEFAULT 0,
            orders_ct_only          INT DEFAULT 0,
            orders_both             INT DEFAULT 0,

            drivers_yango_only      INT DEFAULT 0,
            drivers_ct_only         INT DEFAULT 0,
            drivers_both            INT DEFAULT 0,

            parks_without_credentials INT DEFAULT 0,
            endpoints_failed_count  INT DEFAULT 0,
            ingestion_latency_ms    BIGINT,

            overall_status          TEXT NOT NULL DEFAULT 'PENDING',
            computed_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

            UNIQUE (source_date, park_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ysr_date
        ON ops.yango_shadow_reconciliation_day (source_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ysr_park
        ON ops.yango_shadow_reconciliation_day (park_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ysr_status
        ON ops.yango_shadow_reconciliation_day (overall_status);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.yango_shadow_reconciliation_day;")
