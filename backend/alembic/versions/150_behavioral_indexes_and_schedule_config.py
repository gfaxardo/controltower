"""
150 — Behavioral Performance Indexes + Routine Schedule Config.

Fase 1F-7 — Agrega:
  - Indices en fraud.trip_risk_features para rutinas conductuales
  - fraud.routine_schedule_config: daily/weekly/monthly plan
  - Indices en fraud.driver_risk_snapshot para behavioral profile
"""
from alembic import op

revision = "150_behavioral_indexes_and_schedule_config"
down_revision = "149_case_confidence_and_behavioral_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Indices on fraud.trip_risk_features for behavioral routines ──
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_trf_origin_cluster ON fraud.trip_risk_features(origin_cluster_key, computed_at) WHERE origin_cluster_key IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_trf_route_signature ON fraud.trip_risk_features(route_signature, computed_at) WHERE route_signature IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_trf_driver_route ON fraud.trip_risk_features(driver_id, route_signature, computed_at)",
        "CREATE INDEX IF NOT EXISTS idx_trf_driver_origin ON fraud.trip_risk_features(driver_id, origin_cluster_key, computed_at)",
        "CREATE INDEX IF NOT EXISTS idx_trf_park_origin ON fraud.trip_risk_features(park_id, origin_cluster_key, computed_at) WHERE origin_cluster_key IS NOT NULL",
    ]:
        op.execute(idx_sql)

    # ── Indices on fraud.driver_risk_snapshot ──
    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_drs_profile_class ON fraud.driver_risk_snapshot(behavioral_profile_class)",
        "CREATE INDEX IF NOT EXISTS idx_drs_confidence ON fraud.driver_risk_snapshot(behavioral_confidence_score)",
    ]:
        op.execute(idx_sql)

    # ── Routine Schedule Config table ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.routine_schedule_config (
            id BIGSERIAL PRIMARY KEY,
            routine_name TEXT NOT NULL,
            frequency TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT true,
            max_runtime_seconds INTEGER,
            config_version TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(routine_name, frequency)
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_rsched_frequency ON fraud.routine_schedule_config(frequency)",
        "CREATE INDEX IF NOT EXISTS idx_rsched_enabled ON fraud.routine_schedule_config(enabled, frequency)",
    ]:
        op.execute(idx_sql)

    # ── Trip behavior feature cache table (for pre-computed route data) ──
    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud.trip_behavior_feature_cache (
            id BIGSERIAL PRIMARY KEY,
            source_table TEXT NOT NULL,
            source_trip_id TEXT NOT NULL,
            driver_id TEXT NOT NULL,
            park_id TEXT,
            trip_datetime TIMESTAMPTZ,
            origin_cluster_key TEXT,
            destination_cluster_key TEXT,
            route_signature TEXT,
            reverse_route_signature TEXT,
            amount NUMERIC,
            distance NUMERIC,
            duration NUMERIC,
            computed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(source_table, source_trip_id)
        )
    """)

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS idx_tbfc_trip_dt ON fraud.trip_behavior_feature_cache(trip_datetime)",
        "CREATE INDEX IF NOT EXISTS idx_tbfc_driver ON fraud.trip_behavior_feature_cache(driver_id)",
        "CREATE INDEX IF NOT EXISTS idx_tbfc_origin_cluster ON fraud.trip_behavior_feature_cache(origin_cluster_key) WHERE origin_cluster_key IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_tbfc_route_signature ON fraud.trip_behavior_feature_cache(route_signature) WHERE route_signature IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS idx_tbfc_park ON fraud.trip_behavior_feature_cache(park_id)",
    ]:
        op.execute(idx_sql)

    # ── Add frequency column to routine_run_log for traceability ──
    op.execute("""
        ALTER TABLE fraud.routine_run_log
        ADD COLUMN IF NOT EXISTS frequency TEXT
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE fraud.routine_run_log DROP COLUMN IF EXISTS frequency")
    op.execute("DROP TABLE IF EXISTS fraud.trip_behavior_feature_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS fraud.routine_schedule_config CASCADE")
    for idx_name in [
        "idx_trf_origin_cluster", "idx_trf_route_signature",
        "idx_trf_driver_route", "idx_trf_driver_origin", "idx_trf_park_origin",
        "idx_drs_profile_class", "idx_drs_confidence",
    ]:
        op.execute(f"DROP INDEX IF EXISTS fraud.{idx_name}")
