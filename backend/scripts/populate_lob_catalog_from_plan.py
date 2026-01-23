"""
Script para poblar ops.lob_catalog desde plan.plan_long_valid.
Extrae todas las LOB únicas del plan y las inserta en el catálogo canónico.

⚠️ IMPORTANTE: Solo inserta LOB que existen en el PLAN.
NO crea LOB desde trips_all.
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
    Pobla ops.lob_catalog con LOB únicas desde plan.plan_long_valid.
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
            
            # Extraer LOB únicas del plan
            logger.info("Extrayendo LOB únicas desde plan.plan_long_valid...")
            cursor.execute("""
                SELECT DISTINCT
                    COALESCE(line_of_business, '') as lob_name,
                    COALESCE(country, '') as country,
                    COALESCE(city, '') as city
                FROM plan.plan_long_valid
                WHERE COALESCE(line_of_business, '') != ''
                ORDER BY COALESCE(country, ''), COALESCE(city, ''), COALESCE(line_of_business, '')
            """)
            
            lob_rows = cursor.fetchall()
            logger.info(f"Encontradas {len(lob_rows)} combinaciones únicas de LOB en el plan")
            
            # Insertar en el catálogo (ignorar duplicados)
            inserted = 0
            skipped = 0
            
            for lob_name, country, city in lob_rows:
                try:
                    cursor.execute("""
                        INSERT INTO ops.lob_catalog (lob_name, country, city, source, status)
                        VALUES (%s, %s, %s, 'plan', 'active')
                        ON CONFLICT (lob_name, country, city) DO UPDATE
                        SET status = 'active',
                            source = 'plan'
                    """, (lob_name, country, city))
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Error al insertar LOB {lob_name} ({country}, {city}): {e}")
                    skipped += 1
            
            conn.commit()
            logger.info(f"✅ Catálogo poblado: {inserted} LOB insertadas/actualizadas, {skipped} errores")
            
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
