"""fix_revenue_plan_input

Revision ID: 009_fix_revenue_plan_input
Revises: 008_consolidate_real_monthly_phase2a
Create Date: 2025-01-27 18:00:00.000000

CORRECCIÓN CRÍTICA: Revenue Plan debe ser INPUT, no calculado.
- Cambia projected_revenue de GENERATED a campo normal
- Permite que revenue_plan del Excel se guarde directamente
- Elimina cálculo trips * ticket que generaba GMV en lugar de Revenue
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009_fix_revenue_plan_input'
down_revision: Union[str, None] = '008_consolidate_real_phase2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    CORRECCIÓN CRÍTICA: Revenue Plan es INPUT del Excel, NO se calcula.
    
    Cambia projected_revenue de GENERATED ALWAYS AS (trips * ticket) a campo normal.
    Esto permite que revenue_plan del Excel se guarde directamente en projected_revenue.
    """
    
    # Paso 1: Backup de datos actuales (si existen)
    op.execute("""
        DO $$
        BEGIN
            -- Crear tabla temporal con datos actuales si existe revenue calculado
            CREATE TEMP TABLE IF NOT EXISTS tmp_plan_revenue_backup AS
            SELECT id, projected_revenue
            FROM ops.plan_trips_monthly
            WHERE projected_revenue IS NOT NULL;
        EXCEPTION
            WHEN OTHERS THEN
                -- Si la tabla no existe o hay error, continuar
                NULL;
        END $$;
    """)
    
    # Paso 2: Eliminar la columna GENERATED y recrearla como campo normal
    op.execute("ALTER TABLE ops.plan_trips_monthly DROP COLUMN IF EXISTS projected_revenue CASCADE")
    
    # Paso 3: Agregar projected_revenue como campo normal (NULL permitido)
    op.execute("""
        ALTER TABLE ops.plan_trips_monthly
        ADD COLUMN projected_revenue NUMERIC
    """)
    
    # Paso 4: Actualizar comentarios
    op.execute("""
        COMMENT ON COLUMN ops.plan_trips_monthly.projected_revenue IS 
        'Revenue Plan neto esperado (INPUT del Excel). NO es GMV (trips * ticket). Este valor proviene directamente del archivo cargado y nunca debe recalcularse.';
    """)
    
    # Paso 5: Actualizar vistas que dependían de projected_revenue si es necesario
    # (Las vistas ya deberían funcionar con el campo normal)
    
    # Verificar y recrear vistas que usan projected_revenue
    op.execute("""
        DO $$
        BEGIN
            -- v_plan_trips_monthly_latest debería seguir funcionando
            -- Solo verificar que exista
            IF NOT EXISTS (
                SELECT 1 FROM pg_views 
                WHERE schemaname = 'ops' 
                AND viewname = 'v_plan_trips_monthly_latest'
            ) THEN
                -- Recrear vista básica si no existe
                CREATE VIEW ops.v_plan_trips_monthly_latest AS
                WITH latest_version AS (
                    SELECT plan_version
                    FROM ops.plan_trips_monthly
                    GROUP BY plan_version
                    ORDER BY MAX(created_at) DESC
                    LIMIT 1
                )
                SELECT 
                    p.*
                FROM ops.plan_trips_monthly p
                INNER JOIN latest_version lv ON p.plan_version = lv.plan_version;
            END IF;
        EXCEPTION
            WHEN OTHERS THEN
                -- Continuar si hay error
                NULL;
        END $$;
    """)


def downgrade() -> None:
    """
    Revertir a projected_revenue GENERATED (NO RECOMENDADO - pérdida de datos reales).
    """
    # Eliminar columna normal
    op.execute("ALTER TABLE ops.plan_trips_monthly DROP COLUMN IF EXISTS projected_revenue CASCADE")
    
    # Recrear como GENERATED
    op.execute("""
        ALTER TABLE ops.plan_trips_monthly
        ADD COLUMN projected_revenue NUMERIC GENERATED ALWAYS AS (
            CASE
                WHEN projected_trips IS NOT NULL AND projected_ticket IS NOT NULL 
                THEN projected_trips::NUMERIC * projected_ticket
                ELSE NULL
            END
        ) STORED
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.plan_trips_monthly.projected_revenue IS 
        'Campo calculado: projected_trips * projected_ticket (GMV)';
    """)
