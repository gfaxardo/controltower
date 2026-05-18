from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
import hashlib
import json

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
                    
                    if values_list:
                        cursor.executemany("""
                            INSERT INTO plan.plan_long_raw (
                                period_type, period, country, city, line_of_business, metric, plan_value, source_file_name, file_hash
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (period_type, period, country, city, line_of_business, metric, file_hash) 
                            DO UPDATE SET plan_value = EXCLUDED.plan_value
                        """, values_list)
                        
                        rows_inserted += cursor.rowcount
                        conn.commit()
                        
                except Exception as e:
                    conn.rollback()
                    errors_count += len(batch)
                    logger.error(f"Error al insertar batch {batch_start}-{batch_end} en plan_long_raw: {e}")
                    continue
            
            cursor.close()
            
            if errors_count > 0:
                logger.warning(f"Se insertaron {rows_inserted} filas en plan_long_raw, {errors_count} filas con errores")
            else:
                logger.info(f"✅ {rows_inserted} filas insertadas en plan_long_raw")
            
            return rows_inserted
            
    except Exception as e:
        logger.error(f"Error al guardar plan_long_raw: {e}")
        raise

def save_plan_projection_raw(
    rows: List[Dict],
    source_file_name: str
) -> int:
    """
    Guarda filas de plan en staging.plan_projection_raw para homologación LOB.
    Mapea columnas del CSV a staging.plan_projection_raw.
    
    Formato esperado en rows:
    - period (YYYY-MM) -> period_date
    - country -> country
    - city -> city
    - line_of_business -> lob_name
    - metric -> trips_plan o revenue_plan según metric
    - plan_value -> trips_plan o revenue_plan
    
    Retorna el número de filas insertadas.
    """
    if not rows:
        return 0
    
    rows_inserted = 0
    batch_size = 100
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            for batch_start in range(0, len(rows), batch_size):
                batch_end = min(batch_start + batch_size, len(rows))
                batch = rows[batch_start:batch_end]
                
                values_list = []
                
                for row in batch:
                    # Mapear period (YYYY-MM) a period_date
                    period_str = row.get('period', '')
                    period_date = None
                    if period_str:
                        try:
                            # Convertir YYYY-MM a DATE (primer día del mes)
                            from datetime import datetime
                            period_date = datetime.strptime(period_str, '%Y-%m').date()
                        except:
                            logger.warning(f"Period '{period_str}' no tiene formato YYYY-MM, se omite")
                            continue
                    
                    country = row.get('country')
                    city = row.get('city')
                    lob_name = row.get('line_of_business')  # Mapeo: line_of_business -> lob_name
                    metric = row.get('metric', '').lower()
                    plan_value = row.get('plan_value')
                    
                    if not lob_name:
                        continue
                    
                    # Mapear metric a trips_plan o revenue_plan
                    trips_plan = None
                    revenue_plan = None
                    
                    if metric == 'trips':
                        trips_plan = plan_value
                    elif metric == 'revenue':
                        revenue_plan = plan_value
                    # commission y active_drivers no se mapean a trips_plan/revenue_plan
                    
                    # Guardar fila completa en raw_row para auditoría
                    raw_row_json = json.dumps(row, default=str)
                    
                    values_list.append((
                        country,
                        city,
                        lob_name,
                        period_date,
                        trips_plan,
                        revenue_plan,
                        raw_row_json
                    ))
                
                if values_list:
                    cursor.executemany("""
                        INSERT INTO staging.plan_projection_raw (
                            country, city, lob_name, period_date, trips_plan, revenue_plan, raw_row
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """, values_list)
                    
                    rows_inserted += cursor.rowcount
                    conn.commit()
            
            cursor.close()
            logger.info(f"✅ {rows_inserted} filas insertadas en staging.plan_projection_raw")
            
            return rows_inserted
            
    except Exception as e:
        logger.error(f"Error al guardar plan_projection_raw: {e}")
        raise

