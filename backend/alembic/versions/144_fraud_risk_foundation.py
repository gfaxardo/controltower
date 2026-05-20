"""
144 — Fraud Risk Control Foundation.
Fase 1F — Crea esquema fraud con tablas de reglas, trust, riesgo, casos y auditoria.

Crea esquema fraud con:
  - fraud.rule_catalog
  - fraud.driver_trust_snapshot
  - fraud.trip_risk_features
  - fraud.driver_risk_snapshot
  - fraud.risk_cases
  - fraud.action_audit_log
  - fraud.external_identity_clusters
"""
from alembic import op

revision = "144_fraud_risk_foundation"
down_revision = "143_last_good_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS fraud")

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.rule_catalog (
            id BIGSERIAL PRIMARY KEY,
            rule_code TEXT UNIQUE NOT NULL,
            rule_name TEXT NOT NULL,
            description TEXT,
            severity_default TEXT NOT NULL,
            weight NUMERIC NOT NULL DEFAULT 0,
            enabled BOOLEAN NOT NULL DEFAULT true,
            requires_source JSONB,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.driver_trust_snapshot (
            id BIGSERIAL PRIMARY KEY,
            driver_id TEXT NOT NULL,
            park_id TEXT,
            total_completed_trips BIGINT NOT NULL DEFAULT 0,
            completed_trips_7d BIGINT NOT NULL DEFAULT 0,
            completed_trips_30d BIGINT NOT NULL DEFAULT 0,
            first_completed_trip_at TIMESTAMPTZ,
            last_completed_trip_at TIMESTAMPTZ,
            trust_tier TEXT NOT NULL,
            trust_reason JSONB,
            computed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(driver_id, park_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.trip_risk_features (
            id BIGSERIAL PRIMARY KEY,
            source_table TEXT NOT NULL,
            source_trip_id TEXT NOT NULL,
            driver_id TEXT NOT NULL,
            park_id TEXT,
            trip_datetime TIMESTAMPTZ,
            payment_method TEXT,
            amount NUMERIC,
            distance NUMERIC,
            duration NUMERIC,
            pickup_lat NUMERIC,
            pickup_lng NUMERIC,
            pickup_cluster_key TEXT,
            pickup_address_norm TEXT,
            city TEXT,
            country TEXT,
            flags JSONB,
            triggered_rules JSONB,
            risk_score NUMERIC NOT NULL DEFAULT 0,
            severity TEXT NOT NULL DEFAULT 'low',
            computed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(source_table, source_trip_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.driver_risk_snapshot (
            id BIGSERIAL PRIMARY KEY,
            driver_id TEXT NOT NULL,
            park_id TEXT,
            risk_score NUMERIC NOT NULL DEFAULT 0,
            severity TEXT NOT NULL DEFAULT 'low',
            triggered_rules JSONB,
            suspicious_trip_count BIGINT NOT NULL DEFAULT 0,
            completed_trip_count BIGINT NOT NULL DEFAULT 0,
            recommended_action TEXT,
            action_reason JSONB,
            computed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(driver_id, park_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.risk_cases (
            id BIGSERIAL PRIMARY KEY,
            case_code TEXT UNIQUE NOT NULL,
            driver_id TEXT NOT NULL,
            park_id TEXT,
            severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            risk_score NUMERIC NOT NULL DEFAULT 0,
            case_reason JSONB,
            recommended_action TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            review_decision TEXT,
            review_comment TEXT
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.action_audit_log (
            id BIGSERIAL PRIMARY KEY,
            case_id BIGINT REFERENCES fraud.risk_cases(id),
            driver_id TEXT NOT NULL,
            park_id TEXT,
            action_type TEXT NOT NULL,
            action_mode TEXT NOT NULL,
            action_status TEXT NOT NULL,
            payload JSONB,
            result JSONB,
            created_by TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.external_identity_clusters (
            id BIGSERIAL PRIMARY KEY,
            cluster_type TEXT NOT NULL,
            cluster_key_hash TEXT NOT NULL,
            drivers JSONB,
            evidence JSONB,
            severity TEXT NOT NULL DEFAULT 'low',
            computed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(cluster_type, cluster_key_hash)
        )
    """)

    # Indices
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_trust_driver ON fraud.driver_trust_snapshot(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_trust_park ON fraud.driver_trust_snapshot(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_trust_tier ON fraud.driver_trust_snapshot(trust_tier)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_driver ON fraud.trip_risk_features(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_park ON fraud.trip_risk_features(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_severity ON fraud.trip_risk_features(severity)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_computed ON fraud.trip_risk_features(computed_at)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_cluster ON fraud.trip_risk_features(pickup_cluster_key)",
        "CREATE INDEX IF NOT EXISTS idx_trip_risk_source ON fraud.trip_risk_features(source_table, source_trip_id)",
        "CREATE INDEX IF NOT EXISTS idx_driver_risk_driver ON fraud.driver_risk_snapshot(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_driver_risk_park ON fraud.driver_risk_snapshot(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_driver_risk_severity ON fraud.driver_risk_snapshot(severity)",
        "CREATE INDEX IF NOT EXISTS idx_cases_status ON fraud.risk_cases(status)",
        "CREATE INDEX IF NOT EXISTS idx_cases_driver ON fraud.risk_cases(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_cases_park ON fraud.risk_cases(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_cases_severity ON fraud.risk_cases(severity)",
        "CREATE INDEX IF NOT EXISTS idx_audit_case ON fraud.action_audit_log(case_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_driver ON fraud.action_audit_log(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_rule_code ON fraud.rule_catalog(rule_code)",
        "CREATE INDEX IF NOT EXISTS idx_identity_cluster ON fraud.external_identity_clusters(cluster_type, cluster_key_hash)",
    ]:
        op.execute(idx_sql)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS fraud.action_audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.risk_cases CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.driver_risk_snapshot CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.trip_risk_features CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.driver_trust_snapshot CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.rule_catalog CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.external_identity_clusters CASCADE")
    op.execute("DROP SCHEMA IF EXISTS fraud CASCADE")
