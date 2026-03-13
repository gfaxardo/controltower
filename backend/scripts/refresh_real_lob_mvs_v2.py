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

from app.db.connection import get_db, init_db_pool
from app.services.observability_service import log_refresh

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MV_MONTHLY = "ops.mv_real_lob_month_v2"
MV_WEEKLY = "ops.mv_real_lob_week_v2"
REFRESH_TIMEOUT_MS = 600000


def _refresh_one(cur, conn, mv_name: str) -> None:
    cur.execute("SET statement_timeout = %s", (str(REFRESH_TIMEOUT_MS),))
    try:
        cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")
        logger.info("Refrescando %s (CONCURRENTLY)...", mv_name)
    except Exception as e:
        err_msg = str(e).lower()
        if "not been populated" in err_msg or "concurrently cannot be used" in err_msg:
            conn.rollback()
            cur.execute("SET statement_timeout = %s", (str(REFRESH_TIMEOUT_MS),))
            logger.info("Refrescando %s (primera población, sin CONCURRENTLY)...", mv_name)
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv_name}")
        else:
            raise
    conn.commit()


def main():
    init_db_pool()
    script_name = "refresh_real_lob_mvs_v2.py"
    try:
        log_refresh(MV_MONTHLY, status="running", script_name=script_name, trigger_type="script")
        with get_db() as conn:
            cur = conn.cursor()
            _refresh_one(cur, conn, MV_MONTHLY)
            log_refresh(MV_MONTHLY, status="ok", script_name=script_name, trigger_type="script")
            log_refresh(MV_WEEKLY, status="running", script_name=script_name, trigger_type="script")
            _refresh_one(cur, conn, MV_WEEKLY)
            log_refresh(MV_WEEKLY, status="ok", script_name=script_name, trigger_type="script")
            cur.close()
        logger.info("Refresh de Real LOB v2 MVs completado correctamente.")
    except Exception as e:
        logger.exception("Error al refrescar Real LOB v2 MVs: %s", e)
        log_refresh(MV_MONTHLY, status="error", script_name=script_name, error_message=str(e)[:500])
        log_refresh(MV_WEEKLY, status="error", script_name=script_name, error_message=str(e)[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
