#!/usr/bin/env python3
"""
FASE A — Asegura que las MVs month_v2 y week_v2 tengan la definición 098
(base FROM ops.v_real_trips_with_lob_v2_120d). Solo recrea las MVs; no toca vistas ni índices.
Tras ejecutar, las MVs quedan vacías (WITH NO DATA); usar bootstrap para poblarlas.
Uso: cd backend && python scripts/ensure_098_mvs_definition.py
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass


def main():
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        conn.autocommit = True
        cur = conn.cursor()

        cur.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")

        cur.execute("""
            CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
            WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2_120d),
            global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
            agg AS (
                SELECT
                    country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
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
                a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
                a.month_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
                (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
            FROM agg a
            CROSS JOIN global_max g
            WITH NO DATA
        """)
        cur.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")

        cur.execute("""
            CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
            WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2_120d),
            global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
            agg AS (
                SELECT
                    country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
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
                a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
                a.week_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
                (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
            FROM agg a
            CROSS JOIN global_max g
            WITH NO DATA
        """)
        cur.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")

    print("MVs recreadas con definición 098 (base FROM v_real_trips_with_lob_v2_120d). Ejecutar bootstrap para poblarlas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
