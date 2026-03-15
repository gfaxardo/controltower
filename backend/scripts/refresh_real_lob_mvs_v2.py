#!/usr/bin/env python3
"""
Refresca las Materialized Views de Real LOB v2 (ops.mv_real_lob_month_v2, ops.mv_real_lob_week_v2).
Uso: desde backend/ ejecutar python -m scripts.refresh_real_lob_mvs_v2
Recomendado: ejecutar diariamente tras ingesta.
"""
import os
import sys
import logging

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

import time

from app.db.connection import get_db, init_db_pool
from app.services.observability_service import log_refresh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MV_MONTHLY = "ops.mv_real_lob_month_v2"
MV_WEEKLY = "ops.mv_real_lob_week_v2"
# CT-MV-PERFORMANCE-HARDENING: 6h timeout, más memoria para evitar spills
REFRESH_TIMEOUT_MS = 21600000  # 6h
REFRESH_WORK_MEM = "512MB"
REFRESH_MAINTENANCE_WORK_MEM = "1GB"


def _set_refresh_session(cur) -> None:
    cur.execute("SET statement_timeout = %s", (str(REFRESH_TIMEOUT_MS),))
    try:
        cur.execute("SET work_mem = %s", (REFRESH_WORK_MEM,))
        cur.execute("SET maintenance_work_mem = %s", (REFRESH_MAINTENANCE_WORK_MEM,))
    except Exception as e:
        logger.debug("Session work_mem/maintenance_work_mem (ignorado): %s", e)


def _get_count(cur, mv_name: str) -> int | None:
    try:
        schema, name = mv_name.split(".", 1)
        cur.execute("SELECT COUNT(*) AS n FROM %s.%s" % (schema, name))
        row = cur.fetchone()
        return int(row[0] if hasattr(row, "__getitem__") else (row.get("n", 0) if isinstance(row, dict) else 0))
    except Exception:
        return None


def _refresh_one(cur, conn, mv_name: str) -> None:
    _set_refresh_session(cur)
    try:
        cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")
        logger.info("Refrescando %s (CONCURRENTLY)...", mv_name)
    except Exception as e:
        err_msg = str(e).lower()
        if "not been populated" in err_msg or "concurrently cannot be used" in err_msg:
            conn.rollback()
            _set_refresh_session(cur)
            logger.info("Refrescando %s (primera población, sin CONCURRENTLY)...", mv_name)
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv_name}")
        else:
            raise
    conn.commit()


def main():
    init_db_pool()
    script_name = "refresh_real_lob_mvs_v2.py"
    try:
        with get_db() as conn:
            cur = conn.cursor()
            # Orden: 1) monthly, 2) weekly (STEP 8)
            for mv_name in (MV_MONTHLY, MV_WEEKLY):
                log_refresh(mv_name, status="running", script_name=script_name, trigger_type="script")
                rows_before = _get_count(cur, mv_name)
                t0 = time.monotonic()
                try:
                    _refresh_one(cur, conn, mv_name)
                    duration_seconds = round(time.monotonic() - t0, 2)
                    rows_after = _get_count(cur, mv_name)
                    log_refresh(mv_name, status="ok", script_name=script_name, trigger_type="script",
                                rows_before=rows_before, rows_after=rows_after, duration_seconds=duration_seconds)
                    logger.info("%s: %.1fs, rows %s -> %s", mv_name, duration_seconds, rows_before, rows_after)
                except Exception as e:
                    log_refresh(mv_name, status="error", script_name=script_name, error_message=str(e)[:500])
                    raise
            cur.close()
        logger.info("Refresh de Real LOB v2 MVs completado correctamente.")
    except Exception as e:
        logger.exception("Error al refrescar Real LOB v2 MVs: %s", e)
        log_refresh(MV_MONTHLY, status="error", script_name=script_name, error_message=str(e)[:500])
        log_refresh(MV_WEEKLY, status="error", script_name=script_name, error_message=str(e)[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
