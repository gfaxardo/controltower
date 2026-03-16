"""
DEBUG: Drill mensual LOB — trazabilidad cancelaciones.
Ejecuta queries A–E y muestra payload del endpoint.
Uso: cd backend && python -m scripts.debug_drill_monthly_cancellations
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


def main():
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    months = ["2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01"]

    print("=" * 60)
    print("FASE 1–2 — EVIDENCIA POR CAPA (MESES Nov 2025 – Mar 2026)")
    print("=" * 60)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # A. FUENTE RAÍZ (trips_all + trips_2026, condicion)
        print("\n--- A. FUENTE RAÍZ (por mes, por país desde condicion) ---")
        try:
            cur.execute("""
                WITH m AS (
                    SELECT unnest(ARRAY['2025-11-01','2025-12-01','2026-01-01','2026-02-01','2026-03-01']::date[]) AS month_start
                ),
                all_trips AS (
                    SELECT
                        CASE WHEN t.park_id::text ILIKE '%%lima%%' OR t.park_id::text ILIKE '%%pe%%' THEN 'pe'
                             WHEN t.park_id::text ILIKE '%%co%%' OR t.park_id::text ILIKE '%%bogot%%' OR t.park_id::text ILIKE '%%cali%%' THEN 'co'
                             ELSE NULL END AS country,
                        date_trunc('month', t.fecha_inicio_viaje)::date AS month_start,
                        COUNT(*) FILTER (WHERE t.condicion = 'Completado') AS completed_trips,
                        COUNT(*) FILTER (WHERE t.condicion = 'Cancelado' OR t.condicion ILIKE '%%cancel%%') AS cancelled_trips
                    FROM public.trips_all t
                    WHERE t.fecha_inicio_viaje >= '2025-11-01' AND t.fecha_inicio_viaje < '2026-04-01'
                    GROUP BY 1, 2
                ),
                t2026 AS (
                    SELECT
                        CASE WHEN t.park_id::text ILIKE '%%lima%%' OR t.park_id::text ILIKE '%%pe%%' THEN 'pe'
                             WHEN t.park_id::text ILIKE '%%co%%' OR t.park_id::text ILIKE '%%bogot%%' OR t.park_id::text ILIKE '%%cali%%' THEN 'co'
                             ELSE NULL END AS country,
                        date_trunc('month', t.fecha_inicio_viaje)::date AS month_start,
                        COUNT(*) FILTER (WHERE t.condicion = 'Completado') AS completed_trips,
                        COUNT(*) FILTER (WHERE t.condicion = 'Cancelado' OR t.condicion ILIKE '%%cancel%%') AS cancelled_trips
                    FROM public.trips_2026 t
                    WHERE t.fecha_inicio_viaje >= '2026-01-01' AND t.fecha_inicio_viaje < '2026-04-01'
                    GROUP BY 1, 2
                ),
                combined AS (
                    SELECT country, month_start, SUM(completed_trips) AS completed_trips, SUM(cancelled_trips) AS cancelled_trips
                    FROM (SELECT * FROM all_trips UNION ALL SELECT * FROM t2026) u
                    WHERE country IS NOT NULL
                    GROUP BY country, month_start
                )
                SELECT country, month_start::text, completed_trips, cancelled_trips
                FROM combined
                ORDER BY country, month_start
                LIMIT 20
            """)
            rows = cur.fetchall()
            for r in rows:
                print(f"  {r['country']} {r['month_start']} completed={r['completed_trips']} cancelled={r['cancelled_trips']}")
            if not rows:
                print("  (sin filas o sin país inferible desde park_id)")
        except Exception as e:
            print(f"  ERROR: {e}")

        # B. MONTH_V3
        print("\n--- B. MONTH_V3 (ops.mv_real_lob_month_v3) ---")
        try:
            cur.execute("""
                SELECT month_start::text, country,
                       SUM(completed_trips) AS completed_trips,
                       SUM(cancelled_trips) AS cancelled_trips
                FROM ops.mv_real_lob_month_v3
                WHERE month_start >= '2025-11-01' AND month_start < '2026-04-01'
                GROUP BY month_start, country
                ORDER BY country, month_start
                LIMIT 20
            """)
            rows = cur.fetchall()
            for r in rows:
                print(f"  {r['country']} {r['month_start']} completed={r['completed_trips']} cancelled={r['cancelled_trips']}")
            if not rows:
                print("  (sin filas)")
        except Exception as e:
            print(f"  ERROR: {e}")

        # C. REAL_DRILL_DIM_FACT period_grain=month, breakdown=lob
        print("\n--- C. REAL_DRILL_DIM_FACT (period_grain=month, breakdown=lob) ---")
        try:
            cur.execute("""
                SELECT period_start::text, country,
                       SUM(trips) AS completed_trips,
                       SUM(cancelled_trips) AS cancelled_trips
                FROM ops.real_drill_dim_fact
                WHERE period_grain = 'month' AND breakdown = 'lob'
                  AND period_start >= '2025-11-01' AND period_start < '2026-04-01'
                GROUP BY period_start, country
                ORDER BY country, period_start
                LIMIT 20
            """)
            rows = cur.fetchall()
            for r in rows:
                print(f"  {r['country']} {r['period_start']} completed={r['completed_trips']} cancelled={r['cancelled_trips']}")
            if not rows:
                print("  (sin filas — el populate NO llena month)")
        except Exception as e:
            print(f"  ERROR: {e}")

        # D. MV_REAL_DRILL_DIM_AGG (misma query que C)
        print("\n--- D. MV_REAL_DRILL_DIM_AGG (period_grain=month, breakdown=lob) ---")
        try:
            cur.execute("""
                SELECT period_start::text, country,
                       SUM(trips) AS completed_trips,
                       SUM(cancelled_trips) AS cancelled_trips
                FROM ops.mv_real_drill_dim_agg
                WHERE period_grain = 'month' AND breakdown = 'lob'
                  AND period_start >= '2025-11-01' AND period_start < '2026-04-01'
                GROUP BY period_start, country
                ORDER BY country, period_start
                LIMIT 20
            """)
            rows = cur.fetchall()
            for r in rows:
                print(f"  {r['country']} {r['period_start']} completed={r['completed_trips']} cancelled={r['cancelled_trips']}")
            if not rows:
                print("  (sin filas)")
        except Exception as e:
            print(f"  ERROR: {e}")

        # ¿Existen filas month en real_drill_dim_fact?
        cur.execute("""
            SELECT period_grain, COUNT(*) AS cnt, MIN(period_start)::text AS min_ps, MAX(period_start)::text AS max_ps
            FROM ops.real_drill_dim_fact
            GROUP BY period_grain
        """)
        print("\n--- Granos en real_drill_dim_fact ---")
        for r in cur.fetchall():
            print(f"  {r['period_grain']}: {r['cnt']} filas, {r['min_ps']} .. {r['max_ps']}")

        cur.close()

    # E. ENDPOINT
    print("\n--- E. ENDPOINT GET /ops/real-lob/drill?period=month&desglose=LOB ---")
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:8000/ops/real-lob/drill?period=month&desglose=LOB&segmento=all",
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        for c in data.get("countries") or []:
            country = c.get("country", "")
            kpis = c.get("kpis") or {}
            rows = c.get("rows") or []
            print(f"  {country} KPIs: cancelaciones={kpis.get('cancelaciones')} viajes={kpis.get('viajes')}")
            for row in (rows[:2] if isinstance(rows, list) else []):
                print(f"    row period={row.get('period_start')} cancelaciones={row.get('cancelaciones')} viajes={row.get('viajes')}")
    except Exception as e:
        print(f"  ERROR (¿backend levantado?): {e}")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
