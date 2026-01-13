from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

def save_plan_rows_raw(
    rows: List[Dict],
    source_file_name: str,
    file_hash: str
) -> int:
    """
    Guarda filas de plan en plan_long_raw.
    Retorna el número de filas insertadas.
    """
    # #region agent log
    import json
    import time
    LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
    start_time = time.time()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Inicio save_plan_rows_raw","data":{"total_rows":len(rows)},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    if not rows:
        return 0
    
    rows_inserted = 0
    errors_count = 0
    batch_size = 100
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            for batch_start in range(0, len(rows), batch_size):
                batch_end = min(batch_start + batch_size, len(rows))
                batch = rows[batch_start:batch_end]
                
                # #region agent log
                try:
                    with open(LOG_PATH, "a", encoding="utf-8") as f:
                        json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Procesando batch","data":{"batch_start":batch_start,"batch_end":batch_end,"batch_size":len(batch),"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                        f.write("\n")
                except: pass
                # #endregion
                
                try:
                    # #region agent log
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Construyendo values_list","data":{"batch_size":len(batch)},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                            f.write("\n")
                    except: pass
                    # #endregion
                    
                    values_list = []
                    seen_keys = set()
                    duplicates_in_batch = []
                    
                    for idx, row in enumerate(batch):
                        conflict_key = (
                            row.get('period_type', 'month'),
                            row.get('period'),
                            row.get('country'),
                            row.get('city'),
                            row.get('line_of_business'),
                            row.get('metric'),
                            file_hash
                        )
                        
                        if conflict_key in seen_keys:
                            duplicates_in_batch.append({
                                'index': idx,
                                'key': conflict_key,
                                'plan_value': row.get('plan_value')
                            })
                            continue
                        
                        seen_keys.add(conflict_key)
                        values_list.append((
                            row.get('period_type', 'month'),
                            row.get('period'),
                            row.get('country'),
                            row.get('city'),
                            row.get('line_of_business'),
                            row.get('metric'),
                            row.get('plan_value'),
                            source_file_name,
                            file_hash
                        ))
                    
                    if duplicates_in_batch:
                        logger.warning(f"ADVERTENCIA: {len(duplicates_in_batch)} filas duplicadas filtradas en batch {batch_start}-{batch_end} de plan_long_raw. Insertando {len(values_list)} filas únicas.")
                    
                    if not values_list:
                        logger.warning(f"Batch {batch_start}-{batch_end} vacío después de filtrar duplicados en plan_long_raw, saltando INSERT")
                        continue
                    
                    # #region agent log
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Antes de executemany","data":{"values_count":len(values_list)},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                            f.write("\n")
                    except: pass
                    # #endregion
                    
                    from psycopg2.extras import execute_values
                    execute_values(
                        cursor,
                        """
                        INSERT INTO plan.plan_long_raw 
                        (period_type, period, country, city, line_of_business, metric, plan_value, source_file_name, file_hash)
                        VALUES %s
                        ON CONFLICT (period_type, period, country, city, line_of_business, metric, file_hash)
                        DO UPDATE SET
                            plan_value = EXCLUDED.plan_value,
                            uploaded_at = NOW()
                        """,
                        values_list,
                        template=None,
                        page_size=100
                    )
                    
                    # #region agent log
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Después de executemany","data":{"batch_start":batch_start},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                            f.write("\n")
                    except: pass
                    # #endregion
                    
                    rows_inserted += len(values_list) if values_list else 0
                    
                except Exception as e:
                    # #region agent log
                    try:
                        with open(LOG_PATH, "a", encoding="utf-8") as f:
                            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Error en batch","data":{"error":str(e),"error_type":type(e).__name__,"batch_start":batch_start},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                            f.write("\n")
                    except: pass
                    # #endregion
                    
                    errors_count += len(batch)
                    logger.warning(f"Error al insertar batch {batch_start}-{batch_end} en plan_long_raw: {e}")
                    conn.rollback()
                    raise
            
            conn.commit()
            cursor.close()
            
    except Exception as e:
        logger.error(f"Error en transacción save_plan_rows_raw: {e}")
        errors_count = len(rows) - rows_inserted
    
    # #region agent log
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H2","location":"plan_repo.py:save_plan_rows_raw","message":"Fin save_plan_rows_raw batch","data":{"rows_inserted":rows_inserted,"errors_count":errors_count,"total_elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    logger.info(f"Guardadas {rows_inserted} filas en plan.plan_long_raw ({errors_count} errores)")
    return rows_inserted

