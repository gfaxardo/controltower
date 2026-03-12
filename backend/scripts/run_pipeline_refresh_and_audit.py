"""
Pipeline unificado: refresca derivados en orden y ejecuta auditoría de freshness.
Orden: 1) Backfill Real LOB (mes actual + anterior), 2) Refresh Driver Lifecycle MVs,
       3) Refresh Supply MVs, 4) Run data freshness audit.

Uso: cd backend && python -m scripts.run_pipeline_refresh_and_audit

Opciones:
  --skip-backfill     Omitir backfill Real LOB (solo refresh MVs + audit).
  --skip-driver       Omitir refresh driver lifecycle.
  --skip-supply       Omitir refresh supply.
  --skip-audit        Omitir ejecución del audit (solo refrescos).
  --backfill-months N Meses a backfillar desde hoy hacia atrás (default: 2 = actual + anterior).

Diseñado para cron diario tras carga de viajes. Deja evidencia en ops.data_freshness_audit.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def _last_day_of_month(d: date) -> date:
    if d.month == 12:
        next_ = d.replace(year=d.year + 1, month=1)
    else:
        next_ = d.replace(month=d.month + 1)
    return next_ - timedelta(days=1)


def run_backfill(months_back: int = 2) -> bool:
    """Ejecuta backfill Real LOB para los últimos N meses (incluye mes actual)."""
    today = date.today()
    start = _first_day_of_month(today)
    to_d = _last_day_of_month(today)
    from_d = start
    for _ in range(months_back):
        from_d = _first_day_of_month(from_d - timedelta(days=1))
    from_str = from_d.strftime("%Y-%m-%d")
    to_str = to_d.strftime("%Y-%m-%d")
    logger.info("Backfill Real LOB: --from %s --to %s (resume=true)", from_str, to_str)
    r = subprocess.run(
        [sys.executable, "-m", "scripts.backfill_real_lob_mvs", "--from", from_str, "--to", to_str, "--resume", "true"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if r.returncode != 0:
        logger.error("Backfill falló: %s", r.stderr or r.stdout)
        return False
    logger.info("Backfill OK")
    return True


def run_refresh_driver_lifecycle() -> bool:
    """Ejecuta ops.refresh_driver_lifecycle_mvs() con statement_timeout=0 para evitar cancelación en MVs grandes."""
    try:
        from app.settings import settings
        import psycopg2

        params = {
            "host": settings.DB_HOST or "localhost",
            "port": settings.DB_PORT or 5432,
            "dbname": settings.DB_NAME or "yego_integral",
            "user": settings.DB_USER or "",
            "password": settings.DB_PASSWORD or "",
            "options": "-c statement_timeout=0 -c lock_timeout=0",
        }
        conn = psycopg2.connect(**params)
        conn.autocommit = False
        try:
            cur = conn.cursor()
            cur.execute("SELECT ops.refresh_driver_lifecycle_mvs()")
            conn.commit()
            cur.close()
            logger.info("Refresh Driver Lifecycle MVs OK")
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.exception("Refresh driver lifecycle falló: %s", e)
        return False


def run_refresh_supply() -> bool:
    """Ejecuta ops.refresh_supply_alerting_mvs() vía servicio."""
    try:
        from app.services.supply_service import refresh_supply_alerting_mvs

        refresh_supply_alerting_mvs()
        logger.info("Refresh Supply MVs OK")
        return True
    except Exception as e:
        logger.exception("Refresh supply falló: %s", e)
        return False


def run_audit() -> bool:
    """Ejecuta run_data_freshness_audit y escribe en ops.data_freshness_audit."""
    logger.info("Ejecutando auditoría de freshness...")
    r = subprocess.run(
        [sys.executable, "-m", "scripts.run_data_freshness_audit"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if r.returncode != 0:
        logger.error("Audit falló: %s", r.stderr or r.stdout)
        return False
    if r.stdout:
        for line in r.stdout.strip().split("\n"):
            logger.info("  %s", line)
    logger.info("Auditoría escrita en ops.data_freshness_audit")
    return True


def main() -> None:
    from app.db.connection import init_db_pool

    init_db_pool()

    parser = argparse.ArgumentParser(description="Pipeline refresh + audit")
    parser.add_argument("--skip-backfill", action="store_true", help="No ejecutar backfill Real LOB")
    parser.add_argument("--skip-driver", action="store_true", help="No ejecutar refresh driver lifecycle")
    parser.add_argument("--skip-supply", action="store_true", help="No ejecutar refresh supply")
    parser.add_argument("--skip-audit", action="store_true", help="No ejecutar audit")
    parser.add_argument("--backfill-months", type=int, default=2, help="Meses a backfillar (default 2)")
    args = parser.parse_args()

    ok = True
    if not args.skip_backfill:
        ok = run_backfill(months_back=args.backfill_months) and ok
    else:
        logger.info("Skip backfill (--skip-backfill)")

    if not args.skip_driver:
        ok = run_refresh_driver_lifecycle() and ok
    else:
        logger.info("Skip driver lifecycle (--skip-driver)")

    if not args.skip_supply:
        ok = run_refresh_supply() and ok
    else:
        logger.info("Skip supply (--skip-supply)")

    if not args.skip_audit:
        ok = run_audit() and ok
    else:
        logger.info("Skip audit (--skip-audit)")

    if not ok:
        sys.exit(1)
    logger.info("Pipeline refresh + audit completado.")


if __name__ == "__main__":
    main()
