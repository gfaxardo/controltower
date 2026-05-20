"""
143 — Last Good Data: snapshot tables + serving views.
Fase 1E — Protege data cerrada con snapshots y serving views.

Crea:
  - ops.real_business_slice_month_snapshot (copia estructural de month_fact + metadata)
  - ops.v_real_business_slice_month_serving (elige snapshot vs working fact)
"""

from alembic import op

revision = "143_last_good_snapshots"
down_revision = "142_period_closure_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Snapshot table: copia estructura de month_fact + metadata
    op.execute("DROP TABLE IF EXISTS ops.real_business_slice_month_snapshot CASCADE")
    op.execute("""
        CREATE TABLE ops.real_business_slice_month_snapshot (
            LIKE ops.real_business_slice_month_fact INCLUDING DEFAULTS
        )
    """)
    # Add metadata columns
    for col_sql in [
        "ADD COLUMN snapshot_id BIGSERIAL",
        "ADD COLUMN snapshot_version TEXT NOT NULL DEFAULT '1'",
        "ADD COLUMN snapshot_status TEXT NOT NULL DEFAULT 'active'",
        "ADD COLUMN grain TEXT NOT NULL DEFAULT 'monthly'",
        "ADD COLUMN period_start DATE NOT NULL",
        "ADD COLUMN period_end DATE NOT NULL",
        "ADD COLUMN closure_registry_id BIGINT",
        "ADD COLUMN refresh_run_log_id BIGINT",
        "ADD COLUMN source_fact_checksum TEXT",
        "ADD COLUMN snapshot_checksum TEXT",
        "ADD COLUMN row_count BIGINT",
        "ADD COLUMN created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "ADD COLUMN created_by TEXT",
        "ADD COLUMN notes TEXT",
        "ADD CONSTRAINT chk_snapshot_status CHECK (snapshot_status IN ('active', 'superseded', 'invalid'))",
    ]:
        op.execute(f"ALTER TABLE ops.real_business_slice_month_snapshot {col_sql}")

    # Indices
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshot_month_period
        ON ops.real_business_slice_month_snapshot (period_start DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshot_month_status
        ON ops.real_business_slice_month_snapshot (snapshot_status)
    """)
    op.execute("""
        DROP INDEX IF EXISTS uq_snapshot_month_active
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_snapshot_month_active
        ON ops.real_business_slice_month_snapshot (period_start, COALESCE(country,''), COALESCE(city,''), COALESCE(business_slice_name,''), COALESCE(fleet_display_name,''))
        WHERE snapshot_status = 'active'
    """)

    op.execute("COMMENT ON TABLE ops.real_business_slice_month_snapshot IS 'Snapshot estable de month_fact para periodos locked. Fase 1E.'")

    # Serving view: snapshot if locked+active, else working fact
    op.execute("DROP VIEW IF EXISTS ops.v_real_business_slice_month_serving CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_business_slice_month_serving AS
        WITH snapshot_periods AS (
            SELECT DISTINCT period_start, period_end
            FROM ops.real_business_slice_month_snapshot
            WHERE snapshot_status = 'active'
        ),
        locked_periods AS (
            SELECT grain, period_start, period_end, status
            FROM ops.period_closure_registry
            WHERE status IN ('locked', 'closed')
        )
        SELECT
            f.month,
            f.country,
            f.city,
            f.business_slice_name,
            f.fleet_display_name,
            f.is_subfleet,
            f.subfleet_name,
            f.parent_fleet_name,
            f.trips_completed,
            f.trips_cancelled,
            f.active_drivers,
            f.connected_only_drivers,
            f.connected_only_drivers_status,
            f.avg_ticket,
            f.commission_pct,
            f.trips_per_driver,
            f.revenue_yego_net,
            f.precio_km,
            f.tiempo_km,
            f.completados_por_hora,
            f.cancelados_por_hora,
            f.refreshed_at,
            'working_fact'::text AS serving_source,
            'open'::text AS data_status,
            NULL::text AS snapshot_version,
            NULL::timestamptz AS snapshot_created_at,
            NULL::text AS period_lock_status,
            NULL::text AS warning_message
        FROM ops.real_business_slice_month_fact f
        WHERE NOT EXISTS (
            SELECT 1 FROM locked_periods l
            WHERE l.period_start = f.month
        )
        UNION ALL
        SELECT
            s.month,
            s.country,
            s.city,
            s.business_slice_name,
            s.fleet_display_name,
            s.is_subfleet,
            s.subfleet_name,
            s.parent_fleet_name,
            COALESCE(s.trips_completed, 0),
            COALESCE(s.trips_cancelled, 0),
            COALESCE(s.active_drivers, 0),
            s.connected_only_drivers,
            s.connected_only_drivers_status,
            s.avg_ticket,
            s.commission_pct,
            s.trips_per_driver,
            s.revenue_yego_net,
            s.precio_km,
            s.tiempo_km,
            s.completados_por_hora,
            s.cancelados_por_hora,
            s.refreshed_at,
            'snapshot'::text AS serving_source,
            'locked_snapshot'::text AS data_status,
            s.snapshot_version,
            s.created_at AS snapshot_created_at,
            l.status AS period_lock_status,
            NULL::text AS warning_message
        FROM ops.real_business_slice_month_snapshot s
        JOIN locked_periods l ON l.period_start = s.month
        WHERE s.snapshot_status = 'active'
    """)

    op.execute("COMMENT ON VIEW ops.v_real_business_slice_month_serving IS 'Serving view: snapshot para locked, working fact para open. Fase 1E.'")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_business_slice_month_serving CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.real_business_slice_month_snapshot CASCADE")
