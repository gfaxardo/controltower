"""
218 — LG-RNA-2B: RNA Pilot Measurement Fact

Creates:
- growth.rna_pilot_measurement_fact

down_revision: 217_yego_lima_rna_priority
"""

from alembic import op

revision = "218_yego_lima_rna_pilot_measurement"
down_revision = "217_yego_lima_rna_priority"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS growth;")
    op.execute("""
        CREATE TABLE IF NOT EXISTS growth.rna_pilot_measurement_fact (
            id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            driver_profile_id           text NOT NULL,
            priority_band               text NOT NULL DEFAULT 'COLD',
            rna_score                   numeric(6,2) NOT NULL DEFAULT 0,
            cohort_date                 date,
            exported_at                 timestamptz,
            contacted_at                timestamptz,
            contact_status              text,
            contact_disposition         text,
            first_trip_after_contact    timestamptz,
            trips_after_contact_7d      integer DEFAULT 0,
            trips_after_contact_30d     integer DEFAULT 0,
            activated_after_contact     boolean DEFAULT false,
            measurement_window_days     integer DEFAULT 30,
            measured_at                 timestamptz NOT NULL DEFAULT now(),
            data_quality                text DEFAULT 'NO_CONTACT_DATA',
            UNIQUE (driver_profile_id, cohort_date)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_rna_pilot_band ON growth.rna_pilot_measurement_fact (priority_band);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_rna_pilot_cohort ON growth.rna_pilot_measurement_fact (cohort_date);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS growth.rna_pilot_measurement_fact;")
