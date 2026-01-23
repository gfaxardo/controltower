"""
Repositorio para obtener datos del universo LOB (Fase 2C+).
Accede a las vistas creadas para mapeo PLAN → REAL.
"""

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def get_lob_universe_check(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_name: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene el universo LOB desde ops.v_lob_universe_check.
    Muestra qué LOB del plan tienen viajes reales y cuáles no.
    Si el catálogo está vacío, retorna lista vacía (modo REAL-only).
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Verificar si hay LOB en el catálogo
            cursor.execute("SELECT COUNT(*) FROM ops.lob_catalog WHERE status = 'active'")
            catalog_count = cursor.fetchone()[0]
            
            if catalog_count == 0:
                logger.info("Catálogo LOB vacío - modo REAL-only")
                return []
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if city:
                where_conditions.append("city = %s")
                params.append(city)
            
            if lob_name:
                where_conditions.append("lob_name = %s")
                params.append(lob_name)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT
                    country,
                    city,
                    lob_name,
                    lob_id,
                    real_trips,
                    exists_in_real,
                    exists_in_plan,
                    coverage_status
                FROM ops.v_lob_universe_check
                {where_clause}
                ORDER BY country, city, lob_name
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener universo LOB: {e}")
        raise

def get_real_without_plan_lob(
    country: Optional[str] = None,
    city: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene viajes reales que no tienen mapeo a ninguna LOB del plan.
    Incluye market_type, city_raw, lob_base.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if city:
                where_conditions.append("city = %s")
                params.append(city)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT
                    country,
                    city,
                    city_raw,
                    lob_base,
                    market_type,
                    trips_count,
                    first_seen_date,
                    last_seen_date
                FROM ops.v_real_without_plan_lob
                {where_clause}
                ORDER BY trips_count DESC
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener viajes sin LOB del plan: {e}")
        raise

def get_lob_mapping_quality_checks() -> Dict:
    """
    Obtiene métricas de calidad del mapeo LOB.
    Retorna un diccionario con las métricas.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT metric, value
                FROM ops.v_lob_mapping_quality_checks
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            # Convertir a diccionario
            metrics = {}
            for row in results:
                metrics[row['metric']] = row['value']
            
            return metrics
            
    except Exception as e:
        logger.error(f"Error al obtener métricas de calidad: {e}")
        raise

def get_unmatched_by_location() -> List[Dict]:
    """
    Obtiene viajes unmatched agrupados por país/ciudad.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT
                    country,
                    city,
                    unmatched_trips,
                    distinct_tipo_servicio,
                    pct_of_location_trips
                FROM ops.v_lob_unmatched_by_location
                ORDER BY unmatched_trips DESC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener unmatched por ubicación: {e}")
        raise

def get_lob_catalog(
    country: Optional[str] = None,
    city: Optional[str] = None,
    status: Optional[str] = 'active'
) -> List[Dict]:
    """
    Obtiene el catálogo de LOB.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if city:
                where_conditions.append("city = %s")
                params.append(city)
            
            if status:
                where_conditions.append("status = %s")
                params.append(status)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT
                    lob_id,
                    lob_name,
                    country,
                    city,
                    description,
                    status,
                    source,
                    created_at
                FROM ops.lob_catalog
                {where_clause}
                ORDER BY country, city, lob_name
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener catálogo LOB: {e}")
        raise
