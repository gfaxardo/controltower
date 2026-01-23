"""enhance_phase2c_lob_with_mother_rule

Revision ID: 020_enhance_phase2c_lob
Revises: 019_phase2c_lob_universe
Create Date: 2026-01-23 01:00:00.000000

FASE 2C+ v2: Regla madre LOB = tipo_servicio, B2B override, City normalization
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '020_enhance_phase2c_lob'
down_revision = '019_phase2c_lob_universe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    
    # B) City Normalization
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.city_normalization (
            city_norm_id SERIAL PRIMARY KEY,
            country TEXT,
            city_raw TEXT NOT NULL,
            city_normalized TEXT NOT NULL,
            confidence TEXT CHECK (confidence IN ('high','medium','low')) DEFAULT 'high',
            notes TEXT,
            created_at TIMESTAMP DEFAULT now(),
            UNIQUE(country, city_raw)
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_city_normalization_country_raw
        ON ops.city_normalization(country, city_raw)
    """)
    
    op.execute("DROP VIEW IF EXISTS ops.v_city_resolved CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_city_resolved AS
        SELECT
            t.id as trip_id,
            COALESCE(d.country, '') as country,
            COALESCE(d.city, '') AS city_raw,
            COALESCE(cn.city_normalized, COALESCE(d.city, '')) AS city_resolved,
            CASE WHEN cn.city_normalized IS NULL THEN 'RAW' ELSE 'NORMALIZED' END AS city_resolution_status
        FROM public.trips_all t
        LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
        LEFT JOIN ops.city_normalization cn
            ON (cn.country IS NULL OR cn.country = COALESCE(d.country, ''))
            AND cn.city_raw = COALESCE(d.city, '')
        WHERE t.condicion = 'Completado'
    """)
    
    # C) LOB Base + B2B (Regla Madre)
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_base CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_base AS
        SELECT
            t.id as trip_id,
            t.fecha_inicio_viaje as trip_date,
            vc.country,
            vc.city_resolved AS city,
            vc.city_raw,
            COALESCE(t.tipo_servicio, '') AS lob_base,
            CASE 
                WHEN COALESCE(t.pago_corporativo, 0)::numeric > 0 THEN 'B2B' 
                ELSE 'B2C' 
            END AS market_type,
            CASE 
                WHEN COALESCE(t.pago_corporativo, 0)::numeric > 0 
                THEN 'B2B_' || COALESCE(t.tipo_servicio, '') 
                ELSE COALESCE(t.tipo_servicio, '') 
            END AS lob_effective,
            t.pago_corporativo as pago_corporativo_raw
        FROM public.trips_all t
        JOIN ops.v_city_resolved vc ON vc.trip_id = t.id
        WHERE t.condicion = 'Completado'
    """)
    
    # Actualizar lob_plan_real_mapping para incluir market_type
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'lob_plan_real_mapping' 
                AND column_name = 'market_type'
            ) THEN
                ALTER TABLE ops.lob_plan_real_mapping 
                ADD COLUMN market_type TEXT CHECK (market_type IN ('B2B', 'B2C'));
            END IF;
        END $$;
    """)
    
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'lob_plan_real_mapping' 
                AND column_name = 'tipo_servicio'
            ) THEN
                -- Renombrar tipo_servicio a service_type para consistencia
                ALTER TABLE ops.lob_plan_real_mapping 
                RENAME COLUMN tipo_servicio TO service_type;
            END IF;
        END $$;
    """)
    
    # G) Actualizar v_real_lob_resolution para usar v_real_lob_base
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
    
    # H) Actualizar v_real_without_plan_lob para incluir market_type
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
            MAX(trip_date) AS last_seen_date
        FROM ops.v_real_lob_resolution
        WHERE resolution_status = 'UNMATCHED'
        GROUP BY country, city, city_raw, lob_base, market_type
        ORDER BY trips_count DESC
    """)
    
    # Actualizar índices
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_mapping_market_type
        ON ops.lob_plan_real_mapping(market_type)
        WHERE market_type IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_mapping_service_type
        ON ops.lob_plan_real_mapping(service_type)
        WHERE service_type IS NOT NULL
    """)
    
    # E) Vista plan_lob_source_candidates (auto-discovery)
    # Esta vista busca automáticamente dónde están las LOB del plan
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_source_candidates CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_lob_source_candidates AS
        -- Buscar en plan.plan_long_valid (si existe y tiene datos)
        SELECT DISTINCT
            COALESCE(line_of_business, '') as lob_name,
            COALESCE(country, '') as country,
            COALESCE(city, '') as city,
            'plan.plan_long_valid' as source_table
        FROM plan.plan_long_valid
        WHERE COALESCE(line_of_business, '') != ''
        AND EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'plan' 
            AND table_name = 'plan_long_valid'
        )
        -- Si no hay datos, esta vista retornará 0 filas (correcto)
    """)


def downgrade() -> None:
    # Eliminar vistas
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_base")
    op.execute("DROP VIEW IF EXISTS ops.v_city_resolved")
    
    # Eliminar columnas agregadas
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'lob_plan_real_mapping' 
                AND column_name = 'market_type'
            ) THEN
                ALTER TABLE ops.lob_plan_real_mapping DROP COLUMN market_type;
            END IF;
        END $$;
    """)
    
    # Eliminar tabla
    op.execute("DROP TABLE IF EXISTS ops.city_normalization")
