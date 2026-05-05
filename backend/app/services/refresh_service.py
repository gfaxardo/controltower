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

# Marcador para refresh vía pipeline Python (sin SELECT ops.fn()).
PYTHON_OMNIVIEW_FACTS_MARKER = "__python__:omniview_business_slice_facts"

# Lista de datasets/fuentes de refresh: SQL `schema.func()` o marcador Python.
KNOWN_REFRESH_DATASETS: List[Tuple[str, str]] = [
    ("mv_real_trips_monthly", "ops.refresh_real_trips_monthly"),
    # Ops Matrix semanal/day/month: mismo job POST /business-slice/real-refresh-omniview
    ("real_business_slice_week_fact", PYTHON_OMNIVIEW_FACTS_MARKER),
]

# Mapeo de datasets a fuentes de truth para freshness (tabla/columna y ancla opcional).
# Validado contra information_schema - si columna no existe, retorna error claro.
DATASET_SOURCE_MAP: Dict[str, Dict[str, str]] = {
    "mv_real_trips_monthly": {
        "table": "public.trips_2026",
        "column": "fecha_finalizacion",
        "target_date_mode": "D-1_CLOSED",
    },
    "real_business_slice_week_fact": {
        "table": "ops.real_business_slice_week_fact",
        "column": "week_start",
        "target_date_mode": "WEEK_CLOSED",
        "period_anchor": "iso_week_monday_of_d_minus_1",
    },
}

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10

# Umbral para considerar datos stale (en minutos)
DATA_FRESHNESS_THRESHOLD_MINUTES = 1440  # 24 horas

# Umbral mínimo de filas para considerar datos con calidad aceptable
MIN_DATA_QUALITY_ROWS = 100


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


def _is_python_omniview_facts(marker: str) -> bool:
    return marker == PYTHON_OMNIVIEW_FACTS_MARKER


