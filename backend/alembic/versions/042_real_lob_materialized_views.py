"""
Real LOB: Materialized Views para respuestas < 2s.
Crea ops.mv_real_trips_by_lob_month y ops.mv_real_trips_by_lob_week desde las vistas
existentes (misma definición lógica). Índices UNIQUE para REFRESH CONCURRENTLY.
No modifica Plan vs Real (ops.v_plan_vs_real_realkey_final).
"""
from alembic import op

revision = "042_real_lob_materialized_views"
down_revision = "041_real_lob_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) MV mensual (WITH NO DATA para evitar timeout en migración; poblar con scripts/refresh_real_lob_mvs.py)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_by_lob_month AS
        SELECT
            country,
            city,
            lob_name,
            period_date AS month_start,
            SUM(trips) AS trips,
            COALESCE(SUM(revenue), 0) AS revenue
        FROM ops.v_real_universe_with_lob
        GROUP BY country, city, lob_name, period_date
        WITH NO DATA
    """)
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_real_trips_by_lob_month IS 'Real LOB observability: viajes REAL por LOB por mes. Refrescar con refresh_real_lob_mvs.py.'")
    # UNIQUE para REFRESH MATERIALIZED VIEW CONCURRENTLY
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_lob_month_cclm
        ON ops.mv_real_trips_by_lob_month (country, city, lob_name, month_start)
    """)
    op.execute("""
        CREATE INDEX idx_mv_real_lob_month_ccm
        ON ops.mv_real_trips_by_lob_month (country, city, month_start)
    """)

    # 2) MV semanal (WITH NO DATA; poblar con scripts/refresh_real_lob_mvs.py)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_by_lob_week AS
        SELECT
            country,
            city,
            lob_name,
            week_start AS week_start,
            SUM(trips) AS trips,
            COALESCE(SUM(revenue), 0) AS revenue
        FROM ops.v_real_universe_with_lob_week
        GROUP BY country, city, lob_name, week_start
        WITH NO DATA
    """)
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_real_trips_by_lob_week IS 'Real LOB observability: viajes REAL por LOB por semana. Refrescar con refresh_real_lob_mvs.py.'")
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_lob_week_ccwl
        ON ops.mv_real_trips_by_lob_week (country, city, lob_name, week_start)
    """)
    op.execute("""
        CREATE INDEX idx_mv_real_lob_week_ccw
        ON ops.mv_real_trips_by_lob_week (country, city, week_start)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_by_lob_week")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_by_lob_month")
