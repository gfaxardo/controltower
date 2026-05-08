"""
Diagnóstico P1: migración 137, MVs, tiempos vista vs MV, uso de settings.

Uso (desde backend/):
  python -m scripts.diagnose_plan_vs_real_performance
  python -m scripts.diagnose_plan_vs_real_performance --month 2026-04 --country co
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.chdir(BACKEND_DIR)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="2026-04", help="YYYY-MM para filtros de prueba")
    parser.add_argument("--country", default="co", help="País de prueba o vacío para omitir")
    args = parser.parse_args()

    from app.db.connection import init_db_pool, get_db
    from app.settings import settings
    from app.services.plan_vs_real_service import (
        VIEW_REALKEY,
        MV_PLAN_VS_REAL_MONTHLY,
        get_plan_vs_real_monthly,
    )
    from psycopg2.extras import RealDictCursor

    init_db_pool()

    print("=== SETTINGS ===")
    print("USE_PLAN_VS_REAL_MONTHLY_MV:", getattr(settings, "USE_PLAN_VS_REAL_MONTHLY_MV", "MISSING"))
    print("DB:", settings.DB_NAME, "@", settings.DB_HOST)

    ym = args.month.strip()
    y, m = int(ym[0:4]), int(ym[5:7])
    from datetime import date as date_cls

    start = date_cls(y, m, 1)
    if m == 12:
        end = date_cls(y + 1, 1, 1)
    else:
        end = date_cls(y, m + 1, 1)

    where = "period_date >= %s::date AND period_date < %s::date"
    params: list = [start, end]
    if args.country:
        where += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params.append(args.country)

    q = f"""
        SELECT COUNT(*) AS n,
               COALESCE(SUM(trips_plan),0) AS sp,
               COALESCE(SUM(trips_real),0) AS sr,
               MAX(period_date) AS max_pd
        FROM {{rel}}
        WHERE {where}
    """

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 5"
        )
        rows = cur.fetchall()
        print("\n=== ALEMBIC (últimas filas en tabla) ===")
        for r in rows:
            print(" ", dict(r))

        for label, rel in (
            ("to_regclass MV legacy", MV_PLAN_VS_REAL_MONTHLY),
            ("to_regclass MV canon", "ops.mv_plan_vs_real_monthly_fact_canonical"),
        ):
            cur.execute("SELECT to_regclass(%s) AS c", (rel,))
            r = cur.fetchone()
            print(f"\n=== {label} ===", dict(r) if r else r)

        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'ops'
              AND tablename IN ('mv_plan_vs_real_monthly_fact', 'mv_plan_vs_real_monthly_fact_canonical')
            ORDER BY tablename, indexname
            """
        )
        idx = cur.fetchall()
        print("\n=== ÍNDICES MV (pg_indexes) ===")
        for r in idx:
            print(dict(r).get("indexname"), "|", (dict(r).get("indexdef") or "")[:120], "...")

        for rel in (VIEW_REALKEY, MV_PLAN_VS_REAL_MONTHLY):
            sql = q.format(rel=rel)
            t0 = time.perf_counter()
            cur.execute(sql, params)
            agg = dict(cur.fetchone() or {})
            dt = time.perf_counter() - t0
            print(f"\n=== AGG TIMING {rel} ===")
            print(f"  wall_s: {dt:.3f}")
            print(f"  {agg}")

        cur.execute(
            "SELECT COUNT(*) AS n, MAX(period_date) AS mx, MAX(updated_at) AS mu FROM ops.mv_plan_vs_real_monthly_fact"
        )
        snap = dict(cur.fetchone() or {})
        print("\n=== MV SNAPSHOT (sin filtro) ===", snap)

        cur.close()

    print("\n=== SERVICIO PYTHON get_plan_vs_real_monthly ===")
    t0 = time.perf_counter()
    data = get_plan_vs_real_monthly(
        country=args.country or None,
        month=ym,
        use_canonical=False,
    )
    dt = time.perf_counter() - t0
    print(f"  wall_s: {dt:.3f}")
    print(f"  rows: {len(data)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