def save_plan_rows(
    rows: List[Dict],
    source_file_name: str,
    file_hash: str,
    table_name: str = 'plan_long_valid'
) -> int:
    """
    Guarda filas de plan en la tabla especificada (plan_long_valid, plan_long_out_of_universe, etc.).
    Retorna el número de filas insertadas.
    """
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
                
                try:
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
                        logger.warning(f"ADVERTENCIA: {len(duplicates_in_batch)} filas duplicadas filtradas en batch {batch_start}-{batch_end} de {table_name}. Insertando {len(values_list)} filas únicas.")
                    
                    if values_list:
                        cursor.executemany(f"""
                            INSERT INTO plan.{table_name} (
                                period_type, period, country, city, line_of_business, metric, plan_value, source_file_name, file_hash
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (period_type, period, country, city, line_of_business, metric, file_hash) 
                            DO UPDATE SET plan_value = EXCLUDED.plan_value
                        """, values_list)
                        
                        rows_inserted += cursor.rowcount
                        conn.commit()
                        
                except Exception as e:
                    conn.rollback()
                    errors_count += len(batch)
                    logger.error(f"Error al insertar batch {batch_start}-{batch_end} en {table_name}: {e}")
                    continue
            
            cursor.close()
            
            if errors_count > 0:
                logger.warning(f"Se insertaron {rows_inserted} filas en {table_name}, {errors_count} filas con errores")
            else:
                logger.info(f"✅ {rows_inserted} filas insertadas en {table_name}")
            
            return rows_inserted
            
    except Exception as e:
        logger.error(f"Error al guardar {table_name}: {e}")
        raise

def calculate_file_hash(file_content: bytes) -> str:
    """Calcula el hash SHA256 del contenido del archivo."""
    return hashlib.sha256(file_content).hexdigest()

