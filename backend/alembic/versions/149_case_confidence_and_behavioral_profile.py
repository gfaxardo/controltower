"""
149 — Case Confidence Score + Behavioral Profile Class.

Fase 1F-5C — Agrega:
  - fraud.risk_cases.case_confidence_score: score 0-100
  - fraud.risk_cases.confidence_reason: desglose del scoring
  - fraud.risk_cases.calibration_status: ya existe (148), se documenta
  - fraud.risk_cases.calibration_version: ya existe (148), se documenta
  - fraud.driver_risk_snapshot.behavioral_profile_class: normal/watchlist/suspicious/high_risk/critical_pattern
  - fraud.driver_risk_snapshot.behavioral_profile_reason: desglose
  - fraud.driver_risk_snapshot.behavioral_confidence_score: score numerico 0-100
"""
from alembic import op

revision = "149_case_confidence_and_behavioral_profile"
down_revision = "148_threshold_config_calibration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── fraud.risk_cases: confidence columns ──
    for col_sql in [
        "ALTER TABLE fraud.risk_cases ADD COLUMN IF NOT EXISTS case_confidence_score NUMERIC",
        "ALTER TABLE fraud.risk_cases ADD COLUMN IF NOT EXISTS confidence_reason JSONB",
    ]:
        op.execute(col_sql)

    # ── fraud.driver_risk_snapshot: behavioral profile columns ──
    for col_sql in [
        "ALTER TABLE fraud.driver_risk_snapshot ADD COLUMN IF NOT EXISTS behavioral_profile_class TEXT",
        "ALTER TABLE fraud.driver_risk_snapshot ADD COLUMN IF NOT EXISTS behavioral_profile_reason JSONB",
        "ALTER TABLE fraud.driver_risk_snapshot ADD COLUMN IF NOT EXISTS behavioral_confidence_score NUMERIC",
    ]:
        op.execute(col_sql)

    # ── Indices ──
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_cases_confidence ON fraud.risk_cases(case_confidence_score)",
        "CREATE INDEX IF NOT EXISTS idx_cases_calibrated ON fraud.risk_cases(calibration_status, calibration_version)",
        "CREATE INDEX IF NOT EXISTS idx_driver_risk_profile ON fraud.driver_risk_snapshot(behavioral_profile_class)",
    ]:
        op.execute(idx_sql)


def downgrade() -> None:
    for col in ["case_confidence_score", "confidence_reason"]:
        op.execute(f"ALTER TABLE fraud.risk_cases DROP COLUMN IF EXISTS {col}")
    for col in ["behavioral_profile_class", "behavioral_profile_reason", "behavioral_confidence_score"]:
        op.execute(f"ALTER TABLE fraud.driver_risk_snapshot DROP COLUMN IF EXISTS {col}")
    for idx in ["idx_cases_confidence", "idx_cases_calibrated", "idx_driver_risk_profile"]:
        op.execute(f"DROP INDEX IF EXISTS fraud.{idx}")
