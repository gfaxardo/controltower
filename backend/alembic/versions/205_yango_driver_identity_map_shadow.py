"""
205 — CF-H2C.1: Yango Driver Identity Map Shadow

Creates:
- ops.yango_driver_identity_map_shadow

Cross-references CT driver identity (public.drivers, public.trips_2026)
with Yango driver identity (raw_yango.driver_profiles_raw, raw_yango.orders_raw).

Shadow mode: does NOT replace any production driver identity source.
Each row documents the match method and confidence.

down_revision: 204_merge_cf_h2c_heads
"""

from alembic import op

revision = "205_yango_driver_identity_map_shadow"
down_revision = "204_merge_cf_h2c_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_driver_identity_map_shadow (
            id                          BIGSERIAL PRIMARY KEY,

            -- CT Bridge identity
            ct_driver_id                TEXT,
            ct_full_name                TEXT,
            ct_phone_raw                TEXT,
            ct_phone_normalized         TEXT,
            ct_license_number           TEXT,
            ct_park_id                  TEXT,
            ct_work_status              TEXT,
            ct_active                   BOOLEAN,

            -- trips_2026 reference
            trips_2026_driver_key       TEXT,

            -- Yango API identity
            yango_driver_profile_id     TEXT,
            yango_full_name             TEXT,
            yango_phone_raw             TEXT,
            yango_phone_normalized      TEXT,
            yango_work_status           TEXT,
            yango_park_id               TEXT,

            -- Match metadata
            park_id                     TEXT NOT NULL,
            match_method                TEXT NOT NULL,
            match_confidence            TEXT NOT NULL,
            match_score                 NUMERIC(10,4),

            -- Activity evidence
            first_seen_order_at         TIMESTAMPTZ,
            last_seen_order_at          TIMESTAMPTZ,
            orders_count                INT DEFAULT 0,

            -- Source status
            source_status               TEXT NOT NULL DEFAULT 'SHADOW',

            -- Audit
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

            UNIQUE (ct_driver_id, yango_driver_profile_id, match_method)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ydim_ct_driver
        ON ops.yango_driver_identity_map_shadow (ct_driver_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ydim_yango_driver
        ON ops.yango_driver_identity_map_shadow (yango_driver_profile_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ydim_confidence
        ON ops.yango_driver_identity_map_shadow (match_confidence);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ydim_park
        ON ops.yango_driver_identity_map_shadow (park_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.yango_driver_identity_map_shadow;")
