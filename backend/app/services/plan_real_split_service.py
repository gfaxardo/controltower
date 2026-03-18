"""
Servicio para obtener Plan y Real por separado, y comparación solo donde hay overlap.
LEGACY: Real mensual desde ops.mv_real_trips_monthly. La canonical se invoca solo vía endpoint
GET /ops/real/monthly?source=canonical (Resumen). New consumers must use canonical only.
Ver docs/REAL_CANONICAL_CHAIN.md.
"""

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def _get_currency_code(country: Optional[str]) -> str:
    """Mapea país a código de moneda. PE/peru->PEN, CO/colombia->COP. Default: PEN."""
    if not country:
        return 'PEN'
    country_lower = country.lower()
    if country_lower in ('pe', 'peru'):
        return 'PEN'
    elif country_lower in ('co', 'colombia'):
        return 'COP'
    else:
        return 'PEN'  # Default


def get_real_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: int = 2025
) -> List[Dict]:
    """
    Obtiene datos REAL mensuales desde ops.mv_real_trips_monthly (LEGACY).
    Para cadena canónica usar GET /ops/real/monthly?source=canonical o get_real_monthly_canonical.
    Retorna currency_code basado en country (PE=PEN, CO=COP).
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = ["EXTRACT(YEAR FROM month) = %s"]
            params = [year]
            
            if country:
                # Normalizar país: PE/CO -> peru/colombia (valores en dim_park)
                country_normalized = country.lower()
                if country_normalized == 'pe':
                    country_normalized = 'peru'
                elif country_normalized == 'co':
                    country_normalized = 'colombia'
                where_conditions.append("LOWER(TRIM(country)) = %s")
                params.append(country_normalized)
            
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
            
            # FASE 2A: Sin proxies, solo revenue real
            query = f"""
                SELECT 
                    month,
                    SUM(trips_real_completed) as trips_real_completed,
                    SUM(revenue_real_yego) as revenue_real_yego,
                    SUM(active_drivers_real) as active_drivers_real,
                    AVG(avg_ticket_real) FILTER (WHERE avg_ticket_real IS NOT NULL) as avg_ticket_real,
                    -- Métricas derivadas (calculadas desde datos reales)
                    CASE
                        WHEN SUM(active_drivers_real) > 0
                        THEN SUM(trips_real_completed)::NUMERIC / SUM(active_drivers_real)
                        ELSE NULL
                    END as trips_per_driver,
                    CASE
                        WHEN SUM(trips_real_completed) > 0
                        THEN SUM(revenue_real_yego) / SUM(trips_real_completed)
                        ELSE NULL
                    END as margen_unitario_yego,
                    -- Para determinar currency_code, usar el primer país si hay uno único
                    COUNT(DISTINCT country) as country_count,
                    MAX(country) FILTER (WHERE country IS NOT NULL) as primary_country,
                    -- Flag para meses parciales
                    BOOL_OR(is_partial_real) as is_partial_real
                FROM ops.mv_real_trips_monthly
                {where_clause}
                GROUP BY month
                ORDER BY month
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            # Determinar currency_code: si country está filtrado, usarlo; si no, usar el más común
            currency_code = _get_currency_code(country) if country else 'PEN'
            
            result = []
            for row in rows:
                month = row['month']
                period = month.strftime('%Y-%m') if hasattr(month, 'strftime') else str(month)[:7]
                
                # Si no hay país filtrado pero hay un país único en los datos, usar ese para currency
                row_currency = currency_code
                if not country and row.get('primary_country') and row.get('country_count') == 1:
                    row_currency = _get_currency_code(row['primary_country'])
                
                result.append({
                    'period': period,
                    'month': str(month),
                    'trips_real_completed': int(row['trips_real_completed']) if row['trips_real_completed'] else 0,
                    'revenue_real_yego': float(row['revenue_real_yego']) if row['revenue_real_yego'] else 0,
                    'active_drivers_real': int(row['active_drivers_real']) if row['active_drivers_real'] else 0,
                    'avg_ticket_real': float(row['avg_ticket_real']) if row['avg_ticket_real'] else None,
                    # Métricas derivadas
                    'trips_per_driver': float(row['trips_per_driver']) if row['trips_per_driver'] is not None else None,
                    'margen_unitario_yego': float(row['margen_unitario_yego']) if row['margen_unitario_yego'] is not None else None,
                    'currency_code': row_currency,
                    'is_partial_real': bool(row.get('is_partial_real', False))
                })
            
            logger.info(f"Real monthly generado: {len(result)} períodos para año {year}, currency={currency_code}")
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
            
            # Query desde plan y real v2 directamente (sin usar vista comparativa que tiene proxies)
            query = f"""
                SELECT 
                    p.month,
                    p.country,
                    p.city_norm as city_norm,
                    p.lob_base,
                    p.segment,
                    SUM(p.projected_trips) as projected_trips,
                    SUM(p.projected_revenue) as projected_revenue,
                    SUM(COALESCE(r.trips_real_completed, 0)) as trips_real_completed,
                    SUM(COALESCE(r.revenue_real_yego, 0)) as revenue_real_yego,
                    CASE
                        WHEN SUM(COALESCE(r.trips_real_completed, 0)) > 0
                        THEN SUM(COALESCE(r.revenue_real_yego, 0)) / SUM(COALESCE(r.trips_real_completed, 0))
                        ELSE NULL
                    END as margen_unitario_yego,
                    BOOL_OR(r.is_partial_real) as is_partial_real,
                    SUM(p.projected_trips - COALESCE(r.trips_real_completed, 0)) as gap_trips,
                    SUM(p.projected_revenue - COALESCE(r.revenue_real_yego, 0)) as gap_revenue
                FROM ops.v_plan_trips_monthly_latest p
                    LEFT JOIN ops.mv_real_trips_monthly r 
                    ON p.month = r.month 
                    AND p.country = r.country 
                    AND p.city_norm = r.city_norm 
                    AND p.lob_base = r.lob_base 
                    AND COALESCE(p.segment, '') = COALESCE(r.segment, '')
                {where_clause}
                GROUP BY p.month, p.country, p.city_norm, p.lob_base, p.segment
                HAVING SUM(COALESCE(r.trips_real_completed, 0)) > 0 OR SUM(p.projected_trips) > 0
                ORDER BY p.month
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
                    'revenue_real_yego': float(row['revenue_real_yego']) if row['revenue_real_yego'] else 0,
                    'margen_unitario_yego': float(row['margen_unitario_yego']) if row['margen_unitario_yego'] is not None else None,
                    'gap_trips': int(row['gap_trips']) if row['gap_trips'] is not None else None,
                    'gap_revenue': float(row['gap_revenue']) if row['gap_revenue'] is not None else None,
                    'is_partial_real': bool(row.get('is_partial_real', False))
                })
            
            logger.info(f"Overlap monthly generado: {len(result)} períodos comparables")
            return result
            
    except Exception as e:
        logger.error(f"Error al obtener overlap monthly: {e}")
        # Retornar lista vacía en caso de error (tolerante)
        return []
