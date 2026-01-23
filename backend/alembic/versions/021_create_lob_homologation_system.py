"""create_lob_homologation_system

Revision ID: 021_lob_homologation
Revises: 020_enhance_phase2c_lob
Create Date: 2026-01-23 02:00:00.000000

FASE 2C+ Homologación LOB: REAL tipo_servicio ↔ PLAN CSV
Sistema de diccionario auditable para homologar LOB entre REAL y PLAN.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '021_lob_homologation'
down_revision = '020_enhance_phase2c_lob'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A) REAL UNIVERSE (tipo_servicio)
    op.execute("DROP VIEW IF EXISTS ops.v_real_tipo_servicio_universe CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_tipo_servicio_universe AS
        SELECT
            COALESCE(d.country, '') as country,
            COALESCE(d.city, '') as city,
            COALESCE(t.tipo_servicio, '') AS real_tipo_servicio,
            COUNT(*) AS trips_count,
            MIN(t.fecha_inicio_viaje::DATE) AS first_seen_date,
            MAX(t.fecha_inicio_viaje::DATE) AS last_seen_date
        FROM public.trips_all t
        LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
        WHERE t.tipo_servicio IS NOT NULL
        AND t.condicion = 'Completado'
        GROUP BY COALESCE(d.country, ''), COALESCE(d.city, ''), COALESCE(t.tipo_servicio, '')
    """)
    
    # B) PLAN STAGING (CSV)
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")
    
    op.execute("""
        CREATE TABLE IF NOT EXISTS staging.plan_projection_raw (
            plan_raw_id SERIAL PRIMARY KEY,
            country TEXT,
            city TEXT,
            lob_name TEXT,
            period_date DATE,
            trips_plan NUMERIC,
            revenue_plan NUMERIC,
            raw_row JSONB,
            loaded_at TIMESTAMP DEFAULT now()
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_projection_raw_country_city
        ON staging.plan_projection_raw(country, city)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_projection_raw_lob_name
        ON staging.plan_projection_raw(lob_name)
        WHERE lob_name IS NOT NULL
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_plan_projection_raw_period
        ON staging.plan_projection_raw(period_date)
    """)
    
    # Vista de universo del plan
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_universe_raw CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_lob_universe_raw AS
        SELECT
            country,
            city,
            TRIM(LOWER(lob_name)) AS plan_lob_name,
            SUM(trips_plan) AS trips_plan,
            SUM(revenue_plan) AS revenue_plan,
            MIN(period_date) AS first_period,
            MAX(period_date) AS last_period,
            COUNT(*) AS raw_rows_count
        FROM staging.plan_projection_raw
        WHERE lob_name IS NOT NULL
        AND TRIM(lob_name) != ''
        GROUP BY country, city, TRIM(LOWER(lob_name))
    """)
    
    # C) HOMOLOGATION TABLE (PUENTE)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.lob_homologation (
            homologation_id SERIAL PRIMARY KEY,
            country TEXT,
            city TEXT,
            real_tipo_servicio TEXT NOT NULL,
            plan_lob_name TEXT NOT NULL,
            confidence TEXT CHECK (confidence IN ('high','medium','low')) DEFAULT 'medium',
            notes TEXT,
            created_at TIMESTAMP DEFAULT now(),
            created_by TEXT,
            UNIQUE(country, city, real_tipo_servicio, plan_lob_name)
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_homologation_country_city
        ON ops.lob_homologation(country, city)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_homologation_real
        ON ops.lob_homologation(real_tipo_servicio)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_homologation_plan
        ON ops.lob_homologation(plan_lob_name)
    """)
    
    # D) SUGERENCIA AUTOMÁTICA (SIN AUTODECISIÓN)
    op.execute("DROP VIEW IF EXISTS ops.v_lob_homologation_suggestions CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_lob_homologation_suggestions AS
        WITH real AS (
            SELECT DISTINCT 
                country, 
                city, 
                TRIM(LOWER(real_tipo_servicio)) AS r,
                real_tipo_servicio AS r_original,
                trips_count
            FROM ops.v_real_tipo_servicio_universe
        ),
        plan AS (
            SELECT DISTINCT 
                country, 
                city, 
                TRIM(LOWER(plan_lob_name)) AS p,
                plan_lob_name AS p_original,
                trips_plan
            FROM ops.v_plan_lob_universe_raw
        ),
        existing AS (
            SELECT DISTINCT
                COALESCE(country, '') as country,
                COALESCE(city, '') as city,
                TRIM(LOWER(real_tipo_servicio)) as real_norm,
                TRIM(LOWER(plan_lob_name)) as plan_norm
            FROM ops.lob_homologation
        )
        SELECT
            r.country,
            r.city,
            r.r_original AS real_tipo_servicio,
            p.p_original AS plan_lob_name,
            r.trips_count AS real_trips_count,
            p.trips_plan AS plan_trips,
            CASE
                WHEN r.r = p.p THEN 'high'
                WHEN p.p LIKE '%' || r.r || '%' OR r.r LIKE '%' || p.p || '%' THEN 'low'
                ELSE 'low'
            END AS suggested_confidence,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM existing e
                    WHERE (e.country = r.country OR e.country = '' OR r.country = '')
                    AND (e.city = r.city OR e.city = '' OR r.city = '')
                    AND e.real_norm = r.r
                    AND e.plan_norm = p.p
                ) THEN true
                ELSE false
            END AS already_homologated
        FROM real r
        JOIN plan p
            ON (
                (p.country = r.country) 
                OR (p.country IS NULL AND r.country = '')
                OR (r.country IS NULL AND p.country = '')
                OR (p.country = '' AND r.country = '')
            )
            AND (
                (p.city = r.city)
                OR (p.city IS NULL AND r.city = '')
                OR (r.city IS NULL AND p.city = '')
                OR (p.city = '' AND r.city = '')
            )
        WHERE NOT EXISTS (
            SELECT 1 FROM existing e
            WHERE (e.country = r.country OR e.country = '' OR r.country = '')
            AND (e.city = r.city OR e.city = '' OR r.city = '')
            AND e.real_norm = r.r
            AND e.plan_norm = p.p
        )
        ORDER BY 
            CASE
                WHEN r.r = p.p THEN 1
                WHEN p.p LIKE '%' || r.r || '%' OR r.r LIKE '%' || p.p || '%' THEN 2
                ELSE 3
            END,
            r.trips_count DESC
    """)
    
    # E) REPORTES (vistas para que Gonzalo decida)
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_without_homologation CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_without_homologation AS
        SELECT 
            u.country,
            u.city,
            u.real_tipo_servicio,
            u.trips_count,
            u.first_seen_date,
            u.last_seen_date
        FROM ops.v_real_tipo_servicio_universe u
        LEFT JOIN ops.lob_homologation h
            ON (h.country IS NULL OR h.country = '' OR h.country = u.country)
            AND (h.city IS NULL OR h.city = '' OR h.city = u.city)
            AND TRIM(LOWER(h.real_tipo_servicio)) = TRIM(LOWER(u.real_tipo_servicio))
        WHERE h.homologation_id IS NULL
        ORDER BY u.trips_count DESC
    """)
    
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_without_homologation CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_lob_without_homologation AS
        SELECT 
            p.country,
            p.city,
            p.plan_lob_name,
            p.trips_plan,
            p.revenue_plan,
            p.first_period,
            p.last_period
        FROM ops.v_plan_lob_universe_raw p
        LEFT JOIN ops.lob_homologation h
            ON (h.country IS NULL OR h.country = '' OR h.country = p.country)
            AND (h.city IS NULL OR h.city = '' OR h.city = p.city)
            AND TRIM(LOWER(h.plan_lob_name)) = TRIM(LOWER(p.plan_lob_name))
        WHERE h.homologation_id IS NULL
        ORDER BY p.trips_plan DESC
    """)


def downgrade() -> None:
    # Eliminar vistas
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_without_homologation")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_without_homologation")
    op.execute("DROP VIEW IF EXISTS ops.v_lob_homologation_suggestions")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_lob_universe_raw")
    op.execute("DROP VIEW IF EXISTS ops.v_real_tipo_servicio_universe")
    
    # Eliminar tablas
    op.execute("DROP TABLE IF EXISTS ops.lob_homologation")
    op.execute("DROP TABLE IF EXISTS staging.plan_projection_raw")