def save_plan_rows(
    rows: List[Dict],
    source_file_name: str,
    file_hash: str,
    table_name: str = 'plan_long_valid'
) -> int:
    """
    Guarda filas de plan en una de las 3 tablas: plan_long_valid, plan_long_out_of_universe, plan_long_missing.
    Retorna el número de filas insertadas.
    """
    if table_name not in ['plan_long_valid', 'plan_long_out_of_universe', 'plan_long_missing']:
        raise ValueError(f"Tabla inválida: {table_name}")
    
    if not rows:
        return 0
    
    # #region agent log
    import json
    import time
    LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
    start_time = time.time()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H5","location":"plan_repo.py:save_plan_rows","message":"Iniciando guardado batch","data":{"total_rows":len(rows),"table_name":table_name},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    rows_inserted = 0
    errors_count = 0
    batch_size = 100
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            for batch_start in range(0, len(rows), batch_size):
                batch_end = min(batch_start + batch_size, len(rows))
                batch = rows[batch_start:batch_end]
                
                # #region agent log
                try:
                    with open(LOG_PATH, "a", encoding="utf-8") as f:
                        json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H5","location":"plan_repo.py:save_plan_rows","message":"Procesando batch","data":{"batch_start":batch_start,"batch_end":batch_end,"table_name":table_name,"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                        f.write("\n")
                except: pass
                # #endregion
                
                try:
                    if table_name == 'plan_long_missing':
                        values_list = []
                        for row in batch:
                            values_list.append((
                                row.get('period_type', 'month'),
                                row.get('period'),
                                row.get('country'),
                                row.get('city'),
                                row.get('line_of_business'),
                                row.get('metric'),
                                source_file_name,
                                file_hash
                            ))
                        
                        from psycopg2.extras import execute_values
                        execute_values(
                            cursor,
                            f"""
                            INSERT INTO plan.{table_name} 
                            (period_type, period, country, city, line_of_business, metric, source_file_name, file_hash)
                            VALUES %s
                            ON CONFLICT (period_type, period, country, city, line_of_business, metric, file_hash)
                            DO NOTHING
                            """,
                            values_list,
                            template=None,
                            page_size=100
                        )
                    else:
                        values_list = []
                        seen_keys = set()
                        duplicates_in_batch = []
                        
                        for idx, row in enumerate(batch):
                            conflict_key = (
                                row.get('period_type', 'month'),
                                row.get('period'),
                                row.get('country'),
                                row.get('city'),
                                row.get('line_of_business'),
                                row.get('metric'),
                                file_hash
                            )
                            
                            if conflict_key in seen_keys:
                                duplicates_in_batch.append({
                                    'index': idx,
                                    'key': conflict_key,
                                    'plan_value': row.get('plan_value')
                                })
                                continue
                            
                            seen_keys.add(conflict_key)
                            
                            if table_name == 'plan_long_out_of_universe':
                                if 'reason' not in row:
                                    logger.error(f"ERROR: Fila sin key 'reason': {row}")
                                    reason = 'UNKNOWN_REASON'
                                else:
                                    reason = row.get('reason')
                                    if not reason or reason is None:
                                        logger.warning(f"ADVERTENCIA: reason es None o vacío en fila, usando UNKNOWN_REASON")
                                        reason = 'UNKNOWN_REASON'
                                
                                values_list.append((
                                    row.get('period_type', 'month'),
                                    row.get('period'),
                                    row.get('country'),
                                    row.get('city'),
                                    row.get('line_of_business'),
                                    row.get('metric'),
                                    row.get('plan_value'),
                                    source_file_name,
                                    file_hash,
                                    reason
                                ))
                            else:
                                values_list.append((
                                    row.get('period_type', 'month'),
                                    row.get('period'),
                                    row.get('country'),
                                    row.get('city'),
                                    row.get('line_of_business'),
                                    row.get('metric'),
                                    row.get('plan_value'),
                                    source_file_name,
                                    file_hash
                                ))
                        
                        from psycopg2.extras import execute_values
                        if duplicates_in_batch:
                            import json
                            import time
                            LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
                            try:
                                with open(LOG_PATH, "a", encoding="utf-8") as f:
                                    json.dump({
                                        "sessionId": "debug-session",
                                        "runId": "post-fix",
                                        "hypothesisId": "H6",
                                        "location": "plan_repo.py:save_plan_rows",
                                        "message": "DUPLICADOS EN BATCH filtrados",
                                        "data": {
                                            "batch_start": batch_start,
                                            "batch_end": batch_end,
                                            "duplicates_count": len(duplicates_in_batch),
                                            "duplicates": duplicates_in_batch[:5],
                                            "total_in_batch": len(batch),
                                            "unique_keys": len(seen_keys),
                                            "values_list_size": len(values_list)
                                        },
                                        "timestamp": int(time.time() * 1000)
                                    }, f, ensure_ascii=False)
                                    f.write("\n")
                            except: pass
                            logger.warning(f"ADVERTENCIA: {len(duplicates_in_batch)} filas duplicadas filtradas en batch {batch_start}-{batch_end}. Insertando {len(values_list)} filas únicas.")
                        
                        if not values_list:
                            logger.warning(f"Batch {batch_start}-{batch_end} vacío después de filtrar duplicados, saltando INSERT")
                            continue
                        
                        if table_name == 'plan_long_out_of_universe':
                            if values_list and len(values_list[0]) != 10:
                                logger.error(f"ERROR: values_list tiene {len(values_list[0])} elementos, se esperan 10 (incluyendo reason)")
                            
                            template_sql = "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                            execute_values(
                                cursor,
                                f"""
                                INSERT INTO plan.{table_name} 
                                (period_type, period, country, city, line_of_business, metric, plan_value, source_file_name, file_hash, reason)
                                VALUES %s
                                ON CONFLICT (period_type, period, country, city, line_of_business, metric, file_hash)
                                DO UPDATE SET
                                    plan_value = EXCLUDED.plan_value,
                                    reason = EXCLUDED.reason,
                                    uploaded_at = NOW()
                                """,
                                values_list,
                                template=template_sql,
                                page_size=100
                            )
                        else:
                            execute_values(
                                cursor,
                                f"""
                                INSERT INTO plan.{table_name} 
                                (period_type, period, country, city, line_of_business, metric, plan_value, source_file_name, file_hash)
                                VALUES %s
                                ON CONFLICT (period_type, period, country, city, line_of_business, metric, file_hash)
                                DO UPDATE SET
                                    plan_value = EXCLUDED.plan_value,
                                    uploaded_at = NOW()
                                """,
                                values_list,
                                template=None,
                                page_size=100
                            )
                    
                    rows_inserted += len(values_list) if values_list else 0
                    
                except Exception as e:
                    errors_count += len(batch)
                    logger.warning(f"Error al insertar batch {batch_start}-{batch_end} en {table_name}: {e}")
                    conn.rollback()
                    raise
            
            conn.commit()
            
            if table_name == 'plan_long_out_of_universe' and rows_inserted > 0:
                cursor_log = conn.cursor(cursor_factory=RealDictCursor)
                cursor_log.execute("""
                    SELECT reason, COUNT(*) as count
                    FROM plan.plan_long_out_of_universe
                    WHERE file_hash = %s
                    GROUP BY reason
                    ORDER BY count DESC
                """, (file_hash,))
                reason_stats = cursor_log.fetchall()
                cursor_log.close()
                
                reason_summary = {}
                null_reason_count = 0
                for row in reason_stats:
                    reason_val = row['reason']
                    if reason_val is None:
                        null_reason_count += row['count']
                    else:
                        reason_summary[reason_val] = row['count']
                
                logger.info(f"Validación post-insert para {table_name} (file_hash={file_hash[:8]}...): {reason_summary}")
                
                if null_reason_count > 0:
                    logger.error(f"ERROR CRÍTICO: Se encontraron {null_reason_count} filas con reason=NULL en {table_name} después del INSERT")
                else:
                    logger.info(f"✓ Validación exitosa: Todas las {rows_inserted} filas tienen reason no-null")
            
            cursor.close()
            
    except Exception as e:
        logger.error(f"Error en transacción save_plan_rows: {e}")
        errors_count = len(rows) - rows_inserted
    
    # #region agent log
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H5","location":"plan_repo.py:save_plan_rows","message":"Guardado completado batch","data":{"rows_inserted":rows_inserted,"errors_count":errors_count,"table_name":table_name,"total_elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    logger.info(f"Guardadas {rows_inserted} filas en plan.{table_name} ({errors_count} errores)")
    return rows_inserted

