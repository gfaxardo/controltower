"""151 — Autocobro Eligibility Readiness.

Fase 1F-8 — Agrega:
  - fraud.autocobro_eligibility_policy: versionado de politicas de elegibilidad
  - fraud.autocobro_eligibility_snapshot: snapshot de elegibilidad por driver
  - Indices de soporte
"""
from alembic import op

revision = "151_autocobro_eligibility_readiness"
down_revision = "150_behavioral_indexes_and_schedule_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Autocobro Eligibility Policy table ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.autocobro_eligibility_policy (
            id BIGSERIAL PRIMARY KEY,
            policy_version TEXT UNIQUE NOT NULL,
            enabled BOOLEAN DEFAULT true,
            policy_config JSONB NOT NULL,
            rationale TEXT NULL,
            created_by TEXT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # Seed v1 preview policy
    op.execute("""
        INSERT INTO fraud.autocobro_eligibility_policy
            (policy_version, enabled, policy_config, rationale, created_by)
        VALUES (
            'autocobro_v1_preview',
            true,
            '{
                "rules": {
                    "eligible": [
                        {"id": "E1", "field": "trust_tier", "op": "eq", "value": "trusted"},
                        {"id": "E2", "field": "total_completed_trips", "op": "gte", "value": 50},
                        {"id": "E3", "field": "behavioral_profile_class", "op": "in", "value": ["normal", "watchlist"]},
                        {"id": "E4", "field": "open_high_critical_cases", "op": "eq", "value": 0},
                        {"id": "E5", "field": "max_case_confidence_score", "op": "lt", "value": 60},
                        {"id": "E6", "field": "synthetic_identity", "op": "eq", "value": false},
                        {"id": "E7", "field": "short_trip_farming", "op": "eq", "value": false},
                        {"id": "E8", "field": "high_card_new_driver", "op": "eq", "value": false},
                        {"id": "E9", "field": "recommended_action", "op": "not_in", "value": ["restrict_driver_review", "disable_autocobro", "hold_bonus_review"]}
                    ],
                    "review_required": [
                        {"id": "R1", "condition": "trust_tier_eq_new_or_unproven AND total_completed_trips_gte_30"},
                        {"id": "R2", "field": "behavioral_profile_class", "op": "eq", "value": "suspicious"},
                        {"id": "R3", "condition": "open_medium_cases_confidence_30_59"},
                        {"id": "R4", "condition": "is_fraud_candidate_no_high_critical_cases"},
                        {"id": "R5", "condition": "behavioral_profile_null_but_trusted_50plus"}
                    ],
                    "restricted": [
                        {"id": "X1", "field": "behavioral_profile_class", "op": "in", "value": ["high_risk", "critical_pattern"]},
                        {"id": "X2", "field": "open_high_critical_cases", "op": "gt", "value": 0},
                        {"id": "X3", "field": "recommended_action", "op": "in", "value": ["restrict_driver_review", "disable_autocobro", "hold_bonus_review"]},
                        {"id": "X4", "field": "max_case_confidence_score", "op": "gte", "value": 60},
                        {"id": "X5", "field": "short_trip_farming", "op": "eq", "value": true},
                        {"id": "X6", "field": "high_card_new_driver", "op": "eq", "value": true},
                        {"id": "X7", "field": "trust_tier", "op": "eq", "value": "restricted"}
                    ],
                    "unknown": [
                        {"id": "U1", "field": "trust_tier", "op": "is_null", "value": null},
                        {"id": "U2", "field": "trust_tier", "op": "eq", "value": "unknown"},
                        {"id": "U3", "field": "total_completed_trips", "op": "lt", "value": 3}
                    ]
                },
                "evaluation_order": ["unknown", "restricted", "review_required", "eligible"],
                "mode": "preview_only",
                "external_execution": false
            }'::jsonb,
            'Politica deterministica inicial de elegibilidad de autocobro basada en trust_tier, behavioral_profile_class, open cases, y flags de riesgo. Preview-only. Sin ejecucion real.',
            'fase_1f8_architect'
        )
        ON CONFLICT (policy_version) DO NOTHING
    """)

    # ── Autocobro Eligibility Snapshot table ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.autocobro_eligibility_snapshot (
            id BIGSERIAL PRIMARY KEY,
            driver_id TEXT NOT NULL,
            park_id TEXT NULL,
            policy_version TEXT NOT NULL,
            eligibility_status TEXT NOT NULL,
            eligibility_reason JSONB NULL,
            trust_tier TEXT NULL,
            total_completed_trips BIGINT NULL,
            behavioral_profile_class TEXT NULL,
            behavioral_confidence_score NUMERIC NULL,
            max_case_confidence_score NUMERIC NULL,
            open_case_count INTEGER DEFAULT 0,
            high_case_count INTEGER DEFAULT 0,
            critical_case_count INTEGER DEFAULT 0,
            recommended_action TEXT NULL,
            computed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(driver_id, park_id, policy_version)
        )
    """)

    # ── Indices ──
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_aes_status ON fraud.autocobro_eligibility_snapshot(eligibility_status)",
        "CREATE INDEX IF NOT EXISTS idx_aes_policy ON fraud.autocobro_eligibility_snapshot(policy_version)",
        "CREATE INDEX IF NOT EXISTS idx_aes_driver ON fraud.autocobro_eligibility_snapshot(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_aes_park ON fraud.autocobro_eligibility_snapshot(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_aes_computed ON fraud.autocobro_eligibility_snapshot(computed_at)",
    ]:
        op.execute(idx_sql)


def downgrade() -> None:
    for idx_name in [
        "idx_aes_status", "idx_aes_policy", "idx_aes_driver",
        "idx_aes_park", "idx_aes_computed",
    ]:
        op.execute(f"DROP INDEX IF EXISTS fraud.{idx_name}")
    op.execute("DROP TABLE IF EXISTS fraud.autocobro_eligibility_snapshot CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.autocobro_eligibility_policy CASCADE")
