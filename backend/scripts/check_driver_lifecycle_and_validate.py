#!/usr/bin/env python3
"""
Comprueba MVs driver lifecycle, refresca (con fallback) y ejecuta validaciones.

ENV:
  DRIVER_LIFECYCLE_REFRESH_MODE = concurrently | nonc | none  (default: concurrently)
  DRIVER_LIFECYCLE_TIMEOUT_MINUTES = 60
  DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES = 5
  DRIVER_LIFECYCLE_FALLBACK_NONC = 1 | true | yes  (default: true)

Uso:
  cd backend && python -m scripts.check_driver_lifecycle_and_validate
  python -m scripts.check_driver_lifecycle_and_validate --diagnose

Exit codes: 0 OK, 1 refresh falló, 2 validaciones duras fallaron
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool, get_connection_info, log_connection_context
from psycopg2.extras import RealDictCursor


def _env_mode():
    return (os.environ.get("DRIVER_LIFECYCLE_REFRESH_MODE") or "concurrently").strip().lower()


def _env_timeout_minutes():
    try:
        return int(os.environ.get("DRIVER_LIFECYCLE_TIMEOUT_MINUTES") or "60")
    except ValueError:
        return 60


def _env_lock_timeout_minutes():
    try:
        return int(os.environ.get("DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES") or "5")
    except ValueError:
        return 5


def _env_fallback_nonc():
    return (os.environ.get("DRIVER_LIFECYCLE_FALLBACK_NONC") or "1").strip().lower() in ("1", "true", "yes")


def _is_timeout_or_lock(exc):
    msg = (str(exc) or "").lower()
    return "timeout" in msg or "lock" in msg or "canceling statement" in msg


def _show_val(row):
    return list(row.values())[0] if row else "?"


def run_diagnose(conn, timeout_min: int, lock_timeout_min: int) -> int:
    """Modo --diagnose: imprime timeouts, pg_stat_activity, locks. No refresca. Exit 0."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print("=== DIAGNÓSTICO DRIVER LIFECYCLE REFRESH ===\n")

    print("1) Timeouts y settings de sesión:")
    cur.execute("SHOW statement_timeout")
    print("   statement_timeout =", _show_val(cur.fetchone()))
    cur.execute("SHOW lock_timeout")
    print("   lock_timeout =", _show_val(cur.fetchone()))
    cur.execute("SHOW maintenance_work_mem")
    print("   maintenance_work_mem =", _show_val(cur.fetchone()))

    print("\n   Valores objetivo (ENV):")
    print(f"   statement_timeout_target = {timeout_min}min")
    print(f"   lock_timeout_target = {lock_timeout_min}min")

    print("\n2) REFRESH en curso (pg_stat_activity):")
    cur.execute("""
        SELECT pid, usename, state, wait_event_type, wait_event, left(query, 100) AS query
        FROM pg_stat_activity
        WHERE pid != pg_backend_pid()
          AND query ILIKE '%REFRESH MATERIALIZED VIEW%' AND state <> 'idle'
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print("   ", r)
    else:
        print("   (ninguno)")

    print("\n3) Locks bloqueados/bloqueantes:")
    cur.execute("""
        SELECT blocked_locks.pid AS blocked_pid,
               blocking_locks.pid AS blocking_pid,
               left(blocked_activity.query, 60) AS blocked_query,
               left(blocking_activity.query, 60) AS blocking_query
        FROM pg_locks blocked_locks
        JOIN pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
        JOIN pg_locks blocking_locks
          ON blocking_locks.locktype = blocked_locks.locktype
         AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
         AND blocking_locks.pid != blocked_locks.pid
        JOIN pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
        WHERE NOT blocked_locks.granted
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print("   ", r)
    else:
        print("   (ninguno)")

    cur.close()
    print("\n=== FIN DIAGNÓSTICO ===")
    return 0


def _detect_driver_col(cur) -> str:
    """Detecta columna driver en base: driver_key, driver_id, conductor_id, id."""
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_base'
        AND column_name IN ('driver_key', 'driver_id', 'conductor_id', 'id')
        ORDER BY CASE column_name
            WHEN 'driver_key' THEN 1 WHEN 'driver_id' THEN 2
            WHEN 'conductor_id' THEN 3 WHEN 'id' THEN 4 ELSE 5 END
    """)
    row = cur.fetchone()
    return row["column_name"] if row else "driver_key"


def _detect_freshness_col(cur) -> str | None:
    """Detecta columna freshness: last_completed_ts, last_trip_ts, last_completed_at."""
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'ops' AND table_name = 'mv_driver_lifecycle_base'
        AND (column_name IN ('last_completed_ts', 'last_trip_ts', 'last_completed_at')
             OR column_name LIKE '%last_completed%' OR column_name LIKE '%last_trip%')
        ORDER BY CASE column_name
            WHEN 'last_completed_ts' THEN 1 WHEN 'last_trip_ts' THEN 2
            WHEN 'last_completed_at' THEN 3 ELSE 4 END
        LIMIT 1
    """)
    row = cur.fetchone()
    if row:
        return row["column_name"]
    # Fallback: canonical column from driver_lifecycle_build.sql
    try:
        cur.execute("SELECT 1 FROM ops.mv_driver_lifecycle_base WHERE last_completed_ts IS NULL LIMIT 1")
        return "last_completed_ts"
    except Exception:
        return None