def get_plan_data(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year: Optional[int] = None,
    table_name: str = 'plan_long_valid'
) -> List[Dict]:
    """
    Obtiene datos del plan desde la tabla especificada.
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
                where_conditions.append("city = %s")
                params.append(city)
            
            if line_of_business:
                where_conditions.append("line_of_business = %s")
                params.append(line_of_business)
            
            if year:
                where_conditions.append("period LIKE %s")
                params.append(f"{year}-%")
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            # plan_long_missing no tiene columna plan_value (son huecos sin plan)
            if table_name == 'plan_long_missing':
                columns = "period_type, period, country, city, line_of_business, metric, source_file_name, file_hash"
            else:
                columns = "period_type, period, country, city, line_of_business, metric, plan_value, source_file_name, file_hash"
            query = f"""
                SELECT {columns}
                FROM plan.{table_name}
                {where_clause}
                ORDER BY period, country, city, line_of_business, metric
            """
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            rows = [dict(row) for row in results]
            if table_name == 'plan_long_missing':
                for r in rows:
                    r['plan_value'] = None
            return rows
            
    except Exception as e:
        logger.error(f"Error al obtener datos del plan: {e}")
        raise


# ─── Version metadata governance ─────────────────────────────────────────────

def upsert_plan_version_metadata(
    plan_version_key: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    source_filename: Optional[str] = None,
    uploaded_by: Optional[str] = None,
    row_count: Optional[int] = None,
    valid_rows: Optional[int] = None,
    invalid_rows: Optional[int] = None,
    min_period: Optional[str] = None,
    max_period: Optional[str] = None,
    status: str = "active",
) -> Dict[str, Any]:
    """
    Inserta o actualiza metadata de versión en plan.plan_versions_metadata.
    Si ya existe, actualiza campos de metadata (NO el plan_version_key).
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO plan.plan_versions_metadata (
                    plan_version_key, display_name, description, source_filename,
                    uploaded_by, row_count, valid_rows, invalid_rows,
                    min_period, max_period, status, updated_at
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s::date, %s::date, %s, NOW()
                )
                ON CONFLICT (plan_version_key) DO UPDATE SET
                    display_name    = COALESCE(EXCLUDED.display_name, plan.plan_versions_metadata.display_name),
                    description     = COALESCE(EXCLUDED.description, plan.plan_versions_metadata.description),
                    source_filename = COALESCE(EXCLUDED.source_filename, plan.plan_versions_metadata.source_filename),
                    row_count       = COALESCE(EXCLUDED.row_count, plan.plan_versions_metadata.row_count),
                    valid_rows      = COALESCE(EXCLUDED.valid_rows, plan.plan_versions_metadata.valid_rows),
                    invalid_rows    = COALESCE(EXCLUDED.invalid_rows, plan.plan_versions_metadata.invalid_rows),
                    min_period      = COALESCE(EXCLUDED.min_period, plan.plan_versions_metadata.min_period),
                    max_period      = COALESCE(EXCLUDED.max_period, plan.plan_versions_metadata.max_period),
                    updated_at      = NOW()
                RETURNING id, plan_version_key, display_name, status
                """,
                (
                    plan_version_key,
                    display_name or plan_version_key,
                    description,
                    source_filename,
                    uploaded_by,
                    row_count,
                    valid_rows,
                    invalid_rows,
                    min_period,
                    max_period,
                    status,
                ),
            )
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            if result:
                return {
                    "id": result[0],
                    "plan_version_key": result[1],
                    "display_name": result[2],
                    "status": result[3],
                }
            return {"plan_version_key": plan_version_key, "display_name": display_name or plan_version_key, "status": status}
    except Exception as e:
        logger.error(f"Error en upsert_plan_version_metadata: {e}")
        return {"plan_version_key": plan_version_key, "display_name": display_name or plan_version_key, "status": "error", "error": str(e)}


def get_plan_versions_with_metadata() -> List[Dict[str, Any]]:
    """
    Lista versiones desde plan.plan_versions_metadata con conteo de filas
    desde las tablas fuente.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    m.plan_version_key,
                    m.display_name,
                    m.description,
                    m.source_filename,
                    m.uploaded_by,
                    m.uploaded_at,
                    m.status,
                    m.row_count,
                    m.valid_rows,
                    m.invalid_rows,
                    m.min_period,
                    m.max_period,
                    COALESCE(d.row_count, 0) AS actual_rows
                FROM plan.plan_versions_metadata m
                LEFT JOIN (
                    SELECT plan_version, COUNT(*) AS row_count
                    FROM ops.plan_trips_monthly
                    GROUP BY plan_version
                    UNION ALL
                    SELECT plan_version, COUNT(*) AS row_count
                    FROM staging.control_loop_plan_metric_long
                    GROUP BY plan_version
                ) d ON d.plan_version = m.plan_version_key
                ORDER BY m.uploaded_at DESC
                """
            )
            rows = cursor.fetchall()
            cursor.close()
            results = []
            for r in rows:
                results.append({
                    "plan_version_key": r[0],
                    "display_name": r[1],
                    "description": r[2],
                    "source_filename": r[3],
                    "uploaded_by": r[4],
                    "uploaded_at": r[5].isoformat() if r[5] else None,
                    "status": r[6],
                    "row_count": r[7],
                    "valid_rows": r[8],
                    "invalid_rows": r[9],
                    "min_period": r[10].isoformat() if r[10] else None,
                    "max_period": r[11].isoformat() if r[11] else None,
                    "actual_rows": r[12],
                })
            return results
    except Exception as e:
        logger.warning(f"Error en get_plan_versions_with_metadata (fallback a query simple): {e}")
        return []


def update_plan_version_display_name(
    plan_version_key: str,
    display_name: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Actualiza solo display_name y description de una versión.
    No modifica plan_version_key ni datos de plan.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE plan.plan_versions_metadata
                SET display_name = %s,
                    description = COALESCE(%s, description),
                    updated_at = NOW()
                WHERE plan_version_key = %s
                RETURNING plan_version_key, display_name, description, status, updated_at
                """,
                (display_name, description, plan_version_key),
            )
            result = cursor.fetchone()
            conn.commit()
            cursor.close()
            if result:
                return {
                    "plan_version_key": result[0],
                    "display_name": result[1],
                    "description": result[2],
                    "status": result[3],
                    "updated_at": result[4].isoformat() if result[4] else None,
                }
            raise ValueError(f"Versión no encontrada: {plan_version_key}")
    except Exception as e:
        logger.error(f"Error en update_plan_version_display_name: {e}")
        raise
