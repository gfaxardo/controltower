"""
Refresca MVs de Real LOB de forma segura: work_mem alto, temp usage logging, orden correcto.
Uso: python -m scripts.safe_refresh_real_lob
Ejecutar tras carga de datos en trips_all/trips_2026 o post-migración 064.
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _log_temp_usage(cur) -> None:
    """Registra temp_files y temp_bytes de pg_stat_database."""
    try:
        cur.execute("""
            SELECT datname, temp_files, pg_size_pretty(temp_bytes) AS temp_bytes
            FROM pg_stat_database WHERE datname = current_database()
        """)
        r = cur.fetchone()
        if r:
            logger.info("TEMP: datname=%s temp_files=%s temp_bytes=%s", r[0], r[1], r[2])
    except Exception as e:
        logger.warning("No se pudo obtener temp usage: %s", e)


def main() -> None:
    from app.settings import settings
    from psycopg2 import OperationalError, ProgrammingError

    conn_params = {
        "host": settings.DB_HOST or "localhost",
        "port": settings.DB_PORT or 5432,
        "dbname": settings.DB_NAME or "",
        "user": settings.DB_USER or "",
        "password": settings.DB_PASSWORD or "",
        "options": "-c statement_timeout=0 -c lock_timeout=0",
    }
    try:
        import psycopg2
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cur = conn.cursor()
        try:
            # Blinda sesión: work_mem, maintenance_work_mem
            cur.execute("SET work_mem = '256MB'")
            cur.execute("SET maintenance_work_mem = '512MB'")
            try:
                cur.execute("SET temp_file_limit = '-1'")
            except Exception:
                pass

            _log_temp_usage(cur)

            # Orden: enriched (base) -> dim_agg (lee de enriched) -> rollup_day (independiente)
            # enriched es el más pesado; dim_agg es ligero (lee tabla materializada)
            mvs = [
                ("ops.mv_real_drill_enriched", False),  # sin unique index, no CONCURRENTLY
                ("ops.mv_real_drill_dim_agg", True),    # con unique index
                ("ops.mv_real_rollup_day", True),       # con unique index
            ]
            for mv_name, use_concurrent in mvs:
                try:
                    logger.info("Refrescando %s...", mv_name)
                    _log_temp_usage(cur)
                    if use_concurrent:
                        try:
                            cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")
                            logger.info("%s refreshed (CONCURRENTLY).", mv_name)
                        except (OperationalError, ProgrammingError) as e:
                            if "concurrent" in (str(e) or "").lower() or "unique" in (str(e) or "").lower():
                                logger.info("Usando REFRESH sin CONCURRENTLY para %s...", mv_name)
                                cur.execute(f"REFRESH MATERIALIZED VIEW {mv_name}")
                                logger.info("%s refreshed.", mv_name)
                            else:
                                raise
                    else:
                        cur.execute(f"REFRESH MATERIALIZED VIEW {mv_name}")
                        logger.info("%s refreshed.", mv_name)
                    _log_temp_usage(cur)
                except Exception as e:
                    logger.exception("ERROR al refrescar %s: %s", mv_name, e)
                    raise RuntimeError(f"MV que falló: {mv_name}") from e

            logger.info("Safe refresh Real LOB completado.")
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        logger.exception("Error al refrescar Real LOB: %s", e)
        raise


if __name__ == "__main__":
    main()
