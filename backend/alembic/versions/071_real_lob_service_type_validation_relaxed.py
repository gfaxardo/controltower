r"""
Relajar validación de service_type: solo UNCLASSIFIED si tiene coma, >30 chars o caracteres fuera de [a-z0-9_\-].
Acepta: economico, comfort_plus, delivery-express, cargo, moto, etc. (regex ^[a-z0-9_\-]+$).
"""
from alembic import op

revision = "071_real_lob_service_type_validation_relaxed"
down_revision = "070_real_lob_service_type_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Validación relajada: solo rechazar si contiene coma, >30 caracteres, o caracteres fuera de [a-z0-9_\-]
    # Valor aceptado = LOWER(TRIM(raw_value)) tal cual (sin normalizar espacios a _)
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.validated_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN raw_value IS NULL OR TRIM(COALESCE(raw_value, '')) = '' THEN 'UNCLASSIFIED'
                WHEN LOWER(TRIM(COALESCE(raw_value, ''))) LIKE '%,%' THEN 'UNCLASSIFIED'
                WHEN LENGTH(LOWER(TRIM(COALESCE(raw_value, '')))) > 30 THEN 'UNCLASSIFIED'
                WHEN LOWER(TRIM(COALESCE(raw_value, ''))) !~ '^[a-z0-9_\\-]+$' THEN 'UNCLASSIFIED'
                ELSE LOWER(TRIM(COALESCE(raw_value, '')))
            END
        $$
    """)


def downgrade() -> None:
    # Restaurar lógica 070 (más estricta: palabras, etc.)
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.validated_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN raw_value IS NULL OR TRIM(raw_value) = '' THEN 'UNCLASSIFIED'
                WHEN LENGTH(TRIM(raw_value)) > 30 THEN 'UNCLASSIFIED'
                WHEN raw_value LIKE '%,%' THEN 'UNCLASSIFIED'
                WHEN (LENGTH(TRIM(raw_value)) - LENGTH(REPLACE(TRIM(raw_value), ' ', ''))) > 2 THEN 'UNCLASSIFIED'
                WHEN TRIM(raw_value) !~ '^[a-zA-Z0-9_\\s-]+$' THEN 'UNCLASSIFIED'
                ELSE ops.normalized_service_type(raw_value)
            END
        $$
    """)
