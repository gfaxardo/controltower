"""
Recrear ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2.

La migración 064 hace DROP VIEW ops.v_real_trips_with_lob_v2 CASCADE, lo que elimina
estas MVs (dependen de la vista). 064 no las vuelve a crear. Esta migración las recrea
leyendo de la vista actual (definida en 090), para que el pipeline Real LOB v2 y el
script close_real_lob_governance funcionen.
"""
from alembic import op

revision = "094_recreate_real_lob_mvs_v2"
down_revision = "093_merge_real_lob_and_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Definición alineada con 047: misma estructura, fuente ops.v_real_trips_with_lob_v2
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
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

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
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


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")
