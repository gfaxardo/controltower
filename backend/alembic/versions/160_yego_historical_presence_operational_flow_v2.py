"""
160 — YEGO Historical Presence + Operational Flow V2

Creates:
- ops.mv_yego_driver_historical_presence_v1: per-driver first/last seen dates
- ops.fct_yego_operational_flow_monthly_v2: monthly enriched operational flow

Sources:
- primary_current: public.module_ct_fleet_summary_daily
- historical_auxiliary: trips_2025 + trips_2026

Additive only. No DROP on raw. No production scoring impact.

down_revision: 159_yego_operational_flow_internal_kpi
"""

from alembic import op

revision = "160_yego_historical_presence_operational_flow_v2"
down_revision = "159_yego_operational_flow_internal_kpi"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS ops;")

    # 1. Historical Presence MV — per driver, combining fleet_summary + trips
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_yego_driver_historical_presence_v1 AS
        WITH fleet_presence AS (
            SELECT
                driver_id,
                MIN(fecha) as fleet_first_seen,
                MAX(fecha) as fleet_last_active,
                MIN(fecha) FILTER (WHERE work_time_hours > 0) as fleet_first_sh,
                MIN(fecha) FILTER (WHERE count_orders_completed > 0) as fleet_first_trip
            FROM public.module_ct_fleet_summary_daily
            GROUP BY driver_id
        ),
        trips_presence AS (
            SELECT
                conductor_id as driver_id,
                MIN(fecha_inicio_viaje::date) as trips_first_seen,
                MAX(fecha_inicio_viaje::date) as trips_last_active
            FROM public.trips_2025
            WHERE condicion = 'Completado'
            GROUP BY conductor_id
            UNION ALL
            SELECT
                conductor_id as driver_id,
                MIN(fecha_inicio_viaje::date) as trips_first_seen,
                MAX(fecha_inicio_viaje::date) as trips_last_active
            FROM public.trips_2026
            WHERE condicion = 'Completado'
            GROUP BY conductor_id
        ),
        trips_agg AS (
            SELECT
                driver_id,
                MIN(trips_first_seen) as trips_first_seen,
                MAX(trips_last_active) as trips_last_active
            FROM trips_presence
            GROUP BY driver_id
        ),
        combined AS (
            SELECT
                COALESCE(f.driver_id, t.driver_id) as driver_id,
                f.fleet_first_seen,
                f.fleet_last_active,
                f.fleet_first_sh,
                f.fleet_first_trip,
                t.trips_first_seen,
                t.trips_last_active,
                LEAST(
                    COALESCE(f.fleet_first_seen, '9999-01-01'::date),
                    COALESCE(f.fleet_first_sh, '9999-01-01'::date),
                    COALESCE(t.trips_first_seen, '9999-01-01'::date)
                ) as first_yego_seen_date,
                GREATEST(
                    COALESCE(f.fleet_last_active, '1900-01-01'::date),
                    COALESCE(t.trips_last_active, '1900-01-01'::date)
                ) as last_yego_activity_date
            FROM fleet_presence f
            FULL OUTER JOIN trips_agg t ON t.driver_id = f.driver_id
        )
        SELECT
            driver_id,
            first_yego_seen_date,
            fleet_first_seen IS NOT NULL AND fleet_first_seen = first_yego_seen_date
                as first_seen_from_fleet,
            trips_first_seen IS NOT NULL AND trips_first_seen = first_yego_seen_date
                as first_seen_from_trips,
            fleet_first_seen,
            fleet_first_sh,
            fleet_first_trip,
            trips_first_seen,
            fleet_last_active,
            trips_last_active,
            last_yego_activity_date,
            CASE
                WHEN trips_first_seen IS NOT NULL
                 AND fleet_first_seen IS NOT NULL
                 AND trips_first_seen < fleet_first_seen
                THEN true
                WHEN trips_first_seen IS NOT NULL
                 AND fleet_first_seen IS NULL
                THEN true
                ELSE false
            END as has_pre_fleet_summary_history,
            fleet_first_seen IS NULL as fleet_summary_only_missing,
            trips_first_seen IS NULL as trips_only_missing,
            CASE
                WHEN fleet_first_seen IS NOT NULL AND trips_first_seen IS NOT NULL THEN 'high'
                WHEN fleet_first_seen IS NOT NULL THEN 'medium'
                WHEN trips_first_seen IS NOT NULL THEN 'low'
                ELSE 'unknown'
            END as historical_confidence,
            CASE
                WHEN fleet_first_seen IS NOT NULL
                 AND trips_first_seen IS NOT NULL
                 AND trips_first_seen < fleet_first_seen
                THEN true
                ELSE false
            END as vintage_risk,
            now() as last_refreshed_at
        FROM combined
        WHERE first_yego_seen_date != '9999-01-01'::date;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_yego_historical_presence_v1_pk
        ON ops.mv_yego_driver_historical_presence_v1 (driver_id);
    """)

    # 2. Operational Flow Serving Fact v2 — monthly enriched flow
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.fct_yego_operational_flow_monthly_v2 (
            month_start DATE NOT NULL,
            country TEXT NOT NULL DEFAULT 'PE',
            city_norm TEXT NOT NULL DEFAULT 'lima',
            metric_universe TEXT NOT NULL DEFAULT 'yego_operational',
            definition_set_id TEXT NOT NULL DEFAULT 'yego_operational_supply_30d',
            source_key TEXT NOT NULL DEFAULT 'fleet_summary_daily',
            activity_signal TEXT NOT NULL DEFAULT 'work_time_hours > 0',
            inactivity_window_days INTEGER NOT NULL DEFAULT 30,
            yego_new_drivers INTEGER NOT NULL DEFAULT 0,
            yego_reactivated_drivers INTEGER NOT NULL DEFAULT 0,
            yego_existing_active_drivers INTEGER NOT NULL DEFAULT 0,
            yego_operational_new_plus_reactivated INTEGER NOT NULL DEFAULT 0,
            false_new_drivers_detected INTEGER NOT NULL DEFAULT 0,
            reclassified_new_to_existing_or_reactivated INTEGER NOT NULL DEFAULT 0,
            vintage_risk_count INTEGER NOT NULL DEFAULT 0,
            vintage_risk_pct NUMERIC(5,1) DEFAULT 0,
            split_available BOOLEAN NOT NULL DEFAULT true,
            historical_lookback_start DATE,
            data_until DATE,
            coverage_status TEXT NOT NULL DEFAULT 'pending',
            source_confidence TEXT NOT NULL DEFAULT 'medium',
            definition_status TEXT NOT NULL DEFAULT 'provisional_pending_validation',
            runtime_source TEXT NOT NULL DEFAULT 'serving_fact',
            last_refreshed_at TIMESTAMPTZ DEFAULT now(),
            notes TEXT,
            PRIMARY KEY (month_start, country, city_norm, definition_set_id)
        );
    """)

    # 3. Refresh function
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_yego_historical_presence(concurrent boolean DEFAULT false)
        RETURNS void AS $$
        BEGIN
            IF concurrent THEN
                REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_yego_driver_historical_presence_v1;
            ELSE
                REFRESH MATERIALIZED VIEW ops.mv_yego_driver_historical_presence_v1;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_yego_historical_presence(boolean);")
    op.execute("DROP TABLE IF EXISTS ops.fct_yego_operational_flow_monthly_v2;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_yego_driver_historical_presence_v1;")
