"""
PASO 4 E2E — Tabla oficial de homologación y vistas finales Plan vs Real.
"""
from alembic import op

revision = "034_lob_homologation_final"
down_revision = "033_plan_vs_real_resolved_park"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.lob_homologation_final (
            country TEXT,
            city TEXT,
            park_id TEXT,
            park_name TEXT,
            real_tipo_servicio TEXT,
            plan_lob_name TEXT,
            confidence TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (country, city, park_id, real_tipo_servicio)
        )
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_final CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolved_final CASCADE")

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolved_final AS
        SELECT
            r.country,
            r.city,
            r.park_id,
            r.park_name,
            r.real_tipo_servicio,
            COALESCE(h.plan_lob_name, 'UNMAPPED') AS resolved_lob,
            r.real_trips,
            r.first_seen_date,
            r.last_seen_date
        FROM ops.v_real_universe_by_park_for_hunt r
        LEFT JOIN ops.lob_homologation_final h
            ON LOWER(TRIM(COALESCE(r.country, ''))) = LOWER(TRIM(COALESCE(h.country, '')))
           AND LOWER(TRIM(r.city)) = LOWER(TRIM(COALESCE(h.city, '')))
           AND LOWER(TRIM(r.park_id)) = LOWER(TRIM(COALESCE(h.park_id, '')))
           AND LOWER(TRIM(r.real_tipo_servicio)) = LOWER(TRIM(h.real_tipo_servicio))
    """)

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_final AS
        SELECT
            COALESCE(p.country, r.country) AS country,
            COALESCE(p.city, r.city) AS city,
            COALESCE(p.plan_lob_name, r.resolved_lob) AS lob,
            COALESCE(SUM(p.trips_plan), 0) AS plan_trips,
            COALESCE(SUM(r.real_trips), 0) AS real_trips,
            COALESCE(SUM(r.real_trips), 0) - COALESCE(SUM(p.trips_plan), 0) AS variance_trips
        FROM ops.v_plan_lob_universe_raw p
        FULL OUTER JOIN ops.v_real_lob_resolved_final r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND LOWER(TRIM(p.plan_lob_name)) = LOWER(TRIM(r.resolved_lob))
        GROUP BY 1, 2, 3
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_final CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolved_final CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.lob_homologation_final")
