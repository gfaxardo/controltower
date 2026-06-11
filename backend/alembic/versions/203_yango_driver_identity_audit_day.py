"""
203 — CF-H2C: Yango Driver Identity Audit Day

Creates:
- ops.yango_driver_identity_audit_day

Detects possible mappings between:
- public.drivers (CT bridge driver identity)
- raw_yango.driver_profiles_raw (Yango API driver identity)
- raw_yango.orders_raw (driver activity from Yango)

Uses: driver_id, license, phone, full_name for cross-matching.
Shadow mode: does NOT create a canonical mapping table yet.

down_revision: 202_yango_shadow_reconciliation_day
"""

from alembic import op

revision = "203_yango_driver_identity_audit_day"
down_revision = "202_yango_shadow_reconciliation_day"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_driver_identity_audit_day (
            id                          BIGSERIAL PRIMARY KEY,
            audit_date                  DATE NOT NULL,
            park_id                     TEXT NOT NULL,

            -- CT Bridge driver counts
            ct_drivers_total            BIGINT DEFAULT 0,
            ct_drivers_with_phone       BIGINT DEFAULT 0,
            ct_drivers_with_license     BIGINT DEFAULT 0,
            ct_drivers_active_today     BIGINT DEFAULT 0,

            -- Yango API driver counts
            yango_drivers_total         BIGINT DEFAULT 0,
            yango_drivers_working       BIGINT DEFAULT 0,
            yango_drivers_with_orders   BIGINT DEFAULT 0,

            -- Cross-match counts
            matched_by_name             BIGINT DEFAULT 0,
            matched_by_name_partial     BIGINT DEFAULT 0,
            matched_by_phone            BIGINT DEFAULT 0,
            matched_by_license          BIGINT DEFAULT 0,
            matched_by_both_name_phone  BIGINT DEFAULT 0,
            matched_by_all              BIGINT DEFAULT 0,

            -- Unmatched
            ct_drivers_unmatched        BIGINT DEFAULT 0,
            yango_drivers_unmatched     BIGINT DEFAULT 0,

            -- Potential mapping candidates
            mapping_candidates_high     BIGINT DEFAULT 0,
            mapping_candidates_medium   BIGINT DEFAULT 0,
            mapping_candidates_low      BIGINT DEFAULT 0,

            -- Audit
            overall_match_pct           NUMERIC(10,4),
            identity_audit_status       TEXT NOT NULL DEFAULT 'PENDING',
            computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),

            UNIQUE (audit_date, park_id)
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ydia_date
        ON ops.yango_driver_identity_audit_day (audit_date);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ydia_park
        ON ops.yango_driver_identity_audit_day (park_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS ops.yango_driver_identity_audit_day;")
