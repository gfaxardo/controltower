"""update_lob_resolution_with_homologation

Revision ID: 022_lob_resolution_homologation
Revises: 021_lob_homologation
Create Date: 2026-01-23 03:00:00.000000

FASE 2C+ Homologación: Actualizar v_real_lob_resolution para usar homologación
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '022_lob_resolution_homologation'
down_revision = '021_lob_homologation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Actualizar v_real_lob_resolution para usar homologación
    # Flujo: real_tipo_servicio -> lob_homologation -> plan_lob_name -> lob_catalog
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolution AS
        SELECT
            rb.trip_id,
            rb.country,
            rb.city,
            rb.city_raw,
            rb.trip_date,
            rb.lob_base,
            rb.market_type,
            rb.lob_effective,
            -- Homologación: real_tipo_servicio -> plan_lob_name
            h.plan_lob_name AS homologated_plan_lob,
            h.homologation_id,
            h.confidence AS homologation_confidence,
            -- Resolución final: plan_lob_name -> lob_catalog
            l.lob_id,
            lc.lob_name,
            l.mapping_id,
            CASE 
                WHEN l.lob_id IS NOT NULL THEN 'OK' 
                WHEN h.homologation_id IS NOT NULL THEN 'HOMOLOGATED_NO_MAPPING'
                ELSE 'UNMATCHED' 
            END AS resolution_status,
            l.confidence,
            l.priority as mapping_priority
        FROM ops.v_real_lob_base rb
        -- Paso 1: Homologar real_tipo_servicio -> plan_lob_name
        LEFT JOIN ops.lob_homologation h
            ON (h.country IS NULL OR h.country = '' OR h.country = rb.country)
            AND (h.city IS NULL OR h.city = '' OR h.city = rb.city)
            AND TRIM(LOWER(h.real_tipo_servicio)) = TRIM(LOWER(rb.lob_base))
        -- Paso 2: Mapear plan_lob_name -> lob_catalog (usando mapping rules si existen)
        LEFT JOIN LATERAL (
            SELECT m.*
            FROM ops.lob_plan_real_mapping m
            WHERE
                (m.country IS NULL OR m.country = rb.country)
                AND (m.city IS NULL OR m.city = rb.city)
                AND (
                    -- Si hay homologación, usar plan_lob_name
                    (h.plan_lob_name IS NOT NULL AND m.lob_id IN (
                        SELECT lob_id FROM ops.lob_catalog 
                        WHERE TRIM(LOWER(lob_name)) = TRIM(LOWER(h.plan_lob_name))
                        AND (country IS NULL OR country = '' OR country = rb.country)
                        AND (city IS NULL OR city = '' OR city = rb.city)
                    ))
                    -- Si no hay homologación, intentar match directo por service_type
                    OR (h.plan_lob_name IS NULL AND (
                        m.service_type IS NULL 
                        OR LOWER(TRIM(m.service_type)) = LOWER(TRIM(rb.lob_base))
                    ))
                )
                AND (m.market_type IS NULL OR m.market_type = rb.market_type)
                AND (m.valid_to IS NULL OR rb.trip_date::DATE <= m.valid_to)
                AND (m.valid_from IS NULL OR rb.trip_date::DATE >= m.valid_from)
            ORDER BY m.priority ASC, m.confidence DESC
            LIMIT 1
        ) l ON TRUE
        LEFT JOIN ops.lob_catalog lc ON (
            lc.lob_id = l.lob_id
            OR (
                -- Si hay homologación pero no mapping, intentar match directo por lob_name
                h.plan_lob_name IS NOT NULL
                AND l.lob_id IS NULL
                AND TRIM(LOWER(lc.lob_name)) = TRIM(LOWER(h.plan_lob_name))
                AND (lc.country IS NULL OR lc.country = '' OR lc.country = rb.country)
                AND (lc.city IS NULL OR lc.city = '' OR lc.city = rb.city)
                AND lc.status = 'active'
            )
        )
    """)
    
    # Actualizar v_real_without_plan_lob para mostrar información de homologación
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_without_plan_lob AS
        SELECT
            country,
            city,
            city_raw,
            lob_base,
            market_type,
            COUNT(*) AS trips_count,
            MIN(trip_date) AS first_seen_date,
            MAX(trip_date) AS last_seen_date,
            -- Información de homologación
            COUNT(DISTINCT CASE WHEN homologation_id IS NOT NULL THEN homologation_id END) AS has_homologation_count,
            COUNT(DISTINCT CASE WHEN homologation_id IS NULL THEN trip_id END) AS no_homologation_count
        FROM ops.v_real_lob_resolution
        WHERE resolution_status IN ('UNMATCHED', 'HOMOLOGATED_NO_MAPPING')
        GROUP BY country, city, city_raw, lob_base, market_type
        ORDER BY trips_count DESC
    """)


def downgrade() -> None:
    # Revertir a versión anterior sin homologación
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution")
    
    # Recrear vista anterior (sin homologación)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolution AS
        SELECT
            rb.trip_id,
            rb.country,
            rb.city,
            rb.city_raw,
            rb.trip_date,
            rb.lob_base,
            rb.market_type,
            rb.lob_effective,
            l.lob_id,
            lc.lob_name,
            l.mapping_id,
            CASE 
                WHEN l.lob_id IS NOT NULL THEN 'OK' 
                ELSE 'UNMATCHED' 
            END AS resolution_status,
            l.confidence,
            l.priority as mapping_priority
        FROM ops.v_real_lob_base rb
        LEFT JOIN LATERAL (
            SELECT m.*
            FROM ops.lob_plan_real_mapping m
            WHERE
                (m.country IS NULL OR m.country = rb.country)
                AND (m.city IS NULL OR m.city = rb.city)
                AND (m.service_type IS NULL OR LOWER(TRIM(m.service_type)) = LOWER(TRIM(rb.lob_base)))
                AND (m.market_type IS NULL OR m.market_type = rb.market_type)
                AND (m.valid_to IS NULL OR rb.trip_date::DATE <= m.valid_to)
                AND (m.valid_from IS NULL OR rb.trip_date::DATE >= m.valid_from)
            ORDER BY m.priority ASC, m.confidence DESC
            LIMIT 1
        ) l ON TRUE
        LEFT JOIN ops.lob_catalog lc ON lc.lob_id = l.lob_id
    """)
    
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_without_plan_lob AS
        SELECT
            country,
            city,
            city_raw,
            lob_base,
            market_type,
            COUNT(*) AS trips_count,
            MIN(trip_date) AS first_seen_date,
            MAX(trip_date) AS last_seen_date
        FROM ops.v_real_lob_resolution
        WHERE resolution_status = 'UNMATCHED'
        GROUP BY country, city, city_raw, lob_base, market_type
        ORDER BY trips_count DESC
    """)
