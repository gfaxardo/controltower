"""
Orquestación de refresh de la cadena hourly-first.
Orden: REFRESH hour_v2 → day_v2 → week_v3 → month_v3.
Cada capa depende de la anterior; no se debe refrescar week/month desde fact.

Uso: cd backend && python -m scripts.refresh_hourly_first_chain
  --skip-hour  (solo day/week/month, si hour ya está fresco)
  --timeout 3600  (segundos por REFRESH, default 1800)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MV_HOUR = "ops.mv_real_lob_hour_v2"
MV_DAY = "ops.mv_real_lob_day_v2"
MV_WEEK = "ops.mv_real_lob_week_v3"
MV_MONTH = "ops.mv_real_lob_month_v3"
CHAIN = [
    ("hour", MV_HOUR),
    ("day", MV_DAY),
    ("week", MV_WEEK),
    ("month", MV_MONTH),
]


def _refresh_one(conn, full_name: str, timeout_sec: int, concurrent: bool) -> None:
    cur = conn.cursor()
    cur.execute("SET statement_timeout = %s", (str(timeout_sec * 1000),))
    if concurrent:
        cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY " + full_name)
    else:
        cur.execute("REFRESH MATERIALIZED VIEW " + full_name)
    cur.close()


def run_refresh(skip_hour: bool, timeout_sec: int) -> bool:
    import psycopg2
    from app.db.connection import init_db_pool, _get_connection_params

    init_db_pool()
    params = dict(_get_connection_params())
    params["options"] = (params.get("options") or "").strip()
    start = 0 if not skip_hour else 1
    for name, mv in CHAIN[start:]:
        full_name = mv
        logger.info("REFRESH MATERIALIZED VIEW CONCURRENTLY %s (timeout=%ss)", full_name, timeout_sec)
        conn = None
        try:
            conn = psycopg2.connect(**params)
            conn.autocommit = True
            _refresh_one(conn, full_name, timeout_sec, concurrent=True)
            logger.info("OK %s (concurrent)", full_name)
        except Exception as e:
            err_msg = str(e).lower()
            if "concurrently" in err_msg and ("unique index" in err_msg or "objectnotinprerequisitestate" in err_msg or "create a unique index" in err_msg):
                logger.warning("CONCURRENTLY no disponible para %s (índice único requerido), intentando REFRESH sin CONCURRENTLY: %s", full_name, e)
                try:
                    if conn is None:
                        conn = psycopg2.connect(**params)
                        conn.autocommit = True
                    _refresh_one(conn, full_name, timeout_sec, concurrent=False)
                    logger.info("OK %s (no concurrent)", full_name)
                except Exception as e2:
                    logger.exception("FAIL %s: %s", full_name, e2)
                    if conn:
                        conn.close()
                    return False
            else:
                logger.exception("FAIL %s: %s", full_name, e)
                if conn:
                    conn.close()
                return False
        finally:
            if conn:
                conn.close()
    return True


def main():
    ap = argparse.ArgumentParser(description="Refresh cadena hourly-first: hour → day → week → month")
    ap.add_argument("--skip-hour", action="store_true", help="No refrescar hour (solo day/week/month)")
    ap.add_argument("--timeout", type=int, default=1800, help="Timeout por REFRESH en segundos")
    args = ap.parse_args()
    ok = run_refresh(skip_hour=args.skip_hour, timeout_sec=args.timeout)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
