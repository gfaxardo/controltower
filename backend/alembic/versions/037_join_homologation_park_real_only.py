"""
PASO 4 FIX UNMAPPED — Join homologación SOLO por (park_id, real_tipo_servicio).
Country/city son atributos; no forman parte del join para resolver LOB.
"""
from alembic import op

revision = "037_join_park_real_only"
down_revision = "036_recreate_dep_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Índice para el join por (park_id, real_tipo_servicio)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_homologation_final_park_real
        ON ops.lob_homologation_final (park_id, real_tipo_servicio)
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_final CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolved_final CASCADE")

    # Resolver LOB solo por park_id + real_tipo_servicio (LOWER/TRIM). Si hay varias filas en h, tomar la más reciente.
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
        LEFT JOIN LATERAL (
            SELECT h2.plan_lob_name
            FROM ops.lob_homologation_final h2
            WHERE LOWER(TRIM(h2.park_id)) = LOWER(TRIM(r.park_id))
              AND LOWER(TRIM(h2.real_tipo_servicio)) = LOWER(TRIM(r.real_tipo_servicio))
            ORDER BY h2.created_at DESC NULLS LAST
            LIMIT 1
        ) h ON true
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
    op.execute("DROP INDEX IF EXISTS ops.idx_lob_homologation_final_park_real")
    # Recrear vistas con join por country,city,park_id,real_tipo_servicio (036)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolved_final AS
        SELECT r.country, r.city, r.park_id, r.park_name, r.real_tipo_servicio,
               COALESCE(h.plan_lob_name, 'UNMAPPED') AS resolved_lob,
               r.real_trips, r.first_seen_date, r.last_seen_date
        FROM ops.v_real_universe_by_park_for_hunt r
        LEFT JOIN ops.lob_homologation_final h
            ON LOWER(TRIM(COALESCE(r.country, ''))) = LOWER(TRIM(COALESCE(h.country, '')))
           AND LOWER(TRIM(r.city)) = LOWER(TRIM(COALESCE(h.city, '')))
           AND LOWER(TRIM(r.park_id)) = LOWER(TRIM(COALESCE(h.park_id, '')))
           AND LOWER(TRIM(r.real_tipo_servicio)) = LOWER(TRIM(h.real_tipo_servicio))
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_final AS
        SELECT COALESCE(p.country, r.country) AS country, COALESCE(p.city, r.city) AS city,
               COALESCE(p.plan_lob_name, r.resolved_lob) AS lob,
               COALESCE(SUM(p.trips_plan), 0) AS plan_trips, COALESCE(SUM(r.real_trips), 0) AS real_trips,
               COALESCE(SUM(r.real_trips), 0) - COALESCE(SUM(p.trips_plan), 0) AS variance_trips
        FROM ops.v_plan_lob_universe_raw p
        FULL OUTER JOIN ops.v_real_lob_resolved_final r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND LOWER(TRIM(p.plan_lob_name)) = LOWER(TRIM(r.resolved_lob))
        GROUP BY 1, 2, 3
    """)
