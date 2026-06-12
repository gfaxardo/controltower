"""
217 — LG-RNA-2A: RNA Priority Fact

Creates:
- growth.rna_priority_fact

down_revision: 216_yego_lima_export_audit
"""

from alembic import op

revision = "217_yego_lima_rna_priority"
down_revision = "216_yego_lima_export_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.rna_priority_fact (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_profile_id   text NOT NULL UNIQUE,
            rna_score           numeric(6,2) NOT NULL DEFAULT 0,
            priority_band       text NOT NULL DEFAULT 'COLD',
            contactable         boolean DEFAULT false,
            cancelled_signal    boolean DEFAULT false,
            lifecycle           text,
            value_tier          text,
            momentum            text,
            trips_7d            integer DEFAULT 0,
            trips_30d           integer DEFAULT 0,
            days_since_last_trip integer,
            movement_score      integer DEFAULT 0,
            program_code        text,
            signal_breakdown_json jsonb DEFAULT '{}'::jsonb,
            score_version       text DEFAULT 'v1',
            scored_at           timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rna_priority_band ON growth.rna_priority_fact (priority_band);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_rna_priority_score ON growth.rna_priority_fact (rna_score DESC);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.rna_priority_fact;")
