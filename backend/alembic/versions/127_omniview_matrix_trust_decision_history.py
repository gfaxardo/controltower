"""
Historial de trust / decisión operativa para Omniview Matrix.

Revision ID: 127_omniview_matrix_trust_decision_history
Revises: 126_business_slice_trips_unified_trust
"""

from alembic import op

revision = "127_omniview_matrix_trust_decision_history"
down_revision = "126_business_slice_trips_unified_trust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.omniview_matrix_trust_history (
            id              bigserial PRIMARY KEY,
            period_key      date NOT NULL,
            evaluated_at    timestamptz NOT NULL DEFAULT now(),
            decision_mode   text NOT NULL,
            confidence_score smallint NOT NULL,
            coverage_score   numeric,
            freshness_score  numeric,
            consistency_score numeric,
            top_codes        text[],
            payload          jsonb
        )
    """)
    op.execute("""
        ALTER TABLE ops.omniview_matrix_trust_history
        ADD COLUMN IF NOT EXISTS evaluated_at timestamptz NOT NULL DEFAULT now(),
        ADD COLUMN IF NOT EXISTS decision_mode text,
        ADD COLUMN IF NOT EXISTS confidence_score smallint,
        ADD COLUMN IF NOT EXISTS coverage_score numeric,
        ADD COLUMN IF NOT EXISTS freshness_score numeric,
        ADD COLUMN IF NOT EXISTS consistency_score numeric,
        ADD COLUMN IF NOT EXISTS top_codes text[],
        ADD COLUMN IF NOT EXISTS payload jsonb
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_omniview_matrix_trust_hist_period_eval
        ON ops.omniview_matrix_trust_history (period_key DESC, evaluated_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.omniview_matrix_trust_history CASCADE")
