#!/usr/bin/env python3
"""
CT-REAL-HOURLY-FIRST — Governance y observabilidad.

Flujo:
  1. Inspección de artefactos (vista fact, MVs hour/day/week/month)
  2. Si hourly está vacía → bootstrap hourly
  3. Si hourly tiene datos → REFRESH CONCURRENTLY
  4. Reconstruir day/week/month desde hourly
  5. Validaciones: dims, vista, no-dupes, conteos, duraciones, cancelaciones

Uso:
  cd backend && python scripts/governance_hourly_first.py
  python scripts/governance_hourly_first.py --skip-refresh
  python scripts/governance_hourly_first.py --refresh-only
  python scripts/governance_hourly_first.py --only-hour
"""
import argparse
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

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

try:
    from app.services.observability_service import log_refresh as _log_refresh
except ImportError:
    _log_refresh = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REFRESH_TIMEOUT_MS = int(os.environ.get("REAL_LOB_REFRESH_TIMEOUT_MS", "21600000"))
REFRESH_WORK_MEM = os.environ.get("REAL_LOB_REFRESH_WORK_MEM", "512MB")
REFRESH_MAINTENANCE_WORK_MEM = os.environ.get("REAL_LOB_REFRESH_MAINTENANCE_WORK_MEM", "1GB")

HOURLY_FIRST_OBJECTS = [
    ("canon", "dim_lob_group", "table"),
    ("canon", "dim_service_type", "table"),
    ("ops", "v_trips_real_canon_120d", "view"),
    ("ops", "v_real_trip_fact_v2", "view"),
    ("ops", "mv_real_lob_hour_v2", "materialized view"),
    ("ops", "mv_real_lob_day_v2", "materialized view"),
    ("ops", "mv_real_lob_week_v3", "materialized view"),
    ("ops", "mv_real_lob_month_v3", "materialized view"),
]

MV_HOUR = "ops.mv_real_lob_hour_v2"
MV_DAY = "ops.mv_real_lob_day_v2"
MV_WEEK = "ops.mv_real_lob_week_v3"
MV_MONTH = "ops.mv_real_lob_month_v3"


def _object_exists(cur, schema: str, name: str, kind: str) -> bool:
    if kind == "materialized view":
        cur.execute("SELECT 1 FROM pg_matviews WHERE schemaname = %s AND matviewname = %s", (schema, name))
    elif kind == "view":
        cur.execute("SELECT 1 FROM pg_views WHERE schemaname = %s AND viewname = %s", (schema, name))
    else:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (schema, name),
        )
    return cur.fetchone() is not None


def _mv_is_populated(cur, schema: str, name: str) -> bool:
    try:
        cur.execute(
            "SELECT COALESCE(c.reltuples, 0)::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'm'",
            (schema, name),
        )
        r = cur.fetchone()
        return (r[0] if r else 0) > 0
    except Exception:
        return False


def _mv_count(cur, full_name: str) -> Optional[int]:
    try:
        cur.execute("SELECT COUNT(*) FROM %s" % full_name)
        return cur.fetchone()[0]
    except Exception:
        return None


def inspect_objects(cur) -> Dict[str, bool]:
    result = {}
    for schema, name, kind in HOURLY_FIRST_OBJECTS:
        key = f"{schema}.{name}"
        try:
            result[key] = _object_exists(cur, schema, name, kind)
        except Exception:
            result[key] = False
    return result


def _refresh_or_bootstrap_hour(cur, conn) -> Tuple[bool, Optional[str]]:
    """Refresca hourly si poblada, o llama bootstrap si vacía."""
    populated = _mv_is_populated(cur, "ops", "mv_real_lob_hour_v2")

    if not populated:
        logger.info("Hourly vacía → bootstrap por bloques")
        import subprocess
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "bootstrap_hourly_first.py"), "--only-hour"]
        try:
            r = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=True, text=True, timeout=7200)
            if r.returncode != 0:
                return False, (r.stderr or r.stdout or "bootstrap falló")[:500]
            return True, None
        except subprocess.TimeoutExpired:
            return False, "Bootstrap hour superó timeout 2h"
        except Exception as e:
            return False, str(e)[:500]

    conn.autocommit = True
    try:
        cur.execute("SET statement_timeout = %s", (str(REFRESH_TIMEOUT_MS),))
        try:
            cur.execute("SET work_mem = %s", (REFRESH_WORK_MEM,))
            cur.execute("SET maintenance_work_mem = %s", (REFRESH_MAINTENANCE_WORK_MEM,))
        except Exception:
            pass
        logger.info("REFRESH MATERIALIZED VIEW CONCURRENTLY %s", MV_HOUR)
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY %s" % MV_HOUR)
        return True, None
    except Exception as e:
        return False, str(e)[:500]


