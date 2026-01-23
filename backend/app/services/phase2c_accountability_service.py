"""Servicio para Fase 2C: Accountability - Medir disciplina de ejecución."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict
from datetime import date, datetime

logger = logging.getLogger(__name__)


def get_scoreboard(
    country: Optional[str] = None,
    week_from: Optional[str] = None,
    week_to: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene scoreboard semanal desde ops.v_phase2c_weekly_scoreboard.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if week_from:
                where_conditions.append("week_start >= %s::DATE")
                params.append(week_from)
            
            if week_to:
                where_conditions.append("week_start <= %s::DATE")
                params.append(week_to)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT *
                FROM ops.v_phase2c_weekly_scoreboard
                {where_clause}
                ORDER BY week_start DESC, country
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('week_start'):
                    row_dict['week_start'] = row_dict['week_start'].strftime('%Y-%m-%d')
                result.append(row_dict)
            
            return result
    except Exception as e:
        logger.error(f"Error al obtener scoreboard: {e}")
        raise


def get_backlog(owner_role: Optional[str] = None) -> List[Dict]:
    """
    Obtiene backlog por owner desde ops.v_phase2c_backlog_by_owner.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_clause = ""
            params = []
            
            if owner_role:
                where_clause = "WHERE owner_role = %s"
                params.append(owner_role)
            
            query = f"""
                SELECT *
                FROM ops.v_phase2c_backlog_by_owner
                {where_clause}
                ORDER BY owner_role, country
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error al obtener backlog: {e}")
        raise


def get_breaches(
    country: Optional[str] = None,
    week_start: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene breaches de SLA desde ops.v_phase2c_sla_breaches.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("country = %s")
                params.append(country)
            
            if week_start:
                where_conditions.append("week_start = %s::DATE")
                params.append(week_start)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT *
                FROM ops.v_phase2c_sla_breaches
                {where_clause}
                ORDER BY week_start DESC, severity_score DESC NULLS LAST
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('week_start'):
                    row_dict['week_start'] = row_dict['week_start'].strftime('%Y-%m-%d')
                if row_dict.get('sla_due_at'):
                    row_dict['sla_due_at'] = row_dict['sla_due_at'].isoformat()
                result.append(row_dict)
            
            return result
    except Exception as e:
        logger.error(f"Error al obtener breaches: {e}")
        raise


def run_snapshot():
    """
    Ejecuta snapshot y evaluación de SLA.
    Retorna diccionario con resultados.
    """
    try:
        # Importar funciones del script directamente en lugar de subprocess
        import sys
        import os
        from datetime import datetime, timedelta
        import pytz
        
        # Importar funciones del script
        script_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'scripts')
        sys.path.insert(0, script_dir)
        
        from phase2c_snapshot_and_sla import (
            get_last_closed_week,
            snapshot_alerts,
            evaluate_sla
        )
        
        week_start = get_last_closed_week()
        logger.info(f"Ejecutando snapshot para semana: {week_start}")
        
        snapshot_count = snapshot_alerts(week_start)
        sla_count = evaluate_sla(week_start)
        
        return {
            "success": True,
            "message": "Snapshot y SLA evaluation completados",
            "week_start": week_start.strftime('%Y-%m-%d'),
            "snapshot_count": snapshot_count,
            "sla_count": sla_count
        }
    except Exception as e:
        logger.error(f"Error al ejecutar snapshot: {e}", exc_info=True)
        raise
