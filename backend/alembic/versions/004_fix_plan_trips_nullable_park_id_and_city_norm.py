"""fix_plan_trips_nullable_park_id_and_city_norm

Revision ID: 004_fix_plan_trips_nullable_park_id_and_city_norm
Revises: 003_create_plan_trips_monthly_system
Create Date: 2026-01-16 00:00:00.000000

PASO B: Ajustes para soportar park_id vacío y agregar city_norm
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_fix_plan_trips_nullable_park_id_and_city_norm'
down_revision: Union[str, None] = '003_create_plan_trips_monthly_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar columna city_norm si no existe
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_trips_monthly' 
                AND column_name = 'city_norm'
            ) THEN
                ALTER TABLE ops.plan_trips_monthly 
                ADD COLUMN city_norm TEXT;
                
                -- Llenar city_norm con valores existentes (intentando usar unaccent si está disponible)
                UPDATE ops.plan_trips_monthly
                SET city_norm = LOWER(TRIM(COALESCE(city, '')));
                
                COMMENT ON COLUMN ops.plan_trips_monthly.city_norm IS 
                'Versión normalizada de city para matching: lower(trim(unaccent(city))) o lower(trim(city))';
            END IF;
        END $$;
    """)
    
    # 2. Ajustar UNIQUE constraint para manejar park_id NULL
    # Primero eliminar el constraint existente
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'plan_trips_monthly_unique'
            ) THEN
                ALTER TABLE ops.plan_trips_monthly 
                DROP CONSTRAINT plan_trips_monthly_unique;
            END IF;
        END $$;
    """)
    
    # Crear nuevo constraint que maneja park_id NULL usando COALESCE
    op.execute("""
        CREATE UNIQUE INDEX plan_trips_monthly_unique_idx ON ops.plan_trips_monthly (
            plan_version,
            COALESCE(country, ''),
            COALESCE(city, ''),
            COALESCE(park_id, '__NA__'),
            COALESCE(lob_base, ''),
            COALESCE(segment, ''),
            month
        );
    """)
    
    # Agregar comentario
    op.execute("""
        COMMENT ON INDEX ops.plan_trips_monthly_unique_idx IS 
        'UNIQUE constraint que maneja park_id NULL usando COALESCE(park_id, ''__NA__'')';
    """)


def downgrade() -> None:
    # Eliminar índice UNIQUE
    op.execute("DROP INDEX IF EXISTS ops.plan_trips_monthly_unique_idx")
    
    # Recrear constraint original
    op.execute("""
        ALTER TABLE ops.plan_trips_monthly 
        ADD CONSTRAINT plan_trips_monthly_unique 
        UNIQUE (plan_version, country, city, park_id, lob_base, segment, month)
    """)
    
    # Eliminar columna city_norm
    op.execute("ALTER TABLE ops.plan_trips_monthly DROP COLUMN IF EXISTS city_norm")
