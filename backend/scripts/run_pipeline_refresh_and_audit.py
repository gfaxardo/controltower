"""
Pipeline unificado: refresca derivados en orden y ejecuta auditoría de freshness.
Orden: 1) Refresh cadena hourly-first (hour → day → week → month),
       2) Poblar real_drill_dim_fact desde day_v2/week_v3 (rollup = vista desde day_v2),
       3) Refresh Driver Lifecycle MVs, 4) Refresh Supply MVs, 5) Run data freshness audit.

El backfill legacy (backfill_real_lob_mvs) ya no forma parte del camino principal REAL;
real_rollup_day_fact es vista sobre day_v2; real_drill_dim_fact se puebla desde day_v2/week_v3.

Uso: cd backend && python -m scripts.run_pipeline_refresh_and_audit

Opciones:
  --skip-hourly-first   Omitir refresh cadena hourly-first (mv_real_lob_*_v2/v3).
  --skip-drill-populate Omitir población de real_drill_dim_fact desde day_v2/week_v3.
  --skip-driver         Omitir refresh driver lifecycle.
  --skip-supply         Omitir refresh supply.
  --skip-audit          Omitir ejecución del audit (solo refrescos).
  --drill-days N        Ventana días para drill day (default: 120).
  --drill-weeks N       Ventana semanas para drill week (default: 18).

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


def run_populate_drill(days: int = 120, weeks: int = 18, months: int = 6) -> bool:
    """Pobla real_drill_dim_fact desde mv_real_lob_day_v2, week_v3 y month_v3 (hourly-first)."""
    logger.info("Poblando real_drill_dim_fact desde day_v2/week_v3/month_v3 (days=%s, weeks=%s, months=%s)...", days, weeks, months)
    r = subprocess.run(
        [
            sys.executable, "-m", "scripts.populate_real_drill_from_hourly_chain",
            "--days", str(days), "--weeks", str(weeks), "--months", str(months),
        ],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if r.returncode != 0:
        logger.error("Populate drill falló: %s", r.stderr or r.stdout)
        return False
    logger.info("Populate drill OK")
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


def run_hourly_first_chain() -> bool:
    """Ejecuta refresh de la cadena hourly-first: hour_v2 → day_v2 → week_v3 → month_v3."""
    logger.info("Refresh cadena hourly-first (hour → day → week → month)...")
    r = subprocess.run(
        [sys.executable, "-m", "scripts.refresh_hourly_first_chain"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=7200,
    )
    if r.returncode != 0:
        logger.error("Hourly-first chain falló: %s", r.stderr or r.stdout)
        return False
    logger.info("Hourly-first chain OK")
    return True


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


def run_trips_2026_coverage_audit() -> bool:
    """Auditoría de cobertura comercial trips_2026 (comision_empresa_asociada, pago_corporativo). Falla si cae bajo umbral."""
    logger.info("Ejecutando auditoría de cobertura comercial trips_2026...")
    r = subprocess.run(
        [sys.executable, "-m", "scripts.audit_trips_2026_commercial_coverage", "--weeks", "4"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        logger.error("Cobertura comercial trips_2026 FAIL: %s", r.stderr or r.stdout)
        return False
    logger.info("Cobertura comercial trips_2026 OK")
    return True


def run_margin_quality_audit() -> bool:
    """Ejecuta auditoría de huecos de margen en fuente REAL y escribe en ops.real_margin_quality_audit."""
    logger.info("Ejecutando auditoría de calidad de margen (REAL)...")
    r = subprocess.run(
        [sys.executable, "-m", "scripts.audit_real_margin_source_gaps", "--days", "90", "--persist"],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if r.returncode not in (0, 1, 2):
        logger.warning("Margin quality audit terminó con código %s: %s", r.returncode, r.stderr or r.stdout)
    if r.stdout:
        for line in r.stdout.strip().split("\n")[-15:]:
            logger.info("  %s", line)
    logger.info("Auditoría de margen ejecutada (ops.real_margin_quality_audit si existe tabla)")
    return True


def main() -> None:
    from app.db.connection import init_db_pool

    init_db_pool()

    parser = argparse.ArgumentParser(description="Pipeline refresh + audit")
    parser.add_argument("--skip-hourly-first", action="store_true", help="No ejecutar refresh cadena hourly-first")
    parser.add_argument("--skip-drill-populate", action="store_true", help="No poblar real_drill_dim_fact desde day_v2/week_v3")
    parser.add_argument("--skip-driver", action="store_true", help="No ejecutar refresh driver lifecycle")
    parser.add_argument("--skip-supply", action="store_true", help="No ejecutar refresh supply")
    parser.add_argument("--skip-audit", action="store_true", help="No ejecutar audit")
    parser.add_argument("--skip-coverage-audit", action="store_true", help="No ejecutar auditoría cobertura trips_2026")
    parser.add_argument("--drill-days", type=int, default=120, help="Ventana días para drill (default 120)")
    parser.add_argument("--drill-weeks", type=int, default=18, help="Ventana semanas para drill (default 18)")
    parser.add_argument("--drill-months", type=int, default=6, help="Ventana meses para drill (default 6)")
    args = parser.parse_args()

    ok = True
    if not getattr(args, "skip_hourly_first", False):
        ok = run_hourly_first_chain() and ok
    else:
        logger.info("Skip hourly-first chain (--skip-hourly-first)")
    if not getattr(args, "skip_drill_populate", False):
        ok = run_populate_drill(days=args.drill_days, weeks=args.drill_weeks, months=args.drill_months) and ok
    else:
        logger.info("Skip drill populate (--skip-drill-populate)")

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
        if not getattr(args, "skip_coverage_audit", False):
            ok = run_trips_2026_coverage_audit() and ok
        ok = run_margin_quality_audit() and ok
    else:
        logger.info("Skip audit (--skip-audit)")

    if not ok:
        sys.exit(1)
    logger.info("Pipeline refresh + audit completado.")


if __name__ == "__main__":
    main()
