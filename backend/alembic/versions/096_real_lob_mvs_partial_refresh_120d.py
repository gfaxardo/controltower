"""
CT-MV-PERFORMANCE-HARDENING: ventana de cálculo 120 días para MVs críticas.

Recrea ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2 limitando la base
a fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days' para reducir
tiempo de refresh (refresh 4h → ~5 min típico). Histórico fuera de ventana
no se recalcula.
"""
from alembic import op

revision = "096_real_lob_mvs_partial_120d"
down_revision = "095_mv_performance_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
        ),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                lob_group,
                real_tipo_servicio_norm,
                segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        )
        SELECT
            a.country,
            a.city,
            a.park_id,
            a.park_name,
            a.lob_group,
            a.real_tipo_servicio_norm,
            a.segment_tag,
            a.month_start,
            a.trips,
            a.revenue,
            a.margin_total,
            a.distance_total_km,
            a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
        FROM agg a
        CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
        ),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                lob_group,
                real_tipo_servicio_norm,
                segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*) AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        )
        SELECT
            a.country,
            a.city,
            a.park_id,
            a.park_name,
            a.lob_group,
            a.real_tipo_servicio_norm,
            a.segment_tag,
            a.week_start,
            a.trips,
            a.revenue,
            a.margin_total,
            a.distance_total_km,
            a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
        FROM agg a
        CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")


def downgrade() -> None:
    # Restaurar definición sin ventana 120d (igual que 094/095)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue, SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km, MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        )
        SELECT a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag, a.month_start,
            a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
        FROM agg a CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue, SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km, MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        )
        SELECT a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag, a.week_start,
            a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
        FROM agg a CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")
