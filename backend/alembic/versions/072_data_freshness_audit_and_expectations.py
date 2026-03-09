"""
Freshness & Coverage: tabla de expectativas por dataset y tabla de auditoría.
- ops.data_freshness_expectations: config por dataset (grain, expected_delay_days, source/derived objects, alert_threshold_days).
- ops.data_freshness_audit: resultados por ejecución (source_max_date, derived_max_date, expected_latest_date, lag_days, status, alert_reason, checked_at).
Los scripts de monitoreo insertan filas en data_freshness_audit; la API lee la última ejecución.
"""
from alembic import op

revision = "072_data_freshness_audit"
down_revision = "071_real_service_type_unmapped_monitor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) Config: expectativas por dataset ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.data_freshness_expectations (
            id serial PRIMARY KEY,
            dataset_name text NOT NULL UNIQUE,
            grain text NOT NULL,
            expected_delay_days int NOT NULL DEFAULT 1,
            source_object text,
            source_date_column text,
            derived_object text,
            derived_date_column text,
            active boolean NOT NULL DEFAULT true,
            owner text,
            alert_threshold_days int,
            created_at timestamptz DEFAULT now(),
            updated_at timestamptz DEFAULT now()
        )
    """)
    op.execute("COMMENT ON TABLE ops.data_freshness_expectations IS 'Configuración de expectativas de freshness por dataset (grain, delay, objetos fuente/derivado, umbral de alerta)'")

    # --- 2) Auditoría: una fila por dataset por ejecución ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.data_freshness_audit (
            id serial PRIMARY KEY,
            dataset_name text NOT NULL,
            source_object text,
            derived_object text,
            grain text NOT NULL,
            source_max_date date,
            derived_max_date date,
            expected_latest_date date,
            lag_days int,
            missing_expected_days int,
            status text NOT NULL,
            alert_reason text,
            checked_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_data_freshness_audit_dataset_checked ON ops.data_freshness_audit (dataset_name, checked_at DESC)")
    op.execute("COMMENT ON TABLE ops.data_freshness_audit IS 'Resultados de cada ejecución del chequeo de freshness; status: OK, PARTIAL_EXPECTED, LAGGING, MISSING_EXPECTED_DATA'")

    # --- 3) Semilla de expectativas (datasets conocidos) ---
    op.execute("""
        INSERT INTO ops.data_freshness_expectations
        (dataset_name, grain, expected_delay_days, source_object, source_date_column, derived_object, derived_date_column, active, owner, alert_threshold_days)
        VALUES
        ('trips_base', 'day', 1, 'public.trips_all', 'fecha_inicio_viaje', NULL, NULL, true, 'ops', 2),
        ('trips_2026', 'day', 1, 'public.trips_2026', 'fecha_inicio_viaje', NULL, NULL, true, 'ops', 2),
        ('real_lob', 'day', 1, 'ops.v_trips_real_canon', 'fecha_inicio_viaje', 'ops.real_rollup_day_fact', 'trip_day', true, 'ops', 3),
        ('real_lob_drill', 'week', 7, 'ops.v_trips_real_canon', 'fecha_inicio_viaje', 'ops.real_drill_dim_fact', 'period_start', true, 'ops', 7),
        ('driver_lifecycle', 'day', 1, 'ops.v_driver_lifecycle_trips_completed', 'completion_ts', 'ops.mv_driver_lifecycle_base', 'last_completed_ts', true, 'ops', 3),
        ('driver_lifecycle_weekly', 'week', 7, 'ops.mv_driver_lifecycle_base', 'last_completed_ts', 'ops.mv_driver_weekly_stats', 'week_start', true, 'ops', 7),
        ('supply_weekly', 'week', 7, 'ops.mv_driver_weekly_stats', 'week_start', 'ops.mv_supply_segments_weekly', 'week_start', true, 'ops', 7)
        ON CONFLICT (dataset_name) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops.data_freshness_audit CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.data_freshness_expectations CASCADE")
