"""
PASO 3D E2E — Vista REAL por park: JOIN parks.id = trips_all.park_id.
Llave homologación: (country, city, park_id, real_tipo_servicio) → plan_lob_name.
"""
from alembic import op

revision = "032_real_universe_join_parks_id"
down_revision = "031_real_universe_join_b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Vista REAL por park con JOIN correcto (parks.id = trips_all.park_id)
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.id::text AS park_id,
          COALESCE(NULLIF(TRIM(p.name::text), ''), NULLIF(TRIM(p.created_at::text), ''), p.id::text) AS park_name,
          LOWER(TRIM(COALESCE(p.city::text, ''))) AS city,
          ''::text AS country,
          LOWER(TRIM(t.tipo_servicio::text)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """)

    # 2) updated_at y permitir confidence = 'unmapped'
    op.execute("ALTER TABLE ops.lob_homologation ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT now()")
    op.execute("ALTER TABLE ops.lob_homologation DROP CONSTRAINT IF EXISTS lob_homologation_confidence_check")
    op.execute("ALTER TABLE ops.lob_homologation ADD CONSTRAINT lob_homologation_confidence_check CHECK (confidence IN ('high','medium','low','unmapped'))")
    op.execute("ALTER TABLE ops.lob_homologation ALTER COLUMN plan_lob_name DROP NOT NULL")

    # 3) Llave única homologación: (country, city, park_id, real_tipo_servicio) — una fila por clave
    op.execute("DROP INDEX IF EXISTS ops.uq_lob_homologation_country_city_park_real_plan")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lob_homologation_key
        ON ops.lob_homologation (country, city, park_id, real_tipo_servicio)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ops.uq_lob_homologation_key")
    op.execute("ALTER TABLE ops.lob_homologation DROP CONSTRAINT IF EXISTS lob_homologation_confidence_check")
    op.execute("ALTER TABLE ops.lob_homologation ADD CONSTRAINT lob_homologation_confidence_check CHECK (confidence IN ('high','medium','low'))")
    op.execute("ALTER TABLE ops.lob_homologation DROP COLUMN IF EXISTS updated_at")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lob_homologation_country_city_park_real_plan
        ON ops.lob_homologation (country, city, park_id, real_tipo_servicio, plan_lob_name)
    """)
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT p.city::text AS park_id,
          COALESCE(NULLIF(TRIM(p.created_at::text), ''), NULLIF(TRIM(p.name::text), ''), NULLIF(TRIM(p.id::text), ''), p.city::text) AS park_name,
          ''::text AS country,
          LOWER(TRIM(p.id::text)) AS city,
          LOWER(TRIM(t.tipo_servicio)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p ON REPLACE(LOWER(TRIM(p.city::text)), '-', '') = REPLACE(LOWER(TRIM(t.park_id::text)), '-', '')
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """)
