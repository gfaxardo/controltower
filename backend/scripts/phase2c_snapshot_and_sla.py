#!/usr/bin/env python3
"""
Script para snapshot de alertas y evaluación de SLA (Fase 2C).
Hace snapshot de alertas de la última semana cerrada y evalúa SLA.

Uso:
    python phase2c_snapshot_and_sla.py
"""
import sys
import os
from datetime import datetime, timedelta
import pytz

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Timezone para SLA (America/Lima)
LIMA_TZ = pytz.timezone('America/Lima')


def get_last_closed_week():
    """Obtiene la última semana cerrada (semana anterior a la actual)."""
    today = datetime.now(LIMA_TZ).date()
    # Calcular lunes de la semana actual
    days_since_monday = today.weekday()
    monday_current_week = today - timedelta(days=days_since_monday)
    # Última semana cerrada es la semana anterior (lunes de la semana pasada)
    last_week_monday = monday_current_week - timedelta(days=7)
    return last_week_monday


def calculate_sla_due_at(week_start):
    """
    Calcula sla_due_at: martes 12:00 America/Lima de la semana siguiente al week_start.
    week_start es el lunes de la semana auditada.
    """
    # Martes de la semana siguiente = week_start + 8 días
    tuesday_next_week = week_start + timedelta(days=8)
    # Crear datetime a las 12:00 en timezone Lima
    sla_due_at = datetime.combine(tuesday_next_week, datetime.min.time().replace(hour=12))
    sla_due_at = LIMA_TZ.localize(sla_due_at)
    return sla_due_at


