"""
133 — Canonical business slice layer.

- dim.dim_business_slice_mapping: raw_value -> canonical_value
- seed inicial para tajadas operativas y aliases más frecuentes
"""

from alembic import op

revision = "133_business_slice_canonical_mapping_layer"
down_revision = "132_control_loop_tajadas_realignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS dim")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dim.dim_business_slice_mapping (
            raw_value TEXT PRIMARY KEY,
            canonical_value TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_dim_business_slice_mapping_canonical
        ON dim.dim_business_slice_mapping (canonical_value)
        """
    )
    op.execute(
        """
        COMMENT ON TABLE dim.dim_business_slice_mapping IS
        'Capa canónica única de tajadas: cada raw_value se resuelve a canonical_value.'
        """
    )
    op.execute(
        """
        INSERT INTO dim.dim_business_slice_mapping (raw_value, canonical_value)
        SELECT x.raw_value, x.canonical_value
        FROM (
            VALUES
                ('Delivery', 'Delivery'),
                ('Delivery moto', 'Delivery'),
                ('Delivery bicicleta', 'Delivery'),
                ('Mensajería', 'Delivery'),
                ('Mensajeria', 'Delivery'),
                ('Moto', 'Moto'),
                ('Taxi Moto', 'Moto'),
                ('Taxi moto', 'Moto'),
                ('Tuk Tuk', 'Tuk Tuk'),
                ('Auto regular', 'Auto regular'),
                ('Carga', 'Carga'),
                ('PRO', 'PRO'),
                ('YMA', 'YMA'),
                ('YMM', 'YMM')
        ) AS x(raw_value, canonical_value)
        WHERE NOT EXISTS (
            SELECT 1
            FROM dim.dim_business_slice_mapping d
            WHERE lower(trim(d.raw_value)) = lower(trim(x.raw_value))
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dim.dim_business_slice_mapping CASCADE")
