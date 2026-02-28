#!/usr/bin/env python3
"""
Script para refrescar la vista materializada ops.mv_real_trips_weekly
con manejo de timeout. Usa engine propio (pool_size=2, max_overflow=0) y dispose al final.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from sqlalchemy import create_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get_database_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    from app.settings import settings
    return settings.database_url


def refresh_mv_weekly(raw_conn, timeout_seconds=7200):
    """
    Refresca la vista materializada semanal.
    """
    cursor = raw_conn.cursor()
    try:
        cursor.execute(f"SET statement_timeout = '{timeout_seconds * 1000}ms'")
        logger.info("Timeout configurado a %s segundos", timeout_seconds)

        logger.info("Iniciando REFRESH MATERIALIZED VIEW ops.mv_real_trips_weekly...")
        start_time = time.time()

        cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_weekly")
        raw_conn.commit()

        elapsed = time.time() - start_time
        logger.info("Refresh completado en %.2f segundos", elapsed)
        return True, elapsed
    except Exception as e:
        error_msg = str(e)
        logger.error("Refresh fallo: %s", error_msg)
        if "timeout" in error_msg.lower() or "57014" in error_msg:
            logger.error("Timeout detectado. Considera aumentar el timeout.")
        raw_conn.rollback()
        return False, None
    finally:
        cursor.close()


def check_mv_weekly_status(raw_conn):
    """Verifica el estado de la MV semanal"""
    cursor = raw_conn.cursor()
    try:
        cursor.execute("""
            SELECT
                schemaname,
                matviewname,
                hasindexes,
                ispopulated
            FROM pg_matviews
            WHERE schemaname = 'ops'
              AND matviewname = 'mv_real_trips_weekly';
        """)
        mv_info = cursor.fetchone()

        if mv_info:
            logger.info(
                "Vista materializada: %s.%s",
                mv_info[0], mv_info[1],
            )
            logger.info("  Tiene indices: %s", mv_info[2])
            logger.info("  Esta poblada: %s", mv_info[3])
        else:
            logger.warning("MV semanal no existe. Ejecuta la migracion 014 primero.")
            return

        cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_weekly;")
        count = cursor.fetchone()[0]
        logger.info("  Total de registros: %s", f"{count:,}")

        cursor.execute("SELECT MAX(refreshed_at) as last_refresh FROM ops.mv_real_trips_weekly")
        refresh_info = cursor.fetchone()
        if refresh_info and refresh_info[0]:
            logger.info("  Ultima actualizacion: %s", refresh_info[0])
    except Exception as e:
        logger.warning("Error al verificar estado: %s", e)
    finally:
        cursor.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Refrescar vista materializada ops.mv_real_trips_weekly")
    parser.add_argument("--timeout", type=int, default=7200,
                        help="Timeout en segundos (default: 7200 = 2 horas)")
    parser.add_argument("--check-only", action="store_true",
                        help="Solo verificar estado, no refrescar")

    args = parser.parse_args()

    url = _get_database_url()
    if not url or url.startswith("driver://"):
        logger.error("DATABASE_URL no configurada o invalida")
        return 1

    engine = create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    try:
        print("=" * 80)
        print("REFRESH DE VISTA MATERIALIZADA: ops.mv_real_trips_weekly")
        print("=" * 80)

        with engine.connect() as conn:
            raw_conn = conn.connection
            print("\n1. Estado actual de la vista:")
            check_mv_weekly_status(raw_conn)

            if args.check_only:
                print("\n[Modo check-only: no se ejecutara refresh]")
                return 0

            print(f"\n2. Ejecutando refresh (timeout: {args.timeout}s)...")
            success, elapsed = refresh_mv_weekly(raw_conn, args.timeout)

            if success:
                print("\n" + "=" * 80)
                print("REFRESH COMPLETADO EXITOSAMENTE")
                print("=" * 80)
                print(f"Tiempo transcurrido: {elapsed:.2f} segundos")

                print("\n3. Verificando nueva fecha de actualizacion...")
                check_mv_weekly_status(raw_conn)
                return 0
            else:
                print("\n" + "=" * 80)
                print("REFRESH FALLO")
                print("=" * 80)
                return 1
    except Exception as e:
        logger.error("Error general: %s", e)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
