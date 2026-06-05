"""
177 — YEGO Lima Growth: Recency Policy Fields (Fase 5B.1E)

Adds recency governance columns to opportunity_policy_config.

down_revision: 176_yego_lima_opportunity_policy_governance
"""

from alembic import op

revision = "177_yego_lima_recency_policy_fields"
down_revision = "176_yego_lima_opportunity_policy_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS active_growth_max_inactive_days integer NOT NULL DEFAULT 30;
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS high_value_recovery_max_inactive_days integer NOT NULL DEFAULT 14;
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS dormant_recovery_min_inactive_days integer NOT NULL DEFAULT 30;
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS dormant_recovery_enabled boolean NOT NULL DEFAULT false;
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS low_cost_reactivation_min_inactive_days integer NOT NULL DEFAULT 90;
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS require_recent_signal_for_active_growth boolean NOT NULL DEFAULT true;
    """)
    op.execute("""
        ALTER TABLE growth.yango_lima_opportunity_policy_config
        ADD COLUMN IF NOT EXISTS require_decline_evidence_for_churn boolean NOT NULL DEFAULT true;
    """)


def downgrade():
    for col in [
        "active_growth_max_inactive_days",
        "high_value_recovery_max_inactive_days",
        "dormant_recovery_min_inactive_days",
        "dormant_recovery_enabled",
        "low_cost_reactivation_min_inactive_days",
        "require_recent_signal_for_active_growth",
        "require_decline_evidence_for_churn",
    ]:
        op.execute(f"ALTER TABLE growth.yango_lima_opportunity_policy_config DROP COLUMN IF EXISTS {col};")
