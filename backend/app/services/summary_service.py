from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

def get_plan_monthly_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict]:
    """
    Obtiene resumen mensual de Plan en formato pivot desde ops.v_plan_trips_monthly_latest.
    Retorna lista con period, trips_plan, revenue_plan.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Construir query desde vista latest
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if city and city.lower() != 'todas':
                where_conditions.append("city_norm = %s")
                params.append(city.lower().strip())
            
            if line_of_business and line_of_business.lower() != 'todas':
                where_conditions.append("lob_base = %s")
                params.append(line_of_business)
            
            if year:
                where_conditions.append("EXTRACT(YEAR FROM month) = %s")
                params.append(year)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    month,
                    SUM(projected_trips) as trips_plan,
                    SUM(projected_revenue) as revenue_plan
                FROM ops.v_plan_trips_monthly_latest
                {where_clause}
                GROUP BY month
                ORDER BY month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            # Convertir a formato esperado (period como YYYY-MM)
            result = []
            for row in rows:
                month = row['month']
                if month:
                    period = month.strftime('%Y-%m') if hasattr(month, 'strftime') else str(month)[:7]
                    result.append({
                        'period': period,
                        'trips_plan': int(row['trips_plan']) if row['trips_plan'] else None,
                        'revenue_plan': float(row['revenue_plan']) if row['revenue_plan'] else None
                    })
            
            logger.info(f"Resumen mensual de Plan generado: {len(result)} períodos")
            return result
            
    except Exception as e:
        logger.error(f"Error al generar resumen mensual de Plan: {e}")
        raise

