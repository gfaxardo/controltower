"""
Refresh de ops.mv_plan_vs_real_monthly_fact y ops.mv_plan_vs_real_monthly_fact_canonical.

Tras migración 137 (ops.mv_plan_vs_real_monthly_fact) y carga plan/trips, ejecutar para poblar o actualizar el snapshot.
Orden recomendado: tras scripts.refresh_hourly_first_chain (si se desea alinear con real canónica)
y/o tras ingest de staging.plan_projection_realkey_raw; típicamente al final del pipeline diario.

Uso:
  cd backend && python -m scripts.refresh_plan_vs_real_monthly_mvs
  python -m scripts.refresh_plan_vs_real_monthly_mvs --no-concurrent

También: SELECT ops.refresh_plan_vs_real_monthly_facts(FALSE);  (SQL, sin CONCURRENTLY)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    from app.db.connection import init_db_pool
    from app.services.plan_vs_real_service import refresh_plan_vs_real_monthly_materialized_views

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no-concurrent",
        action="store_true",
        help="REFRESH sin CONCURRENTLY (útil si aún no existen índices únicos)",
    )
    args = parser.parse_args()
    init_db_pool()
    refresh_plan_vs_real_monthly_materialized_views(concurrent=not args.no_concurrent)
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
