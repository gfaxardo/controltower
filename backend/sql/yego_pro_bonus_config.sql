-- ============================================================================
-- Yego Pro Profitability — P1.4.4 Bonus Config Persistence
-- ============================================================================
-- Crea tabla ops.yego_pro_bonus_config para persistir tablas de bonos
-- configurables del Simulator.
--
-- Ejecutar:
--   psql -d yego_integral -f backend/sql/yego_pro_bonus_config.sql
-- ============================================================================

BEGIN;

-- --------------------------------------------------------------------------
-- 1. Tabla principal
-- --------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ops.yego_pro_bonus_config (
    id              BIGSERIAL       PRIMARY KEY,
    park_id         TEXT            NOT NULL,
    country         TEXT            NULL,
    city            TEXT            NULL,
    config_name     TEXT            NOT NULL DEFAULT 'default',
    bonus_type      TEXT            NOT NULL
                    CHECK (bonus_type IN ('general_branded', 'general_unbranded', 'premier')),
    trips_min       INTEGER         NOT NULL CHECK (trips_min > 0),
    bonus_pct       NUMERIC(8,4)    NOT NULL CHECK (bonus_pct >= 0),
    bonus_amount    NUMERIC(12,2)   NOT NULL CHECK (bonus_amount >= 0),
    effective_from  DATE            NOT NULL DEFAULT CURRENT_DATE,
    effective_to    DATE            NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    source          TEXT            NOT NULL DEFAULT 'manual',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by      TEXT            NULL
);

-- --------------------------------------------------------------------------
-- 2. Indices
-- --------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_yego_bonus_config_park_type_active
    ON ops.yego_pro_bonus_config (park_id, bonus_type, is_active);

CREATE INDEX IF NOT EXISTS idx_yego_bonus_config_park_name_active
    ON ops.yego_pro_bonus_config (park_id, config_name, is_active);

CREATE INDEX IF NOT EXISTS idx_yego_bonus_config_effective
    ON ops.yego_pro_bonus_config (effective_from, effective_to);

-- --------------------------------------------------------------------------
-- 3. Funcion seed: inserta defaults solo si no existen configs activas
--    para el park_id dado. Idempotente.
-- --------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ops.fn_yego_seed_bonus_defaults(
    p_park_id TEXT,
    p_config_name TEXT DEFAULT 'default'
) RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER := 0;
BEGIN
    -- Verificar si ya hay configs activas para este park_id/config_name
    SELECT COUNT(*) INTO v_count
    FROM ops.yego_pro_bonus_config
    WHERE park_id = p_park_id
      AND config_name = p_config_name
      AND is_active = TRUE;

    IF v_count > 0 THEN
        RETURN 0; -- ya existen, no hace nada
    END IF;

    -- Insertar defaults: general_branded
    INSERT INTO ops.yego_pro_bonus_config
        (park_id, config_name, bonus_type, trips_min, bonus_pct, bonus_amount, source)
    VALUES
        (p_park_id, p_config_name, 'general_branded', 190, 27, 720, 'seed'),
        (p_park_id, p_config_name, 'general_branded', 150, 25, 550, 'seed'),
        (p_park_id, p_config_name, 'general_branded', 125, 23, 470, 'seed'),
        (p_park_id, p_config_name, 'general_branded', 100, 21, 390, 'seed'),
        (p_park_id, p_config_name, 'general_branded',  75, 20, 320, 'seed'),
        (p_park_id, p_config_name, 'general_branded',  50, 19, 260, 'seed'),
        (p_park_id, p_config_name, 'general_branded',  30, 18, 175, 'seed');

    -- Insertar defaults: general_unbranded
    INSERT INTO ops.yego_pro_bonus_config
        (park_id, config_name, bonus_type, trips_min, bonus_pct, bonus_amount, source)
    VALUES
        (p_park_id, p_config_name, 'general_unbranded', 150, 20, 450, 'seed'),
        (p_park_id, p_config_name, 'general_unbranded', 125, 18, 390, 'seed'),
        (p_park_id, p_config_name, 'general_unbranded', 100, 16, 315, 'seed'),
        (p_park_id, p_config_name, 'general_unbranded',  75, 14, 230, 'seed'),
        (p_park_id, p_config_name, 'general_unbranded',  50, 13, 170, 'seed'),
        (p_park_id, p_config_name, 'general_unbranded',  30, 12, 125, 'seed'),
        (p_park_id, p_config_name, 'general_unbranded',  10, 11,  60, 'seed');

    -- Insertar defaults: premier
    INSERT INTO ops.yego_pro_bonus_config
        (park_id, config_name, bonus_type, trips_min, bonus_pct, bonus_amount, source)
    VALUES
        (p_park_id, p_config_name, 'premier', 20, 40, 600, 'seed'),
        (p_park_id, p_config_name, 'premier', 15, 36, 410, 'seed'),
        (p_park_id, p_config_name, 'premier', 10, 33, 250, 'seed'),
        (p_park_id, p_config_name, 'premier',  8, 31, 190, 'seed'),
        (p_park_id, p_config_name, 'premier',  6, 29, 130, 'seed'),
        (p_park_id, p_config_name, 'premier',  4, 27,  85, 'seed'),
        (p_park_id, p_config_name, 'premier',  2, 25,  40, 'seed');

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

COMMIT;
