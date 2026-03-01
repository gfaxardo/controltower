"""
Servicio para KPIs financieros canónicos REAL y PLAN.
Expone solo campos canónicos según decisiones definitivas.
"""

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def get_real_financials_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict]:
    """
    Obtiene KPIs financieros REAL canónicos desde ops.mv_real_financials_monthly.
    
    Retorna SOLO campos canónicos:
    - trips_real
    - revenue_yego_real
    - take_rate_real
    - margin_per_trip_real
    
    PROHIBIDO exponer GMV como revenue o proxy 3% en REAL.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                # Normalizar país: PE/CO -> peru/colombia
                country_normalized = country.lower()
                if country_normalized == 'pe':
                    country_normalized = 'peru'
                elif country_normalized == 'co':
                    country_normalized = 'colombia'
                where_conditions.append("LOWER(TRIM(country)) = %s")
                params.append(country_normalized)
            
            if city and city.lower() != 'todas':
                where_conditions.append("LOWER(TRIM(city)) = %s")
                params.append(city.lower().strip())
            
            if lob_base and lob_base.lower() != 'todas':
                where_conditions.append("lob_base = %s")
                params.append(lob_base)
            
            if segment:
                where_conditions.append("segment = %s")
                params.append(segment)
            
            if year:
                where_conditions.append("year = %s")
                params.append(year)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    year,
                    month,
                    SUM(trips_real) as trips_real,
                    SUM(revenue_yego_real) as revenue_yego_real,
                    CASE
                        WHEN SUM(gmv_real) > 0
                        THEN SUM(revenue_yego_real) / NULLIF(SUM(gmv_real), 0)
                        ELSE NULL
                    END as take_rate_real,
                    CASE
                        WHEN SUM(trips_real) > 0
                        THEN SUM(revenue_yego_real) / NULLIF(SUM(trips_real), 0)::NUMERIC
                        ELSE NULL
                    END as margin_per_trip_real
                FROM ops.mv_real_financials_monthly
                {where_clause}
                GROUP BY year, month
                ORDER BY year, month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                period = f"{row['year']}-{row['month']:02d}"
                result.append({
                    'period': period,
                    'year': int(row['year']),
                    'month': int(row['month']),
                    'trips_real': int(row['trips_real']) if row['trips_real'] else 0,
                    'revenue_yego_real': float(row['revenue_yego_real']) if row['revenue_yego_real'] else None,
                    'take_rate_real': float(row['take_rate_real']) if row['take_rate_real'] is not None else None,
                    'margin_per_trip_real': float(row['margin_per_trip_real']) if row['margin_per_trip_real'] is not None else None
                })
            
            logger.info(f"KPIs financieros REAL generados: {len(result)} períodos")
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener KPIs financieros REAL: {e}")
        raise


def get_plan_financials_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict]:
    """
    Obtiene KPIs financieros PLAN canónicos desde ops.v_plan_trips_monthly_latest.
    
    Retorna SOLO campos canónicos:
    - projected_trips
    - revenue_yego_plan
    - take_rate_plan
    - margin_per_trip_plan
    - is_estimated
    
    PROHIBIDO exponer GMV como revenue.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if city and city.lower() != 'todas':
                where_conditions.append("city_norm = %s")
                params.append(city.lower().strip())
            
            if lob_base and lob_base.lower() != 'todas':
                where_conditions.append("lob_base = %s")
                params.append(lob_base)
            
            if segment:
                where_conditions.append("segment = %s")
                params.append(segment)
            
            if year:
                where_conditions.append("EXTRACT(YEAR FROM month) = %s")
                params.append(year)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    EXTRACT(YEAR FROM month)::int as year,
                    EXTRACT(MONTH FROM month)::int as month,
                    SUM(projected_trips) as projected_trips,
                    SUM(revenue_yego_plan) as revenue_yego_plan,
                    CASE
                        WHEN SUM(projected_trips) > 0 AND SUM(projected_ticket) > 0
                        THEN SUM(revenue_yego_plan) / NULLIF(SUM(projected_trips) * AVG(projected_ticket), 0)
                        ELSE NULL
                    END as take_rate_plan,
                    CASE
                        WHEN SUM(projected_trips) > 0
                        THEN SUM(revenue_yego_plan) / NULLIF(SUM(projected_trips), 0)::NUMERIC
                        ELSE NULL
                    END as margin_per_trip_plan,
                    BOOL_OR(is_estimated) as is_estimated
                FROM ops.v_plan_trips_monthly_latest
                {where_clause}
                GROUP BY EXTRACT(YEAR FROM month), EXTRACT(MONTH FROM month)
                ORDER BY year, month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                period = f"{row['year']}-{row['month']:02d}"
                result.append({
                    'period': period,
                    'year': int(row['year']),
                    'month': int(row['month']),
                    'projected_trips': int(row['projected_trips']) if row['projected_trips'] else 0,
                    'revenue_yego_plan': float(row['revenue_yego_plan']) if row['revenue_yego_plan'] else None,
                    'take_rate_plan': float(row['take_rate_plan']) if row['take_rate_plan'] is not None else None,
                    'margin_per_trip_plan': float(row['margin_per_trip_plan']) if row['margin_per_trip_plan'] is not None else None,
                    'is_estimated': bool(row['is_estimated']) if row['is_estimated'] is not None else False
                })
            
            logger.info(f"KPIs financieros PLAN generados: {len(result)} períodos")
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener KPIs financieros PLAN: {e}")
        raise
