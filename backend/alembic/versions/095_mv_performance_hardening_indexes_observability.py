"""
CT-MV-PERFORMANCE-HARDENING: índices de consulta y columnas de observabilidad.

- Índices de lookup para ops.mv_real_lob_week_v2 y ops.mv_real_lob_month_v2 (real_tipo_servicio_norm).
  Los índices UNIQUE ya existen (uq_mv_real_lob_*_v2) y permiten REFRESH CONCURRENTLY.
- Columnas en ops.observability_refresh_log: rows_before, rows_after, duration_seconds.
"""
from alembic import op

revision = "095_mv_performance_hardening"
down_revision = "094_recreate_real_lob_mvs_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Índices de consulta (lookup por tipo servicio) — si no existen
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup
        ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup
        ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)
    """)

    # Observabilidad: columnas para métricas de refresh (rows_before, rows_after, duration_seconds)
    for col, typ in [
        ("rows_before", "bigint"),
        ("rows_after", "bigint"),
        ("duration_seconds", "numeric(12,2)"),
    ]:
        op.execute(
            f"ALTER TABLE ops.observability_refresh_log ADD COLUMN IF NOT EXISTS {col} {typ}"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ops.idx_mv_real_lob_week_lookup")
    op.execute("DROP INDEX IF EXISTS ops.idx_mv_real_lob_month_lookup")
    op.execute("ALTER TABLE ops.observability_refresh_log DROP COLUMN IF EXISTS rows_before")
    op.execute("ALTER TABLE ops.observability_refresh_log DROP COLUMN IF EXISTS rows_after")
    op.execute("ALTER TABLE ops.observability_refresh_log DROP COLUMN IF EXISTS duration_seconds")
