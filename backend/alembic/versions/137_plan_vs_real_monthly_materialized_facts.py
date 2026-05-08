"""
FASE 1.5B — Plan vs Real: MVs mensuales aditivas sobre las vistas realkey existentes.

- ops.mv_plan_vs_real_monthly_fact ← ops.v_plan_vs_real_realkey_final
- ops.mv_plan_vs_real_monthly_fact_canonical ← ops.v_plan_vs_real_realkey_canonical

Columnas extra: aliases documentales (projected_*, gap_*, month) y NULL donde la vista
realkey no expone métrica (plan_version, business_slice, drivers). Sin nueva semántica de negocio.

Refresh: ops.refresh_plan_vs_real_monthly_facts(use_concurrent boolean) y script
python -m scripts.refresh_plan_vs_real_monthly_mvs

down_revision: 136_restore_real_rollup_views_after_hourly_mv_rebuild
"""

from alembic import op

revision = "137_plan_vs_real_monthly_materialized_facts"
down_revision = "136_restore_real_rollup_views_after_hourly_mv_rebuild"
branch_labels = None
depends_on = None

# Fragmento común: v.* = columnas de la vista realkey final/canonical (mismo contrato).
_MV_EXTRA_COLS = """
  to_char(v.period_date, 'YYYY-MM') AS month,
  NULL::text AS plan_version,
  v.city AS city_norm,
  v.real_tipo_servicio AS lob_base,
  NULL::text AS segment,
  NULL::text AS business_slice,
  v.trips_plan AS projected_trips,
  NULL::numeric AS projected_drivers,
  NULL::numeric AS projected_ticket,
  v.revenue_plan AS projected_revenue,
  v.trips_real AS trips_real_completed,
  NULL::numeric AS active_drivers_real,
  NULL::numeric AS avg_ticket_real,
  (v.trips_plan - v.trips_real) AS gap_trips,
  (v.revenue_plan - v.revenue_real) AS gap_revenue,
  CASE
    WHEN v.trips_plan > 0 AND v.trips_plan IS NOT NULL THEN
      ((v.trips_plan - v.trips_real)::numeric / v.trips_plan * 100)
    ELSE NULL
  END AS gap_trips_pct,
  CASE
    WHEN v.revenue_plan > 0 AND v.revenue_plan IS NOT NULL THEN
      ((v.revenue_plan - v.revenue_real)::numeric / v.revenue_plan * 100)
    ELSE NULL
  END AS gap_revenue_pct,
  CASE
    WHEN v.trips_plan IS NOT NULL AND v.trips_real IS NOT NULL THEN 'matched'
    WHEN v.trips_plan IS NOT NULL AND v.trips_real IS NULL THEN 'plan_only'
    WHEN v.trips_plan IS NULL AND v.trips_real IS NOT NULL THEN 'real_only'
    ELSE 'unknown'
  END AS comparison_status,
  NULL::text AS join_status,
  clock_timestamp() AS updated_at
"""


def upgrade() -> None:
    op.execute("SET statement_timeout = 0")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_plan_vs_real_monthly_fact_canonical CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_plan_vs_real_monthly_fact CASCADE")
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_plan_vs_real_monthly_facts(boolean)")

    op.execute(
        f"""
        CREATE MATERIALIZED VIEW ops.mv_plan_vs_real_monthly_fact AS
        SELECT
          v.country,
          v.city,
          v.park_id,
          v.park_name,
          v.real_tipo_servicio,
          v.period_date,
          v.trips_plan,
          v.trips_real,
          v.revenue_plan,
          v.revenue_real,
          v.variance_trips,
          v.variance_revenue,
          {_MV_EXTRA_COLS}
        FROM ops.v_plan_vs_real_realkey_final v
        """
    )
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW ops.mv_plan_vs_real_monthly_fact_canonical AS
        SELECT
          v.country,
          v.city,
          v.park_id,
          v.park_name,
          v.real_tipo_servicio,
          v.period_date,
          v.trips_plan,
          v.trips_real,
          v.revenue_plan,
          v.revenue_real,
          v.variance_trips,
          v.variance_revenue,
          {_MV_EXTRA_COLS}
        FROM ops.v_plan_vs_real_realkey_canonical v
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_mv_plan_vs_real_monthly_fact_grain
        ON ops.mv_plan_vs_real_monthly_fact (
          COALESCE(country, ''),
          COALESCE(city, ''),
          COALESCE(park_id, ''),
          COALESCE(real_tipo_servicio, ''),
          period_date
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_mv_plan_vs_real_monthly_fact_canon_grain
        ON ops.mv_plan_vs_real_monthly_fact_canonical (
          COALESCE(country, ''),
          COALESCE(city, ''),
          COALESCE(park_id, ''),
          COALESCE(real_tipo_servicio, ''),
          period_date
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_pvr_mf_period ON ops.mv_plan_vs_real_monthly_fact (period_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_pvr_mf_country_period ON ops.mv_plan_vs_real_monthly_fact (country, period_date)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mv_pvr_mf_filter_ccsp
        ON ops.mv_plan_vs_real_monthly_fact (country, city, real_tipo_servicio, period_date)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_pvr_mfc_period ON ops.mv_plan_vs_real_monthly_fact_canonical (period_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mv_pvr_mfc_country_period ON ops.mv_plan_vs_real_monthly_fact_canonical (country, period_date)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_mv_pvr_mfc_filter_ccsp
        ON ops.mv_plan_vs_real_monthly_fact_canonical (country, city, real_tipo_servicio, period_date)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION ops.refresh_plan_vs_real_monthly_facts(p_concurrent boolean DEFAULT TRUE)
        RETURNS void
        LANGUAGE plpgsql
        AS $f$
        BEGIN
          IF p_concurrent THEN
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_plan_vs_real_monthly_fact;
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_plan_vs_real_monthly_fact_canonical;
          ELSE
            REFRESH MATERIALIZED VIEW ops.mv_plan_vs_real_monthly_fact;
            REFRESH MATERIALIZED VIEW ops.mv_plan_vs_real_monthly_fact_canonical;
          END IF;
        END;
        $f$
        """
    )

    op.execute(
        "COMMENT ON MATERIALIZED VIEW ops.mv_plan_vs_real_monthly_fact IS "
        "'FASE 1.5B snapshot de ops.v_plan_vs_real_realkey_final; refrescar tras pipeline/carga plan+trips.'"
    )
    op.execute(
        "COMMENT ON MATERIALIZED VIEW ops.mv_plan_vs_real_monthly_fact_canonical IS "
        "'FASE 1.5B snapshot de ops.v_plan_vs_real_realkey_canonical; refrescar tras pipeline/carga plan+trips.'"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_plan_vs_real_monthly_facts(boolean)")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_plan_vs_real_monthly_fact_canonical CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_plan_vs_real_monthly_fact CASCADE")
