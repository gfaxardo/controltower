from app.db.connection import get_db
from app.contracts.data_contract import get_real_column_name, normalize_country_std, normalize_city_std, normalize_line_of_business_std
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

def get_real_monthly_data(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year: Optional[int] = None,
    metric: str = 'trips'
) -> List[Dict]:
    """
    Obtiene datos reales mensuales desde bi.real_monthly_agg + dim.dim_park.
    Retorna lista de diccionarios en formato long.
    """
    column_name = get_real_column_name(metric)
    if not column_name:
        logger.warning(f"No se encontró columna para métrica {metric}")
        return []
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("COALESCE(d.country, '') = %s")
                params.append(country)
            
            if city:
                where_conditions.append("COALESCE(d.city, '') = %s")
                params.append(city)
            
            if line_of_business:
                where_conditions.append("COALESCE(d.default_line_of_business, '') = %s")
                params.append(line_of_business)
            
            if year:
                where_conditions.append("r.year = %s")
                params.append(year)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    TO_CHAR(TO_DATE(r.year::text || '-' || LPAD(r.month::text, 2, '0') || '-01', 'YYYY-MM-DD'), 'YYYY-MM') as period,
                    'month' as period_type,
                    COALESCE(d.country, NULL) as country,
                    COALESCE(d.city, '') as city,
                    COALESCE(d.default_line_of_business, '') as line_of_business,
                    %s as metric,
                    COALESCE(r.{column_name}, 0) as value
                FROM bi.real_monthly_agg r
                LEFT JOIN dim.dim_park d ON r.park_id = d.park_id
                {where_clause}
                ORDER BY r.year DESC, r.month DESC
            """
            
            params.insert(0, metric)
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener datos reales mensuales: {e}")
        raise

def get_ops_universe_data(country: Optional[str] = None, city: Optional[str] = None) -> List[Dict]:
    """
    Obtiene el universo operativo desde bi.real_monthly_agg + dim.dim_park.
    Retorna combinaciones con valores normalizados (_std) y formato humano.
    El universo se construye dinámicamente desde la query (puede crecer).
    Soporta filtros opcionales por country y city.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = [
                "r.year = 2025",
                "COALESCE(r.orders_completed, 0) > 0",
                "COALESCE(d.city, '') != ''",
                "COALESCE(d.default_line_of_business, '') != ''"
            ]
            params = []
            
            if country:
                where_conditions.append("COALESCE(d.country, '') = %s")
                params.append(country)
            
            if city:
                where_conditions.append("COALESCE(d.city, '') = %s")
                params.append(city)
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT DISTINCT
                    COALESCE(d.country, '') as country,
                    COALESCE(d.city, '') as city,
                    COALESCE(d.default_line_of_business, '') as line_of_business
                FROM bi.real_monthly_agg r
                LEFT JOIN dim.dim_park d ON r.park_id = d.park_id
                {where_clause}
                ORDER BY country, city, line_of_business
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            # Normalizar valores y agregar claves _std
            normalized_results = []
            for row in results:
                row_dict = dict(row)
                # Agregar valores normalizados para comparaciones
                row_dict['country_std'] = normalize_country_std(row_dict.get('country', ''))
                row_dict['city_std'] = normalize_city_std(row_dict.get('city', ''))
                row_dict['line_of_business_std'] = normalize_line_of_business_std(row_dict.get('line_of_business', ''))
                normalized_results.append(row_dict)
            
            return normalized_results
            
    except Exception as e:
        logger.error(f"Error al obtener universo operativo: {e}")
        raise

