-- ============================================================================
-- Yego Pro Profitability — P1.4.5A Scenario Registry
-- ============================================================================
-- Tabla ops.yego_pro_simulation_scenarios para gobernar escenarios
-- del Simulator. Baselines, manuales, sensitivity, etc.
--
-- Ejecutar:
--   psql -d yego_integral -f backend/sql/yego_pro_simulation_scenarios.sql
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ops.yego_pro_simulation_scenarios (
    id                  BIGSERIAL       PRIMARY KEY,
    park_id             TEXT            NOT NULL,
    scenario_name       TEXT            NOT NULL,
    scenario_type       TEXT            NOT NULL DEFAULT 'manual'
                        CHECK (scenario_type IN ('baseline','manual','conservative','aggressive','custom')),
    inputs              JSONB           NOT NULL DEFAULT '{}',
    outputs             JSONB           NOT NULL DEFAULT '{}',
    calculation_trace   JSONB           NOT NULL DEFAULT '[]',
    confidence          TEXT            NULL,
    is_favorite         BOOLEAN         NOT NULL DEFAULT FALSE,
    is_archived         BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by          TEXT            NULL
);

CREATE INDEX IF NOT EXISTS idx_sim_scenarios_park_type
    ON ops.yego_pro_simulation_scenarios (park_id, scenario_type);

CREATE INDEX IF NOT EXISTS idx_sim_scenarios_park_archived
    ON ops.yego_pro_simulation_scenarios (park_id, is_archived);

CREATE INDEX IF NOT EXISTS idx_sim_scenarios_park_fav
    ON ops.yego_pro_simulation_scenarios (park_id, is_favorite);

CREATE INDEX IF NOT EXISTS idx_sim_scenarios_created
    ON ops.yego_pro_simulation_scenarios (created_at DESC);

COMMIT;
