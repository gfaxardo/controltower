"""
198 — LG-OEF-2_3_4A: Program Governance + Freshness Registry

Creates:
- growth.yego_lima_program_registry
- growth.yego_lima_freshness_registry

down_revision: 197_yego_lima_action_ledger
"""

from alembic import op

revision = "198_yego_lima_program_freshness"
down_revision = "197_yego_lima_action_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_program_registry (
            program_code        text PRIMARY KEY,
            program_name        text NOT NULL,
            description         text,
            active              boolean NOT NULL DEFAULT true,
            priority            integer DEFAULT 0,
            policy_version      text DEFAULT 'v1',
            valid_from          date DEFAULT CURRENT_DATE,
            valid_to            date,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        INSERT INTO growth.yego_lima_program_registry (program_code, program_name, description, active, priority)
        VALUES 
            ('PROGRAM_HIGH_VALUE_RECOVERY', 'High Value Recovery', 'High historical value, recently inactive drivers', true, 1),
            ('PROGRAM_CHURN_PREVENTION', 'Churn Prevention', 'Drivers at risk of churning or declining', true, 2),
            ('PROGRAM_14_90', 'Programa 14/90', 'New or reactivated drivers within 14-90 day window', true, 3),
            ('PROGRAM_ACTIVE_GROWTH', 'Active Growth', 'Active drivers below weekly performance target', true, 4)
        ON CONFLICT (program_code) DO NOTHING
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.yego_lima_freshness_registry (
            component           text NOT NULL,
            last_refresh_at     timestamptz,
            freshness_status    text DEFAULT 'UNKNOWN',
            latency_minutes     integer,
            run_id              text,
            max_data_date       date,
            updated_at          timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (component)
        )
    """)

    op.execute("""
        INSERT INTO growth.yego_lima_freshness_registry (component, freshness_status)
        VALUES 
            ('raw_orders', 'UNKNOWN'),
            ('driver_state', 'UNKNOWN'),
            ('eligibility', 'UNKNOWN'),
            ('prioritized', 'UNKNOWN'),
            ('queue', 'UNKNOWN'),
            ('daily_registry', 'UNKNOWN'),
            ('snapshot_registry', 'UNKNOWN')
        ON CONFLICT (component) DO NOTHING
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_freshness_registry")
    op.execute("DROP TABLE IF EXISTS growth.yego_lima_program_registry")
