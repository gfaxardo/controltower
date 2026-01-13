from app.db.connection import get_db
from app.settings import settings
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    'dim.dim_park': {'park_id', 'city', 'country', 'default_line_of_business'},
    'bi.real_monthly_agg': {'park_id', 'year', 'month', 'orders_completed'},
    'bi.real_daily_enriched': {'park_id', 'date', 'orders_completed'}
}

def verify_schema() -> Dict[str, List[Dict]]:
    """
    Verifica que las tablas tengan las columnas mínimas requeridas.
    Retorna un diccionario con las estructuras de las tablas.
    """
    table_structures = {}
    missing_columns = {}
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            for table_key in REQUIRED_COLUMNS.keys():
                schema, table = table_key.split('.')
                required = REQUIRED_COLUMNS[table_key]
                
                try:
                    cursor.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                    """, (schema, table))
                    
                    columns = cursor.fetchall()
                    found_columns = {col[0] for col in columns}
                    
                    table_structures[table_key] = [
                        {
                            'name': col[0],
                            'type': col[1],
                            'nullable': col[2] == 'YES'
                        }
                        for col in columns
                    ]
                    
                    missing = required - found_columns
                    if missing:
                        missing_columns[table_key] = list(missing)
                    
                    logger.info(f"Tabla {table_key}: {len(columns)} columnas encontradas")
                    if missing:
                        logger.warning(f"Tabla {table_key}: Faltan columnas: {missing}")
                    
                except Exception as e:
                    logger.error(f"Error al inspeccionar {table_key}: {e}")
                    missing_columns[table_key] = [f"Error: {str(e)}"]
            
            cursor.close()
            
            if missing_columns and settings.ENVIRONMENT == 'dev':
                error_msg = "Columnas críticas faltantes:\n"
                for table, missing in missing_columns.items():
                    error_msg += f"  {table}: {missing}\n"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info("Verificación de esquema completada exitosamente")
            return table_structures
            
    except Exception as e:
        logger.error(f"Error en verificación de esquema: {e}")
        raise

def inspect_revenue_column() -> bool:
    """
    Inspecciona si existe una columna de revenue en bi.real_monthly_agg.
    Retorna True si existe, False si no.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'bi' 
                AND table_name = 'real_monthly_agg'
                AND (
                    column_name ILIKE '%revenue%' 
                    OR column_name ILIKE '%ingreso%'
                    OR column_name ILIKE '%income%'
                );
            """)
            result = cursor.fetchone()
            cursor.close()
            
            has_revenue = result is not None
            if has_revenue:
                logger.info(f"Columna de revenue encontrada: {result[0]}")
            else:
                logger.info("No se encontró columna de revenue en bi.real_monthly_agg")
            
            return has_revenue
    except Exception as e:
        logger.warning(f"Error al inspeccionar columna revenue: {e}")
        return False

def inspect_real_columns() -> Dict[str, any]:
    """
    Inspecciona y documenta las columnas reales de las tablas de datos.
    Ejecuta queries de muestra y loggea la estructura completa.
    Retorna diccionario con información de columnas detectadas.
    """
    inspection_results = {
        'real_monthly_agg': {
            'sample_rows': [],
            'columns': [],
            'trips_column': None,
            'revenue_column': None,
            'period_format': 'year/month'
        },
        'real_daily_enriched': {
            'sample_rows': [],
            'columns': [],
            'trips_column': None
        },
        'dim_park': {
            'sample_rows': [],
            'columns': []
        }
    }
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            logger.info("=" * 80)
            logger.info("INSPECCIÓN DE COLUMNAS REALES")
            logger.info("=" * 80)
            
            try:
                cursor.execute("SELECT * FROM bi.real_monthly_agg LIMIT 5;")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                inspection_results['real_monthly_agg']['columns'] = columns
                inspection_results['real_monthly_agg']['sample_rows'] = [
                    dict(zip(columns, row)) for row in rows
                ]
                
                logger.info(f"\nbi.real_monthly_agg - Columnas encontradas ({len(columns)}):")
                for col in columns:
                    logger.info(f"  - {col}")
                
                if 'orders_completed' in columns:
                    inspection_results['real_monthly_agg']['trips_column'] = 'orders_completed'
                    logger.info(f"\n✓ Columna de trips detectada: orders_completed")
                else:
                    logger.warning("⚠ No se encontró columna 'orders_completed' para trips")
                
                revenue_cols = [c for c in columns if any(term in c.lower() for term in ['revenue', 'ingreso', 'income'])]
                if revenue_cols:
                    inspection_results['real_monthly_agg']['revenue_column'] = revenue_cols[0]
                    logger.info(f"✓ Columna de revenue detectada: {revenue_cols[0]}")
                else:
                    inspection_results['real_monthly_agg']['revenue_column'] = None
                    logger.info("ℹ No se encontró columna de revenue (se usará null)")
                
                if 'year' in columns and 'month' in columns:
                    logger.info(f"✓ Period construido desde: year + month (formato YYYY-MM)")
                else:
                    logger.warning("⚠ No se encontraron columnas 'year' y 'month' para construir period")
                
                if rows:
                    logger.info(f"\nMuestra de datos (primer registro):")
                    sample = dict(zip(columns, rows[0]))
                    for key, value in list(sample.items())[:10]:
                        logger.info(f"  {key}: {value}")
                
            except Exception as e:
                logger.error(f"Error al inspeccionar bi.real_monthly_agg: {e}")
            
            try:
                cursor.execute("SELECT * FROM bi.real_daily_enriched LIMIT 5;")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                inspection_results['real_daily_enriched']['columns'] = columns
                inspection_results['real_daily_enriched']['sample_rows'] = [
                    dict(zip(columns, row)) for row in rows
                ]
                
                logger.info(f"\nbi.real_daily_enriched - Columnas encontradas ({len(columns)}):")
                for col in columns:
                    logger.info(f"  - {col}")
                
                if 'orders_completed' in columns:
                    inspection_results['real_daily_enriched']['trips_column'] = 'orders_completed'
                    logger.info(f"✓ Columna de trips detectada: orders_completed")
                
                if rows:
                    logger.info(f"\nMuestra de datos (primer registro):")
                    sample = dict(zip(columns, rows[0]))
                    for key, value in list(sample.items())[:10]:
                        logger.info(f"  {key}: {value}")
                
            except Exception as e:
                logger.error(f"Error al inspeccionar bi.real_daily_enriched: {e}")
            
            try:
                cursor.execute("SELECT * FROM dim.dim_park LIMIT 5;")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                inspection_results['dim_park']['columns'] = columns
                inspection_results['dim_park']['sample_rows'] = [
                    dict(zip(columns, row)) for row in rows
                ]
                
                logger.info(f"\ndim.dim_park - Columnas encontradas ({len(columns)}):")
                for col in columns:
                    logger.info(f"  - {col}")
                
                required_dims = ['park_id', 'city', 'country', 'default_line_of_business']
                found_dims = [d for d in required_dims if d in columns]
                if len(found_dims) == len(required_dims):
                    logger.info(f"✓ Todas las columnas dimensionales requeridas encontradas")
                else:
                    missing = set(required_dims) - set(found_dims)
                    logger.warning(f"⚠ Faltan columnas dimensionales: {missing}")
                
                if rows:
                    logger.info(f"\nMuestra de datos (primer registro):")
                    sample = dict(zip(columns, rows[0]))
                    for key, value in list(sample.items())[:10]:
                        logger.info(f"  {key}: {value}")
                
            except Exception as e:
                logger.error(f"Error al inspeccionar dim.dim_park: {e}")
            
            cursor.close()
            
            try:
                cursor.execute("""
                    SELECT DISTINCT 
                        COALESCE(d.default_line_of_business, '') as line_of_business,
                        COUNT(DISTINCT d.park_id) as park_count
                    FROM bi.real_monthly_agg r
                    LEFT JOIN dim.dim_park d ON r.park_id = d.park_id
                    WHERE r.year = 2025
                    AND COALESCE(r.orders_completed, 0) > 0
                    AND COALESCE(d.default_line_of_business, '') != ''
                    GROUP BY d.default_line_of_business
                    ORDER BY line_of_business
                """)
                lines_of_business = cursor.fetchall()
                
                logger.info(f"\nLíneas de negocio en universo operativo 2025:")
                for line, count in lines_of_business:
                    logger.info(f"  - '{line}' ({count} parques)")
                
                inspection_results['universe_lines_of_business'] = [line[0] for line in lines_of_business if line[0]]
                
            except Exception as e:
                logger.warning(f"Error al obtener líneas de negocio del universo: {e}")
            
            logger.info("=" * 80)
            logger.info("INSPECCIÓN COMPLETADA")
            logger.info("=" * 80)
            
            return inspection_results
            
    except Exception as e:
        logger.error(f"Error en inspección de columnas reales: {e}")
        raise

