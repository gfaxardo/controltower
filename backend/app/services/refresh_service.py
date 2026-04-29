"""
Refresh Service - Auditoría y ejecución de refresh de materialized views.
"""
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.db.connection import get_db

logger = logging.getLogger(__name__)

# Lista de datasets/funcsiones de refresh conocidas
KNOWN_REFRESH_FUNCTIONS = [
    "ops.refresh_real_trips_monthly",
]


def run_refresh_job(
    dataset_name: Optional[str] = None,
    custom_functions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Ejecuta refresh de materialized views y registra auditoría.
    
    Args:
        dataset_name: Nombre del dataset a refrescar (si None, refresca todos)
        custom_functions: Lista de funciones SQL adicionales a ejecutar
    
    Returns:
        Dict con resultado de la operación
    """
    start_time = time.perf_counter()
    results = []
    overall_status = "success"
    overall_error = None
    
    # Determinar funciones a ejecutar
    functions_to_run = custom_functions if custom_functions else []
    if dataset_name is None:
        # Ejecutar todas las funciones conocidas
        functions_to_run = KNOWN_REFRESH_FUNCTIONS.copy()
    elif dataset_name and not functions_to_run:
        # Buscar función específica
        func_name = f"ops.refresh_{dataset_name.replace('mv_', '')}"
        if func_name in KNOWN_REFRESH_FUNCTIONS:
            functions_to_run = [func_name]
        else:
            func_name = f"ops.refresh_{dataset_name}"
            functions_to_run = [func_name]
    
    if not functions_to_run:
        logger.warning("No functions to run for dataset: %s", dataset_name)
        return {
            "status": "failed",
            "error": f"No refresh functions found for dataset: {dataset_name}",
            "duration_seconds": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # Ejecutar cada función
    for func in functions_to_run:
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Verificar si la función existe
                cursor.execute("""
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = %s AND p.proname = %s
                """, (func.split('.')[0], func.split('.')[1]))
                
                if not cursor.fetchone():
                    logger.warning("Refresh function does not exist: %s", func)
                    results.append({
                        "function": func,
                        "status": "skipped",
                        "error": "Function does not exist",
                    })
                    continue
                
                # Ejecutar refresh
                func_start = time.perf_counter()
                cursor.execute(f"SELECT {func}()")
                conn.commit()
                func_duration = time.perf_counter() - func_start
                
                results.append({
                    "function": func,
                    "status": "success",
                    "duration_seconds": round(func_duration, 2),
                })
                
                cursor.close()
                
        except Exception as e:
            logger.error("Error executing refresh function %s: %s", func, str(e))
            results.append({
                "function": func,
                "status": "failed",
                "error": str(e),
            })
            overall_status = "failed"
            overall_error = str(e)
    
    total_duration = time.perf_counter() - start_time
    
    # Registrar en auditoría
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bi.refresh_audit (
                    dataset_name,
                    last_refresh_at,
                    status,
                    duration_seconds,
                    error_message
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                dataset_name or "all",
                datetime.utcnow(),
                overall_status,
                round(total_duration, 2),
                overall_error,
            ))
            conn.commit()
            cursor.close()
    except Exception as e:
        logger.error("Failed to write audit record: %s", str(e))
    
    return {
        "status": overall_status,
        "dataset_name": dataset_name or "all",
        "functions_executed": len(results),
        "results": results,
        "duration_seconds": round(total_duration, 2),
        "timestamp": datetime.utcnow().isoformat(),
        "error": overall_error,
    }


def get_last_refresh_status(
    dataset_name: Optional[str] = None,
    threshold_minutes: int = 120,
) -> Dict[str, Any]:
    """
    Obtiene el estado del último refresh para un dataset.
    
    Args:
        dataset_name: Nombre del dataset (None = 'all')
        threshold_minutes: Minutos para considerar datos como stale
    
    Returns:
        Dict con estado del refresh
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Obtener último registro
            cursor.execute("""
                SELECT 
                    dataset_name,
                    last_refresh_at,
                    status,
                    duration_seconds,
                    error_message,
                    EXTRACT(EPOCH FROM (NOW() - last_refresh_at)) / 60 as minutes_since
                FROM bi.refresh_audit
                WHERE dataset_name = COALESCE(%s, 'all')
                ORDER BY created_at DESC
                LIMIT 1
            """, (dataset_name,))
            
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                return {
                    "dataset": dataset_name or "all",
                    "status": "unknown",
                    "message": "No refresh records found",
                    "threshold_minutes": threshold_minutes,
                }
            
            dataset, last_at, last_status, duration, error_msg, minutes_since = row
            
            # Determinar status
            if last_status == "failed":
                status = "failed"
            elif minutes_since > threshold_minutes:
                status = "stale"
            else:
                status = "fresh"
            
            return {
                "dataset": dataset,
                "last_refresh_at": last_at.isoformat() if last_at else None,
                "minutes_since_last_refresh": round(minutes_since, 2) if minutes_since else None,
                "status": status,
                "last_status": last_status,
                "last_error": error_msg,
                "last_duration_seconds": float(duration) if duration else None,
                "threshold_minutes": threshold_minutes,
            }
            
    except Exception as e:
        logger.error("Error getting refresh status: %s", str(e))
        return {
            "dataset": dataset_name or "all",
            "status": "error",
            "message": str(e),
            "threshold_minutes": threshold_minutes,
        }


def list_refresh_history(
    dataset_name: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Lista el historial de refresh.
    
    Args:
        dataset_name: Filtrar por dataset (None = todos)
        limit: Límite de registros
    
    Returns:
        Lista de registros de auditoría
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            if dataset_name:
                cursor.execute("""
                    SELECT 
                        dataset_name,
                        last_refresh_at,
                        status,
                        duration_seconds,
                        error_message,
                        created_at
                    FROM bi.refresh_audit
                    WHERE dataset_name = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (dataset_name, limit))
            else:
                cursor.execute("""
                    SELECT 
                        dataset_name,
                        last_refresh_at,
                        status,
                        duration_seconds,
                        error_message,
                        created_at
                    FROM bi.refresh_audit
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            return [
                {
                    "dataset_name": row[0],
                    "last_refresh_at": row[1].isoformat() if row[1] else None,
                    "status": row[2],
                    "duration_seconds": float(row[3]) if row[3] else None,
                    "error_message": row[4],
                    "created_at": row[5].isoformat() if row[5] else None,
                }
                for row in rows
            ]
            
    except Exception as e:
        logger.error("Error listing refresh history: %s", str(e))
        return []
