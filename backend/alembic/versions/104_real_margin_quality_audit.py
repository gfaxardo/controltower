"""
Tabla de auditoría para hallazgos de calidad de margen en fuente (REAL).
Alertas: REAL_MARGIN_SOURCE_GAP_COMPLETED (completados sin margen), REAL_CANCELLED_WITH_MARGIN (cancelados con margen).
"""
from alembic import op

revision = "104_real_margin_quality_audit"
down_revision = "103_real_drill_dim_fact_cancelled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.real_margin_quality_audit (
            id serial PRIMARY KEY,
            alert_code text NOT NULL,
            severity text NOT NULL,
            detected_at timestamptz NOT NULL DEFAULT now(),
            grain_date date,
            affected_trips bigint,
            denominator_trips bigint,
            pct numeric,
            message_humano_legible text,
            dimensions jsonb,
            metadata jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_real_margin_quality_audit_alert_detected ON ops.real_margin_quality_audit (alert_code, detected_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_real_margin_quality_audit_severity ON ops.real_margin_quality_audit (severity)")
    op.execute("COMMENT ON TABLE ops.real_margin_quality_audit IS 'Hallazgos de auditoría: huecos de margen en fuente REAL (completados sin margen, cancelados con margen). Script: audit_real_margin_source_gaps.'")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.real_margin_quality_audit CASCADE")
