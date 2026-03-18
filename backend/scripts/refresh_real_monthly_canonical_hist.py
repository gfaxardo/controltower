"""
Refresca ops.mv_real_monthly_canonical_hist (canónica mensual REAL histórica).
Ejecutar tras poblar/actualizar trips_all o trips_2026. Puede ser lento (escanea v_trips_real_canon).
Uso: python -m scripts.refresh_real_monthly_canonical_hist [--timeout 3600]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    ap = argparse.ArgumentParser(description="REFRESH mv_real_monthly_canonical_hist")
    ap.add_argument("--timeout", type=int, default=3600, help="Statement timeout segundos")
    args = ap.parse_args()
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = %s", (str(args.timeout * 1000),))
        logger.info("Refrescando ops.mv_real_monthly_canonical_hist (timeout %ss)...", args.timeout)
        cur.execute("REFRESH MATERIALIZED VIEW ops.mv_real_monthly_canonical_hist")
        cur.close()
    logger.info("OK: mv_real_monthly_canonical_hist refrescada.")


if __name__ == "__main__":
    main()
    sys.exit(0)
