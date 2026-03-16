"""
Auditoría de coherencia del módulo REAL (FASE 5 + 6).
- Reconciliación: para el mismo (country, period_grain, period_start, segment), total por LOB = total por park = total por tipo_servicio.
- Semanal vs mensual: mismos periodos deben ser reconciliables desde la misma base.
- Parks: parks en real_drill_dim_fact (drill) vs parks en MVs (filters); duplicidad de etiquetas; parks sin data en ventana reciente.

Uso: cd backend && python -m scripts.audit_real_coherence [--weeks 4] [--months 3]
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


def run(weeks_recent: int = 4, months_recent: int = 3) -> bool:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    today = date.today()
    start_week = today - timedelta(weeks=weeks_recent)
    start_month = today - timedelta(days=months_recent * 31)

    results = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ─── 1) Reconciliación: por (country, period_grain, period_start, segment) total LOB vs park vs service_type ───
        cur.execute("""
            WITH by_lob AS (
                SELECT country, period_grain, period_start, segment, SUM(trips) AS total
                FROM ops.real_drill_dim_fact WHERE breakdown = 'lob' GROUP BY 1,2,3,4
            ),
            by_park AS (
                SELECT country, period_grain, period_start, segment, SUM(trips) AS total
                FROM ops.real_drill_dim_fact WHERE breakdown = 'park' GROUP BY 1,2,3,4
            ),
            by_svc AS (
                SELECT country, period_grain, period_start, segment, SUM(trips) AS total
                FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type' GROUP BY 1,2,3,4
            ),
            joined AS (
                SELECT
                    COALESCE(l.country, p.country, s.country) AS country,
                    COALESCE(l.period_grain, p.period_grain, s.period_grain) AS period_grain,
                    COALESCE(l.period_start, p.period_start, s.period_start) AS period_start,
                    COALESCE(l.segment, p.segment, s.segment) AS segment,
                    l.total AS total_lob,
                    p.total AS total_park,
                    s.total AS total_service_type,
                    (l.total - p.total) AS diff_lob_park,
                    (l.total - s.total) AS diff_lob_svc,
                    (p.total - s.total) AS diff_park_svc
                FROM by_lob l
                FULL OUTER JOIN by_park p ON l.country = p.country AND l.period_grain = p.period_grain AND l.period_start = p.period_start AND l.segment IS NOT DISTINCT FROM p.segment
                FULL OUTER JOIN by_svc s ON COALESCE(l.country, p.country) = s.country AND COALESCE(l.period_grain, p.period_grain) = s.period_grain AND COALESCE(l.period_start, p.period_start) = s.period_start AND COALESCE(l.segment, p.segment) IS NOT DISTINCT FROM s.segment
            )
            SELECT * FROM joined
            WHERE (period_start >= %s::date OR (period_grain = 'month' AND period_start >= %s::date))
              AND (total_lob IS DISTINCT FROM total_park OR total_lob IS DISTINCT FROM total_service_type OR total_park IS DISTINCT FROM total_service_type)
            LIMIT 50
        """, (start_week, start_month))
        rec = cur.fetchall()
        results.append(("1. Reconciliación: discrepancias LOB vs park vs service_type (mismo grain)", [dict(r) for r in rec]))

        # ─── 2) Totales por grain (sin desglose) para comparar week vs month en mismo país ───
        cur.execute("""
            SELECT country, period_grain, period_start, SUM(trips) AS total_trips
            FROM ops.real_drill_dim_fact
            WHERE period_start >= %s
            GROUP BY country, period_grain, period_start
            ORDER BY country, period_grain, period_start DESC
            LIMIT 30
        """, (start_week,))
        results.append(("2. Totales por country/period_grain/period_start (muestra reciente)", [dict(r) for r in cur.fetchall()]))

        # ─── 3) Parks en drill (real_drill_dim_fact) vs parks en MVs (month_v2) ───
        cur.execute("""
            SELECT DISTINCT dimension_id AS park_id, dimension_key AS park_name, city, country
            FROM ops.real_drill_dim_fact
            WHERE breakdown = 'park' AND dimension_id IS NOT NULL AND TRIM(COALESCE(dimension_id,'')) <> ''
            ORDER BY country, city, dimension_key
            LIMIT 200
        """)
        drill_parks = {tuple((r["park_id"], r["country"], r["city"], r["park_name"])) for r in cur.fetchall()}
        cur.execute("""
            SELECT DISTINCT park_id, park_name, city, country
            FROM ops.mv_real_lob_month_v2
            WHERE park_id IS NOT NULL AND country IS NOT NULL
            LIMIT 200
        """)
        try:
            mv_parks = {tuple((r["park_id"], r["country"], r["city"], (r["park_name"] or ""))) for r in cur.fetchall()}
        except Exception:
            mv_parks = set()
        in_drill_not_mv = drill_parks - mv_parks if mv_parks else drill_parks
        in_mv_not_drill = mv_parks - drill_parks if drill_parks else mv_parks
        results.append(("3a. Parks solo en drill (real_drill_dim_fact), no en mv_real_lob_month_v2", list(in_drill_not_mv)[:30]))
        results.append(("3b. Parks solo en MV month_v2, no en drill", list(in_mv_not_drill)[:30]))

        # ─── 4) Duplicidad de etiqueta (mismo park_name + city + country para distinto park_id) ───
        cur.execute("""
            SELECT dimension_key, city, country, COUNT(DISTINCT dimension_id) AS cnt_ids,
                   array_agg(DISTINCT dimension_id) AS park_ids
            FROM ops.real_drill_dim_fact
            WHERE breakdown = 'park' AND dimension_id IS NOT NULL
            GROUP BY dimension_key, city, country
            HAVING COUNT(DISTINCT dimension_id) > 1
            LIMIT 20
        """)
        results.append(("4. Etiquetas duplicadas (mismo nombre+ciudad+país, distinto park_id)", [dict(r) for r in cur.fetchall()]))

        cur.close()

    for title, data in results:
        print("\n" + "=" * 60)
        print(title)
        print("=" * 60)
        if not data:
            print("  (ninguna / vacío)")
        else:
            for r in data:
                print("  ", r)
    return True


def main():
    ap = argparse.ArgumentParser(description="Auditoría de coherencia REAL: reconciliación LOB/park/service_type, parks drill vs MVs, duplicados")
    ap.add_argument("--weeks", type=int, default=4, help="Semanas atrás para ventana week")
    ap.add_argument("--months", type=int, default=3, help="Meses atrás para ventana month")
    args = ap.parse_args()
    ok = run(weeks_recent=args.weeks, months_recent=args.months)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