def main():
    parser = argparse.ArgumentParser(description="Check driver lifecycle MVs, refresh, validate")
    parser.add_argument("--diagnose", action="store_true", help="Solo diagnóstico (locks, timeouts), no refresh")
    args = parser.parse_args()

    db, user, host, port = get_connection_info()
    print(f"Config: db={db} user={user} host={host}:{port}")
    init_db_pool()
    mode = _env_mode()
    timeout_min = _env_timeout_minutes()
    lock_timeout_min = _env_lock_timeout_minutes()
    fallback = _env_fallback_nonc()

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Evitar transacción implícita antes de SET (autocommit para timeouts)
        conn.autocommit = True
        log_connection_context(cur)
        if args.diagnose:
            cur.close()
            return run_diagnose(conn, timeout_min, lock_timeout_min)

        try:
            # --- Timeouts ANTES ---
            cur.execute("SHOW statement_timeout")
            st_before = _show_val(cur.fetchone())
            cur.execute("SHOW lock_timeout")
            lt_before = _show_val(cur.fetchone())
            cur.execute("SHOW maintenance_work_mem")
            mw_val = _show_val(cur.fetchone())
            print("Before SET:")
            print("  statement_timeout =", st_before)
            print("  lock_timeout =", lt_before)
            print("  maintenance_work_mem =", mw_val)
            print("ENV: DRIVER_LIFECYCLE_REFRESH_MODE =", mode)
            print("     DRIVER_LIFECYCLE_TIMEOUT_MINUTES =", timeout_min)
            print("     DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES =", lock_timeout_min)
            print("     DRIVER_LIFECYCLE_FALLBACK_NONC =", fallback)

            # --- Imponer timeouts (SET, NO SET LOCAL) inmediatamente después de conectar ---
            cur.execute(f"SET statement_timeout = '{timeout_min}min'")
            cur.execute(f"SET lock_timeout = '{lock_timeout_min}min'")

            # --- Confirmar timeouts DESPUÉS ---
            cur.execute("SHOW statement_timeout")
            st_after = _show_val(cur.fetchone())
            cur.execute("SHOW lock_timeout")
            lt_after = _show_val(cur.fetchone())
            print("After SET:")
            print("  statement_timeout =", st_after)
            print("  lock_timeout =", lt_after)

            # Validar: si sigue 15s o no aplicó, abortar
            st_lower = (st_after or "").lower()
            if "15s" in st_lower or st_lower == "15" or ("60" not in st_lower and "min" not in st_lower and "1h" not in st_lower):
                print("\n*** ERROR: statement_timeout no se aplicó correctamente. Abortando. ***")
                print("  Antes:", st_before, "| Después:", st_after)
                print("  Ejecuta: python -m scripts.diagnose_pg_timeouts")
                print("  para diagnosticar qué está forzando el timeout (rol, db, config).")
                cur.close()
                return 2

            # Listar MVs existentes: pg_matviews + to_regclass como validación cruzada
            cur.execute("""
                SELECT matviewname FROM pg_matviews
                WHERE schemaname = 'ops'
                  AND (
                    matviewname LIKE 'mv_driver_lifecycle%%'
                    OR matviewname IN ('mv_driver_weekly_stats', 'mv_driver_monthly_stats')
                    OR matviewname IN ('mv_driver_cohorts_weekly', 'mv_driver_cohort_kpis')
                  )
                ORDER BY matviewname
            """)
            all_mvs = [r["matviewname"] for r in cur.fetchall()]
            # Fallback: si pg_matviews vacío, validar con to_regclass
            if not all_mvs:
                cur.execute("""
                    SELECT to_regclass('ops.mv_driver_lifecycle_base') AS base,
                           to_regclass('ops.mv_driver_weekly_stats') AS weekly,
                           to_regclass('ops.mv_driver_monthly_stats') AS monthly
                """)
                tr = cur.fetchone()
                if tr and (tr.get("base") or tr.get("weekly") or tr.get("monthly")):
                    found = [n for n, v in [("mv_driver_lifecycle_base", tr.get("base")),
                                            ("mv_driver_weekly_stats", tr.get("weekly")),
                                            ("mv_driver_monthly_stats", tr.get("monthly"))] if v]
                    print("\nMVs driver lifecycle en ops: ninguna (pg_matviews)")
                    print("  to_regclass SÍ encuentra:", found, "- posible schema/search_path")
                else:
                    print("\nMVs driver lifecycle en ops: ninguna")
            else:
                print("\nMVs driver lifecycle en ops:", all_mvs)
            mvs_lifecycle = [m for m in all_mvs if m.startswith("mv_driver_lifecycle")]
            mvs_extra = [m for m in all_mvs if m in ("mv_driver_weekly_stats", "mv_driver_monthly_stats")]

            if not mvs_lifecycle:
                print("Ejecuta antes: python -m scripts.run_driver_lifecycle_build")
                cur.close()
                return 2

            use_3only = (
                set(mvs_lifecycle)
                <= {"mv_driver_lifecycle_base", "mv_driver_lifecycle_weekly_kpis", "mv_driver_lifecycle_monthly_kpis"}
                and not mvs_extra
            )
            func_concurrent = "ops.refresh_driver_lifecycle_mvs_3only()" if use_3only else "ops.refresh_driver_lifecycle_mvs()"
            func_nonc = "ops.refresh_driver_lifecycle_mvs_nonc_3only()" if use_3only else "ops.refresh_driver_lifecycle_mvs_nonc()"
            if use_3only:
                print("Usando funciones 3only")

            # --- Refresh ---
            refresh_ok = False
            used_fallback = False
            if mode == "none":
                print("\nModo none: no se refresca. Modo usado: none")
                refresh_ok = True
            elif mode == "nonc":
                t0 = time.perf_counter()
                try:
                    cur.execute(f"SELECT {func_nonc}")
                    conn.commit()
                    print("\nOK: refresh (nonc) completado")
                    print(f"  Modo usado: nonc | Duración: {time.perf_counter() - t0:.1f} s")
                    refresh_ok = True
                except Exception as e:
                    conn.rollback()
                    print("\nERROR refresh nonc:", e)
            elif mode == "concurrently":
                t0 = time.perf_counter()
                try:
                    cur.execute(f"SELECT {func_concurrent}")
                    conn.commit()
                    print("\nOK: refresh (concurrently) completado")
                    print(f"  Modo usado: concurrently | Duración: {time.perf_counter() - t0:.1f} s")
                    refresh_ok = True
                except Exception as e:
                    conn.rollback()
                    print("\nRefresh concurrently falló:", e)
                    if fallback and _is_timeout_or_lock(e):
                        print("Fallback: intentando refresh NO CONCURRENTLY...")
                        try:
                            cur.execute(f"SELECT {func_nonc}")
                            conn.commit()
                            used_fallback = True
                            refresh_ok = True
                            print("OK: refresh (nonc fallback) completado")
                            print(f"  Modo usado: nonc (fallback) | Duración: {time.perf_counter() - t0:.1f} s")
                        except Exception as e2:
                            conn.rollback()
                            print("ERROR fallback nonc:", e2)
                    else:
                        cur.close()
                        return 1
            else:
                print(f"\nERROR: modo inválido '{mode}' (concurrently|nonc|none)")
                cur.close()
                return 1

            # --- Validaciones ---
            print("\n--- Validaciones ---")

            counts = {}
            mv_names = [
                "ops.mv_driver_lifecycle_base",
                "ops.mv_driver_lifecycle_weekly_kpis",
                "ops.mv_driver_lifecycle_monthly_kpis",
                "ops.mv_driver_weekly_stats",
                "ops.mv_driver_monthly_stats",
            ]
            if any("mv_driver_cohort" in m for m in all_mvs):
                mv_names.extend(["ops.mv_driver_cohorts_weekly", "ops.mv_driver_cohort_kpis"])
            for name in mv_names:
                try:
                    cur.execute(f"SELECT COUNT(*) AS n FROM {name}")
                    counts[name] = cur.fetchone()["n"]
                    print(f"  {name}: {counts[name]:,} filas")
                except Exception as e:
                    print(f"  {name}: {e}")

            # Unicidad: detectar columna driver
            driver_col = _detect_driver_col(cur)
            try:
                cur.execute(
                    f"SELECT COUNT(*) AS total, COUNT(DISTINCT {driver_col}) AS distinct_k FROM ops.mv_driver_lifecycle_base"
                )
                r = cur.fetchone()
                ok = r["total"] == r["distinct_k"]
                print(f"  Unicidad base ({driver_col}): {'OK' if ok else 'DUPLICADOS'} (total={r['total']}, distinct={r['distinct_k']})")
                if not ok:
                    cur.close()
                    return 2
            except Exception as e:
                print("  Unicidad base:", e)
                cur.close()
                return 2

            # Base vacía
            base_count = counts.get("ops.mv_driver_lifecycle_base", 0)
            if base_count == 0:
                print("  *** FAIL: base vacía ***")
                cur.close()
                return 2

            # Freshness: detectar columna
            freshness_col = _detect_freshness_col(cur)
            if freshness_col:
                try:
                    cur.execute(f"SELECT MAX({freshness_col}) AS last_ts FROM ops.mv_driver_lifecycle_base")
                    row = cur.fetchone()
                    if row and row.get("last_ts"):
                        print(f"  Freshness ({freshness_col}): {row['last_ts']}")
                    else:
                        print(f"  Freshness ({freshness_col}): (vacío)")
                except Exception as e:
                    print("  Freshness:", e)
            else:
                print("  Freshness: (columna no encontrada, omitido)")

            # Parks distintos
            try:
                cur.execute(
                    "SELECT COUNT(DISTINCT park_id) AS n FROM ops.mv_driver_weekly_stats WHERE park_id IS NOT NULL AND TRIM(COALESCE(park_id::text, '')) != ''"
                )
                r = cur.fetchone()
                print(f"  Parks distintos (weekly_stats): {r['n']:,}")
            except Exception as e:
                print("  Parks distintos: (error)", e)

            # Park quality: null_share
            try:
                cur.execute("""
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE park_id IS NULL) AS nulls
                    FROM ops.mv_driver_weekly_stats
                """)
                r = cur.fetchone()
                total = r.get("total") or 0
                nulls = r.get("nulls") or 0
                pct = 100.0 * nulls / total if total else 0
                print(f"  park_id NULL: {nulls:,}/{total:,} ({pct:.2f}%)")
                if pct > 5.0:
                    print("  *** WARNING: park_id NULL > 5% ***")
            except Exception as e:
                print("  park_id NULL share: (error)", e)

            # Top 5 parks
            try:
                cur.execute("""
                    WITH act AS (
                        SELECT w.park_id, COUNT(*) AS activations
                        FROM ops.mv_driver_lifecycle_base b
                        JOIN ops.mv_driver_weekly_stats w
                          ON w.driver_key = b.driver_key
                          AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                        WHERE b.activation_ts >= CURRENT_DATE - INTERVAL '28 days'
                          AND w.park_id IS NOT NULL
                        GROUP BY w.park_id
                    )
                    SELECT park_id, activations FROM act ORDER BY activations DESC LIMIT 5
                """)
                rows = cur.fetchall()
                print("  Top 5 parks por activations (últimos 28 días):")
                for row in rows:
                    print(f"    {row['park_id']}: {row['activations']:,}")
            except Exception as e:
                print("  Top 5 parks: (error)", e)

            cur.close()
        finally:
            conn.autocommit = False

    print("\nListo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
