"""
Refresca ops.mv_real_drill_dim_agg y ops.mv_real_rollup_day para Real LOB Drill PRO.
Uso: desde backend/ ejecutar python -m scripts.refresh_real_lob_drill_pro_mv
Recomendado: cron diario tras carga de datos en trips_all.
Usa conexión directa con statement_timeout=0 para evitar timeout del pool.

PREFERIR: scripts.safe_refresh_real_lob (work_mem alto, temp logging, orden correcto).
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Asegurar que app está en el path
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def main():
    from app.settings import settings
    from psycopg2 import OperationalError, ProgrammingError

    # Conexión directa sin timeout (el pool puede tener statement_timeout por defecto)
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
            # Refresh rollup (sin CONCURRENTLY: el índice único con COALESCE no califica en PG para CONCURRENTLY)
            try:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_rollup_day")
                logger.info("ops.mv_real_rollup_day refreshed (concurrent).")
            except (OperationalError, ProgrammingError) as e:
                if "concurrent" in (str(e) or "").lower() or "unique" in (str(e) or "").lower():
                    logger.info("Usando REFRESH sin CONCURRENTLY para mv_real_rollup_day...")
                    cur.execute("REFRESH MATERIALIZED VIEW ops.mv_real_rollup_day")
                    logger.info("ops.mv_real_rollup_day refreshed.")
                else:
                    raise
            # Refresh drill PRO: primero enriched (base), luego dim_agg (agregados)
            try:
                cur.execute("REFRESH MATERIALIZED VIEW ops.mv_real_drill_enriched")
                logger.info("ops.mv_real_drill_enriched refreshed.")
            except (OperationalError, ProgrammingError) as e:
                raise
            try:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_drill_dim_agg")
                logger.info("ops.mv_real_drill_dim_agg refreshed (concurrent).")
            except (OperationalError, ProgrammingError) as e:
                if "concurrent" in (str(e) or "").lower() or "unique" in (str(e) or "").lower():
                    logger.info("Usando REFRESH sin CONCURRENTLY para mv_real_drill_dim_agg...")
                    cur.execute("REFRESH MATERIALIZED VIEW ops.mv_real_drill_dim_agg")
                    logger.info("ops.mv_real_drill_dim_agg refreshed.")
                else:
                    raise
        finally:
            cur.close()
            conn.close()
        logger.info("Refresh Real LOB Drill PRO MVs completado.")
    except Exception as e:
        logger.exception("Error al refrescar MVs: %s", e)
        raise


if __name__ == "__main__":
    main()
