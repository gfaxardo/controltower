"""
Normalización canónica de service_type con unaccent.

Problema: validated_service_type() aplicaba regex ANTES de quitar tildes/espacios/+.
Resultado: 'Económico' (77% de trips PE) → UNCLASSIFIED; tuk-tuk vs tuk_tuk duplicados.

Solución:
1. normalized_service_type(): unaccent → lower → trim → + → _plus → espacios/guiones → _ → solo [a-z0-9_]
2. validated_service_type(): normaliza PRIMERO, luego valida longitud/coma/palabras sobre el raw.
3. Actualizar mapping LOB para cubrir nuevas claves normalizadas (expres, envios, confort_plus, tuk_tuk, taxi_moto).
4. Actualizar v_audit_service_type con la nueva lógica.
"""
from alembic import op

revision = "072_service_type_unaccent_canonical"
down_revision = "071_real_lob_service_type_validation_relaxed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0) Extensión unaccent
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # 1) Normalización canónica: unaccent, lower, trim, + → _plus, espacios/guiones → _, solo [a-z0-9_]
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

    # 2) Validación: normalizar PRIMERO, rechazar solo basura evidente sobre el raw
    op.execute(r"""
        CREATE OR REPLACE FUNCTION ops.validated_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN raw_value IS NULL OR TRIM(COALESCE(raw_value, '')) = '' THEN 'UNCLASSIFIED'
                WHEN TRIM(COALESCE(raw_value, '')) LIKE '%,%' THEN 'UNCLASSIFIED'
                WHEN LENGTH(TRIM(COALESCE(raw_value, ''))) > 30 THEN 'UNCLASSIFIED'
                WHEN (LENGTH(TRIM(raw_value)) - LENGTH(REPLACE(TRIM(raw_value), ' ', ''))) > 2 THEN 'UNCLASSIFIED'
                ELSE ops.normalized_service_type(raw_value)
            END
        $$
    """)

    # 3) Actualizar mapping LOB con claves normalizadas que faltaban
    op.execute("""
        INSERT INTO canon.map_real_tipo_servicio_to_lob_group (real_tipo_servicio, lob_group) VALUES
            ('confort_plus', 'auto taxi'),
            ('tuk_tuk', 'tuk tuk'),
            ('taxi_moto', 'taxi moto'),
            ('expres', 'delivery'),
            ('envios', 'delivery'),
            ('xl', 'auto taxi'),
            ('economy', 'auto taxi')
        ON CONFLICT (real_tipo_servicio) DO UPDATE SET lob_group = EXCLUDED.lob_group
    """)

    # 4) Recrear vista de auditoría (columnas cambian: se añade service_type_validated)
    op.execute("DROP VIEW IF EXISTS ops.v_audit_service_type")
    op.execute("""
        CREATE VIEW ops.v_audit_service_type AS
        SELECT
            TRIM(COALESCE(t.tipo_servicio::text, '')) AS service_type_raw,
            ops.normalized_service_type(t.tipo_servicio::text) AS service_type_normalized,
            ops.validated_service_type(t.tipo_servicio::text) AS service_type_validated,
            COUNT(*)::bigint AS viajes,
            (-1) * SUM(t.comision_empresa_asociada)::numeric AS margen_total
        FROM ops.v_trips_real_canon t
        WHERE t.condicion = 'Completado'
          AND t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_inicio_viaje::date >= (CURRENT_DATE - INTERVAL '90 days')::date
          AND t.tipo_servicio IS NOT NULL
        GROUP BY TRIM(COALESCE(t.tipo_servicio::text, '')),
                 ops.normalized_service_type(t.tipo_servicio::text),
                 ops.validated_service_type(t.tipo_servicio::text)
        ORDER BY viajes DESC
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM canon.map_real_tipo_servicio_to_lob_group
        WHERE real_tipo_servicio IN ('confort_plus', 'tuk_tuk', 'taxi_moto', 'expres', 'envios', 'xl', 'economy')
    """)
    # Restaurar funciones de 071
    op.execute(r"""
        CREATE OR REPLACE FUNCTION ops.validated_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN raw_value IS NULL OR TRIM(COALESCE(raw_value, '')) = '' THEN 'UNCLASSIFIED'
                WHEN LOWER(TRIM(COALESCE(raw_value, ''))) LIKE '%,%' THEN 'UNCLASSIFIED'
                WHEN LENGTH(LOWER(TRIM(COALESCE(raw_value, '')))) > 30 THEN 'UNCLASSIFIED'
                WHEN LOWER(TRIM(COALESCE(raw_value, ''))) !~ '^[a-z0-9_\-]+$' THEN 'UNCLASSIFIED'
                ELSE LOWER(TRIM(COALESCE(raw_value, '')))
            END
        $$
    """)
    op.execute(r"""
        CREATE OR REPLACE FUNCTION ops.normalized_service_type(raw_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT regexp_replace(
                regexp_replace(
                    regexp_replace(LOWER(TRIM(COALESCE(raw_value, ''))), '\s+', '_', 'g'),
                    '-', '_', 'g'
                ),
                '[^a-z0-9_]', '', 'g'
            )
        $$
    """)