def _rebuild_derived(cur) -> Dict[str, Tuple[bool, Optional[str], int]]:
    """Reconstruye day/week/month desde hourly (DROP + CREATE)."""
    import subprocess
    results = {}
    for flag, name in [("--only-day", "day"), ("--only-week", "week"), ("--only-month", "month")]:
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "bootstrap_hourly_first.py"), flag]
        try:
            r = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=True, text=True, timeout=3600)
            ok = r.returncode == 0
            results[name] = (ok, None if ok else (r.stderr or r.stdout)[:500], 0)
        except Exception as e:
            results[name] = (False, str(e)[:500], 0)
    return results


def run_validations(cur) -> Dict[str, Any]:
    val: Dict[str, Any] = {
        "fact_view_ok": False,
        "dims_populated": False,
        "canonical_no_dupes": None,
        "hourly_populated": False,
        "day_populated": False,
        "week_populated": False,
        "month_populated": False,
        "hourly_count": 0,
        "day_count": 0,
        "week_count": 0,
        "month_count": 0,
        "cancel_reason_norm_populated": False,
        "trip_duration_reasonable": None,
        "week_no_raw_deps": True,
        "month_no_raw_deps": True,
    }
    try:
        cur.execute("SET LOCAL statement_timeout = '300000'")
    except Exception:
        pass

    # Vista fact consultable (use hourly MV to avoid expensive full scan)
    try:
        cur.execute("SELECT 1 FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_real_trip_fact_v2'")
        val["fact_view_ok"] = cur.fetchone() is not None
    except Exception:
        val["fact_view_ok"] = False

    # Dimensiones
    try:
        cur.execute("SELECT COUNT(*) FROM canon.dim_service_type WHERE is_active = true")
        val["dims_populated"] = cur.fetchone()[0] > 0
    except Exception:
        pass

    # Canonical no dupes (use hourly MV instead of fact view for speed)
    try:
        cur.execute("""
            SELECT DISTINCT real_tipo_servicio_norm FROM ops.mv_real_lob_hour_v2
            WHERE real_tipo_servicio_norm IS NOT NULL
        """)
        rows = cur.fetchall()
        keys = [r[0] for r in rows] if rows else []
        bad = {"confort+", "confort plus", "comfort+", "tuk-tuk", "mensajería", "mensajeria", "express"}
        val["canonical_no_dupes"] = len([k for k in keys if k and k.lower() in bad]) == 0
    except Exception:
        pass

    # Conteos MVs
    for mv, key_pop, key_cnt in [
        (MV_HOUR, "hourly_populated", "hourly_count"),
        (MV_DAY, "day_populated", "day_count"),
        (MV_WEEK, "week_populated", "week_count"),
        (MV_MONTH, "month_populated", "month_count"),
    ]:
        n = _mv_count(cur, mv)
        if n is not None:
            val[key_cnt] = n
            val[key_pop] = n > 0

    # Cancel reason norm poblado
    try:
        cur.execute("""
            SELECT COUNT(*) FROM ops.mv_real_lob_hour_v2
            WHERE cancel_reason_norm IS NOT NULL AND cancel_reason_norm != ''
        """)
        val["cancel_reason_norm_populated"] = cur.fetchone()[0] > 0
    except Exception:
        pass

    # Duración razonable
    try:
        cur.execute("""
            SELECT
                AVG(duration_avg_minutes),
                MIN(duration_avg_minutes),
                MAX(duration_avg_minutes)
            FROM ops.mv_real_lob_hour_v2
            WHERE duration_avg_minutes IS NOT NULL
        """)
        r = cur.fetchone()
        if r and r[0]:
            avg, mn, mx = float(r[0]), float(r[1]), float(r[2])
            val["trip_duration_reasonable"] = 1 <= avg <= 120 and mn >= 0.5 and mx <= 600
        else:
            val["trip_duration_reasonable"] = None
    except Exception:
        pass

    # Verificar que week/month NO dependen de tablas crudas
    for mv_name, key in [(MV_WEEK, "week_no_raw_deps"), (MV_MONTH, "month_no_raw_deps")]:
        try:
            schema, name = mv_name.split(".")
            cur.execute("""
                SELECT definition FROM pg_matviews
                WHERE schemaname = %s AND matviewname = %s
            """, (schema, name))
            r = cur.fetchone()
            if r:
                defn = r[0].lower()
                val[key] = "trips_all" not in defn and "trips_2026" not in defn
            else:
                val[key] = True
        except Exception:
            pass

    return val


