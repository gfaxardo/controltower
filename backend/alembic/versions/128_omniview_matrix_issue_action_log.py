"""
Tracking de acciones ejecutadas sobre issues de Omniview Matrix.

Revision ID: 128_omniview_matrix_issue_action_log
Revises: 127_omniview_matrix_trust_decision_history
"""

from alembic import op

revision = "128_omniview_matrix_issue_action_log"
down_revision = "127_omniview_matrix_trust_decision_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.omniview_matrix_issue_action_log (
            id            bigserial PRIMARY KEY,
            issue_key     text NOT NULL,
            issue_code    text NOT NULL,
            city          text,
            lob           text,
            period_key    date,
            metric        text,
            action_status text NOT NULL,
            action_label  text,
            notes         text,
            executed_at   timestamptz NOT NULL DEFAULT now(),
            resolved_at   timestamptz,
            payload       jsonb
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_omniview_matrix_issue_action_log_key_exec
        ON ops.omniview_matrix_issue_action_log (issue_key, executed_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.omniview_matrix_issue_action_log CASCADE")
