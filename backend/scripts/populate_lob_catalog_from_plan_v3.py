"""
Script v3 para poblar ops.lob_catalog desde ops.v_plan_lob_universe_raw (homologación).
Usa la vista que agrega datos desde staging.plan_projection_raw.

⚠️ IMPORTANTE: Solo inserta LOB que existen en el PLAN (desde CSV).
NO crea LOB desde trips_all.
Si no hay datos en staging, NO inserta nada y genera mensaje claro.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def populate_lob_catalog():
    """
    Pobla ops.lob_catalog con LOB únicas desde ops.v_plan_lob_universe_raw.
    """
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Verificar que existe la tabla
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'ops' 
                    AND table_name = 'lob_catalog'
                )
            """)
            if not cursor.fetchone()[0]:
                logger.error("La tabla ops.lob_catalog no existe. Ejecuta la migración 019 primero.")
                return
            
            # Verificar que existe la vista
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_schema = 'ops' 
                    AND table_name = 'v_plan_lob_universe_raw'
                )
            """)
            if not cursor.fetchone()[0]:
                logger.error("La vista ops.v_plan_lob_universe_raw no existe. Ejecuta la migración 021 primero.")
                return
            
            # Contar filas en la vista
            cursor.execute("SELECT COUNT(*) FROM ops.v_plan_lob_universe_raw")
            count_result = cursor.fetchone()
            row_count = count_result[0] if count_result else 0
            
            if row_count == 0:
                logger.warning("⚠️ PLAN LOB source not found or empty; catalog not populated; proceed with REAL-only visibility + unmatched.")
                logger.info("El sistema funcionará en modo REAL-only hasta que se cargue el plan CSV en staging.plan_projection_raw.")
                return
            
            logger.info(f"Encontradas {row_count} LOB únicas en ops.v_plan_lob_universe_raw")
            
            # Extraer LOB únicas desde la vista
            logger.info("Extrayendo LOB únicas desde ops.v_plan_lob_universe_raw...")
            query = """
                INSERT INTO ops.lob_catalog (lob_name, country, city, source, status)
                SELECT 
                    plan_lob_name as lob_name,
                    country,
                    city,
                    'plan_csv',
                    'active'
                FROM ops.v_plan_lob_universe_raw
                GROUP BY country, city, plan_lob_name
                ORDER BY country, city, plan_lob_name
                ON CONFLICT (lob_name, country, city) DO UPDATE
                SET status = 'active',
                    source = 'plan_csv'
            """
            
            cursor.execute(query)
            inserted = cursor.rowcount
            
            conn.commit()
            logger.info(f"✅ Catálogo poblado: {inserted} LOB insertadas/actualizadas")
            
            # Mostrar resumen
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(DISTINCT country) as countries,
                    COUNT(DISTINCT city) as cities,
                    COUNT(DISTINCT lob_name) as lob_names
                FROM ops.lob_catalog
                WHERE status = 'active'
            """)
            summary = cursor.fetchone()
            logger.info(f"📊 Resumen del catálogo:")
            logger.info(f"   Total LOB activas: {summary[0]}")
            logger.info(f"   Países: {summary[1]}")
            logger.info(f"   Ciudades: {summary[2]}")
            logger.info(f"   Nombres únicos de LOB: {summary[3]}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error al poblar catálogo: {e}")
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    populate_lob_catalog()
