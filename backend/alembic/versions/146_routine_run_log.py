"""
146 — Routine Run Log: audit trail para cada corrida antifraude.
Fase 1F-3 — Registra inicio, fin, duracion y resultado de cada rutina.
"""
from alembic import op

revision = "146_routine_run_log"
down_revision = "145_payment_identity_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.routine_run_log (
            id BIGSERIAL PRIMARY KEY,
            run_code TEXT UNIQUE NOT NULL,
            routine_name TEXT NOT NULL,
            mode TEXT NOT NULL,
            dry_run BOOLEAN NOT NULL DEFAULT true,
            date_from DATE,
            date_to DATE,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ DEFAULT now(),
            finished_at TIMESTAMPTZ,
            duration_seconds NUMERIC,
            source_summary JSONB,
            result_summary JSONB,
            error_summary JSONB,
            created_by TEXT
        )
    """)
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_rrl_routine ON fraud.routine_run_log(routine_name)",
        "CREATE INDEX IF NOT EXISTS idx_rrl_status ON fraud.routine_run_log(status)",
        "CREATE INDEX IF NOT EXISTS idx_rrl_started ON fraud.routine_run_log(started_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_rrl_mode ON fraud.routine_run_log(mode)",
    ]:
        op.execute(idx)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fraud.routine_run_log CASCADE")
