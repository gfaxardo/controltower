#!/usr/bin/env python3
"""
Cierre E2E REAL LOB: inspección de estado, refresh seguro y validación.

- Inspecciona estado Alembic (current, heads).
- Inspecciona objetos BD (dimensiones, vistas, MVs).
- Refresca SOLO las MVs que existan (no falla si faltan MVs v2).
- Opcional: ejecutar backfill de drill/rollup si aplica.
- Imprime resumen: migraciones, dims, vistas, MVs refrescadas, validaciones.

Uso:
  cd backend && python scripts/close_real_lob_governance.py
  python scripts/close_real_lob_governance.py --refresh-only
  python scripts/close_real_lob_governance.py --skip-refresh
  python scripts/close_real_lob_governance.py --only-month   # solo mv_real_lob_month_v2
  python scripts/close_real_lob_governance.py --only-week    # solo mv_real_lob_week_v2

  Timeout por MV (por defecto 6h): REAL_LOB_REFRESH_TIMEOUT_MS=21600000
  Memoria: REAL_LOB_REFRESH_WORK_MEM=512MB REAL_LOB_REFRESH_MAINTENANCE_WORK_MEM=1GB
"""
import argparse
import os
import sys
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from app.services.observability_service import log_refresh as _log_refresh
except ImportError:
    _log_refresh = None

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Objetos que definen la ruta canónica REAL LOB
REAL_LOB_OBJECTS = [
    ("canon", "dim_lob_group", "table"),
    ("canon", "dim_lob_real", "table"),
    ("canon", "dim_service_type", "table"),
    ("canon", "dim_real_service_type_lob", "table"),
    ("ops", "v_real_trips_service_lob_resolved", "view"),
    ("ops", "v_real_trips_with_lob_v2", "view"),
    ("ops", "mv_real_lob_month_v2", "materialized view"),
    ("ops", "mv_real_lob_week_v2", "materialized view"),
    ("ops", "real_drill_dim_fact", "table"),
    ("ops", "mv_real_drill_dim_agg", "view"),  # en 064 es vista sobre real_drill_dim_fact
    ("ops", "real_rollup_day_fact", "table"),
]

# MVs que se intentan refrescar (solo si existen)
MVS_TO_REFRESH = [
    ("ops", "mv_real_lob_month_v2"),
    ("ops", "mv_real_lob_week_v2"),
]

# Timeout por refresh: 6h por defecto (CT-MV-PERFORMANCE-HARDENING); override con REAL_LOB_REFRESH_TIMEOUT_MS
REFRESH_TIMEOUT_MS = int(os.environ.get("REAL_LOB_REFRESH_TIMEOUT_MS", "21600000"))  # 6h
# Memoria para acelerar agregaciones y reducir spills (STEP 5)
REFRESH_WORK_MEM = os.environ.get("REAL_LOB_REFRESH_WORK_MEM", "512MB")
REFRESH_MAINTENANCE_WORK_MEM = os.environ.get("REAL_LOB_REFRESH_MAINTENANCE_WORK_MEM", "1GB")


