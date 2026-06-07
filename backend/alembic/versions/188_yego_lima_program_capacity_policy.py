"""
188 — LG-UX-R2.8E: Program Capacity Policy

Creates:
- growth.yego_lima_program_capacity_policy

Governed allocation policy per program.
Min/max caps, target share, allocation mode.
Versioned. Audit trace. No auto-apply.

down_revision: 187_yego_lima_attribution_candidates
"""

from alembic import op

revision = "188_yego_lima_program_capacity_policy"
down_revision = "187_yego_lima_attribution_candidates"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_capacity_policy (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            version         integer NOT NULL DEFAULT 1,
            policy_date_from date NOT NULL DEFAULT CURRENT_DATE,
            policy_date_to  date,
            program_code    text NOT NULL,
            priority_rank   integer NOT NULL,
            allocation_mode text NOT NULL DEFAULT 'STRICT_PRIORITY'
                CHECK (allocation_mode IN ('STRICT_PRIORITY', 'PROPORTIONAL', 'HYBRID')),
            min_daily_capacity integer,
            max_daily_capacity integer,
            target_share_pct numeric(5,2),
            is_enabled      boolean NOT NULL DEFAULT true,
            policy_reason   text,
            created_at      timestamptz NOT NULL DEFAULT now(),
            updated_at      timestamptz NOT NULL DEFAULT now(),
            created_by      text NOT NULL DEFAULT 'system'
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_policy_program_date
        ON growth.yego_lima_program_capacity_policy (program_code, policy_date_from)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_policy_enabled
        ON growth.yego_lima_program_capacity_policy (is_enabled)
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_capacity_policy")
