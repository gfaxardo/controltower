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
    Obtiene datos reales mensuales desde ops.mv_real_trips_monthly (sin proxies).
    Retorna lista de diccionarios en formato long.
    
    NOTA: Usa la vista materializada ops.mv_real_trips_monthly que se alimenta de public.trips_all
    filtrando condicion='Completado'. Revenue real = SUM(comision_empresa_asociada).
    """
    # Mapeo de métricas a columnas en ops.mv_real_trips_monthly (sin proxies)
    metric_column_map = {
        'trips': 'trips_real_completed',
        'revenue': 'revenue_real_yego',  # Revenue real canónico
        'active_drivers': 'active_drivers_real',
        'avg_ticket': 'avg_ticket_real',
        'trips_per_driver': None  # Se calcula
    }
    
    column_name = metric_column_map.get(metric)
    if not column_name and metric != 'trips_per_driver':
        logger.warning(f"No se encontró columna para métrica {metric} en ops.mv_real_trips_monthly")
        return []
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("COALESCE(r.country, '') = %s")
                params.append(country)
            
            if city:
                # Normalizar ciudad para matching con city_norm
                city_norm = city.lower().strip()
                where_conditions.append("r.city_norm = %s")
                params.append(city_norm)
            
            if line_of_business:
                where_conditions.append("COALESCE(r.lob_base, '') = %s")
                params.append(line_of_business)
            
            if year:
                where_conditions.append("EXTRACT(YEAR FROM r.month) = %s")
                params.append(year)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Construir query según métrica
            if metric == 'trips_per_driver':
                # Calcular trips_per_driver
                value_expr = """
                    CASE 
                        WHEN SUM(r.active_drivers_real) > 0 
                        THEN SUM(r.trips_real_completed)::NUMERIC / SUM(r.active_drivers_real)
                        ELSE NULL
                    END
                """
                group_by = "GROUP BY TO_CHAR(r.month, 'YYYY-MM'), r.country, r.city, r.lob_base"
            else:
                value_expr = f"COALESCE(SUM(r.{column_name}), 0)"
                group_by = "GROUP BY TO_CHAR(r.month, 'YYYY-MM'), r.country, r.city, r.lob_base"
            
            query = f"""
                SELECT 
                    TO_CHAR(r.month, 'YYYY-MM') as period,
                    'month' as period_type,
                    COALESCE(r.country, '') as country,
                    COALESCE(r.city, '') as city,
                    COALESCE(r.lob_base, '') as line_of_business,
                    %s as metric,
                    {value_expr} as value
                FROM ops.mv_real_trips_monthly r
                {where_clause}
                {group_by}
                ORDER BY period DESC, r.country, r.city, r.lob_base
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
    Obtiene el universo operativo desde ops.mv_real_trips_monthly (vista materializada basada en trips_all).
    Retorna combinaciones con valores normalizados (_std) y formato humano.
    El universo se construye dinámicamente desde la query (puede crecer).
    Soporta filtros opcionales por country y city.
    
    NOTA: Usa ops.mv_real_trips_monthly que se alimenta de public.trips_all filtrando condicion='Completado'.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = [
                "EXTRACT(YEAR FROM r.month) = 2025",
                "COALESCE(r.trips_real_completed, 0) > 0",
                "COALESCE(r.city, '') != ''",
                "COALESCE(r.lob_base, '') != ''"
            ]
            params = []
            
            if country:
                where_conditions.append("COALESCE(r.country, '') = %s")
                params.append(country)
            
            if city:
                # Normalizar ciudad para matching con city_norm
                city_norm = city.lower().strip()
                where_conditions.append("r.city_norm = %s")
                params.append(city_norm)
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT DISTINCT
                    COALESCE(r.country, '') as country,
                    COALESCE(r.city, '') as city,
                    COALESCE(r.lob_base, '') as line_of_business
                FROM ops.mv_real_trips_monthly r
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

