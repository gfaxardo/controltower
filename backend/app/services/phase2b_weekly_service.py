"""Servicio para Fase 2B semanal: Plan vs Real y alertas."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


def get_plan_vs_real_weekly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    week_start_from: Optional[str] = None,
    week_start_to: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene comparación Plan vs Real semanal desde ops.v_plan_vs_real_weekly.
    Filtros opcionales por llaves y rango de week_start.
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
                city_norm = city.lower().strip()
                where_conditions.append("city_norm = %s")
                params.append(city_norm)

            if lob_base:
                where_conditions.append("lob_base = %s")
                params.append(lob_base)

            if segment:
                where_conditions.append("segment = %s")
                params.append(segment)

            if week_start_from:
                where_conditions.append("week_start >= %s::DATE")
                params.append(week_start_from)

            if week_start_to:
                where_conditions.append("week_start <= %s::DATE")
                params.append(week_start_to)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            query = f"""
                SELECT
                    week_start,
                    country,
                    city_norm,
                    lob_base,
                    segment,
                    trips_real,
                    trips_plan,
                    gap_trips,
                    gap_trips_pct,
                    drivers_real,
                    drivers_plan,
                    gap_drivers,
                    gap_drivers_pct,
                    productividad_real,
                    productividad_plan,
                    gap_prod,
                    revenue_real,
                    revenue_plan,
                    gap_revenue,
                    gap_revenue_pct,
                    ingreso_por_viaje_real,
                    ingreso_por_viaje_plan,
                    gap_unitario,
                    gap_unitario_pct,
                    efecto_volumen,
                    efecto_unitario,
                    trips_teoricos_por_drivers,
                    trips_teoricos_por_prod
                FROM ops.v_plan_vs_real_weekly
                {where_clause}
                ORDER BY week_start DESC, country, city_norm, lob_base, segment
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            for row in rows:
                if row.get('week_start'):
                    row['week_start'] = row['week_start'].strftime('%Y-%m-%d')

            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener Plan vs Real semanal: {e}")
        raise


def get_alerts_weekly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    week_start_from: Optional[str] = None,
    week_start_to: Optional[str] = None,
    dominant_driver: Optional[str] = None,
    unit_alert: Optional[bool] = None
) -> List[Dict]:
    """
    Obtiene alertas semanales desde ops.v_alerts_2b_weekly.
    Filtros opcionales: dominant_driver (UNIT/VOL), unit_alert (true/false).
    Ordenado por severity_score desc.
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
                city_norm = city.lower().strip()
                where_conditions.append("city_norm = %s")
                params.append(city_norm)

            if lob_base:
                where_conditions.append("lob_base = %s")
                params.append(lob_base)

            if segment:
                where_conditions.append("segment = %s")
                params.append(segment)

            if week_start_from:
                where_conditions.append("a.week_start >= %s::DATE")
                params.append(week_start_from)

            if week_start_to:
                where_conditions.append("a.week_start <= %s::DATE")
                params.append(week_start_to)

            if dominant_driver:
                where_conditions.append("a.dominant_driver = %s")
                params.append(dominant_driver)

            if unit_alert is not None:
                where_conditions.append("a.unit_alert = %s")
                params.append(unit_alert)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            query = f"""
                SELECT
                    a.week_start,
                    a.country,
                    a.city_norm,
                    a.lob_base,
                    a.segment,
                    a.trips_real,
                    a.trips_plan,
                    a.gap_trips,
                    a.gap_trips_pct,
                    a.revenue_real,
                    a.revenue_plan,
                    a.gap_revenue,
                    a.gap_revenue_pct,
                    a.gap_unitario,
                    a.gap_unitario_pct,
                    a.efecto_volumen,
                    a.efecto_unitario,
                    a.why,
                    a.dominant_driver,
                    a.unit_alert,
                    a.severity_score,
                    a.alert_key,
                    a.critical,
                    CASE 
                        WHEN act.phase2b_action_id IS NOT NULL THEN true 
                        ELSE false 
                    END as has_action
                FROM ops.v_alerts_2b_weekly a
                LEFT JOIN ops.phase2b_actions act ON (
                    a.week_start = act.week_start
                    AND a.country = act.country
                    AND COALESCE(a.city_norm, '') = COALESCE(act.city_norm, '')
                    AND COALESCE(a.lob_base, '') = COALESCE(act.lob_base, '')
                    AND COALESCE(a.segment, '') = COALESCE(act.segment, '')
                )
                {where_clause}
                ORDER BY a.severity_score DESC NULLS LAST, ABS(a.gap_revenue) DESC NULLS LAST, ABS(a.gap_trips) DESC NULLS LAST
            """

            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()

            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('week_start'):
                    row_dict['week_start'] = row_dict['week_start'].strftime('%Y-%m-%d')
                # Asegurar que has_action sea boolean
                row_dict['has_action'] = bool(row_dict.get('has_action', False))
                # Asegurar que unit_alert sea boolean
                row_dict['unit_alert'] = bool(row_dict.get('unit_alert', False))
                # Mantener backward compatibility con dominant_effect
                if 'dominant_driver' in row_dict and 'dominant_effect' not in row_dict:
                    row_dict['dominant_effect'] = row_dict.get('dominant_driver')
                result.append(row_dict)

            return result
    except Exception as e:
        logger.error(f"Error al obtener alertas semanales: {e}")
        raise
