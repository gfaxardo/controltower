"""
Capa canónica service_type -> LOB: una sola fuente de verdad.
- canon.dim_real_service_type_lob: dimensión (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at).
- canon.normalize_real_tipo_servicio(raw): función única de normalización raw -> norm.
- ops.v_real_trips_service_lob_resolved: vista por viaje con tipo_servicio_raw, tipo_servicio_norm, lob_group_resolved, is_unclassified.
- ops.v_real_trips_with_lob_v2: redefinida para leer de la capa resuelta (mantiene contrato).
- Semilla: datos desde canon.map_real_tipo_servicio_to_lob_group (no se elimina; se documenta dim como fuente de verdad).
"""
from alembic import op

revision = "070_canonical_service_type_lob"
down_revision = "069_real_lob_residual_diagnostic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) Dimensión canónica ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.dim_real_service_type_lob (
            service_type_norm text PRIMARY KEY,
            lob_group text NOT NULL,
            mapping_source text NOT NULL DEFAULT 'manual',
            is_active boolean NOT NULL DEFAULT true,
            notes text,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        COMMENT ON TABLE canon.dim_real_service_type_lob IS
        'Capa canónica Real: service_type normalizado -> lob_group. Única fuente de verdad para mapping; auditable.'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_dim_real_service_type_lob_lob ON canon.dim_real_service_type_lob (lob_group)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_dim_real_service_type_lob_active ON canon.dim_real_service_type_lob (is_active) WHERE is_active = true")

    # --- 2) Poblar desde mapping actual (no se pierden mappings validados) ---
    op.execute("""
        INSERT INTO canon.dim_real_service_type_lob (service_type_norm, lob_group, mapping_source, is_active, notes, updated_at)
        SELECT real_tipo_servicio, lob_group, 'manual', true, 'Migrado desde map_real_tipo_servicio_to_lob_group', now()
        FROM canon.map_real_tipo_servicio_to_lob_group
        ON CONFLICT (service_type_norm) DO UPDATE SET
            lob_group = EXCLUDED.lob_group,
            updated_at = now()
    """)

    # --- 3) Función única de normalización (raw -> norm) ---
    op.execute("""
        CREATE OR REPLACE FUNCTION canon.normalize_real_tipo_servicio(raw text)
        RETURNS text
        LANGUAGE sql
        STABLE
        AS $$
            SELECT CASE
                WHEN raw IS NULL OR TRIM(raw::text) = '' THEN NULL
                WHEN LENGTH(TRIM(raw::text)) > 30 THEN 'UNCLASSIFIED'
                WHEN LOWER(TRIM(raw::text)) IN ('economico', 'económico') THEN 'economico'
                WHEN LOWER(TRIM(raw::text)) IN ('confort', 'comfort') THEN 'confort'
                WHEN LOWER(TRIM(raw::text)) = 'confort+' THEN 'confort+'
                WHEN LOWER(TRIM(raw::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                WHEN LOWER(TRIM(raw::text)) IN ('exprés','exprs') THEN 'express'
                WHEN LOWER(TRIM(raw::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(raw::text))
                WHEN LOWER(TRIM(raw::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                ELSE LOWER(TRIM(raw::text))
            END
        $$
    """)
    op.execute("COMMENT ON FUNCTION canon.normalize_real_tipo_servicio(text) IS 'Normalización canónica tipo_servicio raw -> clave para lookup en dim_real_service_type_lob.'")

    # --- 4) Vista por viaje: capa resuelta (trazabilidad raw -> norm -> lob) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_trips_service_lob_resolved AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                t.distancia_km,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                canon.normalize_real_tipo_servicio(tipo_servicio::text) AS tipo_servicio_norm
            FROM with_country
        )
        SELECT
            r.country,
            r.city,
            r.park_id,
            r.park_name,
            r.fecha_inicio_viaje,
            r.tipo_servicio AS tipo_servicio_raw,
            r.tipo_servicio_norm,
            COALESCE(d.lob_group, 'UNCLASSIFIED') AS lob_group_resolved,
            (d.service_type_norm IS NULL OR NOT COALESCE(d.is_active, true)) AS is_unclassified,
            CASE WHEN r.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            r.revenue,
            r.comision_empresa_asociada,
            r.distancia_km
        FROM with_norm r
        LEFT JOIN canon.dim_real_service_type_lob d ON d.service_type_norm = r.tipo_servicio_norm AND d.is_active = true
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_service_lob_resolved IS
        'Capa resuelta por viaje: tipo_servicio_raw -> tipo_servicio_norm (canon.normalize_real_tipo_servicio) -> lob_group_resolved (canon.dim_real_service_type_lob). Trazabilidad completa.'
    """)

    # --- 5) v_real_trips_with_lob_v2: wrapper sobre capa resuelta (mantiene contrato existente) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_trips_with_lob_v2 AS
        SELECT
            country,
            city,
            park_id,
            park_name,
            fecha_inicio_viaje,
            tipo_servicio_norm AS real_tipo_servicio_norm,
            lob_group_resolved AS lob_group,
            segment_tag,
            revenue,
            comision_empresa_asociada,
            distancia_km
        FROM ops.v_real_trips_service_lob_resolved
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_with_lob_v2 IS
        'Real LOB v2: wrapper sobre v_real_trips_service_lob_resolved. Mantiene contrato (real_tipo_servicio_norm, lob_group) para drill y backfill.'
    """)


def downgrade() -> None:
    # Restaurar v_real_trips_with_lob_v2 a su definición anterior (064: CASE inline + map)
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_trips_with_lob_v2 AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                t.distancia_km,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM with_country
        )
        SELECT
            v.country,
            v.city,
            v.park_id,
            v.park_name,
            v.fecha_inicio_viaje,
            v.real_tipo_servicio_norm,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            v.revenue,
            v.comision_empresa_asociada,
            v.distancia_km
        FROM with_norm v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved CASCADE")
    op.execute("DROP FUNCTION IF EXISTS canon.normalize_real_tipo_servicio(text)")
    op.execute("DROP TABLE IF EXISTS canon.dim_real_service_type_lob CASCADE")
