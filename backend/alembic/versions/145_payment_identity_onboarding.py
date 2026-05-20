"""
145 — Payment Identity Onboarding: fuente segura + import log.
Fase 1F-2 — Crea tablas seguras para identidad bancaria sin exponer account_number completo.

Crea:
  - fraud.payment_identity_source (account_hash, masked, sin raw account_number)
  - fraud.payment_identity_import_log (trazabilidad de imports)
"""
from alembic import op

revision = "145_payment_identity_onboarding"
down_revision = "144_fraud_risk_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.payment_identity_source (
            id BIGSERIAL PRIMARY KEY,
            driver_id TEXT NOT NULL,
            park_id TEXT,
            bank_name_norm TEXT,
            account_hash TEXT NOT NULL,
            masked_account_number TEXT,
            source_name TEXT NOT NULL,
            source_batch_id TEXT,
            source_row_number INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT true,
            evidence JSONB,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(driver_id, account_hash, source_name)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.payment_identity_import_log (
            id BIGSERIAL PRIMARY KEY,
            batch_id TEXT UNIQUE NOT NULL,
            source_name TEXT NOT NULL,
            file_name TEXT,
            dry_run BOOLEAN NOT NULL DEFAULT true,
            status TEXT NOT NULL,
            total_rows INTEGER DEFAULT 0,
            valid_rows INTEGER DEFAULT 0,
            invalid_rows INTEGER DEFAULT 0,
            duplicated_rows INTEGER DEFAULT 0,
            inserted_rows INTEGER DEFAULT 0,
            updated_rows INTEGER DEFAULT 0,
            skipped_rows INTEGER DEFAULT 0,
            errors JSONB,
            started_at TIMESTAMPTZ DEFAULT now(),
            finished_at TIMESTAMPTZ,
            created_by TEXT
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_pis_driver ON fraud.payment_identity_source(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_pis_park ON fraud.payment_identity_source(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_pis_hash ON fraud.payment_identity_source(account_hash)",
        "CREATE INDEX IF NOT EXISTS idx_pis_batch ON fraud.payment_identity_source(source_batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_pis_active ON fraud.payment_identity_source(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_piil_batch ON fraud.payment_identity_import_log(batch_id)",
        "CREATE INDEX IF NOT EXISTS idx_piil_status ON fraud.payment_identity_import_log(status)",
    ]:
        op.execute(idx_sql)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fraud.payment_identity_import_log CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.payment_identity_source CASCADE")
