"""create_plan_city_map

Revision ID: 006_create_plan_city_map
Revises: 005_create_real_trips_monthly_aggregate
Create Date: 2026-01-16 12:00:00.000000

PASO B: Crear diccionario de mapeo de ciudades Plan -> Real
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006_create_plan_city_map'
down_revision: Union[str, None] = '005_create_real_trips_monthly_aggregate'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Crear tabla ops.plan_city_map
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.plan_city_map (
            country TEXT NOT NULL,
            plan_city_raw TEXT NOT NULL,
            plan_city_norm TEXT NOT NULL,
            real_city_norm TEXT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (country, plan_city_norm)
        )
    """)
    
    # 2. Agregar columna plan_city_resolved_norm a ops.plan_trips_monthly
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_trips_monthly' 
                AND column_name = 'plan_city_resolved_norm'
            ) THEN
                ALTER TABLE ops.plan_trips_monthly 
                ADD COLUMN plan_city_resolved_norm TEXT NULL;
                
                COMMENT ON COLUMN ops.plan_trips_monthly.plan_city_resolved_norm IS 
                'City normalizado resuelto desde plan_city_map.real_city_norm (si existe). Usado para matching con Real.';
            END IF;
        END $$;
    """)
    
    # 3. Crear índices
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_city_map_country_norm ON ops.plan_city_map(country, plan_city_norm)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_city_map_real_norm ON ops.plan_city_map(real_city_norm) WHERE real_city_norm IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_plan_trips_resolved_norm ON ops.plan_trips_monthly(plan_city_resolved_norm) WHERE plan_city_resolved_norm IS NOT NULL")
    
    # 4. Crear función para actualizar updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.update_plan_city_map_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 5. Crear trigger para updated_at
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_plan_city_map_updated_at ON ops.plan_city_map;
        CREATE TRIGGER trigger_plan_city_map_updated_at
        BEFORE UPDATE ON ops.plan_city_map
        FOR EACH ROW
        EXECUTE FUNCTION ops.update_plan_city_map_updated_at();
    """)
    
    # 6. Comentarios
    op.execute("""
        COMMENT ON TABLE ops.plan_city_map IS 
        'Diccionario de mapeo de ciudades: Plan (city_norm) -> Real (city_norm). Permite resolver diferencias de nombres entre Plan y Real.';
        
        COMMENT ON COLUMN ops.plan_city_map.plan_city_raw IS 
        'Nombre original de la ciudad en el Plan (sin normalizar)';
        
        COMMENT ON COLUMN ops.plan_city_map.plan_city_norm IS 
        'Nombre normalizado de la ciudad en el Plan: lower(trim(city))';
        
        COMMENT ON COLUMN ops.plan_city_map.real_city_norm IS 
        'Nombre normalizado correspondiente en Real (dim_park). NULL significa que aún no se ha mapeado.';
    """)


def downgrade() -> None:
    # Eliminar trigger y función
    op.execute("DROP TRIGGER IF EXISTS trigger_plan_city_map_updated_at ON ops.plan_city_map")
    op.execute("DROP FUNCTION IF EXISTS ops.update_plan_city_map_updated_at()")
    
    # Eliminar columna de plan_trips_monthly
    op.execute("ALTER TABLE ops.plan_trips_monthly DROP COLUMN IF EXISTS plan_city_resolved_norm")
    
    # Eliminar tabla
    op.execute("DROP TABLE IF EXISTS ops.plan_city_map CASCADE")
