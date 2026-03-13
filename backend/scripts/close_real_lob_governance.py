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

  Timeout por MV (por defecto 2h): REAL_LOB_REFRESH_TIMEOUT_MS=10800000
  Memoria (opcional): REAL_LOB_REFRESH_WORK_MEM=512MB REAL_LOB_REFRESH_MAINTENANCE_WORK_MEM=1GB
"""
import argparse
import os
import sys
import logging
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

# Timeout por refresh (ms). 2h por defecto; override con REAL_LOB_REFRESH_TIMEOUT_MS
REFRESH_TIMEOUT_MS = int(os.environ.get("REAL_LOB_REFRESH_TIMEOUT_MS", "7200000"))
# Memoria para acelerar agregaciones (opcional; puede requerir permisos)
REFRESH_WORK_MEM = os.environ.get("REAL_LOB_REFRESH_WORK_MEM", "256MB")
REFRESH_MAINTENANCE_WORK_MEM = os.environ.get("REAL_LOB_REFRESH_MAINTENANCE_WORK_MEM", "512MB")


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


def _set_refresh_session(cur) -> None:
    """Ajusta timeout y memoria de sesión para refreshes largos."""
    cur.execute("SET LOCAL statement_timeout = %s", (str(REFRESH_TIMEOUT_MS),))
    try:
        cur.execute("SET LOCAL work_mem = %s", (REFRESH_WORK_MEM,))
        cur.execute("SET LOCAL maintenance_work_mem = %s", (REFRESH_MAINTENANCE_WORK_MEM,))
    except Exception as e:
        logger.debug("No se pudo setear work_mem/maintenance_work_mem (ignorado): %s", e)


def refresh_mv_if_exists(cur, conn, mv_schema: str, mv_name: str) -> Tuple[bool, Optional[str]]:
    """Refresca MV si existe. Retorna (ok, error_message). Timeout y memoria configurables."""
    if not _object_exists(cur, mv_schema, mv_name, "materialized view"):
        return False, None  # no existe, no error
    full = f"{mv_schema}.{mv_name}"
    try:
        _set_refresh_session(cur)
        cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {full}")
        conn.commit()
        return True, None
    except Exception as e:
        err = str(e).lower()
        conn.rollback()
        if "not been populated" in err or "concurrently cannot be used" in err:
            try:
                _set_refresh_session(cur)
                cur.execute(f"REFRESH MATERIALIZED VIEW {mv_schema}.{mv_name}")
                conn.commit()
                return True, None
            except Exception as e2:
                conn.rollback()
                return False, str(e2)
        return False, str(e)


def run_validations(cur) -> Dict[str, Any]:
    """Validaciones rápidas: dimensiones pobladas, vista consultable."""
    val: Dict[str, Any] = {"dims_populated": False, "view_select_ok": False, "canonical_no_dupes": None}
    try:
        cur.execute("SELECT COUNT(*) AS n FROM canon.dim_service_type WHERE is_active = true")
        row = cur.fetchone()
        n = row[0] if hasattr(row, "__getitem__") else (row.get("n") if isinstance(row, dict) else 0)
        val["dims_populated"] = n and int(n) > 0
    except Exception:
        val["dims_populated"] = False
    try:
        cur.execute("SELECT real_tipo_servicio_norm, lob_group FROM ops.v_real_trips_with_lob_v2 LIMIT 1")
        cur.fetchone()
        val["view_select_ok"] = True
    except Exception:
        val["view_select_ok"] = False
    # Duplicados: no debe haber confort+ y comfort_plus como distintos en la vista
    try:
        cur.execute("""
            SELECT real_tipo_servicio_norm, COUNT(*) AS c
            FROM ops.v_real_trips_with_lob_v2
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

            # Refresh MVs (solo las que existan)
            if not args.skip_refresh:
                logger.info("Refresh MVs: timeout=%s ms (~%s min), work_mem=%s, maintenance_work_mem=%s",
                            REFRESH_TIMEOUT_MS, REFRESH_TIMEOUT_MS // 60000, REFRESH_WORK_MEM, REFRESH_MAINTENANCE_WORK_MEM)
                for schema, name in MVS_TO_REFRESH:
                    ok, err = refresh_mv_if_exists(cur, conn, schema, name)
                    key = f"{schema}.{name}"
                    if ok:
                        summary["mvs_refreshed"].append(key)
                        logger.info("Refrescada: %s", key)
                    elif err:
                        summary["mvs_failed"].append((key, err))
                        logger.warning("Falló refresh %s: %s", key, err)
                        summary["overall_ok"] = False
                    else:
                        summary["mvs_skipped_not_exist"].append(key)
                        logger.info("Omitida (no existe): %s", key)
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
