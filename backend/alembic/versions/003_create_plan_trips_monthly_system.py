"""create_plan_trips_monthly_system

Revision ID: 003_create_plan_trips_monthly_system
Revises: 002_create_territory_mapping_system
Create Date: 2025-01-27 12:00:00.000000

PASO B: Sistema canónico de PLAN desde CSV Ruta 27
- Tabla canónica versionada (append-only)
- Vistas para consultas
- Sin lógica de negocio mezclada con Real
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_create_plan_trips_monthly_system'
down_revision: Union[str, None] = '002_create_territory_mapping_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Asegurar que existe el esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    
    # 1. CREAR TABLA CANÓNICA DE PLAN
    op.execute("DROP TABLE IF EXISTS ops.plan_trips_monthly CASCADE")
    op.execute("""
        CREATE TABLE ops.plan_trips_monthly (
            id BIGSERIAL PRIMARY KEY,
            plan_version TEXT NOT NULL,
            country TEXT,
            city TEXT,
            park_id TEXT,
            lob_base TEXT,
            segment TEXT CHECK (segment IN ('b2b', 'b2c')),
            month DATE NOT NULL,
            projected_trips INTEGER,
            projected_drivers INTEGER,
            projected_ticket NUMERIC,
            projected_trips_per_driver NUMERIC GENERATED ALWAYS AS (
                CASE 
                    WHEN projected_drivers > 0 THEN projected_trips::NUMERIC / projected_drivers
                    ELSE NULL
                END
            ) STORED,
            projected_revenue NUMERIC GENERATED ALWAYS AS (
                CASE
                    WHEN projected_trips IS NOT NULL AND projected_ticket IS NOT NULL 
                    THEN projected_trips::NUMERIC * projected_ticket
                    ELSE NULL
                END
            ) STORED,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Índices para búsquedas comunes
            CONSTRAINT plan_trips_monthly_unique 
                UNIQUE (plan_version, country, city, park_id, lob_base, segment, month)
        )
    """)
    
    # Índices para performance
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_version ON ops.plan_trips_monthly(plan_version)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_month ON ops.plan_trips_monthly(month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_park ON ops.plan_trips_monthly(park_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_country_city_lob ON ops.plan_trips_monthly(country, city, lob_base)")
    
    # Comentarios para documentación
    op.execute("""
        COMMENT ON TABLE ops.plan_trips_monthly IS 
        'Tabla canónica de PLAN versionado (append-only). Fuente: CSV Ruta 27. Campos calculados: projected_trips_per_driver, projected_revenue';
        
        COMMENT ON COLUMN ops.plan_trips_monthly.plan_version IS 
        'Versión del plan (ej: ruta27_v1, ruta27_v2). Append-only, nunca se actualiza ni borra.';
        
        COMMENT ON COLUMN ops.plan_trips_monthly.segment IS 
        'Segmento: b2b o b2c';
        
        COMMENT ON COLUMN ops.plan_trips_monthly.projected_trips_per_driver IS 
        'Campo calculado: projected_trips / projected_drivers';
        
        COMMENT ON COLUMN ops.plan_trips_monthly.projected_revenue IS 
        'Campo calculado: projected_trips * projected_ticket';
    """)
    
    # 2. CREAR VISTA: ops.v_plan_trips_monthly
    op.execute("DROP VIEW IF EXISTS ops.v_plan_trips_monthly CASCADE")
    op.execute("""
        CREATE VIEW ops.v_plan_trips_monthly AS
        SELECT 
            plan_version,
            country,
            city,
            park_id,
            lob_base,
            segment,
            month,
            projected_trips,
            projected_drivers,
            projected_ticket,
            projected_trips_per_driver,
            projected_revenue,
            created_at
        FROM ops.plan_trips_monthly
        ORDER BY plan_version DESC, month, country, city, lob_base, segment
    """)
    
    op.execute("""
        COMMENT ON VIEW ops.v_plan_trips_monthly IS 
        'Vista simplificada de plan mensual. Última versión por defecto (order by plan_version DESC)';
    """)
    
    # 3. CREAR VISTA: ops.v_plan_trips_daily_equivalent
    op.execute("DROP VIEW IF EXISTS ops.v_plan_trips_daily_equivalent CASCADE")
    op.execute("""
        CREATE VIEW ops.v_plan_trips_daily_equivalent AS
        SELECT 
            plan_version,
            country,
            city,
            park_id,
            lob_base,
            segment,
            month,
            projected_trips,
            projected_drivers,
            projected_ticket,
            projected_trips_per_driver,
            projected_revenue,
            -- Dividir por días del mes
            CASE 
                WHEN projected_trips IS NOT NULL 
                THEN projected_trips::NUMERIC / EXTRACT(DAY FROM (DATE_TRUNC('month', month) + INTERVAL '1 month - 1 day')::DATE)
                ELSE NULL
            END AS projected_trips_daily,
            CASE 
                WHEN projected_revenue IS NOT NULL 
                THEN projected_revenue::NUMERIC / EXTRACT(DAY FROM (DATE_TRUNC('month', month) + INTERVAL '1 month - 1 day')::DATE)
                ELSE NULL
            END AS projected_revenue_daily,
            EXTRACT(DAY FROM (DATE_TRUNC('month', month) + INTERVAL '1 month - 1 day')::DATE) AS days_in_month,
            created_at
        FROM ops.plan_trips_monthly
        ORDER BY plan_version DESC, month, country, city, lob_base, segment
    """)
    
    op.execute("""
        COMMENT ON VIEW ops.v_plan_trips_daily_equivalent IS 
        'Plan mensual convertido a equivalentes diarios (dividido por días del mes)';
    """)
    
    # 4. CREAR VISTA: ops.v_plan_kpis_monthly
    op.execute("DROP VIEW IF EXISTS ops.v_plan_kpis_monthly CASCADE")
    op.execute("""
        CREATE VIEW ops.v_plan_kpis_monthly AS
        SELECT 
            plan_version,
            country,
            city,
            park_id,
            lob_base,
            segment,
            month,
            -- KPIs principales
            projected_trips AS kpi_trips,
            projected_drivers AS kpi_drivers,
            projected_revenue AS kpi_revenue,
            projected_trips_per_driver AS kpi_productivity_required,
            -- KPIs derivados
            projected_ticket AS kpi_ticket_avg,
            CASE 
                WHEN projected_drivers > 0 
                THEN projected_trips::NUMERIC / projected_drivers
                ELSE NULL
            END AS kpi_trips_per_driver,
            created_at
        FROM ops.plan_trips_monthly
        ORDER BY plan_version DESC, month, country, city, lob_base, segment
    """)
    
    op.execute("""
        COMMENT ON VIEW ops.v_plan_kpis_monthly IS 
        'KPIs mensuales del plan: trips, drivers, revenue, productivity requerida';
    """)
    
    # 5. CREAR TABLA DE AUDITORÍA PARA VALIDACIONES
    op.execute("DROP TABLE IF EXISTS ops.plan_validation_results CASCADE")
    op.execute("""
        CREATE TABLE ops.plan_validation_results (
            id BIGSERIAL PRIMARY KEY,
            plan_version TEXT NOT NULL,
            validation_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            validation_type TEXT NOT NULL CHECK (validation_type IN ('orphan_plan', 'orphan_real', 'missing_combo')),
            country TEXT,
            city TEXT,
            park_id TEXT,
            lob_base TEXT,
            segment TEXT,
            month DATE,
            severity TEXT CHECK (severity IN ('error', 'warning', 'info')),
            message TEXT,
            row_count BIGINT
        )
    """)
    
    op.execute("""
        COMMENT ON TABLE ops.plan_validation_results IS 
        'Resultados de validaciones post-ingesta de plan. Solo registro, no modifica datos.';
    """)
    
    # Índices para validaciones
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_validation_version ON ops.plan_validation_results(plan_version, validation_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_validation_type ON ops.plan_validation_results(validation_type, severity)")


def downgrade() -> None:
    # Eliminar vistas
    op.execute("DROP VIEW IF EXISTS ops.v_plan_kpis_monthly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_trips_daily_equivalent CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_trips_monthly CASCADE")
    
    # Eliminar tablas
    op.execute("DROP TABLE IF EXISTS ops.plan_validation_results CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.plan_trips_monthly CASCADE")
