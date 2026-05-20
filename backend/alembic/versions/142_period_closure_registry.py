"""
142 — Period Closure Registry: protege periodos cerrados de refresh normal.
Fase 1D — Closed Period Protection.

Crea:
  - ops.period_closure_registry: estado de cierre por grain/periodo/scope
  - ops.v_period_closure_status: vista de estado actual
"""

from alembic import op

revision = "142_period_closure_registry"
down_revision = "141_business_slice_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.period_closure_registry (
            id                  BIGSERIAL PRIMARY KEY,
            grain               TEXT NOT NULL,
            period_start        DATE NOT NULL,
            period_end          DATE NOT NULL,
            country             TEXT,
            city                TEXT,
            business_slice_name TEXT,
            status              TEXT NOT NULL DEFAULT 'open',
            closure_scope       TEXT NOT NULL DEFAULT 'global',
            source_max_date     DATE,
            last_reliable_data_date DATE,
            qa_status           TEXT DEFAULT 'pending',
            qa_summary          JSONB,
            fact_row_count      BIGINT,
            raw_completed_count BIGINT,
            fact_completed_count BIGINT,
            unmatched_count     BIGINT,
            ambiguous_count     BIGINT,
            coverage_pct        NUMERIC,
            checksum            TEXT,
            closed_at           TIMESTAMPTZ,
            closed_by           TEXT,
            reopened_at         TIMESTAMPTZ,
            reopened_by         TEXT,
            reopen_reason       TEXT,
            refresh_run_log_id  BIGINT,
            notes               TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_period_status CHECK (
                status IN ('open', 'provisional', 'closed', 'locked', 'backfill', 'failed_closure')
            ),
            CONSTRAINT chk_period_qa CHECK (
                qa_status IN ('pending', 'pass', 'fail', 'warning')
            ),
            CONSTRAINT chk_period_scope CHECK (
                closure_scope IN ('global', 'country', 'city', 'slice')
            ),
            CONSTRAINT chk_period_grain CHECK (
                grain IN ('daily', 'weekly', 'monthly', 'ytd')
            )
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_period_closure
        ON ops.period_closure_registry (grain, period_start, period_end, COALESCE(country, ''), COALESCE(city, ''), COALESCE(business_slice_name, ''))
    """)

    op.execute("COMMENT ON TABLE ops.period_closure_registry IS 'Registro de cierre de periodos. Protege data cerrada de refreshes normales.'")

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_period_closure_grain_start
        ON ops.period_closure_registry (grain, period_start DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_period_closure_status
        ON ops.period_closure_registry (status)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_period_closure_country_city
        ON ops.period_closure_registry (country, city)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_period_closure_updated
        ON ops.period_closure_registry (updated_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_period_closure_qa
        ON ops.period_closure_registry (qa_status)
    """)

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_period_closure_status AS
        SELECT
            grain,
            period_start,
            period_end,
            country,
            city,
            business_slice_name,
            status,
            qa_status,
            coverage_pct,
            raw_completed_count,
            fact_completed_count,
            unmatched_count,
            ambiguous_count,
            checksum,
            closed_at,
            reopened_at,
            reopen_reason,
            last_reliable_data_date,
            source_max_date,
            notes,
            closure_scope,
            refresh_run_log_id
        FROM ops.period_closure_registry
        ORDER BY grain, period_start DESC, COALESCE(country,''), COALESCE(city,'')
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_period_closure_status")
    op.execute("DROP TABLE IF EXISTS ops.period_closure_registry")