def _execute_omniview_facts_refresh(dataset_name: str) -> Dict[str, Any]:
    """
    Misma lógica que POST /ops/business-slice/real-refresh-omniview.
    Siempre force=True para el job por lotes (sin cooldown artificial).
    """
    from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job

    start_time = time.perf_counter()
    attempts: List[Dict[str, Any]] = []
    final_status = "failed"
    final_error: Optional[str] = None

    for attempt in range(1, MAX_RETRIES + 1):
        attempt_start = time.perf_counter()
        attempt_error: Optional[str] = None
        attempt_status = "failed"
        try:
            out = run_business_slice_real_refresh_job(force=True)
            elapsed = round(time.perf_counter() - attempt_start, 2)

            if out.get("skipped"):
                reason = str(out.get("reason") or "skipped")
                attempt_status = "skipped"
                final_status = "skipped"
                final_error = reason
                attempts.append({
                    "attempt": attempt,
                    "status": attempt_status,
                    "error": reason,
                    "duration_seconds": elapsed,
                })
                # skip sin reintentar (sin upstream, etc.)
                break

            errors_list = list(out.get("errors") or [])
            if bool(out.get("ok")) and not errors_list:
                attempt_status = "success"
                final_status = "success"
                final_error = None
                attempts.append({
                    "attempt": attempt,
                    "status": attempt_status,
                    "error": None,
                    "duration_seconds": elapsed,
                })
                break

            attempt_error = str(errors_list[:5]) if errors_list else "real_refresh_ok_false"
            attempt_status = "failed"
            final_error = attempt_error
            attempts.append({
                "attempt": attempt,
                "status": attempt_status,
                "error": attempt_error,
                "duration_seconds": elapsed,
            })

        except Exception as e:
            elapsed = round(time.perf_counter() - attempt_start, 2)
            attempt_error = str(e)
            final_error = attempt_error
            attempts.append({
                "attempt": attempt,
                "status": "failed",
                "error": attempt_error,
                "duration_seconds": elapsed,
            })

        if attempt_status in ("success", "skipped"):
            break
        if attempt < MAX_RETRIES:
            logger.info("Waiting %d seconds before omniview_facts retry %d...", RETRY_DELAY_SECONDS, attempt + 1)
            time.sleep(RETRY_DELAY_SECONDS)

    total_duration = time.perf_counter() - start_time
    return {
        "dataset_name": dataset_name,
        "function": PYTHON_OMNIVIEW_FACTS_MARKER,
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
            
            if _is_python_omniview_facts(func_name):
                result = _execute_omniview_facts_refresh(ds_name)
            else:
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
            # Usar EXTRACT(EPOCH FROM (NOW() - last_refresh_at AT TIME ZONE 'UTC'))
            # para asegurar comparación consistente entre timestamps
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

            # Asegurar que minutes_since nunca sea negativo
            if minutes_since is not None and minutes_since < 0:
                minutes_since = 0.0

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


def _validate_column_exists(conn, table_name: str, column_name: str) -> bool:
    """Valida que una columna exista en la tabla usando information_schema."""
    try:
        cursor = conn.cursor()
        # Parsear schema.table
        if '.' in table_name:
            schema, table = table_name.split('.', 1)
        else:
            schema = 'public'
            table = table_name
        
        cursor.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s AND column_name = %s
        """, (schema, table, column_name))
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    except Exception:
        return False


def get_data_freshness(
    dataset_name: str,
    data_threshold_minutes: int = DATA_FRESHNESS_THRESHOLD_MINUTES,
) -> Dict[str, Any]:
    """
    Frescura operativa cerrada (sin intradía).

    - D-1_CLOSED (trips): día calendario CURRENT_DATE - 1.
    - WEEK_CLOSED (week_fact): lunes ISO de la semana que contiene D-1.
    """
    source_config = DATASET_SOURCE_MAP.get(dataset_name)
    target_mode = (
        (source_config.get("target_date_mode") if source_config else None) or "D-1_CLOSED"
    )

    if not source_config:
        return {
            "dataset": dataset_name,
            "data_status": "unknown",
            "message": f"No source of truth configured for dataset: {dataset_name}",
            "target_date_mode": target_mode,
            "target_date": None,
            "row_count_target_date": None,
            "avg_last_7_closed_days": None,
            "volume_ratio": None,
            "data_quality_status": "UNKNOWN",
        }

    table = source_config["table"]
    column = source_config["column"]
    period_anchor = source_config.get("period_anchor")

    try:
        with get_db() as conn:
            # Validar que la columna exista
            if not _validate_column_exists(conn, table, column):
                return {
                    "dataset": dataset_name,
                    "data_status": "error",
                    "source_table": table,
                    "source_column": column,
                    "message": f"Column '{column}' does not exist in table '{table}'",
                    "target_date_mode": target_mode,
                    "target_date": None,
                    "row_count_target_date": None,
                    "avg_last_7_closed_days": None,
                    "volume_ratio": None,
                    "data_quality_status": "ERROR",
                }

            cursor = conn.cursor()

            if period_anchor == "iso_week_monday_of_d_minus_1":
                params_sel = (
                    "(date_trunc('week', (CURRENT_DATE - INTERVAL '1 day')::timestamp))::date AS target_date"
                )
                hist_span = "7 weeks"
                log_label = "WEEK_CLOSED"
            else:
                params_sel = "(CURRENT_DATE - INTERVAL '1 day')::date AS target_date"
                hist_span = "7 days"
                log_label = "D-1_CLOSED"

            cursor.execute(f"""
                WITH params AS (
                    SELECT {params_sel}
                ),
                target AS (
                    SELECT COUNT(*) AS target_rows
                    FROM {table}, params
                    WHERE DATE({column}) = DATE(params.target_date)
                ),
                history AS (
                    SELECT DATE({column}) AS d, COUNT(*) AS cnt
                    FROM {table}, params
                    WHERE DATE({column}) >= DATE(params.target_date) - INTERVAL '{hist_span}'
                      AND DATE({column}) < DATE(params.target_date)
                    GROUP BY DATE({column})
                )
                SELECT
                    params.target_date,
                    target.target_rows,
                    AVG(history.cnt) AS avg_last_7_closed_days,
                    (SELECT MAX({column}) FROM {table}) AS max_date
                FROM params
                LEFT JOIN target ON TRUE
                LEFT JOIN history ON TRUE
                GROUP BY params.target_date, target.target_rows
            """)

            row = cursor.fetchone()
            cursor.close()

            if not row:
                return {
                    "dataset": dataset_name,
                    "data_status": "stale",
                    "source_table": table,
                    "source_column": column,
                    "message": "No data returned for freshness query",
                    "target_date_mode": target_mode,
                    "target_date": None,
                    "row_count_target_date": None,
                    "avg_last_7_closed_days": None,
                    "volume_ratio": None,
                    "data_quality_status": "UNKNOWN",
                }

            target_date = row[0]
            row_count_target_date = row[1] if row[1] is not None else 0
            avg_last_7_closed_days = row[2]
            last_data_at = row[3]

            # DATE(max_date) >= target_date → fresh (sin conversiones TZ en app)
            data_status = "stale"
            if last_data_at is not None and target_date is not None:
                last_data_date = last_data_at.date() if hasattr(last_data_at, "date") else last_data_at
                target_d = target_date.date() if hasattr(target_date, "date") else target_date
                data_status = "fresh" if last_data_date >= target_d else "stale"

            volume_ratio = None
            data_quality_status = "UNKNOWN"

            if row_count_target_date == 0:
                data_quality_status = "CRITICAL"
                volume_ratio = 0.0
            elif avg_last_7_closed_days is None or avg_last_7_closed_days <= 0:
                data_quality_status = "UNKNOWN"
                volume_ratio = None
            else:
                volume_ratio = row_count_target_date / avg_last_7_closed_days
                if volume_ratio < 0.3:
                    data_quality_status = "CRITICAL"
                elif volume_ratio < 0.7:
                    data_quality_status = "WARNING"
                else:
                    data_quality_status = "OK"

            logger.info(
                "Data quality metrics for %s [%s/%s]: target_date=%s, rows=%s, avg_hist=%s, ratio=%s, status=%s",
                dataset_name, target_mode, log_label, target_date, row_count_target_date,
                avg_last_7_closed_days, volume_ratio, data_quality_status,
            )

            target_date_str = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)

            avg7 = (
                float(avg_last_7_closed_days)
                if avg_last_7_closed_days is not None
                else None
            )
            vol = round(float(volume_ratio), 2) if volume_ratio is not None else None

            return {
                "dataset": dataset_name,
                "data_status": data_status,
                "source_table": table,
                "source_column": column,
                "target_date_mode": target_mode,
                "target_date": target_date_str,
                "row_count_target_date": row_count_target_date,
                "avg_last_7_closed_days": round(avg7, 2) if avg7 is not None else None,
                "volume_ratio": vol,
                "data_quality_status": data_quality_status,
            }

    except Exception as e:
        logger.error("Error getting data freshness for %s: %s", dataset_name, str(e))
        return {
            "dataset": dataset_name,
            "data_status": "error",
            "source_table": table,
            "source_column": column,
            "error": str(e),
            "target_date_mode": target_mode,
            "target_date": None,
            "row_count_target_date": None,
            "avg_last_7_closed_days": None,
            "volume_ratio": None,
            "data_quality_status": "ERROR",
        }


def get_combined_refresh_status(
    dataset_name: Optional[str] = None,
    refresh_threshold_minutes: int = 120,
    data_threshold_minutes: int = DATA_FRESHNESS_THRESHOLD_MINUTES,
) -> Dict[str, Any]:
    """
    Estado combinado refresh MV + freshness D-1_CLOSED + calidad de volumen.

    Args:
        dataset_name: Nombre del dataset
        refresh_threshold_minutes: Minutos para considerar refresh stale
        data_threshold_minutes: Reservado por compatibilidad de API (freshness D-1 no usa umbral por minutos)

    Returns:
        Dict con overall_status y bloque ``data`` solo con campos D-1_CLOSED
    """
    # Obtener status de refresh
    refresh_status = get_last_refresh_status(dataset_name, refresh_threshold_minutes)

    # Dataset name real (puede ser None)
    actual_dataset = dataset_name or refresh_status.get("dataset") or "mv_real_trips_monthly"

    # Obtener freshness de datos (incluye data_quality)
    data_freshness = get_data_freshness(actual_dataset, data_threshold_minutes)

    # Extraer estados
    refresh_st = refresh_status.get("status")
    # data_status siempre string (nunca None en payload)
    data_st = data_freshness.get("data_status") or "unknown"
    data_quality_st = data_freshness.get("data_quality_status")

    # Calcular overall_status con prioridad:
    # 1. data_quality CRITICAL → CRITICAL
    # 2. refresh failed → CRITICAL
    # 3. data stale → WARNING
    # 4. data_quality WARNING → WARNING
    # 5. else → OK (si ambos fresh)
    if data_quality_st == "CRITICAL":
        overall_status = "CRITICAL"
        overall_message = "Data quality critical - volume drop detected"
    elif refresh_st == "failed":
        overall_status = "CRITICAL"
        overall_message = "Refresh failed - data may be outdated"
    elif data_st == "stale":
        overall_status = "WARNING"
        overall_message = "Data source is stale - no new data available"
    elif data_quality_st == "WARNING":
        overall_status = "WARNING"
        overall_message = "Data quality warning - lower than usual volume"
    elif refresh_st == "stale":
        overall_status = "WARNING"
        overall_message = "Refresh is stale - last refresh too old"
    elif refresh_st == "fresh" and data_st == "fresh" and data_quality_st in ("OK", "UNKNOWN"):
        overall_status = "OK"
        tmode = data_freshness.get("target_date_mode") or "D-1_CLOSED"
        if tmode == "WEEK_CLOSED":
            overall_message = (
                "Refresh and closed-week fact data are acceptable"
                if data_quality_st == "OK"
                else "Refresh and closed-week fact data are acceptable (volume baseline unavailable)"
            )
        else:
            overall_message = (
                "Refresh and D-1 closed data are acceptable"
                if data_quality_st == "OK"
                else "Refresh and D-1 closed data are acceptable (volume baseline unavailable)"
            )
    elif refresh_st == "error" or data_st == "error" or data_quality_st == "ERROR":
        overall_status = "ERROR"
        overall_message = "Error checking status"
    else:
        overall_status = "UNKNOWN"
        overall_message = "Status unknown"

    return {
        "dataset": actual_dataset,
        "overall_status": overall_status,
        "overall_message": overall_message,
        "refresh": {
            "status": refresh_st,
            "last_refresh_at": refresh_status.get("last_refresh_at"),
            "minutes_since_last_refresh": refresh_status.get("minutes_since_last_refresh"),
            "last_status": refresh_status.get("last_status"),
            "last_error": refresh_status.get("last_error"),
            "threshold_minutes": refresh_threshold_minutes,
        },
        "data": {
            "source_table": data_freshness.get("source_table"),
            "source_column": data_freshness.get("source_column"),
            "target_date": data_freshness.get("target_date"),
            "target_date_mode": data_freshness.get("target_date_mode"),
            "row_count_target_date": data_freshness.get("row_count_target_date"),
            "avg_last_7_closed_days": data_freshness.get("avg_last_7_closed_days"),
            "volume_ratio": data_freshness.get("volume_ratio"),
            "data_quality_status": data_freshness.get("data_quality_status"),
            "data_status": data_st,
        },
    }
