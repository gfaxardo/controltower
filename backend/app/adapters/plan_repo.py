from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional
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
            
            query = f"""
                SELECT 
                    period_type,
                    period,
                    country,
                    city,
                    line_of_business,
                    metric,
                    plan_value,
                    source_file_name,
                    file_hash
                FROM plan.{table_name}
                {where_clause}
                ORDER BY period, country, city, line_of_business, metric
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
            
    except Exception as e:
        logger.error(f"Error al obtener datos del plan: {e}")
        raise
