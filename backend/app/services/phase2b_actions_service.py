"""Servicio para Fase 2B: Gestión de acciones operativas."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict
from datetime import date, datetime
from uuid import UUID

logger = logging.getLogger(__name__)


def create_action(
    week_start: date,
    country: str,
    city_norm: Optional[str],
    lob_base: Optional[str],
    segment: Optional[str],
    alert_type: str,
    root_cause: str,
    action_type: str,
    action_description: str,
    owner_role: str,
    owner_user_id: Optional[UUID],
    due_date: date
) -> Dict:
    """
    Crea una nueva acción.
    Validaciones:
    - No permitir crear acción sin due_date
    - Auto-marcar MISSED si due_date < today y status != DONE
    """
    if not due_date:
        raise ValueError("due_date es obligatorio")

    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Determinar status inicial
            today = date.today()
            initial_status = 'MISSED' if due_date < today else 'OPEN'
            
            query = """
                INSERT INTO ops.phase2b_actions (
                    week_start, country, city_norm, lob_base, segment,
                    alert_type, root_cause, action_type, action_description,
                    owner_role, owner_user_id, due_date, status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                RETURNING *
            """
            
            cursor.execute(query, (
                week_start, country, city_norm, lob_base, segment,
                alert_type, root_cause, action_type, action_description,
                owner_role, owner_user_id, due_date, initial_status
            ))
            
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            
            return dict(result)
    except Exception as e:
        logger.error(f"Error al crear acción: {e}")
        raise


def get_actions(
    week_start: Optional[date] = None,
    owner_role: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict]:
    """
    Obtiene acciones con filtros opcionales.
    Auto-marca acciones MISSED antes de retornar.
    """
    try:
        # Auto-marcar acciones MISSED antes de consultar
        mark_missed_actions()
        
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if week_start:
                where_conditions.append("week_start = %s")
                params.append(week_start)
            
            if owner_role:
                where_conditions.append("owner_role = %s")
                params.append(owner_role)
            
            if status:
                where_conditions.append("status = %s")
                params.append(status)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            query = f"""
                SELECT *
                FROM ops.phase2b_actions
                {where_clause}
                ORDER BY week_start DESC, created_at DESC
            """
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            # Convertir fechas a strings para JSON
            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('week_start'):
                    row_dict['week_start'] = row_dict['week_start'].strftime('%Y-%m-%d')
                if row_dict.get('due_date'):
                    row_dict['due_date'] = row_dict['due_date'].strftime('%Y-%m-%d')
                if row_dict.get('created_at'):
                    row_dict['created_at'] = row_dict['created_at'].isoformat()
                if row_dict.get('updated_at'):
                    row_dict['updated_at'] = row_dict['updated_at'].isoformat()
                result.append(row_dict)
            
            return result
    except Exception as e:
        logger.error(f"Error al obtener acciones: {e}")
        raise


def get_action_by_id(action_id: int) -> Optional[Dict]:
    """
    Obtiene una acción por ID.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT *
                FROM ops.phase2b_actions
                WHERE phase2b_action_id = %s
            """
            
            cursor.execute(query, (action_id,))
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                return None
            
            row_dict = dict(row)
            if row_dict.get('week_start'):
                row_dict['week_start'] = row_dict['week_start'].strftime('%Y-%m-%d')
            if row_dict.get('due_date'):
                row_dict['due_date'] = row_dict['due_date'].strftime('%Y-%m-%d')
            if row_dict.get('created_at'):
                row_dict['created_at'] = row_dict['created_at'].isoformat()
            if row_dict.get('updated_at'):
                row_dict['updated_at'] = row_dict['updated_at'].isoformat()
            
            return row_dict
    except Exception as e:
        logger.error(f"Error al obtener acción por ID: {e}")
        raise


def update_action(
    action_id: int,
    status: Optional[str] = None,
    action_description: Optional[str] = None
) -> Optional[Dict]:
    """
    Actualiza una acción.
    Validaciones:
    - No permitir cambiar acción si status = DONE
    - Auto-marcar MISSED si due_date < today y status != DONE
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Verificar que la acción existe y no está DONE
            current = get_action_by_id(action_id)
            if not current:
                return None
            
            if current.get('status') == 'DONE':
                raise ValueError("No se puede modificar una acción con status DONE")
            
            # Construir UPDATE dinámico
            updates = []
            params = []
            
            if status is not None:
                updates.append("status = %s")
                params.append(status)
            
            if action_description is not None:
                updates.append("action_description = %s")
                params.append(action_description)
            
            if not updates:
                return current
            
            # Verificar si necesita auto-marcar MISSED
            due_date_str = current.get('due_date')
            if due_date_str:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
                today = date.today()
                if due_date < today and status != 'DONE':
                    updates.append("status = %s")
                    params.append('MISSED')
                elif status is None and due_date < today:
                    # Si no se especifica status pero está vencida, auto-marcar
                    updates.append("status = %s")
                    params.append('MISSED')
            
            params.append(action_id)
            
            query = f"""
                UPDATE ops.phase2b_actions
                SET {', '.join(updates)}, updated_at = NOW()
                WHERE phase2b_action_id = %s
                RETURNING *
            """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            
            if not result:
                return None
            
            row_dict = dict(result)
            if row_dict.get('week_start'):
                row_dict['week_start'] = row_dict['week_start'].strftime('%Y-%m-%d')
            if row_dict.get('due_date'):
                row_dict['due_date'] = row_dict['due_date'].strftime('%Y-%m-%d')
            if row_dict.get('created_at'):
                row_dict['created_at'] = row_dict['created_at'].isoformat()
            if row_dict.get('updated_at'):
                row_dict['updated_at'] = row_dict['updated_at'].isoformat()
            
            return row_dict
    except Exception as e:
        logger.error(f"Error al actualizar acción: {e}")
        raise


def check_action_exists(
    week_start: date,
    country: str,
    city_norm: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None
) -> bool:
    """
    Verifica si existe una acción para una alerta específica.
    Usado para marcar has_action en las alertas.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            where_conditions = ["week_start = %s", "country = %s"]
            params = [week_start, country]
            
            if city_norm:
                where_conditions.append("city_norm = %s")
                params.append(city_norm)
            else:
                where_conditions.append("city_norm IS NULL")
            
            if lob_base:
                where_conditions.append("lob_base = %s")
                params.append(lob_base)
            else:
                where_conditions.append("lob_base IS NULL")
            
            if segment:
                where_conditions.append("segment = %s")
                params.append(segment)
            else:
                where_conditions.append("segment IS NULL")
            
            query = f"""
                SELECT EXISTS(
                    SELECT 1
                    FROM ops.phase2b_actions
                    WHERE {' AND '.join(where_conditions)}
                )
            """
            
            cursor.execute(query, params)
            exists = cursor.fetchone()[0]
            cursor.close()
            
            return exists
    except Exception as e:
        logger.error(f"Error al verificar existencia de acción: {e}")
        return False


def mark_missed_actions():
    """
    Auto-marca acciones como MISSED si due_date < today y status != DONE.
    Función para ejecutar periódicamente.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            query = """
                UPDATE ops.phase2b_actions
                SET status = 'MISSED', updated_at = NOW()
                WHERE due_date < CURRENT_DATE
                  AND status != 'DONE'
            """
            
            cursor.execute(query)
            count = cursor.rowcount
            conn.commit()
            cursor.close()
            
            logger.info(f"Marcadas {count} acciones como MISSED")
            return count
    except Exception as e:
        logger.error(f"Error al marcar acciones MISSED: {e}")
        raise
