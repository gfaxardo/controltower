"""
191 — Omniview V2 Serving Snapshots (OV2-CX.3)

Creates ops.omniview_v2_serving_snapshot for pre-computed shell/matrix/health payloads.
Supports read-through serving: UI reads snapshots, not runtime-computed data.

down_revision: 190_raw_yango_revenue_day_contract
"""
from alembic import op

revision = "191_omniview_v2_serving_snapshot"
down_revision = "190_raw_yango_revenue_day_contract"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.omniview_v2_serving_snapshot (
            id              SERIAL PRIMARY KEY,
            source_system   TEXT NOT NULL,
            grain           TEXT NOT NULL DEFAULT 'day',
            operating_date  DATE NOT NULL,
            payload_type    TEXT NOT NULL,
            payload         JSONB NOT NULL,
            status          TEXT NOT NULL DEFAULT 'READY',
            coverage_pct    NUMERIC(5,1) DEFAULT 0,
            freshness_status TEXT DEFAULT 'FRESH',
            generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at      TIMESTAMPTZ,
            build_ms        INTEGER DEFAULT 0,
            source_tables   JSONB DEFAULT '[]',
            warnings        JSONB DEFAULT '[]',
            payload_hash    TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ov2_snapshot
        ON ops.omniview_v2_serving_snapshot (source_system, grain, operating_date, payload_type);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ov2_snapshot_status
        ON ops.omniview_v2_serving_snapshot (status);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ov2_snapshot_date
        ON ops.omniview_v2_serving_snapshot (operating_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ov2_snapshot_generated
        ON ops.omniview_v2_serving_snapshot (generated_at);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.omniview_v2_serving_snapshot;")
