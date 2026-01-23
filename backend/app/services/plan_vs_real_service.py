"""Servicio para comparación Plan vs Real mensual."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def get_plan_vs_real_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    month: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene comparación Plan vs Real mensual desde ops.v_plan_vs_real_monthly_latest.
    
    Filtros opcionales:
    - country: País
    - city: Ciudad (usa city_norm_real para matching)
    - lob_base: Línea de negocio base
    - segment: Segmento (b2b, b2c)
    - month: Mes en formato 'YYYY-MM' o 'YYYY-MM-DD'
    
    Retorna lista con todos los campos de la vista comparativa.
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
                # Normalizar ciudad para matching
                city_norm = city.lower().strip()
                where_conditions.append("city_norm_real = %s")
                params.append(city_norm)
            
            if lob_base:
                where_conditions.append("lob_base = %s")
                params.append(lob_base)
            
            if segment:
                where_conditions.append("segment = %s")
                params.append(segment)
            
            if month:
                # Acepta formato YYYY-MM o YYYY-MM-DD
                if len(month) == 7:  # YYYY-MM
                    where_conditions.append("TO_CHAR(month, 'YYYY-MM') = %s")
                    params.append(month)
                else:  # YYYY-MM-DD
                    where_conditions.append("month = %s::DATE")
                    params.append(month)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    country,
                    month,
                    city_norm_real,
                    lob_base,
                    segment,
                    -- PLAN
                    plan_version,
                    projected_trips,
                    projected_drivers,
                    projected_ticket,
                    projected_trips_per_driver,
                    projected_revenue,
                    -- REAL
                    trips_real_completed,
                    active_drivers_real,
                    avg_ticket_real,
                    trips_per_driver_real,
                    revenue_real_yego,
                    margen_unitario_yego,
                    -- GAPS
                    gap_trips,
                    gap_drivers,
                    gap_ticket,
                    gap_tpd,
                    gap_revenue,
                    -- FLAGS
                    has_plan,
                    has_real,
                    status_bucket
                FROM ops.v_plan_vs_real_monthly_latest
                {where_clause}
                ORDER BY month DESC, country, city_norm_real, lob_base, segment
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            # Convertir month a string para JSON
            for row in results:
                if row.get('month'):
                    row['month'] = row['month'].strftime('%Y-%m-%d')
            
            logger.info(f"Comparación Plan vs Real obtenida: {len(results)} registros")
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener comparación Plan vs Real: {e}")
        raise


def get_alerts_monthly(
    country: Optional[str] = None,
    month: Optional[str] = None,
    alert_level: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene alertas Plan vs Real desde ops.v_plan_vs_real_alerts_monthly_latest.
    
    Filtros opcionales:
    - country: País
    - month: Mes en formato 'YYYY-MM' o 'YYYY-MM-DD'
    - alert_level: Nivel de alerta ('CRITICO', 'MEDIO', 'OK')
    
    Retorna lista con todos los campos de la vista de alertas.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if month:
                # Acepta formato YYYY-MM o YYYY-MM-DD
                if len(month) == 7:  # YYYY-MM
                    where_conditions.append("TO_CHAR(month, 'YYYY-MM') = %s")
                    params.append(month)
                else:  # YYYY-MM-DD
                    where_conditions.append("month = %s::DATE")
                    params.append(month)
            
            if alert_level:
                where_conditions.append("alert_level = %s")
                params.append(alert_level)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT 
                    country,
                    month,
                    city_norm_real,
                    lob_base,
                    segment,
                    plan_version,
                    projected_trips,
                    projected_revenue,
                    trips_real_completed,
                    revenue_real_yego,
                    gap_trips,
                    gap_revenue,
                    gap_trips_pct,
                    gap_revenue_pct,
                    alert_level
                FROM ops.v_plan_vs_real_alerts_monthly_latest
                {where_clause}
                ORDER BY 
                    CASE alert_level
                        WHEN 'CRITICO' THEN 1
                        WHEN 'MEDIO' THEN 2
                        WHEN 'OK' THEN 3
                    END,
                    month DESC,
                    country,
                    city_norm_real
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            # Convertir month a string para JSON
            for row in results:
                if row.get('month'):
                    row['month'] = row['month'].strftime('%Y-%m-%d')
            
            logger.info(f"Alertas Plan vs Real obtenidas: {len(results)} registros")
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener alertas Plan vs Real: {e}")
        raise
