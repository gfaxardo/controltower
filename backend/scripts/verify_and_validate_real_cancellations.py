"""
Verificación y validación de cancelaciones REAL tras corrección estructural.
- Comprueba que cancelled_trips existe en real_drill_dim_fact y mv_real_drill_dim_agg.
- Opcional: ejecuta populate y query de reconciliación.

Uso: cd backend && python -m scripts.verify_and_validate_real_cancellations [--populate] [--reconcile]
"""
from __future__ import annotations

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)


def main():
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    ap = argparse.ArgumentParser(description="Verificar y validar cancelaciones REAL")
    ap.add_argument("--populate", action="store_true", help="Ejecutar populate_real_drill_from_hourly_chain")
    ap.add_argument("--reconcile", action="store_true", help="Ejecutar query de reconciliación (último mes)")
    args = ap.parse_args()

    init_db_pool()
    print("=== Verificación cancelaciones REAL ===\n")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # 1) Columna cancelled_trips en real_drill_dim_fact
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
            ORDER BY ordinal_position
        """)
        cols_fact = [r["column_name"] for r in cur.fetchall()]
        has_cancelled_fact = "cancelled_trips" in cols_fact
        print(f"1. ops.real_drill_dim_fact: cancelled_trips = {has_cancelled_fact} (columnas: {len(cols_fact)})")

        # 2) Columna en mv_real_drill_dim_agg
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'ops' AND table_name = 'mv_real_drill_dim_agg' AND column_name = 'cancelled_trips'
            ) AS ok
        """)
        has_cancelled_mv = cur.fetchone()["ok"]
        print(f"2. ops.mv_real_drill_dim_agg: cancelled_trips = {has_cancelled_mv}")

        # 3) Muestra reciente con cancelled_trips (si existe)
        if has_cancelled_fact:
            cur.execute("""
                SELECT period_grain, period_start, breakdown,
                       COUNT(*) AS rows_count,
                       SUM(trips) AS total_trips,
                       SUM(cancelled_trips) AS total_cancelled
                FROM ops.real_drill_dim_fact
                WHERE period_start >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY period_grain, period_start, breakdown
                ORDER BY period_start DESC, breakdown
                LIMIT 10
            """)
            rows = cur.fetchall()
            print(f"3. Muestra real_drill_dim_fact (últimos 30d): {len(rows)} grupos")
            for r in rows[:3]:
                print(f"   {r['period_grain']} {r['period_start']} breakdown={r['breakdown']} trips={r['total_trips']} cancelled={r['total_cancelled']}")
        else:
            print("3. (omitido: no hay cancelled_trips en real_drill_dim_fact)")

        # 4) Reconciliación (si se pide) — usar week (populate rellena day y week, no month)
        if args.reconcile and has_cancelled_fact:
            print("\n--- Reconciliación (última semana cerrada) ---")
            cur.execute("""
                WITH params AS (
                    SELECT (DATE_TRUNC('week', CURRENT_DATE - INTERVAL '1 week'))::date AS period_start
                ),
                drill_agg AS (
                    SELECT SUM(d.trips) AS completed, SUM(d.cancelled_trips) AS cancelled
                    FROM ops.real_drill_dim_fact d
                    CROSS JOIN params p
                    WHERE d.period_grain = 'week' AND d.period_start = p.period_start AND d.breakdown = 'lob'
                )
                SELECT (SELECT period_start FROM params) AS period_start,
                       (SELECT completed FROM drill_agg) AS drill_completed,
                       (SELECT cancelled FROM drill_agg) AS drill_cancelled
            """)
            rec = cur.fetchone()
            if rec:
                print(f"   Period (week): {rec['period_start']} | Drill (LOB) completed: {rec['drill_completed']} | cancelled: {rec['drill_cancelled']}")

        cur.close()

    if args.populate:
        print("\n--- Ejecutando populate_real_drill_from_hourly_chain ---")
        from scripts.populate_real_drill_from_hourly_chain import run as run_populate
        ok = run_populate(days=120, weeks=18, timeout_sec=3600)
        print(f"   Populate: {'OK' if ok else 'FAIL'}")

    print("\n=== Fin verificación ===")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
