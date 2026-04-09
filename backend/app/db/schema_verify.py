from app.db.connection import get_db
from app.settings import settings
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    'dim.dim_park': {'park_id', 'city', 'country', 'default_line_of_business'},
    'bi.real_daily_enriched': {'park_id', 'date', 'orders_completed'},
}

OPTIONAL_LEGACY_TABLES = {
    'bi.real_monthly_agg': {'park_id', 'year', 'month', 'orders_completed'},
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

            def _check_table(table_key: str, required: set) -> None:
                schema, table = table_key.split('.')
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
                        {'name': col[0], 'type': col[1], 'nullable': col[2] == 'YES'}
                        for col in columns
                    ]
                    missing = required - found_columns
                    logger.info(f"Tabla {table_key}: {len(columns)} columnas encontradas")
                    if missing:
                        logger.warning(f"Tabla {table_key}: Faltan columnas: {missing}")
                    return missing
                except Exception as e:
                    logger.error(f"Error al inspeccionar {table_key}: {e}")
                    return required

            for table_key, required in REQUIRED_COLUMNS.items():
                missing = _check_table(table_key, required)
                if missing:
                    missing_columns[table_key] = list(missing)

            for table_key, required in OPTIONAL_LEGACY_TABLES.items():
                missing = _check_table(table_key, required)
                if missing:
                    logger.warning(
                        f"Tabla legacy {table_key}: columnas faltantes {list(missing)}. "
                        "No es bloqueante — el sistema actual opera sobre ops.*."
                    )
            
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
    LEGACY — inspecciona revenue en bi.real_monthly_agg.
    bi.real_monthly_agg ya no es source of truth operativo de Control Tower.
    El revenue canónico actual se resuelve desde ops.real_business_slice_*_fact.
    Se mantiene como stub para no romper imports existentes.
    """
    logger.debug(
        "LEGACY_BI_SOURCE_DETECTED: inspect_revenue_column — "
        "bi.real_monthly_agg no es fuente operativa. Retornando False."
    )
    return False

def inspect_real_columns() -> Dict[str, any]:
    """
    Inspecciona y documenta las columnas reales de las tablas de datos vigentes.

    NOTA: bi.real_monthly_agg es legacy y se inspecciona opcionalmente.
    El sistema operativo actual de Control Tower NO depende de ella.
    Las fuentes canónicas son: trips_2025/2026, ops.*, dims canónicas.
    """
    inspection_results: Dict[str, any] = {
        'real_monthly_agg': {
            'sample_rows': [],
            'columns': [],
            'trips_column': None,
            'revenue_column': None,
            'period_format': 'year/month',
            'legacy': True,
        },
        'real_daily_enriched': {
            'sample_rows': [],
            'columns': [],
            'trips_column': None,
        },
        'dim_park': {
            'sample_rows': [],
            'columns': [],
        },
    }

    try:
        with get_db() as conn:
            cursor = conn.cursor()

            logger.info("=" * 60)
            logger.info("INSPECCIÓN DE COLUMNAS REALES")
            logger.info("=" * 60)

            # --- bi.real_monthly_agg (LEGACY, no bloqueante) ---
            try:
                cursor.execute("SELECT * FROM bi.real_monthly_agg LIMIT 5;")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                inspection_results['real_monthly_agg']['columns'] = columns
                inspection_results['real_monthly_agg']['sample_rows'] = [
                    dict(zip(columns, row)) for row in rows
                ]
                logger.info(f"bi.real_monthly_agg (LEGACY): {len(columns)} columnas")
            except Exception as e:
                logger.warning(
                    "LEGACY_BI_SOURCE_DETECTED: bi.real_monthly_agg no disponible (%s). "
                    "No es bloqueante — el sistema actual opera sobre ops.*.",
                    e,
                )

            # --- bi.real_daily_enriched ---
            try:
                cursor.execute("SELECT * FROM bi.real_daily_enriched LIMIT 5;")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                inspection_results['real_daily_enriched']['columns'] = columns
                inspection_results['real_daily_enriched']['sample_rows'] = [
                    dict(zip(columns, row)) for row in rows
                ]
                if 'orders_completed' in columns:
                    inspection_results['real_daily_enriched']['trips_column'] = 'orders_completed'
                logger.info(f"bi.real_daily_enriched: {len(columns)} columnas")
            except Exception as e:
                logger.error(f"Error al inspeccionar bi.real_daily_enriched: {e}")

            # --- dim.dim_park ---
            try:
                cursor.execute("SELECT * FROM dim.dim_park LIMIT 5;")
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                inspection_results['dim_park']['columns'] = columns
                inspection_results['dim_park']['sample_rows'] = [
                    dict(zip(columns, row)) for row in rows
                ]
                logger.info(f"dim.dim_park: {len(columns)} columnas")
            except Exception as e:
                logger.error(f"Error al inspeccionar dim.dim_park: {e}")

            # --- LOB universe (desde dim.dim_park, no desde bi.real_monthly_agg) ---
            try:
                cursor.execute("""
                    SELECT DISTINCT
                        COALESCE(default_line_of_business, '') AS line_of_business,
                        COUNT(DISTINCT park_id) AS park_count
                    FROM dim.dim_park
                    WHERE COALESCE(default_line_of_business, '') != ''
                    GROUP BY default_line_of_business
                    ORDER BY line_of_business
                """)
                lines_of_business = cursor.fetchall()
                logger.info(f"Líneas de negocio en dim.dim_park: {len(lines_of_business)}")
                inspection_results['universe_lines_of_business'] = [
                    line[0] for line in lines_of_business if line[0]
                ]
            except Exception as e:
                logger.warning(f"Error al obtener líneas de negocio: {e}")

            logger.info("=" * 60)
            logger.info("INSPECCIÓN COMPLETADA")
            logger.info("=" * 60)

            cursor.close()
            return inspection_results

    except Exception as e:
        logger.error(f"Error en inspección de columnas reales: {e}")
        raise

