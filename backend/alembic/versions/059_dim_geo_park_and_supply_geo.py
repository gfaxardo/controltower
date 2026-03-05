"""
dim.dim_geo_park: dimensión geo park (city, country) para Control Tower Supply.
Fuente inicial: dim.dim_park. city/country = COALESCE desde dim_park o 'UNKNOWN'.
Seed override: backend/seeds/geo_parks_seed.sql (aplicar manualmente o con apply_geo_parks_seed.py).
"""
from alembic import op

revision = "059_dim_geo_park"
down_revision = "058_fix_driver_lifecycle_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS dim")
    op.execute("""
        CREATE TABLE IF NOT EXISTS dim.dim_geo_park (
            park_id text PRIMARY KEY,
            park_name text NOT NULL,
            city text NOT NULL,
            country text NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    # Poblar desde dim_park si existe (park_id, park_name, city, country)
    op.execute("""
        INSERT INTO dim.dim_geo_park (park_id, park_name, city, country)
        SELECT
            p.park_id,
            COALESCE(p.park_name, p.park_id, ''),
            COALESCE(NULLIF(TRIM(p.city), ''), 'UNKNOWN'),
            COALESCE(NULLIF(TRIM(p.country), ''), 'UNKNOWN')
        FROM dim.dim_park p
        ON CONFLICT (park_id) DO UPDATE SET
            park_name = EXCLUDED.park_name,
            city = COALESCE(NULLIF(TRIM(EXCLUDED.city), ''), dim.dim_geo_park.city),
            country = COALESCE(NULLIF(TRIM(EXCLUDED.country), ''), dim.dim_geo_park.country),
            updated_at = now()
    """)
    # Vista solo lectura (activos)
    op.execute("DROP VIEW IF EXISTS dim.v_geo_park CASCADE")
    op.execute("""
        CREATE VIEW dim.v_geo_park AS
        SELECT park_id, park_name, city, country
        FROM dim.dim_geo_park
        WHERE is_active = true
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS dim.v_geo_park CASCADE")
    op.execute("DROP TABLE IF EXISTS dim.dim_geo_park CASCADE")
