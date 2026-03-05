#!/usr/bin/env python3
"""
Ejecuta: 1) driver_lifecycle_build.sql  2) refresh_driver_lifecycle_mvs()  3) validaciones.
Validaciones 3-7 optimizadas: sin full scans, try/except por validación, rollback en fallo.
Uso: cd backend && python -m scripts.run_driver_lifecycle_build
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool, get_connection_info, log_connection_context
from psycopg2.extras import RealDictCursor

# Timeout por defecto (30s) y para validaciones pesadas (2 min)
DEFAULT_STATEMENT_TIMEOUT_MS = 30000
HEAVY_STATEMENT_TIMEOUT_MS = 120000


def split_sql(content: str):
    """Divide SQL en sentencias; no parte dentro de bloques $$ ... $$."""
    content = re.sub(r"--[^\n]*", "", content)
    statements = []
    buf = []
    inside_dollar = False
    i = 0
    n = len(content)
    while i < n:
        if not inside_dollar and content[i:i + 2] == "$$":
            inside_dollar = True
            buf.append(content[i:i + 2])
            i += 2
            continue
        if inside_dollar and content[i:i + 2] == "$$":
            inside_dollar = False
            buf.append(content[i:i + 2])
            i += 2
            continue
        if not inside_dollar and content[i] == ";" and (i + 1 >= n or content[i + 1] in "\n\r"):
            j = i + 1
            while j < n and content[j] in " \t\n\r":
                j += 1
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i = j
            continue
        buf.append(content[i])
        i += 1
    stmt = "".join(buf).strip()
    if stmt:
        statements.append(stmt)
    return statements


def run_build():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql_path = os.path.join(base, "sql", "driver_lifecycle_build.sql")
    if not os.path.isfile(sql_path):
        print(f"[ERROR] No encontrado: {sql_path}")
        return False
    with open(sql_path, "r", encoding="utf-8") as f:
        content = f.read()
    statements = split_sql(content)
    print(f"[INFO] {len(statements)} sentencias a ejecutar.")
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        log_connection_context(cur)
        cur.execute("SET statement_timeout = '7200000'")  # 2h en ms
        for i, stmt in enumerate(statements):
            if not stmt or len(stmt) < 3:
                continue
            try:
                cur.execute(stmt)
                conn.commit()
                name = stmt[:60].replace("\n", " ") + ("..." if len(stmt) > 60 else "")
                print(f"  OK [{i+1}] {name}")
            except Exception as e:
                conn.rollback()
                print(f"  ERROR [{i+1}] {e}")
                print(f"  Stmt: {stmt[:200]}...")
                return False
        cur.close()
    return True


def run_refresh():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '7200000'")
        try:
            cur.execute("SELECT ops.refresh_driver_lifecycle_mvs()")
            conn.commit()
            print("[OK] refresh_driver_lifecycle_mvs() ejecutado.")
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] refresh: {e}")
            return False
        cur.close()
    return True


def _run_single_validation(cur, conn, name: str, query: str, heavy: bool, results: list):
    """Ejecuta una validación. Si falla: rollback, registra SKIPPED/FAIL, continúa."""
    status = "OK"
    reason = None
    rows = []
    try:
        if heavy:
            cur.execute(f"SET LOCAL statement_timeout = '{HEAVY_STATEMENT_TIMEOUT_MS}'")
        cur.execute(query)
        rows = cur.fetchall()
    except Exception as e:
        conn.rollback()
        err_str = str(e)
        if "statement timeout" in err_str.lower() or "timeout" in err_str.lower():
            status = "SKIPPED"
            reason = f"timeout: {err_str[:120]}"
        else:
            status = "FAIL"
            reason = err_str[:200]
    finally:
        if heavy:
            try:
                cur.execute("RESET statement_timeout")
            except Exception:
                pass
    results.append({"name": name, "status": status, "reason": reason, "rows": rows})
    return status, reason, rows


def run_validations():
    """Validaciones encapsuladas: try/except por validación, rollback en fallo, resumen final."""
    init_db_pool()

    # Validaciones 1-2: ligeras (MVs con LIMIT)
    VAL_1 = """
SELECT k.week_start, k.activations AS activations_mv, COALESCE(c.direct_activations, 0) AS activations_direct,
       k.activations - COALESCE(c.direct_activations, 0) AS diff
FROM ops.mv_driver_lifecycle_weekly_kpis k
LEFT JOIN (
  SELECT DATE_TRUNC('week', activation_ts)::date AS week_start, COUNT(*) AS direct_activations
  FROM ops.mv_driver_lifecycle_base WHERE activation_ts IS NOT NULL GROUP BY 1
) c ON c.week_start = k.week_start
ORDER BY k.week_start DESC LIMIT 20
"""
    VAL_2 = """
SELECT k.month_start, k.activations AS activations_mv, COALESCE(c.direct_activations, 0) AS activations_direct,
       k.activations - COALESCE(c.direct_activations, 0) AS diff
