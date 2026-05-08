"""
Snapshot reproducible para investigación lag/freshness (E2E).
No modifica datos. Salida stdout para auditoría.

Uso: cd backend && python -m scripts.diagnose_data_lag_snapshot
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor


def _q(conn, sql: str, params=None):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or [])
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def main() -> None:
    init_db_pool()
    with get_db() as conn:
        print("=== TZ / NOW (sesión DB) ===")
        for r in _q(conn, "SHOW timezone"):
            print(r)
        for r in _q(conn, "SELECT NOW() AS now_ts, CURRENT_DATE AS cur_date"):
            print(r)

        def run_block(name: str, sql: str):
            try:
                rows = _q(conn, sql)
                print(f"=== {name} ===")
                for r in rows:
                    print(r)
            except Exception as e:
                print(f"=== {name} ERROR === {e}")

        run_block(
            "trips_all (max + count últimos 7d civil, ventana índice 200d)",
            """
            SELECT MAX(fecha_inicio_viaje)::date AS max_fecha,
                   COUNT(*) FILTER (
                     WHERE fecha_inicio_viaje::date >= (CURRENT_DATE - INTERVAL '7 days')::date
                       AND fecha_inicio_viaje::date <= CURRENT_DATE
                   ) AS rows_last_7d
            FROM public.trips_all
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '200 days'
            """,
        )
        run_block(
            "trips_2026 (max + count últimos 7d)",
            """
            SELECT MAX(fecha_inicio_viaje)::date AS max_fecha,
                   COUNT(*) FILTER (
                     WHERE fecha_inicio_viaje::date >= (CURRENT_DATE - INTERVAL '7 days')::date
                       AND fecha_inicio_viaje::date <= CURRENT_DATE
                   ) AS rows_last_7d
            FROM public.trips_2026
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '200 days'
            """,
        )
        run_block(
            "trips_2025 si existe",
            """
            SELECT MAX(fecha_inicio_viaje)::date AS max_fecha,
                   COUNT(*) FILTER (
                     WHERE fecha_inicio_viaje::date >= (CURRENT_DATE - INTERVAL '7 days')::date
                   ) AS rows_last_7d
            FROM public.trips_2025
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '200 days'
            """,
        )

        run_block(
            "ops.v_trips_real_canon_120d MAX(fecha_inicio_viaje)",
            """
            SELECT MAX(fecha_inicio_viaje)::date AS mx
            FROM ops.v_trips_real_canon_120d
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '200 days'
            """,
        )
        run_block(
            "ops.mv_real_lob_day_v2 MAX(trip_date)",
            """
            SELECT MAX(trip_date)::date AS mx
            FROM ops.mv_real_lob_day_v2
            WHERE trip_date >= CURRENT_DATE - INTERVAL '200 days'
            """,
        )
        run_block(
            "ops.mv_real_trips_monthly MAX(month) (legacy)",
            """
            SELECT MAX(month)::date AS mx FROM ops.mv_real_trips_monthly
            WHERE month >= CURRENT_DATE - INTERVAL '500 days'
            """,
        )

        run_block(
            "ops.data_freshness_audit última fila por dataset (operational + trips)",
            """
            SELECT DISTINCT ON (dataset_name)
              dataset_name, source_max_date, derived_max_date, status,
              checked_at, LEFT(COALESCE(alert_reason,''), 120) AS alert_reason
            FROM ops.data_freshness_audit
            WHERE dataset_name IN (
              'real_operational', 'real_lob', 'real_lob_drill',
              'trips_base', 'trips_2026', 'driver_lifecycle', 'supply_weekly'
            )
            ORDER BY dataset_name, checked_at DESC
            """,
        )

        run_block("pg_cron instalado", "SELECT extname FROM pg_extension WHERE extname = 'pg_cron'")

        # Lag explícito vs CURRENT_DATE en DB
        for r in _q(
            conn,
            """
            WITH s AS (
              SELECT MAX(fecha_inicio_viaje)::date AS mx FROM public.trips_all
              WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '200 days'
            ),
            d AS (
              SELECT MAX(trip_date)::date AS mx FROM ops.mv_real_lob_day_v2
              WHERE trip_date >= CURRENT_DATE - INTERVAL '200 days'
            )
            SELECT CURRENT_DATE AS db_current_date,
                   s.mx AS source_trips_all_max,
                   d.mx AS derived_day_v2_max,
                   (CURRENT_DATE - s.mx) AS lag_days_source_vs_db_today,
                   (CURRENT_DATE - d.mx) AS lag_days_derived_vs_db_today,
                   (s.mx - d.mx) AS source_minus_derived_days
            FROM s, d
            """,
        ):
            print("=== Resumen lag (días vs CURRENT_DATE en PostgreSQL) ===")
            print(r)

        run_block(
            "v_real_trip_fact_v2: filas con fecha > 2026-03-14",
            """
            SELECT COUNT(*) AS n_after_march14
            FROM ops.v_real_trip_fact_v2
            WHERE fecha_inicio_viaje::date > DATE '2026-03-14'
            """,
        )
        run_block(
            "Definición almacenada ops.mv_real_lob_hour_v2 (primeros 600 chars)",
            """
            SELECT LEFT(definition, 600) AS def_snip
            FROM pg_matviews
            WHERE schemaname = 'ops' AND matviewname = 'mv_real_lob_hour_v2'
            """,
        )

    today_py = date.today()
    print(f"=== date.today() en host Python === {today_py} (comparar con cur_date arriba si TZ difiere)")


if __name__ == "__main__":
    main()
