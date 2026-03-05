#!/usr/bin/env python3
"""
Ejecuta todos los pendientes de Driver Lifecycle PRO:
1. alembic upgrade head
2. Índices CONCURRENTLY (trips_all, trips_2026)
3. Refresh MVs base (ops.refresh_driver_lifecycle_mvs)
4. Refresh MVs PRO (weekly_behavior, churn_segments, behavior_shifts, park_shock)
5. Verificación rápida

Uso: cd backend && python -m scripts.run_all_driver_lifecycle_pending
"""
import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)


def run_cmd(cmd: list, cwd: str = None, env: dict = None, timeout: int = 7200) -> tuple[int, str]:
    """Ejecuta comando, retorna (exit_code, output)."""
    env = env or os.environ.copy()
    cwd = cwd or BACKEND_DIR
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        return r.returncode, out
    except subprocess.TimeoutExpired:
        return -1, "Timeout"
    except Exception as e:
        return -1, str(e)


def main() -> int:
    print("=" * 60)
    print("DRIVER LIFECYCLE PRO — Ejecución de pendientes")
    print("=" * 60)

    # 1) Alembic upgrade head
    print("\n--- 1) Alembic upgrade head ---")
    code, out = run_cmd([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR)
    print(out)
    if code != 0:
        print("WARN: alembic upgrade falló (encoding/conexión). Continuando con pasos que usan app.db...")
        print("      Si las migraciones ya están aplicadas, los siguientes pasos pueden funcionar.")

    # 2) Índices CONCURRENTLY (con Python para evitar psql)
    print("\n--- 2) Índices CONCURRENTLY ---")
    try:
        from app.db.connection import get_db, init_db_pool
        init_db_pool()
        with get_db() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SET statement_timeout = '1h'")
            sql_path = os.path.join(SCRIPT_DIR, "sql", "trips_unified_indexes_concurrent.sql")
            with open(sql_path, "r", encoding="utf-8") as f:
                sql = f.read()
            # Ejecutar cada statement por separado (CONCURRENTLY no puede ir en transacción)
            statements = []
            for s in sql.split(";"):
                stmt = s.strip()
                # Ignorar vacíos, comentarios puros, o líneas que empiezan con --
                if not stmt or stmt.startswith("--"):
                    continue
                # Quitar comentarios al final de línea
                if "--" in stmt:
                    stmt = stmt.split("--")[0].strip()
                if stmt and stmt.upper().startswith("CREATE"):
                    statements.append(stmt)
            for stmt in statements:
                if stmt:
                    try:
                        cur.execute(stmt)
                        print(f"  OK: {stmt[:60]}...")
                    except Exception as e:
                        if "already exists" in str(e).lower():
                            print(f"  SKIP (ya existe): {stmt[:50]}...")
                        else:
                            print(f"  WARN: {e}")
            cur.close()
            conn.autocommit = False
        print("OK: índices aplicados")
    except Exception as e:
        print(f"WARN índices: {e} (puedes ejecutar el SQL a mano)")

    # 3) Build driver lifecycle (si no existen MVs) + Refresh
    print("\n--- 3) Driver Lifecycle build + refresh ---")
    # Primero intentar build (crea MVs si no existen)
    code_build, out_build = run_cmd([sys.executable, "-m", "scripts.run_driver_lifecycle_build"], cwd=BACKEND_DIR, timeout=3600)
    if code_build == 0:
        print("OK: driver_lifecycle_build completado")
    else:
        print("(build falló o ya existía; intentando refresh)")
    code, out = run_cmd([sys.executable, "-m", "scripts.check_driver_lifecycle_and_validate"], cwd=BACKEND_DIR, timeout=3600)
    print(out)
    if code != 0:
        print("ERROR: refresh base falló. Verifica que las MVs existan (run_driver_lifecycle_build).")
        return 2
    print("OK: MVs base refrescadas")

    # 4) Refresh MVs PRO (si existen)
    print("\n--- 4) Refresh MVs PRO ---")
    try:
        from app.db.connection import get_db, init_db_pool
        init_db_pool()
        pro_mvs = [
            "ops.mv_driver_weekly_behavior",
            "ops.mv_driver_churn_segments_weekly",
            "ops.mv_driver_behavior_shifts_weekly",
            "ops.mv_driver_park_shock_weekly",
        ]
        with get_db() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SET statement_timeout = '1h'")
            for mv in pro_mvs:
                try:
                    t0 = time.perf_counter()
                    cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
                    print(f"  OK {mv}: {time.perf_counter() - t0:.1f}s")
                except Exception as e:
                    if "does not exist" in str(e).lower():
                        print(f"  SKIP {mv}: no existe (migración 056 no aplicada?)")
                    else:
                        print(f"  WARN {mv}: {e}")
            cur.close()
            conn.autocommit = False
        print("OK: MVs PRO refrescadas")
    except Exception as e:
        print(f"WARN MVs PRO: {e}")

    # 5) Verificación rápida
    print("\n--- 5) Verificación rápida ---")
    try:
        from app.db.connection import get_db, init_db_pool
        from psycopg2.extras import RealDictCursor
        init_db_pool()
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT COUNT(*) AS n FROM public.trips_unified")
            n_unified = cur.fetchone()["n"]
            print(f"  trips_unified: {n_unified:,} filas")
            cur.execute("SELECT definition FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_driver_lifecycle_trips_completed'")
            row = cur.fetchone()
            uses_unified = "trips_unified" in (row["definition"] or "")
            print(f"  v_driver_lifecycle_trips_completed usa trips_unified: {uses_unified}")
            cur.execute("SELECT COUNT(*) AS n FROM ops.mv_driver_weekly_stats")
            n_ws = cur.fetchone()["n"]
            print(f"  mv_driver_weekly_stats: {n_ws:,} filas")
            try:
                cur.execute("SELECT COUNT(*) AS n FROM ops.mv_driver_weekly_behavior")
                n_wb = cur.fetchone()["n"]
                print(f"  mv_driver_weekly_behavior: {n_wb:,} filas")
            except Exception:
                print("  mv_driver_weekly_behavior: (no existe)")
            cur.close()
        print("OK: verificación completada")
    except Exception as e:
        print(f"WARN verificación: {e}")

    print("\n" + "=" * 60)
    print("Listo. Ejecuta certify para GO/NO-GO: python -m scripts.certify_control_tower_go_nogo")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