def main():
    parser = argparse.ArgumentParser(description="Governance Hourly-First")
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--refresh-only", action="store_true")
    parser.add_argument("--only-hour", action="store_true")
    args = parser.parse_args()

    summary: Dict[str, Any] = {
        "objects": {},
        "objects_ok": [],
        "objects_missing": [],
        "hour_refresh": None,
        "derived_rebuild": {},
        "validations": {},
        "overall_ok": True,
    }

    try:
        from app.db.connection import get_db, init_db_pool
    except ImportError as e:
        logger.error("No se pudo importar app.db.connection: %s", e)
        sys.exit(1)

    init_db_pool()

    try:
        with get_db() as conn:
            cur = conn.cursor()

            objs = inspect_objects(cur)
            summary["objects"] = objs
            for key, exists in objs.items():
                (summary["objects_ok"] if exists else summary["objects_missing"]).append(key)

            logger.info("Objetos OK: %d, Ausentes: %s", len(summary["objects_ok"]), summary["objects_missing"])

            if not args.skip_refresh:
                t0 = time.monotonic()
                ok, err = _refresh_or_bootstrap_hour(cur, conn)
                duration = round(time.monotonic() - t0, 2)
                summary["hour_refresh"] = {"ok": ok, "error": err, "duration_s": duration}
                logger.info("Hour refresh: ok=%s duration=%.1fs", ok, duration)
                if not ok:
                    summary["overall_ok"] = False

                if ok and not args.only_hour and not args.refresh_only:
                    summary["derived_rebuild"] = _rebuild_derived(cur)
                    for name, (ok_d, err_d, _) in summary["derived_rebuild"].items():
                        if not ok_d:
                            logger.warning("Rebuild %s falló: %s", name, err_d)
                            summary["overall_ok"] = False

            summary["validations"] = run_validations(cur)
            cur.close()

    except Exception as e:
        logger.exception("Error: %s", e)
        summary["overall_ok"] = False

    _print_summary(summary)
    sys.exit(0 if summary["overall_ok"] else 1)


def _print_summary(summary: Dict[str, Any]):
    print("\n" + "=" * 60)
    print("CT-REAL-HOURLY-FIRST — Governance Summary")
    print("=" * 60)
    print("Objetos OK:", len(summary.get("objects_ok", [])))
    if summary.get("objects_missing"):
        print("Objetos ausentes:", summary["objects_missing"])
    hr = summary.get("hour_refresh")
    if hr:
        print("Hour refresh: ok=%s duration=%.1fs" % (hr["ok"], hr.get("duration_s", 0)))
        if hr.get("error"):
            print("  error:", hr["error"][:200])
    for name, (ok, err, _) in summary.get("derived_rebuild", {}).items():
        print(f"  {name}: {'OK' if ok else 'FAIL'}" + (f" ({err[:100]})" if err else ""))
    v = summary.get("validations", {})
    print("\nValidaciones:")
    for k, val in v.items():
        print(f"  {k}: {val}")
    print("\nOVERALL:", "OK" if summary.get("overall_ok") else "FAIL")
    print("=" * 60)


if __name__ == "__main__":
    main()
