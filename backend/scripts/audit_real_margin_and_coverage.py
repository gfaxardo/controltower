"""
FASE 1 — Auditoría REAL: margen, WoW, cobertura reciente, duplicidad, cancelaciones.
Responde con evidencia:
  1) ¿Semanas recientes tienen margen_total/margen_trip nulo o no poblado?
  2) ¿Problema en fuente hourly, intermedia, MV, backend o solo frontend?
  3) ¿WoW calculado sobre margen con signo invertido?
  4) ¿Registros duplicados por mismo grain?
  5) ¿Cancelaciones ausentes en fuente, agregación o solo visualización?

Uso: cd backend && python -m scripts.audit_real_margin_and_coverage [--days 30] [--weeks 8]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(days_recent: int = 30, weeks_recent: int = 8) -> bool:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    today = date.today()
    start_day = today - timedelta(days=days_recent)
    start_week = today - timedelta(weeks=weeks_recent)

    results = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ─── 1) Cobertura y margen nulo en semanas recientes (day_v2) ───
        cur.execute("""
            SELECT trip_date, country,
                   SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips,
                   SUM(margin_total) AS margin_total_raw,
                   COUNT(*) FILTER (WHERE margin_total IS NULL) AS rows_null_margin
            FROM ops.mv_real_lob_day_v2
            WHERE trip_date >= %s
            GROUP BY trip_date, country
            ORDER BY trip_date DESC, country
            LIMIT 50
        """, (start_day,))
        rows_day = cur.fetchall()
        results.append(("1. day_v2 reciente (muestra): completed, cancelled, margin_total", rows_day))

        # ─── 2) Cobertura y margen en week_v3 reciente ───
        cur.execute("""
            SELECT week_start, country,
                   SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips,
                   SUM(margin_total) AS margin_total_raw
            FROM ops.mv_real_lob_week_v3
            WHERE week_start >= %s
            GROUP BY week_start, country
            ORDER BY week_start DESC, country
            LIMIT 30
        """, (start_week,))
        rows_week = cur.fetchall()
        results.append(("2. week_v3 reciente: completed, cancelled, margin_total", rows_week))

        # ─── 3) real_drill_dim_fact: period_start reciente y margen nulo ───
        cur.execute("""
            SELECT period_grain, period_start, country,
                   SUM(trips) AS trips,
                   SUM(margin_total) AS margin_total_agg,
                   COUNT(*) FILTER (WHERE margin_total IS NULL) AS rows_null_margin
            FROM ops.real_drill_dim_fact
            WHERE period_grain = 'week' AND period_start >= %s
            GROUP BY period_grain, period_start, country
            ORDER BY period_start DESC, country
            LIMIT 30
        """, (start_week,))
        rows_drill_week = cur.fetchall()
        results.append(("3. real_drill_dim_fact (week) reciente: trips, margin_total_agg, rows_null_margin", rows_drill_week))

        cur.execute("""
            SELECT period_grain, period_start, country,
                   SUM(trips) AS trips,
                   SUM(margin_total) AS margin_total_agg
            FROM ops.real_drill_dim_fact
            WHERE period_grain = 'month' AND period_start >= %s
            GROUP BY period_grain, period_start, country
            ORDER BY period_start DESC, country
            LIMIT 20
        """, (start_day.replace(day=1),))
        rows_drill_month = cur.fetchall()
        results.append(("4. real_drill_dim_fact (month) reciente", rows_drill_month))

        # ─── 5) Signo de margen: cuántas filas con margin_total < 0 en drill ───
        cur.execute("""
            SELECT period_grain, COUNT(*) AS total_rows,
                   COUNT(*) FILTER (WHERE margin_total IS NOT NULL AND margin_total < 0) AS negative_margin_rows,
                   COUNT(*) FILTER (WHERE margin_total IS NOT NULL AND margin_total >= 0) AS non_negative_margin_rows
            FROM ops.real_drill_dim_fact
            WHERE period_start >= %s
            GROUP BY period_grain
        """, (start_week,))
        sign_rows = cur.fetchall()
        results.append(("5. Signo margen en real_drill_dim_fact (reciente): negativos vs no negativos", sign_rows))

        # ─── 6) Duplicidad por grain lógico (clave única) ───
        cur.execute("""
            SELECT country, period_grain, period_start, segment, breakdown,
                   dimension_key, dimension_id, city, COUNT(*) AS cnt
            FROM ops.real_drill_dim_fact
            WHERE period_start >= %s
            GROUP BY country, period_grain, period_start, segment, breakdown,
                     dimension_key, dimension_id, city
            HAVING COUNT(*) > 1
            LIMIT 20
        """, (start_week,))
        dups = cur.fetchall()
        results.append(("6. Duplicados por grain (deben ser 0)", dups))

        # ─── 7) Presencia de cancelaciones en day_v2 vs drill ───
        cur.execute("""
            SELECT trip_date, country,
                   SUM(completed_trips) AS completed,
                   SUM(cancelled_trips) AS cancelled,
                   ROUND(SUM(cancelled_trips)::numeric / NULLIF(SUM(requested_trips), 0), 4) AS cancellation_rate
            FROM ops.mv_real_lob_day_v2
            WHERE trip_date >= %s
            GROUP BY trip_date, country
            ORDER BY trip_date DESC
            LIMIT 15
        """, (start_day,))
        cancel_day = cur.fetchall()
        results.append(("7. Cancelaciones en day_v2 (reciente)", cancel_day))

        # real_drill_dim_fact: desde migración 103 tiene cancelled_trips
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
            AND column_name LIKE '%%cancel%%'
        """)
        drill_cancel_cols = cur.fetchall()
        results.append(("8. Columnas cancel* en real_drill_dim_fact (esperado: cancelled_trips)", drill_cancel_cols))

        # ─── 9) Último period_start en drill por grain ───
        cur.execute("""
            SELECT period_grain, MAX(period_start)::text AS last_period_start
            FROM ops.real_drill_dim_fact
            GROUP BY period_grain
        """)
        last_period = cur.fetchall()
        results.append(("9. Último period_start en real_drill_dim_fact por grain", last_period))

        # ─── 10) real_rollup_day_fact (vista): margen positivo y cobertura ───
        cur.execute("""
            SELECT trip_day, country, SUM(trips) AS trips,
                   SUM(margin_total_pos) AS margin_total_pos,
                   SUM(margin_total_raw) AS margin_total_raw
            FROM ops.real_rollup_day_fact
            WHERE trip_day >= %s
            GROUP BY trip_day, country
            ORDER BY trip_day DESC
            LIMIT 15
        """, (start_day,))
        rollup_recent = cur.fetchall()
        results.append(("10. real_rollup_day_fact reciente: trips, margin_total_pos, margin_total_raw", rollup_recent))

        cur.close()

    # ─── Imprimir resultados ───
    for title, data in results:
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)
        if not data:
            print("  (sin filas)")
        else:
            for r in data:
                print("  ", dict(r))

    return True


def main():
    ap = argparse.ArgumentParser(description="Auditoría REAL: margen, cobertura, signo, duplicidad, cancelaciones")
    ap.add_argument("--days", type=int, default=30, help="Días atrás para ventana día")
    ap.add_argument("--weeks", type=int, default=8, help="Semanas atrás para ventana semana")
    args = ap.parse_args()
    ok = run(days_recent=args.days, weeks_recent=args.weeks)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
