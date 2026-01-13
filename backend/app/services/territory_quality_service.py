"""
Servicio para KPIs de calidad de mapeo territorial.
"""
from typing import Dict, List, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

def get_territory_kpis_total() -> Dict:
    """
    Obtiene KPIs totales de calidad de mapeo territorial.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM ops.v_territory_mapping_quality_kpis")
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return dict(result)
            else:
                return {
                    'total_trips': 0,
                    'pct_territory_resolved': 0.0,
                    'pct_territory_unknown': 0.0,
                    'parks_in_trips': 0,
                    'parks_unmapped': 0,
                    'parks_with_null_country_city': 0
                }
    except Exception as e:
        logger.error(f"Error al obtener KPIs totales de territorio: {e}")
        raise

def get_territory_kpis_weekly() -> List[Dict]:
    """
    Obtiene KPIs semanales de calidad de mapeo territorial.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM ops.v_territory_mapping_quality_kpis_weekly")
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error al obtener KPIs semanales de territorio: {e}")
        raise

def get_unmapped_parks(limit: int = 50) -> List[Dict]:
    """
    Obtiene parks que aparecen en trips_all pero no tienen mapeo en dim.dim_park.
    Ordenados por cantidad de trips (descendente).
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT 
                    t.park_id,
                    COUNT(*) as trips_count,
                    MIN(t.fecha_inicio_viaje) as first_trip_date,
                    MAX(t.fecha_inicio_viaje) as last_trip_date
                FROM public.trips_all t
                WHERE t.park_id IS NOT NULL 
                  AND trim(t.park_id) != ''
                  AND NOT EXISTS (
                      SELECT 1 FROM dim.dim_park dp WHERE dp.park_id = t.park_id
                  )
                GROUP BY t.park_id
                ORDER BY trips_count DESC
                LIMIT %s
            """, (limit,))
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"Error al obtener parks unmapped: {e}")
        raise
