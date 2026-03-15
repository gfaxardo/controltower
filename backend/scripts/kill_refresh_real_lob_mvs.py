#!/usr/bin/env python3
"""
FASE A — CT-REAL-LOB-BOOTSTRAP-REFRESH-FIX.

Detecta y opcionalmente termina REFRESH MATERIALIZED VIEW asociados a
ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2.
Deja evidencia de qué estaba corriendo, cuánto llevaba, y estado final.

Uso:
  cd backend && python scripts/kill_refresh_real_lob_mvs.py           # solo diagnóstico
  cd backend && python scripts/kill_refresh_real_lob_mvs.py --kill    # terminar procesos
"""
import argparse
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

TARGET_MVS = ("ops.mv_real_lob_month_v2", "ops.mv_real_lob_week_v2")


def run_diagnosis(cur) -> list[dict]:
    """Busca queries en curso que sean REFRESH de las MVs objetivo."""
    cur.execute("""
        SELECT
            p.pid,
            p.usename,
            p.application_name,
            p.client_addr,
            p.state,
            p.query_start,
            EXTRACT(EPOCH FROM (now() - p.query_start))::int AS duration_seconds,
            left(p.query, 200) AS query_preview
        FROM pg_stat_activity p
        WHERE p.state != 'idle'
          AND p.pid != pg_backend_pid()
          AND p.query ILIKE '%%REFRESH MATERIALIZED VIEW%%'
          AND (
            p.query ILIKE '%%mv_real_lob_month_v2%%'
            OR p.query ILIKE '%%mv_real_lob_week_v2%%'
          )
        ORDER BY p.query_start
    """)
    return cur.fetchall()


def kill_pid(cur, pid: int) -> bool:
    """Termina el proceso con pg_terminate_backend. Devuelve True si se envió."""
    try:
        cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        return cur.fetchone()[0]
    except Exception:
        return False


def check_locks(cur) -> list[dict]:
    """Locks relacionados con las MVs (relación por nombre)."""
    cur.execute("""
        SELECT
            l.pid,
            l.mode,
            l.granted,
            c.relname,
            n.nspname
        FROM pg_locks l
        JOIN pg_class c ON c.oid = l.relation
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ops'
          AND c.relname IN ('mv_real_lob_month_v2', 'mv_real_lob_week_v2')
    """)
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description="FASE A: detectar/terminar REFRESH Real LOB MVs")
    parser.add_argument("--kill", action="store_true", help="Terminar los procesos encontrados")
    args = parser.parse_args()

    try:
        from app.db.connection import get_db, init_db_pool
    except ImportError as e:
        print("Error: no se pudo importar app.db.connection:", e)
        sys.exit(1)

    init_db_pool()
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "target_mvs": list(TARGET_MVS),
        "running_refreshes": [],
        "killed": [],
        "locks_after": [],
        "state": "clean",
    }

    with get_db() as conn:
        cur = conn.cursor()
        rows = run_diagnosis(cur)
        for r in rows:
            rec = {
                "pid": r[0],
                "usename": r[1],
                "application_name": r[2],
                "client_addr": str(r[3]) if r[3] else None,
                "state": r[4],
                "query_start": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
                "duration_seconds": r[6],
                "query_preview": (r[7] or "")[:200],
            }
            report["running_refreshes"].append(rec)
            print("[REFRESH EN CURSO] pid=%s state=%s duration_seconds=%s" % (r[0], r[4], r[6]))
            print("  query_start=%s" % rec["query_start"])
            print("  preview: %s" % (rec["query_preview"][:120] + "..." if len(rec["query_preview"] or "") > 120 else rec["query_preview"]))

        if not rows:
            print("[OK] No hay REFRESH en curso para las MVs objetivo.")
        elif args.kill:
            for r in rows:
                pid = r[0]
                if kill_pid(cur, pid):
                    report["killed"].append(pid)
                    print("[KILL] Terminado pid=%s" % pid)
                else:
                    print("[WARN] No se pudo terminar pid=%s" % pid)
            try:
                conn.commit()
            except Exception:
                conn.rollback()
        else:
            print("[INFO] Usa --kill para terminar estos procesos.")

        report["locks_after"] = [{"pid": r[0], "mode": r[1], "granted": r[2], "relname": r[3], "nspname": r[4]} for r in check_locks(cur)]
        if report["locks_after"]:
            print("[LOCKS] Locks actuales en ops.mv_real_lob_*_v2:", report["locks_after"])
            report["state"] = "locks_present"
        else:
            report["state"] = "clean" if not report["running_refreshes"] or args.kill else "refreshes_running"
        cur.close()

    print("\n--- Reporte FASE A ---")
    print("Estado final:", report["state"])
    print("Refreshes en curso:", len(report["running_refreshes"]))
    print("PIDs terminados:", report["killed"])
    print("Locks restantes:", len(report["locks_after"]))
    return report


if __name__ == "__main__":
    main()
