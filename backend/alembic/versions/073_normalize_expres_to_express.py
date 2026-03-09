"""
Normalizar Exprés → express (no expres).
Agregar equivalencia explícita en normalized_service_type para el caso 'exprés'/'expres'.
Actualizar mapping LOB: agregar 'express' como alias si no existe; mantener 'expres' por compatibilidad.
"""
from alembic import op

revision = "073_normalize_expres_to_express"
down_revision = "072_service_type_unaccent_canonical"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Actualizar normalized_service_type para mapear expres -> express
    op.execute(r"""
        CREATE OR REPLACE FUNCTION ops.normalized_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            LOWER(TRIM(unaccent(COALESCE(raw_value, '')))),
                            '[+]', '_plus', 'g'
                        ),
                        '[\s-]+', '_', 'g'
                    ),
                    '[^a-z0-9_]', '', 'g'
                ) = 'expres' THEN 'express'
                ELSE regexp_replace(
                    regexp_replace(
                        regexp_replace(
                            LOWER(TRIM(unaccent(COALESCE(raw_value, '')))),
                            '[+]', '_plus', 'g'
                        ),
                        '[\s-]+', '_', 'g'
                    ),
                    '[^a-z0-9_]', '', 'g'
                )
            END
        $$
    """)


def downgrade() -> None:
    op.execute(r"""
        CREATE OR REPLACE FUNCTION ops.normalized_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT regexp_replace(
                regexp_replace(
                    regexp_replace(
                        LOWER(TRIM(unaccent(COALESCE(raw_value, '')))),
                        '[+]', '_plus', 'g'
                    ),
                    '[\s-]+', '_', 'g'
                ),
                '[^a-z0-9_]', '', 'g'
            )
        $$
    """)