def snapshot_alerts(week_start):
    """Hace snapshot de alertas de la semana especificada."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener alertas de la semana desde la vista
            query = """
                SELECT
                    week_start,
                    alert_key,
                    country,
                    city_norm,
                    lob_base,
                    segment,
                    severity_score,
                    critical,
                    gap_revenue,
                    gap_trips,
                    gap_unitario_pct,
                    dominant_driver,
                    why
                FROM ops.v_alerts_2b_weekly
                WHERE week_start = %s
            """
            
            cursor.execute(query, (week_start,))
            alerts = cursor.fetchall()
            
            if not alerts:
                logger.warning(f"No se encontraron alertas para la semana {week_start}")
                return 0
            
            # Upsert en tabla de audit
            upsert_query = """
                INSERT INTO ops.phase2b_alert_audit (
                    week_start, alert_key, country, city_norm, lob_base, segment,
                    severity_score, critical, gap_revenue, gap_trips, gap_unitario_pct,
                    dominant_driver, why, snapshot_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (week_start, alert_key) DO UPDATE SET
                    severity_score = EXCLUDED.severity_score,
                    critical = EXCLUDED.critical,
                    gap_revenue = EXCLUDED.gap_revenue,
                    gap_trips = EXCLUDED.gap_trips,
                    gap_unitario_pct = EXCLUDED.gap_unitario_pct,
                    dominant_driver = EXCLUDED.dominant_driver,
                    why = EXCLUDED.why,
                    snapshot_at = NOW()
            """
            
            count = 0
            for alert in alerts:
                cursor.execute(upsert_query, (
                    alert['week_start'],
                    alert['alert_key'],
                    alert['country'],
                    alert.get('city_norm'),
                    alert.get('lob_base'),
                    alert.get('segment'),
                    alert.get('severity_score'),
                    alert.get('critical', False),
                    alert.get('gap_revenue'),
                    alert.get('gap_trips'),
                    alert.get('gap_unitario_pct'),
                    alert.get('dominant_driver'),
                    alert.get('why')
                ))
                count += 1
            
            conn.commit()
            cursor.close()
            logger.info(f"Snapshot completado: {count} alertas para semana {week_start}")
            return count
            
    except Exception as e:
        logger.error(f"Error al hacer snapshot: {e}", exc_info=True)
        raise


def evaluate_sla(week_start):
    """Evalúa SLA para alertas críticas de la semana."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener alertas críticas auditadas
            query = """
                SELECT
                    week_start,
                    alert_key,
                    country,
                    critical
                FROM ops.phase2b_alert_audit
                WHERE week_start = %s
                  AND critical = true
            """
            
            cursor.execute(query, (week_start,))
            critical_alerts = cursor.fetchall()
            
            if not critical_alerts:
                logger.info(f"No hay alertas críticas para evaluar SLA en semana {week_start}")
                return 0
            
            # Calcular sla_due_at
            sla_due_at = calculate_sla_due_at(week_start)
            
            # Para cada alerta crítica, verificar si tiene acción
            count = 0
            for alert in critical_alerts:
                # Verificar si existe acción
                action_query = """
                    SELECT
                        phase2b_action_id,
                        created_at
                    FROM ops.phase2b_actions
                    WHERE week_start = %s
                      AND country = %s
                      AND COALESCE(city_norm, '') = COALESCE(%s, '')
                      AND COALESCE(lob_base, '') = COALESCE(%s, '')
                      AND COALESCE(segment, '') = COALESCE(%s, '')
                    ORDER BY created_at ASC
                    LIMIT 1
                """
                
                cursor.execute(action_query, (
                    alert['week_start'],
                    alert['country'],
                    alert.get('city_norm'),
                    alert.get('lob_base'),
                    alert.get('segment')
                ))
                action = cursor.fetchone()
                
                has_action = action is not None
                action_created_at = action['created_at'] if action else None
                
                # Determinar SLA status
                now = datetime.now(LIMA_TZ)
                
                if has_action and action_created_at:
                    action_created_at_tz = action_created_at
                    if action_created_at_tz.tzinfo is None:
                        # Asumir UTC si no tiene timezone
                        action_created_at_tz = pytz.UTC.localize(action_created_at_tz)
                    
                    if action_created_at_tz <= sla_due_at:
                        sla_status = 'OK'
                    elif now > sla_due_at:
                        sla_status = 'BREACH'  # Acción tardía
                    else:
                        sla_status = 'PENDING'
                else:
                    # No tiene acción
                    if now > sla_due_at:
                        sla_status = 'BREACH'
                    else:
                        sla_status = 'PENDING'
                
                # Upsert en tabla SLA
                upsert_sla_query = """
                    INSERT INTO ops.phase2b_sla_status (
                        week_start, country, alert_key, is_critical,
                        has_action, action_created_at, sla_due_at, sla_status, evaluated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                    )
                    ON CONFLICT (week_start, alert_key) DO UPDATE SET
                        has_action = EXCLUDED.has_action,
                        action_created_at = EXCLUDED.action_created_at,
                        sla_due_at = EXCLUDED.sla_due_at,
                        sla_status = EXCLUDED.sla_status,
                        evaluated_at = NOW()
                """
                
                cursor.execute(upsert_sla_query, (
                    alert['week_start'],
                    alert['country'],
                    alert['alert_key'],
                    alert['critical'],
                    has_action,
                    action_created_at,
                    sla_due_at,
                    sla_status
                ))
                count += 1
            
            conn.commit()
            cursor.close()
            logger.info(f"SLA evaluado: {count} alertas críticas para semana {week_start}")
            return count
            
    except Exception as e:
        logger.error(f"Error al evaluar SLA: {e}", exc_info=True)
        raise


def main():
    """Función principal: snapshot + SLA evaluation."""
    try:
        week_start = get_last_closed_week()
        logger.info(f"Procesando semana cerrada: {week_start}")
        
        # A) Snapshot
        snapshot_count = snapshot_alerts(week_start)
        
        # B) SLA evaluation (solo para alertas críticas)
        sla_count = evaluate_sla(week_start)
        
        logger.info("=" * 80)
        logger.info("FASE 2C - SNAPSHOT Y SLA COMPLETADO")
        logger.info("=" * 80)
        logger.info(f"Semana procesada: {week_start}")
        logger.info(f"Alertas snapshot: {snapshot_count}")
        logger.info(f"Alertas críticas evaluadas: {sla_count}")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error en ejecución: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
