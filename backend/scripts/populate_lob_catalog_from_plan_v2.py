"""
Script mejorado para poblar ops.lob_catalog desde el plan con auto-discovery.
Busca automáticamente dónde están las LOB del plan y las extrae.

⚠️ IMPORTANTE: Solo inserta LOB que existen en el PLAN.
NO crea LOB desde trips_all.
Si no encuentra fuente del plan, NO inserta nada y genera mensaje claro.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def discover_plan_lob_source():
    """
    Descubre automáticamente dónde están las LOB del plan.
    Retorna (schema, table, lob_column, country_column, city_column) o None.
    """
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Buscar en schemas relevantes
            schemas_to_check = ['plan', 'canon', 'ops']
            
            for schema in schemas_to_check:
                try:
                    cursor.execute("""
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = %s
                        ORDER BY table_name
                    """, (schema,))
                    
                    tables = cursor.fetchall()
                except:
                    continue
                
                for table_row in tables:
                    table_name = table_row[0] if isinstance(table_row, tuple) else table_row
                    
                    # Buscar columnas LOB
                    try:
                        cursor.execute("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = %s
                            AND table_name = %s
                            AND (
                                column_name ILIKE '%line_of_business%'
                                OR column_name ILIKE '%lob%'
                            )
                            LIMIT 1
                        """, (schema, table_name))
                        
                        lob_result = cursor.fetchone()
                        if not lob_result:
                            continue
                        
                        lob_column = lob_result[0]
                        
                        # Buscar country y city (también buscar variantes)
                        cursor.execute("""
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema = %s
                            AND table_name = %s
                            AND (
                                column_name ILIKE 'country%'
                                OR column_name ILIKE 'city%'
                            )
                            ORDER BY column_name
                        """, (schema, table_name))
                        
                        geo_cols = cursor.fetchall()
                        country_col = None
                        city_col = None
                        
                        for col_row in geo_cols:
                            col = col_row[0] if isinstance(col_row, tuple) else col_row
                            col_lower = col.lower()
                            if col_lower == 'country' or col_lower.startswith('country'):
                                country_col = col
                            elif col_lower == 'city' or col_lower.startswith('city'):
                                city_col = col
                        
                        # Verificar que tiene filas
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table_name}")
                            count_result = cursor.fetchone()
                            row_count = count_result[0] if count_result else 0
                        except:
                            row_count = 0
                        
                        if row_count > 0:
                            logger.info(f"✅ Fuente encontrada: {schema}.{table_name} ({row_count} filas)")
                            return (schema, table_name, lob_column, country_col, city_col)
                    except Exception as e:
                        logger.debug(f"Error al inspeccionar {schema}.{table_name}: {e}")
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error en auto-discovery: {e}")
            return None
        finally:
            cursor.close()

def populate_lob_catalog():
    """
    Pobla ops.lob_catalog con LOB únicas desde el plan (auto-discovery).
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
            
            # Auto-discovery
            logger.info("🔍 Buscando fuente de LOB del plan...")
            source = discover_plan_lob_source()
            
            if not source:
                logger.warning("⚠️ PLAN LOB source not found or empty; catalog not populated; proceed with REAL-only visibility + unmatched.")
                logger.info("El sistema funcionará en modo REAL-only hasta que se cargue el plan.")
                return
            
            schema, table, lob_col, country_col, city_col = source
            
            # Construir query dinámica
            select_parts = [
                f"COALESCE({lob_col}, '') as lob_name"
            ]
            
            if country_col:
                select_parts.append(f"COALESCE({country_col}, '') as country")
            else:
                select_parts.append("'' as country")
            
            if city_col:
                select_parts.append(f"COALESCE({city_col}, '') as city")
            else:
                select_parts.append("'' as city")
            
            select_clause = ", ".join(select_parts)
            
            # Extraer LOB únicas
            logger.info(f"Extrayendo LOB únicas desde {schema}.{table}...")
            query = f"""
                INSERT INTO ops.lob_catalog (lob_name, country, city, source, status)
                SELECT 
                    lob_name,
                    country,
                    city,
                    'plan',
                    'active'
                FROM (
                    SELECT DISTINCT
                        {select_clause}
                    FROM {schema}.{table}
                    WHERE COALESCE({lob_col}, '') != ''
                ) s
                GROUP BY lob_name, country, city
                ORDER BY country, city, lob_name
                ON CONFLICT (lob_name, country, city) DO UPDATE
                SET status = 'active',
                    source = 'plan'
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