def _object_exists(cur, schema: str, name: str, kind: str) -> bool:
    if kind == "materialized view":
        cur.execute("""
            SELECT 1 FROM pg_matviews WHERE schemaname = %s AND matviewname = %s
        """, (schema, name))
    elif kind == "view":
        cur.execute("""
            SELECT 1 FROM pg_views WHERE schemaname = %s AND viewname = %s
        """, (schema, name))
    else:
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        """, (schema, name))
    return cur.fetchone() is not None


def inspect_alembic() -> Dict[str, Any]:
    """Estado de Alembic (current, heads) sin conectar a BD de app."""
    out: Dict[str, Any] = {"current": [], "heads": [], "single_head": None}
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            cwd=BACKEND_DIR, capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0 and r.stdout:
            out["current"] = [s.strip() for s in r.stdout.strip().splitlines() if s.strip() and "INFO" not in s]
        r2 = subprocess.run(
            [sys.executable, "-m", "alembic", "heads"],
            cwd=BACKEND_DIR, capture_output=True, text=True, timeout=15
        )
        if r2.returncode == 0 and r2.stdout:
            heads = [s.strip() for s in r2.stdout.strip().splitlines() if s.strip() and "INFO" not in s]
            out["heads"] = heads
            out["single_head"] = len(heads) == 1
    except Exception as e:
        out["error"] = str(e)
    return out


def inspect_objects(cur) -> Dict[str, bool]:
    """Devuelve mapa (schema.name -> existe)."""
    result = {}
    for schema, name, kind in REAL_LOB_OBJECTS:
        key = f"{schema}.{name}"
        try:
            result[key] = _object_exists(cur, schema, name, kind)
        except Exception as e:
            logger.warning("Comprobando %s: %s", key, e)
            result[key] = False
    return result


def _set_refresh_session_autocommit(cur) -> None:
    """Session settings para refresh en conexión dedicada con autocommit. Usar SET (no SET LOCAL)."""
    cur.execute("SET statement_timeout = %s", (str(REFRESH_TIMEOUT_MS),))
    try:
        cur.execute("SET work_mem = %s", (REFRESH_WORK_MEM,))
        cur.execute("SET maintenance_work_mem = %s", (REFRESH_MAINTENANCE_WORK_MEM,))
    except Exception as e:
        logger.debug("No se pudo setear work_mem/maintenance_work_mem (ignorado): %s", e)


def _mv_is_populated(cur, mv_schema: str, mv_name: str) -> bool:
    """True si la MV tiene filas (reltuples > 0); entonces se puede usar CONCURRENTLY."""
    try:
        cur.execute(
            "SELECT COALESCE(c.reltuples, 0)::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'm'",
            (mv_schema, mv_name),
        )
        r = cur.fetchone()
        n = r[0] if r and (hasattr(r, "__getitem__") or isinstance(r, (list, tuple))) else 0
        return (n or 0) > 0
    except Exception:
        return False


def _safe_rollback(conn) -> None:
    """Rollback si la conexión sigue abierta."""
    try:
        if conn and not conn.closed:
            conn.rollback()
    except Exception:
        pass


def _get_mv_count(cur, schema: str, name: str) -> Optional[int]:
    """Conteo de filas de una MV; solo para MVs conocidas (whitelist)."""
    if (schema, name) not in MVS_TO_REFRESH:
        return None
    try:
        cur.execute("SELECT COUNT(*) AS n FROM %s.%s" % (schema, name))
        row = cur.fetchone()
        return int(row[0] if hasattr(row, "__getitem__") else row.get("n", 0))
    except Exception:
        return None


def _run_bootstrap_for_mv(schema: str, name: str) -> Tuple[bool, Optional[str]]:
    """
    Ejecuta bootstrap por bloques para una MV vacía (FASE D).
    No usa refresh gigante; corre scripts/bootstrap_real_lob_mvs_by_blocks.py.
    """
    import subprocess
    if name == "mv_real_lob_month_v2":
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "bootstrap_real_lob_mvs_by_blocks.py"), "--only-month"]
    elif name == "mv_real_lob_week_v2":
        cmd = [sys.executable, os.path.join(SCRIPT_DIR, "bootstrap_real_lob_mvs_by_blocks.py"), "--only-week"]
    else:
        return False, "MV no soportada para bootstrap"
    logger.info("MV %s.%s vacía → bootstrap por bloques (no refresh gigante)", schema, name)
    try:
        r = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=True, text=True, timeout=7200)  # 2h max
        if r.returncode != 0:
            return False, (r.stderr or r.stdout or "bootstrap falló")[:500]
        return True, None
    except subprocess.TimeoutExpired:
        return False, "Bootstrap superó timeout 2h"
    except Exception as e:
        return False, str(e)[:500]


def refresh_mv_dedicated_connection(mv_schema: str, mv_name: str, use_concurrent: bool) -> Tuple[bool, Optional[str]]:
    """
    Refresca una MV en una conexión dedicada (evita InFailedSqlTransaction).
    CONCURRENTLY requiere autocommit; se usa SET (no SET LOCAL) para timeout/memoria.
    Si la MV está vacía (use_concurrent=False), no se hace refresh gigante: se delega a bootstrap por bloques.
    """
    full = f"{mv_schema}.{mv_name}"
    if (mv_schema, mv_name) not in MVS_TO_REFRESH:
        return False, "MV no está en whitelist"

    if not use_concurrent:
        return _run_bootstrap_for_mv(mv_schema, mv_name)

    from app.db.connection import get_db

    try:
        with get_db() as refresh_conn:
            refresh_conn.autocommit = True
            cur_refresh = refresh_conn.cursor()
            try:
                _set_refresh_session_autocommit(cur_refresh)
                logger.info(
                    "Conexión autocommit dedicada para REFRESH MATERIALIZED VIEW CONCURRENTLY: %s",
                    full,
                )
                cur_refresh.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {full}")
                return True, None
            except Exception as e:
                _safe_rollback(refresh_conn)
                msg = str(e)
                if "timeout" in msg.lower() or "statement_timeout" in msg.lower():
                    msg += (
                        " Prueba REAL_LOB_REFRESH_TIMEOUT_MS (ej. 21600000 = 6h) o psql: "
                        "SET statement_timeout='6h'; REFRESH MATERIALIZED VIEW %s;" % full
                    )
                return False, msg
            finally:
                try:
                    cur_refresh.close()
                except Exception:
                    pass
    except Exception as e:
        return False, str(e)


def _real_lob_view_for_validation(cur) -> str:
    """Vista a usar para validaciones: _120d si existe (post-098, index-friendly), sino la estándar."""
    try:
        cur.execute(
            "SELECT 1 FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_real_trips_with_lob_v2_120d'"
        )
        if cur.fetchone():
            return "ops.v_real_trips_with_lob_v2_120d"
    except Exception:
        pass
    return "ops.v_real_trips_with_lob_v2"


def run_validations(cur, statement_timeout_ms: int = 300000) -> Dict[str, Any]:
    """Validaciones: dimensiones pobladas, vista consultable. Timeout 5 min por consulta (vista _120d puede ser lenta)."""
    val: Dict[str, Any] = {"dims_populated": False, "view_select_ok": False, "canonical_no_dupes": None}
    try:
        cur.execute("SET LOCAL statement_timeout = %s", (str(statement_timeout_ms),))
    except Exception:
        pass
    try:
        cur.execute("SELECT COUNT(*) AS n FROM canon.dim_service_type WHERE is_active = true")
        row = cur.fetchone()
        n = row[0] if hasattr(row, "__getitem__") else (row.get("n") if isinstance(row, dict) else 0)
        val["dims_populated"] = n and int(n) > 0
    except Exception:
        val["dims_populated"] = False
    view_name = _real_lob_view_for_validation(cur)
    try:
        cur.execute("SELECT real_tipo_servicio_norm, lob_group FROM " + view_name + " LIMIT 1")
        cur.fetchone()
        val["view_select_ok"] = True
    except Exception as e:
        logger.debug("view_select_ok falló (%s): %s", view_name, e)
        val["view_select_ok"] = False
    # Duplicados: no debe haber confort+ y comfort_plus como distintos en la vista
    try:
        cur.execute("""
            SELECT real_tipo_servicio_norm, COUNT(*) AS c
            FROM """ + view_name + """
            WHERE real_tipo_servicio_norm IS NOT NULL
            GROUP BY real_tipo_servicio_norm
        """)
        rows = cur.fetchall()
        keys = [r[0] if hasattr(r, "__getitem__") else r.get("real_tipo_servicio_norm") for r in rows] if rows else []
        bad = {"confort+", "confort plus", "comfort+", "tuk-tuk", "mensajería", "mensajeria", "express"}
        found_bad = [k for k in keys if k and k.lower() in bad]
        val["canonical_no_dupes"] = len(found_bad) == 0
    except Exception:
        val["canonical_no_dupes"] = None
    return val


def main():
    parser = argparse.ArgumentParser(description="Cierre REAL LOB: inspección, refresh seguro, validación")
    parser.add_argument("--refresh-only", action="store_true", help="Solo refrescar MVs existentes")
    parser.add_argument("--skip-refresh", action="store_true", help="No refrescar MVs; solo inspección y validación")
    parser.add_argument("--only-month", action="store_true", help="Refrescar solo ops.mv_real_lob_month_v2")
    parser.add_argument("--only-week", action="store_true", help="Refrescar solo ops.mv_real_lob_week_v2")
    args = parser.parse_args()

    summary: Dict[str, Any] = {
        "alembic": {},
        "objects": {},
        "objects_ok": [],
        "objects_missing": [],
        "mvs_refreshed": [],
        "mvs_skipped_not_exist": [],
        "mvs_failed": [],
        "validations": {},
        "overall_ok": True,
    }

    # Alembic
    summary["alembic"] = inspect_alembic()
    if summary["alembic"].get("single_head"):
        logger.info("Alembic: un solo head (OK)")
    else:
        logger.warning("Alembic: heads = %s", summary["alembic"].get("heads"))
        if not summary["alembic"].get("single_head"):
            summary["overall_ok"] = False

    try:
        from app.db.connection import get_db, init_db_pool
    except ImportError as e:
        logger.error("No se pudo importar app.db.connection: %s", e)
        summary["overall_ok"] = False
        _print_summary(summary)
        sys.exit(1)

    init_db_pool()
    try:
        with get_db() as conn:
            cur = conn.cursor()
            # Objetos
            objs = inspect_objects(cur)
            summary["objects"] = objs
            for key, exists in objs.items():
                if exists:
                    summary["objects_ok"].append(key)
                else:
                    summary["objects_missing"].append(key)
            logger.info("Objetos OK: %s", len(summary["objects_ok"]))
            if summary["objects_missing"]:
                logger.warning("Objetos ausentes: %s", summary["objects_missing"])

            # Refresh MVs: orden 1) monthly, 2) weekly (STEP 8); opciones --only-month / --only-week
            mvs_to_run = list(MVS_TO_REFRESH)
            if args.only_month:
                mvs_to_run = [("ops", "mv_real_lob_month_v2")]
            elif args.only_week:
                mvs_to_run = [("ops", "mv_real_lob_week_v2")]

            if not args.skip_refresh:
                logger.info("Refresh MVs: timeout=%s ms (~%s min), work_mem=%s, maintenance_work_mem=%s",
                            REFRESH_TIMEOUT_MS, REFRESH_TIMEOUT_MS // 60000, REFRESH_WORK_MEM, REFRESH_MAINTENANCE_WORK_MEM)
                script_name = "close_real_lob_governance.py"
                for schema, name in mvs_to_run:
                    key = f"{schema}.{name}"
                    if not _object_exists(cur, schema, name, "materialized view"):
                        summary["mvs_skipped_not_exist"].append(key)
                        logger.info("Omitida (no existe): %s", key)
                        continue
                    use_concurrent = _mv_is_populated(cur, schema, name)
                    rows_before = _get_mv_count(cur, schema, name)
                    t0 = time.monotonic()
                    if _log_refresh:
                        _log_refresh(key, status="running", script_name=script_name, trigger_type="script")
                    ok, err = refresh_mv_dedicated_connection(schema, name, use_concurrent)
                    duration_seconds = round(time.monotonic() - t0, 2)
                    rows_after = _get_mv_count(cur, schema, name) if ok else None
                    if ok:
                        summary["mvs_refreshed"].append(key)
                        logger.info("Refrescada: %s (%.1fs, rows %s -> %s)", key, duration_seconds, rows_before, rows_after)
                        if _log_refresh:
                            _log_refresh(key, status="ok", script_name=script_name, trigger_type="script",
                                         rows_before=rows_before, rows_after=rows_after, duration_seconds=duration_seconds)
                    elif err:
                        summary["mvs_failed"].append((key, err))
                        logger.warning("Falló refresh %s: %s", key, err)
                        summary["overall_ok"] = False
                        if _log_refresh:
                            _log_refresh(key, status="error", script_name=script_name, error_message=err)
                    else:
                        summary["mvs_skipped_not_exist"].append(key)

                # Validación rowcount (STEP 9)
                for key in summary["mvs_refreshed"]:
                    parts = key.split(".", 1)
                    if len(parts) == 2:
                        n = _get_mv_count(cur, parts[0], parts[1])
                        if n is not None:
                            logger.info("Validación rowcount %s: %s", key, n)
            else:
                for schema, name in MVS_TO_REFRESH:
                    if not objs.get(f"{schema}.{name}"):
                        summary["mvs_skipped_not_exist"].append(f"{schema}.{name}")

            # Validaciones
            summary["validations"] = run_validations(cur)
            if summary["validations"].get("dims_populated"):
                logger.info("Validación: dimensiones pobladas OK")
            else:
                logger.warning("Validación: dimensiones no pobladas o no existen")
            if summary["validations"].get("view_select_ok"):
                logger.info("Validación: vista v_real_trips_with_lob_v2 consultable OK")
            else:
                logger.warning("Validación: vista no consultable o no existe")
            if summary["validations"].get("canonical_no_dupes") is False:
                logger.warning("Validación: se detectaron posibles duplicados de categoría (confort+/tuk-tuk/express)")
                summary["overall_ok"] = False
            cur.close()
    except Exception as e:
        logger.exception("Error: %s", e)
        summary["overall_ok"] = False

    _print_summary(summary)
    sys.exit(0 if summary["overall_ok"] else 1)


def _print_summary(summary: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("CT-REAL-LOB-CLOSURE — Resumen")
    print("=" * 60)
    print("Alembic current:", summary.get("alembic", {}).get("current"))
    print("Alembic heads:", summary.get("alembic", {}).get("heads"))
    print("Un solo head:", summary.get("alembic", {}).get("single_head"))
    print("Objetos OK:", len(summary.get("objects_ok", [])))
    print("Objetos ausentes:", summary.get("objects_missing", []))
    print("MVs refrescadas:", summary.get("mvs_refreshed", []))
    print("MVs omitidas (no existen):", summary.get("mvs_skipped_not_exist", []))
    if summary.get("mvs_failed"):
        print("MVs fallidas:", summary["mvs_failed"])
    print("Validaciones:", summary.get("validations", {}))
    print("OVERALL:", "OK" if summary.get("overall_ok") else "FAIL / WARN")
    print("=" * 60)


if __name__ == "__main__":
    main()
