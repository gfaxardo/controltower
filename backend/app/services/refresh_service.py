"""
Refresh Service - Auditoría y ejecución de refresh de materialized views.
HARDENED: Lock anti-concurrencia + retry automático + registro granular.
"""
import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from app.db.connection import get_db

logger = logging.getLogger(__name__)

# Lista de datasets/funcsiones de refresh conocidas con sus nombres de dataset
KNOWN_REFRESH_DATASETS: List[Tuple[str, str]] = [
    ("mv_real_trips_monthly", "ops.refresh_real_trips_monthly"),
]

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10


def _acquire_lock(lock_name: str = "global") -> bool:
    """
    Adquiere el lock para evitar ejecución concurrente.
    
    Returns:
        True si se adquirió el lock, False si ya está corriendo otro proceso.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Verificar si ya hay un lock activo
            cursor.execute("""
                SELECT is_running, started_at 
                FROM bi.refresh_lock 
                WHERE lock_name = %s
                FOR UPDATE
            """, (lock_name,))
            
            row = cursor.fetchone()
            
            if row is None:
                # Crear registro de lock si no existe
                cursor.execute("""
                    INSERT INTO bi.refresh_lock (lock_name, is_running, updated_at)
                    VALUES (%s, TRUE, NOW())
                    ON CONFLICT (lock_name) DO UPDATE 
                    SET is_running = TRUE, started_at = NOW(), updated_at = NOW()
                    WHERE bi.refresh_lock.lock_name = %s AND bi.refresh_lock.is_running = FALSE
                """, (lock_name, lock_name))
            elif row[0]:  # is_running = True
                # Lock activo - verificar si es muy viejo (más de 2 horas)
                started_at = row[1]
                if started_at:
                    minutes_running = (datetime.now() - started_at).total_seconds() / 60
                    if minutes_running < 120:
                        logger.warning("Refresh already running since %s (%.1f min). Aborting.", started_at, minutes_running)
                        cursor.close()
                        return False
                    else:
                        # Lock zombie - resetear
                        logger.warning("Zombie lock detected (%.1f min). Resetting.", minutes_running)
                        cursor.execute("""
                            UPDATE bi.refresh_lock 
                            SET is_running = TRUE, started_at = NOW(), updated_at = NOW()
                            WHERE lock_name = %s
                        """, (lock_name,))
                else:
                    cursor.close()
                    return False
            else:
                # Adquirir lock
                cursor.execute("""
                    UPDATE bi.refresh_lock 
                    SET is_running = TRUE, started_at = NOW(), updated_at = NOW()
                    WHERE lock_name = %s
                """, (lock_name,))
            
            conn.commit()
            cursor.close()
            logger.info("Lock acquired for refresh job")
            return True
            
    except Exception as e:
        logger.error("Error acquiring lock: %s", str(e))
        return False


def _release_lock(lock_name: str = "global") -> None:
    """Libera el lock después de la ejecución."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE bi.refresh_lock 
                SET is_running = FALSE, updated_at = NOW()
                WHERE lock_name = %s
            """, (lock_name,))
            conn.commit()
            cursor.close()
            logger.info("Lock released")
    except Exception as e:
        logger.error("Error releasing lock: %s", str(e))


def _check_function_exists(conn, func_name: str) -> bool:
    """Verifica si una función SQL existe."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1 FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = %s AND p.proname = %s
        """, (func_name.split('.')[0], func_name.split('.')[1]))
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    except Exception:
        return False


def _execute_single_refresh(
    dataset_name: str,
    func_name: str,
) -> Dict[str, Any]:
    """
    Ejecuta el refresh de un solo dataset con retry automático.
    
    Returns:
        Dict con resultado final del refresh (incluye todos los intentos).
    """
    start_time = time.perf_counter()
    attempts = []
    final_status = "failed"
    final_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        attempt_start = time.perf_counter()
        attempt_error = None
        attempt_status = "failed"
        
        try:
            with get_db() as conn:
                # Verificar si la función existe
                if not _check_function_exists(conn, func_name):
                    attempt_error = f"Function {func_name} does not exist"
                    attempt_status = "skipped"
                    logger.warning("%s - %s", func_name, attempt_error)
                else:
                    # Ejecutar refresh
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT {func_name}()")
                    conn.commit()
                    cursor.close()
                    attempt_status = "success"
                    final_status = "success"
                    final_error = None
                    
        except Exception as e:
            attempt_error = str(e)
            final_error = attempt_error
            logger.error("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, dataset_name, attempt_error)
        
        attempt_duration = time.perf_counter() - attempt_start
        
        attempts.append({
            "attempt": attempt,
            "status": attempt_status,
            "error": attempt_error,
            "duration_seconds": round(attempt_duration, 2),
        })
        
        # Si fue exitoso, no reintentar
        if attempt_status == "success":
            break
        
        # Si no es el último intento, esperar antes de reintentar
        if attempt < MAX_RETRIES and attempt_status != "skipped":
            logger.info("Waiting %d seconds before retry %d...", RETRY_DELAY_SECONDS, attempt + 1)
            time.sleep(RETRY_DELAY_SECONDS)
    
    total_duration = time.perf_counter() - start_time
    
    return {
        "dataset_name": dataset_name,
        "function": func_name,
        "status": final_status,
        "error": final_error,
        "duration_seconds": round(total_duration, 2),
        "attempts": attempts,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _write_audit_record(
    dataset_name: str,
    status: str,
    duration_seconds: float,
    error_message: Optional[str],
) -> None:
    """Escribe un registro en la tabla de auditoría."""
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
                dataset_name,
                datetime.utcnow(),
                status,
                round(duration_seconds, 2),
                error_message,
            ))
            conn.commit()
            cursor.close()
            logger.debug("Audit record written for %s", dataset_name)
    except Exception as e:
        logger.error("Failed to write audit record for %s: %s", dataset_name, str(e))


def run_refresh_job(
    dataset_filter: Optional[str] = None,
    lock_name: str = "global",
) -> Dict[str, Any]:
    """
    Ejecuta refresh de materialized views con lock anti-concurrencia y retry.
    
    Args:
        dataset_filter: Nombre del dataset específico (None = todos)
        lock_name: Nombre del lock para anti-concurrencia
    
    Returns:
        Dict con resultado completo de la operación.
    """
    job_start_time = time.perf_counter()
    
    # Adquirir lock
    if not _acquire_lock(lock_name):
        return {
            "status": "skipped",
            "reason": "another_refresh_is_running",
            "message": "Another refresh job is currently running. Aborting.",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    try:
        # Determinar datasets a procesar
        datasets_to_process = []
        if dataset_filter:
            # Buscar dataset específico
            for ds_name, func_name in KNOWN_REFRESH_DATASETS:
                if ds_name == dataset_filter or ds_name.replace('mv_', '') == dataset_filter:
                    datasets_to_process.append((ds_name, func_name))
                    break
            if not datasets_to_process:
                # Intentar construir nombre de función
                func_name = f"ops.refresh_{dataset_filter.replace('mv_', '')}"
                datasets_to_process.append((dataset_filter, func_name))
        else:
            # Procesar todos
            datasets_to_process = KNOWN_REFRESH_DATASETS.copy()
        
        if not datasets_to_process:
            _release_lock(lock_name)
            return {
                "status": "failed",
                "error": f"No datasets found for filter: {dataset_filter}",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        logger.info("Starting refresh for %d dataset(s)", len(datasets_to_process))
        
        # Procesar cada dataset
        results = []
        overall_success = True
        
        for ds_name, func_name in datasets_to_process:
            logger.info("Refreshing dataset: %s", ds_name)
            
            result = _execute_single_refresh(ds_name, func_name)
            results.append(result)
            
            # Registrar en auditoría (granular por dataset)
            _write_audit_record(
                dataset_name=ds_name,
                status=result["status"],
                duration_seconds=result["duration_seconds"],
                error_message=result.get("error"),
            )
            
            if result["status"] not in ("success", "skipped"):
                overall_success = False
        
        total_duration = time.perf_counter() - job_start_time
        
        return {
            "status": "success" if overall_success else "partial_failure",
            "datasets_processed": len(datasets_to_process),
            "datasets_successful": sum(1 for r in results if r["status"] == "success"),
            "datasets_failed": sum(1 for r in results if r["status"] == "failed"),
            "duration_seconds": round(total_duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }
        
    except Exception as e:
        logger.exception("Unexpected error in refresh job")
        total_duration = time.perf_counter() - job_start_time
        return {
            "status": "failed",
            "error": str(e),
            "duration_seconds": round(total_duration, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    finally:
        # Siempre liberar el lock
        _release_lock(lock_name)


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
                WHERE dataset_name = COALESCE(%s, 'mv_real_trips_monthly')
                ORDER BY created_at DESC
                LIMIT 1
            """, (dataset_name,))
            
            row = cursor.fetchone()
            cursor.close()
            
            if not row:
                return {
                    "dataset": dataset_name or "mv_real_trips_monthly",
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
            "dataset": dataset_name or "mv_real_trips_monthly",
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


def check_refresh_lock_status(lock_name: str = "global") -> Dict[str, Any]:
    """Verifica el estado actual del lock."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lock_name, is_running, started_at, updated_at
                FROM bi.refresh_lock
                WHERE lock_name = %s
            """, (lock_name,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    "lock_name": row[0],
                    "is_running": row[1],
                    "started_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None,
                }
            return {"lock_name": lock_name, "is_running": False, "status": "not_initialized"}
    except Exception as e:
        logger.error("Error checking lock status: %s", str(e))
        return {"lock_name": lock_name, "status": "error", "error": str(e)}
