"""
215 — LG-PROG-2A: Program Engine V2 Shadow Tables

Creates:
- growth.yego_lima_program_v2_registry
- growth.yego_lima_program_v2_rule_config
- growth.yego_lima_program_v2_eligibility_daily
- growth.yego_lima_program_v2_assignment_daily
- growth.yego_lima_program_v2_priority_daily
- growth.yego_lima_program_v2_assignment_transition
- growth.yego_lima_program_v2_impact_daily

down_revision: 214_yego_lima_driver_lifecycle
"""

from alembic import op

revision = "215_yego_lima_program_v2"
down_revision = "214_yego_lima_driver_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_registry (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            program_code    text NOT NULL UNIQUE,
            program_name    text NOT NULL,
            program_family  text NOT NULL,
            priority_order  integer NOT NULL,
            target_segment  text NOT NULL,
            is_active       boolean NOT NULL DEFAULT true,
            is_shadow       boolean NOT NULL DEFAULT true,
            version         text NOT NULL DEFAULT 'v2',
            valid_from      date NOT NULL DEFAULT CURRENT_DATE,
            valid_to        date,
            config_json     jsonb,
            created_at      timestamptz NOT NULL DEFAULT now(),
            updated_at      timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_rule_config (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            program_code    text NOT NULL REFERENCES growth.yego_lima_program_v2_registry(program_code),
            rule_key        text NOT NULL,
            operator        text NOT NULL,
            value_json      jsonb NOT NULL,
            required_flag   boolean NOT NULL DEFAULT true,
            exclusion_flag  boolean NOT NULL DEFAULT false,
            version         text NOT NULL DEFAULT 'v2',
            is_active       boolean NOT NULL DEFAULT true,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_eligibility_daily (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date       date NOT NULL,
            driver_profile_id   text NOT NULL,
            program_code        text NOT NULL,
            eligible            boolean NOT NULL DEFAULT false,
            eligibility_reason  text,
            matched_rules_json  jsonb DEFAULT '[]'::jsonb,
            failed_rules_json   jsonb,
            taxonomy_version    text DEFAULT 'v2',
            program_version     text DEFAULT 'v2',
            created_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE(snapshot_date, driver_profile_id, program_code)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_assignment_daily (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date           date NOT NULL,
            driver_profile_id       text NOT NULL,
            assigned_program_code   text,
            assigned_program_name   text,
            assignment_reason       text,
            priority_order          integer,
            eligible_programs_json  jsonb DEFAULT '[]'::jsonb,
            excluded_programs_json  jsonb DEFAULT '[]'::jsonb,
            taxonomy_segment        text,
            lifecycle_status        text,
            activity_status         text,
            value_tier              text,
            momentum_state          text,
            taxonomy_version        text DEFAULT 'v2',
            program_version         text DEFAULT 'v2',
            created_at              timestamptz NOT NULL DEFAULT now(),
            UNIQUE(snapshot_date, driver_profile_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_priority_daily (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date       date NOT NULL,
            driver_profile_id   text NOT NULL,
            program_code        text NOT NULL,
            priority_score      numeric DEFAULT 0,
            rank_global         integer,
            rank_in_program     integer,
            score_components_json jsonb DEFAULT '{}'::jsonb,
            created_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE(snapshot_date, driver_profile_id, program_code)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_assignment_transition (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_profile_id       text NOT NULL,
            prev_date               date,
            curr_date               date NOT NULL,
            previous_program_code   text,
            current_program_code    text,
            previous_segment        text,
            current_segment         text,
            previous_activity_status text,
            current_activity_status text,
            transition_type         text NOT NULL,
            transition_reason       text,
            evidence_json           jsonb,
            created_at              timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_v2_impact_daily (
            id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            snapshot_date               date NOT NULL,
            driver_profile_id           text NOT NULL,
            assigned_program_code       text,
            baseline_trips_7d           integer DEFAULT 0,
            baseline_trips_30d          integer DEFAULT 0,
            next_day_trips              integer,
            next_7d_trips               integer,
            next_30d_trips              integer,
            delta_1d                    integer,
            delta_7d                    integer,
            delta_30d                   integer,
            previous_activity_status    text,
            current_activity_status     text,
            previous_segment            text,
            current_segment             text,
            moved_positive_flag         boolean DEFAULT false,
            moved_negative_flag         boolean DEFAULT false,
            impact_status               text NOT NULL DEFAULT 'PENDING',
            evidence_json               jsonb,
            created_at                  timestamptz NOT NULL DEFAULT now(),
            UNIQUE(snapshot_date, driver_profile_id)
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_impact_daily")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_assignment_transition")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_priority_daily")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_assignment_daily")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_eligibility_daily")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_rule_config")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_v2_registry")