def get_plan_data(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year: Optional[int] = None,
    table_name: str = 'plan_long_valid'
) -> List[Dict]:
    """
    Obtiene datos de plan desde una de las 3 tablas.
    """
    if table_name not in ['plan_long_valid', 'plan_long_out_of_universe', 'plan_long_missing']:
        raise ValueError(f"Tabla inválida: {table_name}")
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            where_conditions = []
            params = []
            
            if country:
                where_conditions.append("COALESCE(country, '') = %s")
                params.append(country)
            
            if city:
                where_conditions.append("COALESCE(city, '') = %s")
                params.append(city)
            
            if line_of_business:
                where_conditions.append("COALESCE(line_of_business, '') = %s")
                params.append(line_of_business)
            
            if year:
                where_conditions.append("EXTRACT(YEAR FROM TO_DATE(period, 'YYYY-MM')) = %s")
                params.append(year)
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            if table_name == 'plan_long_missing':
                query = f"""
                    SELECT 
                        period_type,
                        period,
                        country,
                        city,
                        line_of_business,
                        metric,
                        NULL as plan_value
                    FROM plan.{table_name}
                    {where_clause}
                    ORDER BY period DESC
                """
            else:
                if table_name == 'plan_long_out_of_universe':
                    query = f"""
                        SELECT 
                            period_type,
                            period,
                            country,
                            city,
                            line_of_business,
                            metric,
                            plan_value,
                            reason
                        FROM plan.{table_name}
                        {where_clause}
                        ORDER BY period DESC
                    """
                else:
                    query = f"""
                        SELECT 
                            period_type,
                            period,
                            country,
                            city,
                            line_of_business,
                            metric,
                            plan_value
                        FROM plan.{table_name}
                        {where_clause}
                        ORDER BY period DESC
                    """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener datos de plan: {e}")
        raise

def calculate_file_hash(file_content: bytes) -> str:
    """Calcula el hash SHA256 de un archivo."""
    return hashlib.sha256(file_content).hexdigest()

