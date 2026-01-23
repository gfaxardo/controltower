"""create_phase2b_actions_table

Revision ID: 015_create_phase2b_actions_table
Revises: 014_create_phase2b_weekly_views
Create Date: 2026-01-22 20:30:06.000000

FASE 2B: Tabla de acciones operativas para seguimiento de alertas.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_create_phase2b_actions_table'
down_revision = '014_create_phase2b_weekly_views'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    # Crear tabla de acciones
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.phase2b_actions (
            phase2b_action_id SERIAL PRIMARY KEY,
            week_start DATE NOT NULL,
            country TEXT NOT NULL,
            city_norm TEXT,
            lob_base TEXT,
            segment TEXT,
            alert_type TEXT NOT NULL,
            root_cause TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_description TEXT NOT NULL,
            owner_role TEXT NOT NULL,
            owner_user_id UUID,
            due_date DATE NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT phase2b_actions_status_check 
                CHECK (status IN ('OPEN', 'IN_PROGRESS', 'DONE', 'MISSED'))
        )
    """)

    # Índices
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_week_start
        ON ops.phase2b_actions(week_start)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_owner_role
        ON ops.phase2b_actions(owner_role)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_status
        ON ops.phase2b_actions(status)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_phase2b_actions_keys_week
        ON ops.phase2b_actions(week_start, country, city_norm, lob_base, segment)
    """)

    # Trigger para actualizar updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.update_phase2b_actions_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        DROP TRIGGER IF EXISTS trigger_update_phase2b_actions_updated_at ON ops.phase2b_actions;
        CREATE TRIGGER trigger_update_phase2b_actions_updated_at
        BEFORE UPDATE ON ops.phase2b_actions
        FOR EACH ROW
        EXECUTE FUNCTION ops.update_phase2b_actions_updated_at();
    """)


def downgrade() -> None:
    # Downgrade intencionalmente no destructivo
    op.execute("DROP TRIGGER IF EXISTS trigger_update_phase2b_actions_updated_at ON ops.phase2b_actions")
    op.execute("DROP FUNCTION IF EXISTS ops.update_phase2b_actions_updated_at()")
    # No eliminamos la tabla para preservar datos
