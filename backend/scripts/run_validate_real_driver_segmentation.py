"""
Ejecuta las validaciones de segmentación REAL (validate_real_driver_segmentation.sql).
Uso: cd backend && python -m scripts.run_validate_real_driver_segmentation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '60s'")

        # 1) Muestra activos
        print("--- 1) Muestra activos (is_active=true) ---")
        cur.execute("""
            SELECT driver_key, period_grain, period_start, country, segment_tag,
                   completed_cnt, cancelled_cnt, is_active, is_cancel_only, is_activity
            FROM ops.v_real_driver_segment_driver_period
            WHERE completed_cnt > 0
            LIMIT 5
        """)
        for r in cur.fetchall():
            print(dict(r))
        print()

        # 2) Muestra solo_cancelan
        print("--- 2) Muestra solo_cancelan (is_cancel_only=true) ---")
        cur.execute("""
            SELECT driver_key, period_grain, period_start, country, segment_tag,
                   completed_cnt, cancelled_cnt, is_active, is_cancel_only, is_activity
            FROM ops.v_real_driver_segment_driver_period
            WHERE completed_cnt = 0 AND cancelled_cnt > 0
            LIMIT 5
        """)
        rows = cur.fetchall()
        for r in rows:
            print(dict(r))
        if not rows:
            print("(ninguna fila: puede ser esperado si no hay conductores solo cancelan)")
        print()

        # 3) Conteo por periodo
        print("--- 3) Conteo por periodo (un mes) ---")
        cur.execute("""
            WITH one_period AS (
              SELECT period_grain, period_start, country
              FROM ops.v_real_driver_segment_driver_period
              WHERE period_grain = 'month'
              LIMIT 1
            )
            SELECT
              p.period_grain,
              p.period_start,
              p.country,
              COUNT(DISTINCT d.driver_key) FILTER (WHERE d.is_active) AS active_drivers,
              COUNT(DISTINCT d.driver_key) FILTER (WHERE d.is_cancel_only) AS cancel_only_drivers,
              COUNT(DISTINCT d.driver_key) FILTER (WHERE d.is_activity) AS activity_drivers
            FROM one_period p
            JOIN ops.v_real_driver_segment_driver_period d
              ON d.period_grain = p.period_grain AND d.period_start = p.period_start AND d.country = p.country
            GROUP BY p.period_grain, p.period_start, p.country
        """)
        r = cur.fetchone()
        print(dict(r) if r else "Sin datos")
        print()

        # 4) Reconciliación (muestra reciente)
        print("--- 4) Reconciliación tajadas (activos por país+periodo) ---")
        cur.execute("""
            SELECT period_grain, period_start, country,
                   SUM(active_drivers) AS sum_active_by_row
            FROM ops.v_real_driver_segment_agg a
            WHERE period_grain = 'month'
            GROUP BY period_grain, period_start, country
            ORDER BY period_start DESC, country
            LIMIT 6
        """)
        for r in cur.fetchall():
            print(dict(r))
        print("OK: validación ejecutada.")
        cur.close()

if __name__ == "__main__":
    main()
