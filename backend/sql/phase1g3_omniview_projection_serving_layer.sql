-- =============================================================================
-- FASE 1G.3 — Omniview Projection Serving Layer
-- Performance serving table para evitar recálculo runtime de proyección diaria.
-- NO modifica lógica funcional de Plan vs Real ni Omniview Matrix.
-- Aditivo y auditable.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS serving;

DROP TABLE IF EXISTS serving.omniview_projection_daily_fact;

CREATE TABLE serving.omniview_projection_daily_fact (
    id              BIGSERIAL PRIMARY KEY,
    plan_version    TEXT NOT NULL,
    grain           TEXT NOT NULL CHECK (grain IN ('daily', 'weekly')),
    country         TEXT NOT NULL,
    city            TEXT NOT NULL,
    business_slice_name TEXT NOT NULL,

    -- Temporal keys
    period_key      TEXT NOT NULL,
    year            INTEGER,
    month           INTEGER,
    trip_date       TEXT,
    week_start      TEXT,
    week_end        TEXT,
    iso_year        INTEGER,
    iso_week        INTEGER,
    month_source    TEXT,

    -- Real metrics
    real_trips           DECIMAL(18,4),
    real_revenue         DECIMAL(18,4),
    real_active_drivers  DECIMAL(18,4),
    real_trips_cancelled DECIMAL(18,4),
    real_avg_ticket      DECIMAL(18,4),
    real_commission_pct  DECIMAL(18,4),
    real_trips_per_driver DECIMAL(18,4),
    real_cancel_rate_pct DECIMAL(18,4),

    -- Plan metrics (projected)
    trips_completed_projected_total    DECIMAL(18,4),
    trips_completed_projected_expected DECIMAL(18,4),
    revenue_yego_net_projected_total   DECIMAL(18,4),
    revenue_yego_net_projected_expected DECIMAL(18,4),
    active_drivers_projected_total     DECIMAL(18,4),
    active_drivers_projected_expected  DECIMAL(18,4),

    -- Attainment scores
    trips_completed                 DECIMAL(18,4),
    revenue_yego_net                DECIMAL(18,4),
    active_drivers                  DECIMAL(18,4),
    trips_completed_attainment_pct  DECIMAL(10,4),
    revenue_yego_net_attainment_pct DECIMAL(10,4),
    active_drivers_attainment_pct   DECIMAL(10,4),
    trips_completed_gap_to_expected  DECIMAL(18,4),
    revenue_yego_net_gap_to_expected DECIMAL(18,4),
    active_drivers_gap_to_expected   DECIMAL(18,4),
    trips_completed_gap_to_full      DECIMAL(18,4),
    revenue_yego_net_gap_to_full     DECIMAL(18,4),
    active_drivers_gap_to_full       DECIMAL(18,4),
    trips_completed_completion_pct   DECIMAL(10,4),
    revenue_yego_net_completion_pct  DECIMAL(10,4),
    active_drivers_completion_pct    DECIMAL(10,4),
    trips_completed_signal          TEXT,
    revenue_yego_net_signal         TEXT,
    active_drivers_signal           TEXT,

    -- Projection quality metadata
    comparison_status       TEXT,
    comparison_basis        TEXT,
    curve_method            TEXT,
    curve_confidence        TEXT,
    fallback_level          INTEGER,
    expected_ratio          DECIMAL(18,8),
    projection_confidence   TEXT,
    projection_anomaly      BOOLEAN DEFAULT FALSE,

    -- Aux metrics
    avg_ticket              DECIMAL(18,4),
    commission_pct          DECIMAL(18,4),
    trips_per_driver        DECIMAL(18,4),
    cancel_rate_pct         DECIMAL(18,4),
    trips_cancelled         DECIMAL(18,4),

    -- UI metadata
    week_label              TEXT,
    week_range_label        TEXT,
    week_full_label         TEXT,
    distribution_model      TEXT,
    gap_pct                 DECIMAL(10,4),
    fleet_display_name      TEXT DEFAULT '',
    is_subfleet             BOOLEAN DEFAULT FALSE,
    subfleet_name           TEXT DEFAULT '',

    -- Audit
    generated_at            TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    batch_id                TEXT
);

-- Índices para queries de lectura del endpoint
CREATE INDEX idx_omv_proj_plan_grain ON serving.omniview_projection_daily_fact(plan_version, grain);
CREATE INDEX idx_omv_proj_geo_period ON serving.omniview_projection_daily_fact(country, city, year, month);
CREATE INDEX idx_omv_proj_bsn ON serving.omniview_projection_daily_fact(business_slice_name);
CREATE INDEX idx_omv_proj_gen ON serving.omniview_projection_daily_fact(generated_at);

-- =============================================================================
-- Filters Catalog: catálogo pre-computado para /ops/business-slice/filters.
-- Evita DISTINCT scan completo sobre la MV cada 5 min.
-- =============================================================================

DROP TABLE IF EXISTS serving.business_slice_filters_catalog;

CREATE TABLE serving.business_slice_filters_catalog (
    country             TEXT NOT NULL,
    city                TEXT NOT NULL,
    business_slice_name TEXT NOT NULL,
    fleet_display_name  TEXT DEFAULT '',
    is_subfleet         BOOLEAN DEFAULT FALSE,
    subfleet_name       TEXT DEFAULT '',
    generated_at        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_bs_filters_cat_uniq
    ON serving.business_slice_filters_catalog(country, city, business_slice_name, fleet_display_name, subfleet_name);
