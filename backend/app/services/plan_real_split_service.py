"""
Servicio para obtener Plan y Real por separado, y comparación solo donde hay overlap.
"""

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def get_real_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: int = 2025
) -> List[Dict]:
    """
    Obtiene datos REAL mensuales agregados desde ops.mv_real_trips_monthly.
    Retorna lista con month, trips_real_completed, revenue_real_proxy, 
    active_drivers_real, avg_ticket_real.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = ["EXTRACT(YEAR FROM month) = %s"]
            params = [year]
            
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
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    month,
                    SUM(trips_real_completed) as trips_real_completed,
                    SUM(revenue_real_proxy) as revenue_real_proxy,
                    SUM(active_drivers_real) as active_drivers_real,
                    AVG(avg_ticket_real) FILTER (WHERE avg_ticket_real IS NOT NULL) as avg_ticket_real
                FROM ops.mv_real_trips_monthly
                {where_clause}
                GROUP BY month
                ORDER BY month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                month = row['month']
                period = month.strftime('%Y-%m') if hasattr(month, 'strftime') else str(month)[:7]
                result.append({
                    'period': period,
                    'month': str(month),
                    'trips_real_completed': int(row['trips_real_completed']) if row['trips_real_completed'] else 0,
                    'revenue_real_proxy': float(row['revenue_real_proxy']) if row['revenue_real_proxy'] else None,
                    'active_drivers_real': int(row['active_drivers_real']) if row['active_drivers_real'] else 0,
                    'avg_ticket_real': float(row['avg_ticket_real']) if row['avg_ticket_real'] else None
                })
            
            logger.info(f"Real monthly generado: {len(result)} períodos para año {year}")
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener Real monthly: {e}")
        raise

def get_plan_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: int = 2026
) -> List[Dict]:
    """
    Obtiene datos PLAN mensuales agregados desde ops.v_plan_trips_monthly_latest.
    Retorna lista con month, projected_trips, projected_revenue, 
    projected_drivers, projected_ticket.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = ["EXTRACT(YEAR FROM month) = %s"]
            params = [year]
            
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
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
                SELECT 
                    month,
                    SUM(projected_trips) as projected_trips,
                    SUM(projected_revenue) as projected_revenue,
                    SUM(projected_drivers) as projected_drivers,
                    AVG(projected_ticket) FILTER (WHERE projected_ticket IS NOT NULL) as projected_ticket
                FROM ops.v_plan_trips_monthly_latest
                {where_clause}
                GROUP BY month
                ORDER BY month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                month = row['month']
                period = month.strftime('%Y-%m') if hasattr(month, 'strftime') else str(month)[:7]
                result.append({
                    'period': period,
                    'month': str(month),
                    'projected_trips': int(row['projected_trips']) if row['projected_trips'] else 0,
                    'projected_revenue': float(row['projected_revenue']) if row['projected_revenue'] else None,
                    'projected_drivers': int(row['projected_drivers']) if row['projected_drivers'] else 0,
                    'projected_ticket': float(row['projected_ticket']) if row['projected_ticket'] else None
                })
            
            logger.info(f"Plan monthly generado: {len(result)} períodos para año {year}")
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener Plan monthly: {e}")
        raise

def get_overlap_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict]:
    """
    Obtiene comparación Plan vs Real SOLO para meses donde hay overlap temporal (status_bucket='matched').
    Retorna lista vacía si no hay overlap, sin error.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Construir condiciones base
            where_conditions = ["status_bucket = 'matched'"]
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if city and city.lower() != 'todas':
                where_conditions.append("city_norm_real = %s")
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
            
            where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Query desde vista comparativa, solo matched (donde hay overlap)
            query = f"""
                SELECT 
                    month,
                    country,
                    city_norm_real as city_norm,
                    lob_base,
                    segment,
                    SUM(projected_trips) as projected_trips,
                    SUM(projected_revenue) as projected_revenue,
                    SUM(trips_real_completed) as trips_real_completed,
                    SUM(revenue_real_proxy) as revenue_real_proxy,
                    SUM(gap_trips) as gap_trips,
                    SUM(gap_revenue_proxy) as gap_revenue
                FROM ops.v_plan_vs_real_monthly_latest
                {where_clause}
                GROUP BY month, country, city_norm_real, lob_base, segment
                ORDER BY month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                month = row['month']
                period = month.strftime('%Y-%m') if hasattr(month, 'strftime') else str(month)[:7]
                result.append({
                    'period': period,
                    'month': str(month),
                    'country': row['country'],
                    'city_norm': row['city_norm'],
                    'lob_base': row['lob_base'],
                    'segment': row['segment'],
                    'projected_trips': int(row['projected_trips']) if row['projected_trips'] else None,
                    'projected_revenue': float(row['projected_revenue']) if row['projected_revenue'] else None,
                    'trips_real_completed': int(row['trips_real_completed']) if row['trips_real_completed'] else None,
                    'revenue_real_proxy': float(row['revenue_real_proxy']) if row['revenue_real_proxy'] else None,
                    'gap_trips': int(row['gap_trips']) if row['gap_trips'] is not None else None,
                    'gap_revenue': float(row['gap_revenue']) if row['gap_revenue'] is not None else None
                })
            
            logger.info(f"Overlap monthly generado: {len(result)} períodos comparables")
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener overlap monthly: {e}")
        # Retornar lista vacía en caso de error (tolerante)
        return []
