"""create_phase2c_lob_universe_mapping

Revision ID: 019_phase2c_lob_universe
Revises: 018_phase2c_accountability
Create Date: 2026-01-23 00:00:00.000000

FASE 2C+: Universo & LOB Mapping (PLAN → REAL)
Sistema explícito y trazable para mapear viajes reales a LOB del plan.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '019_phase2c_lob_universe'
down_revision = '018_phase2c_accountability'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    
    # 1.1 Crear catálogo canónico de LOB del PLAN
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.lob_catalog (
            lob_id SERIAL PRIMARY KEY,
            lob_name TEXT NOT NULL,
            country TEXT NOT NULL,
            city TEXT,
            description TEXT,
            status TEXT CHECK (status IN ('active','deprecated','experimental')) DEFAULT 'active',
            source TEXT DEFAULT 'plan',
            created_at TIMESTAMP DEFAULT now(),
            UNIQUE(lob_name, country, city)
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_catalog_country_city
        ON ops.lob_catalog(country, city)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_catalog_status
        ON ops.lob_catalog(status)
        WHERE status = 'active'
    """)
    
    # 1.2 Crear tabla de reglas de mapping PLAN → REAL
    # Nota: Las columnas service_type, product_type, vehicle_type, fleet_flag, tariff_class
    # son opcionales (NULL = cualquier valor). Usaremos las columnas reales de trips_all
    # como tipo_servicio, park_id (para obtener country/city desde dim_park)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.lob_plan_real_mapping (
            mapping_id SERIAL PRIMARY KEY,
            lob_id INT REFERENCES ops.lob_catalog(lob_id) ON DELETE CASCADE,
            country TEXT,
            city TEXT,
            tipo_servicio TEXT,
            -- Campos opcionales para futuras extensiones
            product_type TEXT,
            vehicle_type TEXT,
            fleet_flag BOOLEAN,
            tariff_class TEXT,
            priority INT NOT NULL DEFAULT 100,
            confidence TEXT CHECK (confidence IN ('high','medium','low')) DEFAULT 'high',
            valid_from DATE DEFAULT CURRENT_DATE,
            valid_to DATE,
            created_at TIMESTAMP DEFAULT now(),
            notes TEXT
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_mapping_lob_id
        ON ops.lob_plan_real_mapping(lob_id)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_mapping_country_city
        ON ops.lob_plan_real_mapping(country, city)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_mapping_tipo_servicio
        ON ops.lob_plan_real_mapping(tipo_servicio)
        WHERE tipo_servicio IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_mapping_priority
        ON ops.lob_plan_real_mapping(priority)
    """)
    
    # 2. Vista de resolución de viajes reales contra el PLAN
    # Usa LATERAL JOIN para aplicar reglas de mapping con prioridad
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_lob_resolution AS
        SELECT
            t.id as trip_id,
            t.park_id,
            t.fecha_inicio_viaje as trip_date,
            COALESCE(d.country, '') as country,
            COALESCE(d.city, '') as city,
            t.tipo_servicio,
            l.lob_id,
            lc.lob_name,
            l.mapping_id,
            CASE
                WHEN l.lob_id IS NOT NULL THEN 'OK'
                ELSE 'UNMATCHED'
            END AS resolution_status,
            l.confidence,
            l.priority as mapping_priority
        FROM public.trips_all t
        LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
        LEFT JOIN LATERAL (
            SELECT m.*
            FROM ops.lob_plan_real_mapping m
            WHERE
                (m.country IS NULL OR m.country = COALESCE(d.country, ''))
                AND (m.city IS NULL OR m.city = COALESCE(d.city, ''))
                AND (m.tipo_servicio IS NULL OR LOWER(TRIM(m.tipo_servicio)) = LOWER(TRIM(COALESCE(t.tipo_servicio, ''))))
                AND (m.valid_to IS NULL OR t.fecha_inicio_viaje::DATE <= m.valid_to)
                AND (m.valid_from IS NULL OR t.fecha_inicio_viaje::DATE >= m.valid_from)
            ORDER BY m.priority ASC, m.confidence DESC
            LIMIT 1
        ) l ON TRUE
        LEFT JOIN ops.lob_catalog lc ON lc.lob_id = l.lob_id
        WHERE t.condicion = 'Completado'
    """)
    
    # 3. Vista de universo LOB - PLAN vs REAL
    op.execute("DROP VIEW IF EXISTS ops.v_lob_universe_check CASCADE")
    op.execute("""
        CREATE VIEW ops.v_lob_universe_check AS
        SELECT
            lc.country,
            lc.city,
            lc.lob_name,
            lc.lob_id,
            COUNT(DISTINCT r.trip_id) AS real_trips,
            CASE WHEN COUNT(r.trip_id) > 0 THEN true ELSE false END AS exists_in_real,
            true AS exists_in_plan,
            CASE
                WHEN COUNT(r.trip_id) = 0 THEN 'PLAN_ONLY'
                ELSE 'OK'
            END AS coverage_status
        FROM ops.lob_catalog lc
        LEFT JOIN ops.v_real_lob_resolution r
            ON r.lob_id = lc.lob_id
            AND lc.status = 'active'
        GROUP BY lc.country, lc.city, lc.lob_name, lc.lob_id
        ORDER BY lc.country, lc.city, lc.lob_name
    """)
    
    # 4. Vista de viajes reales sin LOB del plan
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_without_plan_lob AS
        SELECT
            country,
            city,
            tipo_servicio,
            COUNT(*) AS trips_count,
            MIN(trip_date) as first_trip_date,
            MAX(trip_date) as last_trip_date
        FROM ops.v_real_lob_resolution
        WHERE resolution_status = 'UNMATCHED'
        GROUP BY country, city, tipo_servicio
        ORDER BY trips_count DESC
    """)
    
    # 5. Vista de controles de calidad
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_checks CASCADE")
    op.execute("""
        CREATE VIEW ops.v_lob_mapping_quality_checks AS
        WITH total_trips AS (
            SELECT COUNT(*) as total
            FROM ops.v_real_lob_resolution
        ),
        unmatched_trips AS (
            SELECT COUNT(*) as unmatched
            FROM ops.v_real_lob_resolution
            WHERE resolution_status = 'UNMATCHED'
        ),
        unmatched_by_country_city AS (
            SELECT
                country,
                city,
                COUNT(*) as unmatched_count
            FROM ops.v_real_lob_resolution
            WHERE resolution_status = 'UNMATCHED'
            GROUP BY country, city
        ),
        plan_lob_without_real AS (
            SELECT
                country,
                city,
                lob_name,
                COUNT(*) as lob_count
            FROM ops.v_lob_universe_check
            WHERE coverage_status = 'PLAN_ONLY'
            GROUP BY country, city, lob_name
        ),
        unused_mappings AS (
            SELECT
                m.mapping_id,
                m.lob_id,
                lc.lob_name,
                m.country,
                m.city,
                m.tipo_servicio,
                COUNT(r.trip_id) as matched_trips
            FROM ops.lob_plan_real_mapping m
            LEFT JOIN ops.lob_catalog lc ON m.lob_id = lc.lob_id
            LEFT JOIN ops.v_real_lob_resolution r ON r.mapping_id = m.mapping_id
            GROUP BY m.mapping_id, m.lob_id, lc.lob_name, m.country, m.city, m.tipo_servicio
            HAVING COUNT(r.trip_id) = 0
        )
        SELECT
            'pct_unmatched' as metric,
            ROUND(100.0 * (SELECT unmatched FROM unmatched_trips) / NULLIF((SELECT total FROM total_trips), 0), 2) as value
        UNION ALL
        SELECT
            'total_unmatched',
            (SELECT unmatched FROM unmatched_trips)::NUMERIC
        UNION ALL
        SELECT
            'total_trips',
            (SELECT total FROM total_trips)::NUMERIC
        UNION ALL
        SELECT
            'plan_lob_total',
            (SELECT COUNT(*) FROM ops.lob_catalog WHERE status = 'active')::NUMERIC
        UNION ALL
        SELECT
            'plan_lob_with_real',
            (SELECT COUNT(*) FROM ops.v_lob_universe_check WHERE exists_in_real = true)::NUMERIC
        UNION ALL
        SELECT
            'plan_lob_without_real',
            (SELECT COUNT(*) FROM ops.v_lob_universe_check WHERE coverage_status = 'PLAN_ONLY')::NUMERIC
        UNION ALL
        SELECT
            'unused_mappings',
            (SELECT COUNT(*) FROM unused_mappings)::NUMERIC
    """)
    
    # 6. Vista detallada de unmatched por país/ciudad
    op.execute("DROP VIEW IF EXISTS ops.v_lob_unmatched_by_location CASCADE")
    op.execute("""
        CREATE VIEW ops.v_lob_unmatched_by_location AS
        SELECT
            country,
            city,
            COUNT(*) as unmatched_trips,
            COUNT(DISTINCT tipo_servicio) as distinct_tipo_servicio,
            ROUND(100.0 * COUNT(*) / NULLIF((
                SELECT COUNT(*) 
                FROM ops.v_real_lob_resolution 
                WHERE country = r.country AND city = r.city
            ), 0), 2) as pct_of_location_trips
        FROM ops.v_real_lob_resolution r
        WHERE resolution_status = 'UNMATCHED'
        GROUP BY country, city
        ORDER BY unmatched_trips DESC
    """)


def downgrade() -> None:
    # Eliminar vistas primero (dependencias)
    op.execute("DROP VIEW IF EXISTS ops.v_lob_unmatched_by_location")
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_checks")
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob")
    op.execute("DROP VIEW IF EXISTS ops.v_lob_universe_check")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution")
    
    # Eliminar tablas (en orden de dependencias)
    op.execute("DROP TABLE IF EXISTS ops.lob_plan_real_mapping")
    op.execute("DROP TABLE IF EXISTS ops.lob_catalog")
