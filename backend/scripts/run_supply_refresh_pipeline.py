#!/usr/bin/env python3
"""
Pipeline de refresh del módulo Driver Supply Dynamics.
Ejecuta ops.refresh_supply_alerting_mvs() en orden, registra en ops.supply_refresh_log
y reporta freshness al final.

Uso (desde backend/):
  python -m scripts.run_supply_refresh_pipeline
  python scripts/run_supply_refresh_pipeline.py

Requisito: migración 066_supply_refresh_log aplicada (tabla ops.supply_refresh_log).
Si la tabla no existe, el refresh se ejecuta igual pero no se escribe log.
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
from app.services.supply_service import refresh_supply_alerting_mvs, get_supply_freshness
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    init_db_pool()
    run_id = None

    from app.services.refresh_control_service import refresh_guard, _compute_lock_key

    with refresh_guard(
        refresh_name="supply_refresh_pipeline",
        pipeline_name="supply_refresh",
        trigger_source="manual",
        grain="weekly",
        period_status="mixed",
    ) as guard:
        if guard.skipped:
            logger.info("Supply refresh SKIPPED: otro refresh ya está en curso (lock held).")
            print("SKIPPED: otro refresh ya está en curso")
            return

        try:
            with get_db() as conn:
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT INTO ops.supply_refresh_log (started_at, finished_at, status)
                        VALUES (now(), NULL, 'running')
                        RETURNING id
                    """)
                    row = cur.fetchone()
                    run_id = row[0] if row else None
                    conn.commit()
                    logger.info("Pipeline iniciado run_id=%s", run_id)
                except Exception as e:
                    conn.rollback()
                    logger.warning("No se pudo registrar inicio en supply_refresh_log (¿migración 066?): %s", e)

            # Step 1: Refresh encadenado (4 MVs vía ops.refresh_supply_alerting_mvs)
            logger.info("Ejecutando ops.refresh_supply_alerting_mvs()...")
            refresh_supply_alerting_mvs()
            logger.info("Step 1: refresh_supply_alerting_mvs OK.")

            # Step 2: Verify supply serving views (Fase 1B.2)
            # Las views ops.v_supply_weekly_serving y ops.v_supply_monthly_serving son VIEWS
            # que agregan desde las MVs ya refrescadas en step 1. No requieren refresh adicional.
            try:
                logger.info("Verificando serving views de supply...")
                with get_db() as conn2:
                    cur2 = conn2.cursor()
                    cur2.execute("SELECT MAX(week_start) FROM ops.v_supply_weekly_serving")
                    max_w = cur2.fetchone()[0]
                    cur2.execute("SELECT MAX(month_start) FROM ops.v_supply_monthly_serving")
                    max_m = cur2.fetchone()[0]
                    cur2.close()
                logger.info("Step 2: supply serving views OK (weekly max=%s, monthly max=%s).", str(max_w)[:10] if max_w else "NULL", str(max_m)[:7] if max_m else "NULL")
            except Exception as e2:
                logger.warning("Supply serving views verification falló: %s", e2)

            # Marcar éxito en log
            if run_id is not None:
                with get_db() as conn:
                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            UPDATE ops.supply_refresh_log
                            SET finished_at = now(), status = 'ok', error_message = NULL
                            WHERE id = %s
                        """, (run_id,))
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        logger.warning("No se pudo actualizar supply_refresh_log: %s", e)

            # Freshness final
            freshness = get_supply_freshness()
            logger.info(
                "Freshness: last_week_available=%s last_refresh=%s status=%s",
                freshness.get("last_week_available"),
                freshness.get("last_refresh"),
                freshness.get("status"),
            )
            print("OK")
            print(f"last_week_available={freshness.get('last_week_available')}")
            print(f"last_refresh={freshness.get('last_refresh')}")
            print(f"status={freshness.get('status')}")

        except Exception as e:
            logger.exception("Error en pipeline de supply: %s", e)
            if run_id is not None:
                try:
                    with get_db() as conn:
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE ops.supply_refresh_log
                            SET finished_at = now(), status = 'error', error_message = %s
                            WHERE id = %s
                        """, (str(e)[:500], run_id))
                        conn.commit()
                except Exception as e2:
                    logger.warning("No se pudo registrar error en supply_refresh_log: %s", e2)
            raise


if __name__ == "__main__":
    main()
