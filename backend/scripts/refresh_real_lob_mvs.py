#!/usr/bin/env python3
"""
Refresca las Materialized Views de Real LOB para que los endpoints
/ops/real-lob/monthly y /ops/real-lob/weekly devuelvan datos actualizados.
Uso: desde backend/ ejecutar
  python -m scripts.refresh_real_lob_mvs
o: python scripts/refresh_real_lob_mvs.py
Recomendado: ejecutar diariamente (cron o scheduler).
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MV_MONTHLY = "ops.mv_real_trips_by_lob_month"
MV_WEEKLY = "ops.mv_real_trips_by_lob_week"
# Refresh puede tardar; timeout 10 min
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
    try:
        with get_db() as conn:
            cur = conn.cursor()
            _refresh_one(cur, conn, MV_MONTHLY)
            _refresh_one(cur, conn, MV_WEEKLY)
            cur.close()
        logger.info("Refresh de Real LOB MVs completado correctamente.")
    except Exception as e:
        logger.exception("Error al refrescar Real LOB MVs: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