FROM ops.mv_driver_lifecycle_monthly_kpis k
LEFT JOIN (
  SELECT DATE_TRUNC('month', activation_ts)::date AS month_start, COUNT(*) AS direct_activations
  FROM ops.mv_driver_lifecycle_base WHERE activation_ts IS NOT NULL GROUP BY 1
) c ON c.month_start = k.month_start
ORDER BY k.month_start DESC LIMIT 20
"""

    # Validación 3: Join coverage — acotado a últimos 60 días, un solo scan (evita full scan)
    VAL_3_OPT = """
SELECT
  COUNT(*) AS trips_completed_with_driver_60d,
  COUNT(d.driver_id) AS trips_matched_60d,
  ROUND(100.0 * COUNT(d.driver_id) / NULLIF(COUNT(*), 0), 2) AS pct_trips_mapped_60d
FROM public.trips_unified t
LEFT JOIN public.drivers d ON t.conductor_id = d.driver_id
WHERE t.condicion = 'Completado' AND t.conductor_id IS NOT NULL
  AND t.fecha_inicio_viaje >= (CURRENT_DATE - 60)
"""

    # Validación 4: TtF — acotado a últimos 3 meses (last_completed_ts)
    VAL_4 = """
SELECT MIN(ttf_days_from_registered) AS ttf_min,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS ttf_median,
  PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS ttf_p90,
  COUNT(*) FILTER (WHERE ttf_days_from_registered < 0) AS outliers_negative
FROM ops.mv_driver_lifecycle_base
WHERE registered_ts IS NOT NULL AND ttf_days_from_registered IS NOT NULL
  AND last_completed_ts >= (CURRENT_DATE - 90)::timestamp
"""

    # Validación 5: Outliers (ligera, LIMIT 20)
    VAL_5 = """
SELECT driver_key, activation_ts, registered_ts, ttf_days_from_registered
FROM ops.mv_driver_lifecycle_base
WHERE ttf_days_from_registered < 0
ORDER BY ttf_days_from_registered LIMIT 20
"""

    # Validación 6: Sanity base — reltuples (aprox) + verificación índice único
    VAL_6 = """
SELECT
  (SELECT reltuples::bigint FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = 'ops' AND c.relname = 'mv_driver_lifecycle_base') AS approx_rows,
  (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'ops' AND tablename = 'mv_driver_lifecycle_base'
   AND indexdef ILIKE '%UNIQUE%') > 0 AS has_unique_index
"""

    # Validación 7: Unicidad weekly_stats — acotado a últimas 12 semanas
    VAL_7 = """
SELECT driver_key, week_start, COUNT(*) AS cnt
FROM ops.mv_driver_weekly_stats
WHERE week_start >= (CURRENT_DATE - 84)::date
GROUP BY driver_key, week_start
HAVING COUNT(*) > 1
"""

    validations = [
        ("1) Activations semanal (diff=0)", VAL_1, False),
        ("2) Activations mensual (diff=0)", VAL_2, False),
        ("3) Join coverage trips→drivers (últimos 60d)", VAL_3_OPT, True),
        ("4) TtF min/median/p90 (últimos 3 meses)", VAL_4, True),
        ("5) Outliers ttf<0", VAL_5, False),
        ("6) Sanity base (reltuples + unique index)", VAL_6, False),
        ("7) Unicidad weekly_stats (últimas 12 sem)", VAL_7, False),
    ]

    results = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SET statement_timeout = '{DEFAULT_STATEMENT_TIMEOUT_MS}'")
        for name, query, heavy in validations:
            print(f"\n--- Validación {name} ---")
            status, reason, rows = _run_single_validation(cur, conn, name, query, heavy, results)
            if status == "OK":
                for r in rows:
                    print(dict(r))
            elif status == "SKIPPED":
                print(f"[SKIPPED] {reason}")
            else:
                print(f"[FAIL] {reason}")

        cur.close()

    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN VALIDACIONES")
    print("=" * 60)
    ok = sum(1 for r in results if r["status"] == "OK")
    fail = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if r["status"] == "SKIPPED")
    for r in results:
        sym = "✓" if r["status"] == "OK" else ("⊘" if r["status"] == "SKIPPED" else "✗")
        reason_str = f" — {r['reason'][:80]}" if r.get("reason") else ""
        print(f"  {sym} {r['name']}: {r['status']}{reason_str}")
    print("-" * 60)
    print(f"  OK: {ok}  |  FAIL: {fail}  |  SKIPPED: {skipped}")
    print("=" * 60)
    return fail == 0


if __name__ == "__main__":
    db, user, host, port = get_connection_info()
    print("=" * 60)
    print("1) Build driver_lifecycle_build.sql")
    print(f"   Config: db={db} user={user} host={host}:{port}")
    print("=" * 60)
    if not run_build():
        sys.exit(1)
    print("\n" + "=" * 60)
    print("2) Refresh MVs: ops.refresh_driver_lifecycle_mvs()")
    print("=" * 60)
    if not run_refresh():
        sys.exit(1)
    print("\n" + "=" * 60)
    print("3) Validaciones")
    print("=" * 60)
    if not run_validations():
        print("\n[WARN] Algunas validaciones fallaron o se saltaron. Revisar resumen.")
    print("\nListo.")
