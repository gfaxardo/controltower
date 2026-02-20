"""
[YEGO CT] E2E PASO A.5 — Aplicar fix de park_name en vista final (PLAN_ONLY con park_name desde parks).

1) Pre-checks: COUNT plan raw, plan_month, real_month.
2) Aplica migración 040: alembic upgrade head.
3) Post-checks: park_name null rate, top 20 filas plan_month con park_name/trips_plan,
   matched_pct (si real_month < plan_month => OK sin exigir; si real_month >= plan_month => >= 30%).
4) Exit 0 si park_name null rate <= 1% (plan_month) o <= 5% global y no hay filas plan_month con park_name NULL.
   Exit 1 si park_name sigue NULL para filas del plan_month.

Uso: cd backend && python scripts/pasoA5_fix_park_name_in_final_view.py
"""
import sys
import os
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STMT_TIMEOUT = "300s"


def _run(cur, sql, desc="", params=None):
    try:
        cur.execute(f"SET statement_timeout = '{STMT_TIMEOUT}'")
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return cur.fetchall()
    except Exception as e:
        print(f"  [ERROR] {desc}: {e}")
        return None


def main():
    init_db_pool()
    print("=== PASO A.5 — Fix park_name en vista final (realkey) ===\n")

    # --- 1) Pre-checks ---
    print("--- 1) Pre-checks ---")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            r = _run(cur, "SELECT COUNT(*) FROM staging.plan_projection_realkey_raw", "COUNT plan raw")
            plan_raw_count = r[0][0] if r and r[0][0] is not None else 0
            r = _run(cur, "SELECT MAX(period_date) FROM staging.plan_projection_realkey_raw", "MAX period plan")
            plan_month = r[0][0] if r and r[0][0] else None
            r = _run(cur, """
                SELECT MAX(period_date) FROM ops.v_plan_vs_real_realkey_final WHERE trips_real IS NOT NULL
            """, "MAX period real")
            real_month = r[0][0] if r and r[0][0] else None
        finally:
            cur.close()

    print(f"  COUNT(staging.plan_projection_realkey_raw): {plan_raw_count}")
    print(f"  plan_month (MAX period_date plan): {plan_month}")
    print(f"  real_month (MAX period_date con real): {real_month}")

    # --- 2) Aplicar migración ---
    print("\n--- 2) Aplicar migración (alembic upgrade head) ---")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        timeout=120,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"  [ERROR] alembic: {r.stderr or r.stdout}")
        return 1
    print("  OK")

    # --- 3) Post-checks ---
    print("\n--- 3) Post-checks ---")
    with get_db() as conn:
        cur = conn.cursor()
        try:
            # Null rate global
            r = _run(cur, """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN park_name IS NULL OR TRIM(COALESCE(park_name,'')) = '' THEN 1 ELSE 0 END)
                FROM ops.v_plan_vs_real_realkey_final
            """, "park_name null global")
            total = r[0][0] if r and r[0][0] is not None else 0
            nulls_global = r[0][1] or 0 if r and r[0][0] else 0
            null_rate_global = (nulls_global / total * 100) if total else 0.0

            # Null rate y conteos para plan_month
            plan_month_nulls = None
            plan_month_total = None
            null_rate_plan_month = None
            if plan_month:
                r = _run(cur, """
                    SELECT
                        COUNT(*),
                        SUM(CASE WHEN park_name IS NULL OR TRIM(COALESCE(park_name,'')) = '' THEN 1 ELSE 0 END)
                    FROM ops.v_plan_vs_real_realkey_final
                    WHERE period_date = %s
                """, "park_name null plan_month", params=(plan_month,))
                if r and r[0][0] is not None:
                    plan_month_total = r[0][0]
                    plan_month_nulls = r[0][1] or 0
                    null_rate_plan_month = (plan_month_nulls / plan_month_total * 100) if plan_month_total else 0.0

            # Top 20 filas del plan_month con park_name y trips_plan
            top20 = None
            if plan_month:
                top20 = _run(cur, """
                    SELECT country, city, park_id, park_name, real_tipo_servicio, period_date, trips_plan, trips_real
                    FROM ops.v_plan_vs_real_realkey_final
                    WHERE period_date = %s
                    ORDER BY COALESCE(trips_plan, 0) DESC
                    LIMIT 20
                """, "top 20 plan_month", params=(plan_month,))

            # matched_pct plan_month
            matched_pct = None
            if plan_month:
                r = _run(cur, """
                    SELECT
                        COUNT(*),
                        SUM(CASE WHEN trips_plan IS NOT NULL AND trips_real IS NOT NULL THEN 1 ELSE 0 END)
                    FROM ops.v_plan_vs_real_realkey_final
                    WHERE period_date = %s
                """, "matched plan_month", params=(plan_month,))
                if r and r[0][0] is not None and r[0][0] > 0:
                    matched_pct = (r[0][1] or 0) / r[0][0] * 100
        finally:
            cur.close()

    print(f"  park_name null rate (global): {nulls_global}/{total} ({null_rate_global:.1f}%)")
    if plan_month_total is not None:
        print(f"  park_name null rate (plan_month {plan_month}): {plan_month_nulls}/{plan_month_total} ({null_rate_plan_month:.1f}%)")
    if real_month is not None and plan_month is not None:
        if real_month < plan_month:
            print("  matched_pct: OK (no hay real para el mes del plan aún).")
        else:
            print(f"  matched_pct (plan_month): {matched_pct:.1f}%" if matched_pct is not None else "  matched_pct: N/A")
            if matched_pct is not None and matched_pct < 30:
                print("  [AVISO] matched_pct < 30% (se exige >= 30% cuando hay real en el mes del plan).")

    print("\n  Top 20 filas plan_month (park_name, trips_plan):")
    if top20:
        for row in top20:
            country, city, park_id, park_name, real_tipo_servicio, period_date, trips_plan, trips_real = row
            pn = (park_name or "")[:40] if park_name else "(NULL)"
            print(f"    {country!r} | {city!r} | {park_id!r} | park_name={pn!r} | plan={trips_plan} real={trips_real}")
    else:
        print("    (sin datos o error)")

    # --- 4) Exit codes ---
    # Exit 0: park_name null rate <= 1% (plan_month) O <= 5% global; y ninguna fila plan_month con park_name NULL.
    # Exit 1: hay filas plan_month con park_name NULL; o (global > 5% y plan_month > 1%); o matched_pct < 30% cuando hay real en mes plan.
    print("\n" + "=" * 60)
    fail = False
    if plan_month_nulls is not None and plan_month_nulls > 0:
        print("  [FALLO] Hay filas del plan_month con park_name NULL.")
        fail = True
    if null_rate_global > 5 and (null_rate_plan_month is None or null_rate_plan_month > 1):
        print("  [FALLO] park_name null rate global > 5% y plan_month > 1%.")
        fail = True
    if real_month is not None and plan_month is not None and real_month >= plan_month and matched_pct is not None and matched_pct < 30:
        print("  [FALLO] matched_pct < 30% con real disponible para el mes del plan.")
        fail = True

    if fail:
        print("  EXIT 1")
        return 1
    print("  EXIT 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
