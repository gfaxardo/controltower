"""
Script para verificar qué LOB hay en el plan.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_plan_lob():
    """Verifica qué LOB hay en el plan."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Verificar si existe la tabla
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'plan' 
                    AND table_name = 'plan_long_valid'
                )
            """)
            if not cursor.fetchone()[0]:
                logger.error("La tabla plan.plan_long_valid no existe.")
                return
            
            # Contar total de filas
            cursor.execute("SELECT COUNT(*) FROM plan.plan_long_valid")
            total_rows = cursor.fetchone()[0]
            logger.info(f"Total de filas en plan.plan_long_valid: {total_rows}")
            
            # Verificar LOB únicas
            cursor.execute("""
                SELECT DISTINCT
                    COALESCE(line_of_business, '') as lob_name,
                    COALESCE(country, '') as country,
                    COALESCE(city, '') as city
                FROM plan.plan_long_valid
                ORDER BY COALESCE(country, ''), COALESCE(city, ''), COALESCE(line_of_business, '')
            """)
            
            lob_rows = cursor.fetchall()
            logger.info(f"Encontradas {len(lob_rows)} combinaciones únicas de LOB")
            
            if lob_rows:
                logger.info("\nPrimeras 10 combinaciones:")
                for i, (lob, country, city) in enumerate(lob_rows[:10], 1):
                    logger.info(f"  {i}. {country} / {city} / {lob}")
            else:
                logger.warning("No se encontraron LOB en el plan. Verifica que hayas cargado el plan.")
            
            # Verificar filas con LOB vacío
            cursor.execute("""
                SELECT COUNT(*) 
                FROM plan.plan_long_valid
                WHERE COALESCE(line_of_business, '') = ''
            """)
            empty_lob = cursor.fetchone()[0]
            if empty_lob > 0:
                logger.warning(f"Hay {empty_lob} filas con line_of_business vacío")
            
        except Exception as e:
            logger.error(f"Error al verificar LOB del plan: {e}")
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    check_plan_lob()
