"""
148 — Threshold Config + Calibration Columns.

Fase 1F-5B — Agrega:
  - fraud.rule_threshold_config: thresholds versionados
  - fraud.risk_cases.calibration_status: trazabilidad pre/post calibracion
  - fraud.risk_cases.calibration_version: version de threshold usada
"""
from alembic import op

revision = "148_threshold_config_calibration"
down_revision = "147_trip_behavior_route_features"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.rule_threshold_config (
            id BIGSERIAL PRIMARY KEY,
            rule_code TEXT NOT NULL,
            config_version TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT true,
            threshold_config JSONB NOT NULL,
            rationale TEXT,
            active_from TIMESTAMPTZ DEFAULT now(),
            active_to TIMESTAMPTZ,
            created_by TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(rule_code, config_version)
        )
    """)
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_rtc_rule ON fraud.rule_threshold_config(rule_code)",
        "CREATE INDEX IF NOT EXISTS idx_rtc_version ON fraud.rule_threshold_config(config_version)",
        "CREATE INDEX IF NOT EXISTS idx_rtc_active ON fraud.rule_threshold_config(active_from)",
    ]:
        op.execute(idx_sql)

    # Calibration columns on risk_cases
    for col_sql in [
        "ALTER TABLE fraud.risk_cases ADD COLUMN IF NOT EXISTS calibration_status TEXT",
        "ALTER TABLE fraud.risk_cases ADD COLUMN IF NOT EXISTS calibration_version TEXT",
    ]:
        op.execute(col_sql)


def downgrade() -> None:
    for col in ["calibration_version", "calibration_status"]:
        op.execute(f"ALTER TABLE fraud.risk_cases DROP COLUMN IF EXISTS {col}")
    op.execute("DROP TABLE IF EXISTS fraud.rule_threshold_config CASCADE")
