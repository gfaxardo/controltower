-- FASE 1H.1 — SERVING GOVERNANCE FOUNDATION
-- Tablas de gobernanza operacional de serving facts y refreshes.

-- 1. Serving Registry: registro central de cada fact materializada
CREATE TABLE IF NOT EXISTS ops.serving_registry (
    id                  BIGSERIAL PRIMARY KEY,
    serving_key         TEXT NOT NULL UNIQUE,
    entity_name         TEXT NOT NULL,
    grain               TEXT NOT NULL,
    plan_version        TEXT,
    coverage_scope      JSONB DEFAULT '{}'::jsonb,
    row_count           INTEGER DEFAULT 0,
    freshness_status    TEXT DEFAULT 'unknown'
                        CHECK (freshness_status IN ('fresh','stale','empty','broken','unknown')),
    generated_at        TIMESTAMPTZ,
    generation_duration_ms INTEGER,
    source_dependencies JSONB DEFAULT '[]'::jsonb,
    refresh_status      TEXT DEFAULT 'idle'
                        CHECK (refresh_status IN ('idle','running','success','failed')),
    last_success_at     TIMESTAMPTZ,
    last_failure_at     TIMESTAMPTZ,
    last_failure_reason TEXT,
    fallback_allowed    BOOLEAN DEFAULT FALSE,
    runtime_protected   BOOLEAN DEFAULT TRUE,
    active_flag         BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_serving_registry_grain ON ops.serving_registry(grain);
CREATE INDEX IF NOT EXISTS idx_serving_registry_active ON ops.serving_registry(active_flag);
CREATE INDEX IF NOT EXISTS idx_serving_registry_freshness ON ops.serving_registry(freshness_status);

-- 2. Serving Refresh Log: historial de ejecuciones de refresh
CREATE TABLE IF NOT EXISTS ops.serving_refresh_log (
    id                  BIGSERIAL PRIMARY KEY,
    refresh_id          TEXT NOT NULL,
    serving_key         TEXT NOT NULL REFERENCES ops.serving_registry(serving_key),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    duration_ms         INTEGER,
    rows_generated      INTEGER DEFAULT 0,
    success             BOOLEAN,
    error_message       TEXT,
    triggered_by        TEXT DEFAULT 'manual',
    environment         TEXT DEFAULT 'production',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_serving_refresh_log_key ON ops.serving_refresh_log(serving_key);
CREATE INDEX IF NOT EXISTS idx_serving_refresh_log_time ON ops.serving_refresh_log(started_at DESC);

-- 3. Seed existing serving facts into registry
INSERT INTO ops.serving_registry (serving_key, entity_name, grain, plan_version, row_count, freshness_status, generated_at, active_flag)
SELECT
    'omniview_projection_' || grain || '_' || plan_version,
    'Omniview Projection ' || grain,
    grain,
    plan_version,
    COUNT(*),
    CASE WHEN MAX(generated_at) > NOW() - INTERVAL '24 hours' THEN 'fresh' ELSE 'stale' END,
    MAX(generated_at),
    TRUE
FROM serving.omniview_projection_daily_fact
GROUP BY grain, plan_version
ON CONFLICT (serving_key) DO UPDATE SET
    row_count = EXCLUDED.row_count,
    freshness_status = EXCLUDED.freshness_status,
    generated_at = EXCLUDED.generated_at,
    updated_at = NOW();
