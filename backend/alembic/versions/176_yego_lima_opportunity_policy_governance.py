"""
176 — YEGO Lima Growth: Opportunity Policy Governance (Fase 5B.1)

Creates:
- growth.yango_lima_opportunity_policy_config
- growth.yango_lima_prioritized_opportunity_daily

Additive. No DROP.

down_revision: 175_yego_lima_data_freshness_governance
"""

from alembic import op

revision = "176_yego_lima_opportunity_policy_governance"
down_revision = "175_yego_lima_data_freshness_governance"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_opportunity_policy_config (
            policy_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            policy_name             text NOT NULL,
            is_active               boolean NOT NULL DEFAULT false,

            effective_from          date NOT NULL,
            effective_to            date NULL,

            weekly_trips_target     integer NOT NULL DEFAULT 100,
            critical_threshold      integer NOT NULL DEFAULT 50,
            low_threshold           integer NOT NULL DEFAULT 70,
            medium_threshold        integer NOT NULL DEFAULT 100,
            top_performer_threshold integer NOT NULL DEFAULT 100,
            top_performer_percentile numeric(5,4) NULL DEFAULT 0.8000,

            daily_action_capacity   integer NOT NULL DEFAULT 500,
            max_per_program         integer NULL,

            high_value_min_weekly_trips       integer NOT NULL DEFAULT 80,
            high_value_inactive_days          integer NOT NULL DEFAULT 1,
            high_value_critical_inactive_days integer NOT NULL DEFAULT 3,

            churn_requires_real_decline       boolean NOT NULL DEFAULT true,
            missing_data_is_churn             boolean NOT NULL DEFAULT false,

            exclude_top_performers_from_active_growth boolean NOT NULL DEFAULT true,
            allow_multi_program_eligibility            boolean NOT NULL DEFAULT true,
            enforce_single_actionable_program         boolean NOT NULL DEFAULT true,

            created_at              timestamptz NOT NULL DEFAULT now(),
            updated_at              timestamptz NOT NULL DEFAULT now(),
            created_by              text NULL,
            notes                   text NULL
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yango_lima_prioritized_opportunity_daily (
            opportunity_date        date NOT NULL,
            driver_profile_id       text NOT NULL,
            policy_id               uuid NOT NULL,

            selected_program_code   text NOT NULL,
            eligible_programs       text[] NULL,
            opportunity_type        text NOT NULL,

            lifecycle_state         text NULL,
            performance_state       text NULL,
            retention_state         text NULL,

            completed_orders_7d     integer NULL,
            completed_orders_30d    integer NULL,
            completed_orders_week   integer NULL,
            supply_hours_7d         numeric(18,4) NULL,
            supply_hours_30d        numeric(18,4) NULL,
            distance_to_target      integer NULL,
            historical_avg_orders_12w numeric(18,4) NULL,
            best_week_12w           integer NULL,

            productivity_bucket     text NULL,
            value_tier              text NULL,
            risk_tier               text NULL,

            opportunity_score       numeric(18,4) NOT NULL DEFAULT 0,
            impact_score            numeric(18,4) NULL,
            urgency_score           numeric(18,4) NULL,
            probability_score       numeric(18,4) NULL,
            final_rank              integer NULL,

            is_actionable_today     boolean NOT NULL DEFAULT false,
            action_capacity_rank    integer NULL,
            exclusion_reason        text NULL,
            management_status       text NOT NULL DEFAULT 'PENDING_ACTION',
            assigned_agent          text NULL,
            action_id               uuid NULL,

            generated_at            timestamptz NOT NULL DEFAULT now(),
            closed_at               timestamptz NULL,

            PRIMARY KEY (opportunity_date, driver_profile_id)
        );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_date ON growth.yango_lima_prioritized_opportunity_daily (opportunity_date);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_program ON growth.yango_lima_prioritized_opportunity_daily (selected_program_code);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_actionable ON growth.yango_lima_prioritized_opportunity_daily (is_actionable_today);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_rank ON growth.yango_lima_prioritized_opportunity_daily (final_rank);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_bucket ON growth.yango_lima_prioritized_opportunity_daily (productivity_bucket);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_value ON growth.yango_lima_prioritized_opportunity_daily (value_tier);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_risk ON growth.yango_lima_prioritized_opportunity_daily (risk_tier);")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_active ON growth.yango_lima_opportunity_policy_config (is_active) WHERE is_active = true;")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_prioritized_opportunity_daily;")
    op.execute("DROP TABLE IF EXISTS growth.yango_lima_opportunity_policy_config;")
