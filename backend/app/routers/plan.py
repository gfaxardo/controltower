from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.plan_parser_service import parse_proyeccion_sheet_legacy as parse_proyeccion_sheet, parse_simple_template
from app.services.plan_parser_service import _separate_by_universe, _find_missing_combos
from app.adapters.plan_repo import save_plan_rows, save_plan_rows_raw, save_plan_projection_raw, calculate_file_hash, get_plan_data
from app.models.schemas import PlanUploadResponse
from typing import Optional, List, Dict
from datetime import datetime
import logging
import os
import sys
import tempfile
import importlib.util

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plan", tags=["plan"])

@router.post("/upload_simple", response_model=PlanUploadResponse)
async def upload_plan_simple(file: UploadFile = File(...)):
    """
    Sube un archivo de plantilla simple (CSV o XLSX) del Plan y lo procesa.
    Valida contra universo operativo y separa en 3 tablas: valid, out_of_universe, missing.
    
    Formato esperado: period, country, city, line_of_business, metric, plan_value
    """
    if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx, .xls) o CSV (.csv)")
    
    try:
        # #region agent log
        import json
        import time
        LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
        start_time = time.time()
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"plan.py:upload_plan_simple","message":"Inicio upload_simple","data":{"filename":file.filename},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        from app.services.ops_universe_service import clear_cache, get_ops_universe_set
        clear_cache()
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"plan.py:upload_plan_simple","message":"Después de clear_cache","data":{"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        file_content = await file.read()
        file_hash = calculate_file_hash(file_content)
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"plan.py:upload_plan_simple","message":"Después de leer archivo","data":{"file_size":len(file_content),"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        rows_long = parse_simple_template(file_content, file.filename)
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"plan.py:upload_plan_simple","message":"Después de parse_simple_template","data":{"rows_count":len(rows_long),"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        # Guardar en staging.plan_projection_raw para homologación LOB
        try:
            save_plan_projection_raw(rows_long, file.filename)
        except Exception as e:
            logger.warning(f"Error al guardar en staging.plan_projection_raw (no crítico): {e}")
        
        rows_loaded = save_plan_rows_raw(rows_long, file.filename, file_hash)
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"plan.py:upload_plan_simple","message":"Después de save_plan_rows_raw","data":{"rows_loaded":rows_loaded,"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        valid_rows, out_of_universe_rows = _separate_by_universe(rows_long)
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H3","location":"plan.py:upload_plan_simple","message":"Después de _separate_by_universe","data":{"valid_count":len(valid_rows),"out_of_universe_count":len(out_of_universe_rows),"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        missing_combos = _find_missing_combos(valid_rows, out_of_universe_rows)
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"plan.py:upload_plan_simple","message":"Después de _find_missing_combos","data":{"missing_count":len(missing_combos),"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        rows_valid = save_plan_rows(valid_rows, file.filename, file_hash, 'plan_long_valid')
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"plan.py:upload_plan_simple","message":"Después de save_plan_rows valid","data":{"rows_valid":rows_valid,"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        rows_out_of_universe = save_plan_rows(out_of_universe_rows, file.filename, file_hash, 'plan_long_out_of_universe')
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"plan.py:upload_plan_simple","message":"Después de save_plan_rows out_of_universe","data":{"rows_out_of_universe":rows_out_of_universe,"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        rows_missing = save_plan_rows(missing_combos, file.filename, file_hash, 'plan_long_missing')
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"plan.py:upload_plan_simple","message":"Después de save_plan_rows missing","data":{"rows_missing":rows_missing,"elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        preview_out_of_universe = out_of_universe_rows[:20]
        
        response = PlanUploadResponse(
            rows_valid=rows_valid,
            rows_out_of_universe=rows_out_of_universe,
            missing_combos_count=len(missing_combos),
            source_file_name=file.filename,
            uploaded_at=datetime.now(),
            file_hash=file_hash,
            rows_loaded=rows_loaded,
            preview_out_of_universe_top20=preview_out_of_universe
        )
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"run1","hypothesisId":"H1","location":"plan.py:upload_plan_simple","message":"Antes de retornar respuesta","data":{"total_elapsed":time.time()-start_time},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al subir plan simple: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")

@router.post("/upload_ruta27")
async def upload_plan_ruta27(
    file: UploadFile = File(...),
    plan_version: Optional[str] = Query(None, description="Versión del plan (ej: ruta27_v2026_01_17). Si no se proporciona, se genera automáticamente"),
    replace_all: bool = Query(False, description="Si es True, borra TODOS los planes anteriores antes de subir el nuevo. ADVERTENCIA: Esto borra todo el historial.")
):
    """
    Sube un archivo CSV del Plan en formato Ruta 27 (formato wide).
    Ingiere directamente a ops.plan_trips_monthly (tabla canónica).
    
    Formato esperado: country, city, lob_base, segment, year, month, trips_plan, active_drivers_plan, avg_ticket_plan
    
    COMPORTAMIENTO:
    - Por defecto: Los planes se acumulan por versión (append-only). Cada versión se mantiene.
    - Con replace_all=True: Se borran TODOS los planes anteriores antes de subir el nuevo.
    - Las vistas "latest" siempre muestran la versión más reciente basada en created_at.
    """
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="El archivo debe ser CSV (.csv)")
    
    try:
        from app.db.connection import get_db
        
        # Si replace_all=True, borrar todos los planes anteriores de TODAS las tablas
        if replace_all:
            from app.db.connection import get_db
            with get_db() as conn:
                cursor = conn.cursor()
                try:
                    # Limpiar todas las tablas de plan
                    tables_to_clear = [
                        'ops.plan_trips_monthly',
                        'plan.plan_long_raw',
                        'plan.plan_long_valid',
                        'plan.plan_long_out_of_universe',
                        'plan.plan_long_missing'
                    ]
                    
                    total_deleted = 0
                    for table_name in tables_to_clear:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                            count = cursor.fetchone()[0]
                            if count > 0:
                                cursor.execute(f"DELETE FROM {table_name}")
                                deleted = cursor.rowcount
                                total_deleted += deleted
                                logger.info(f"Borrados {deleted} registros de {table_name}")
                        except Exception as e:
                            # Si la tabla no existe, continuar
                            logger.warning(f"Tabla {table_name} no existe o error al limpiar: {e}")
                    
                    conn.commit()
                    logger.info(f"Limpieza completa: {total_deleted} registros borrados de todas las tablas de plan")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error al borrar planes anteriores: {e}")
                    raise HTTPException(status_code=500, detail=f"Error al borrar planes anteriores: {str(e)}")
                finally:
                    cursor.close()
        
        # Generar versión si no se proporciona
        if not plan_version:
            plan_version = f"ruta27_v{datetime.now().strftime('%Y_%m_%d')}"
        
        # Guardar archivo temporalmente
        file_content = await file.read()
        
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Importar función de ingesta dinámicamente
            # __file__ está en backend/app/routers/plan.py, necesitamos subir 3 niveles para llegar a backend/
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            script_path = os.path.join(backend_dir, 'scripts', 'ingest_plan_from_csv_ruta27.py')
            
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script de ingesta no encontrado: {script_path}")
            
            spec = importlib.util.spec_from_file_location("ingest_plan_from_csv_ruta27", script_path)
            ingest_module = importlib.util.module_from_spec(spec)
            sys.modules['ingest_plan_from_csv_ruta27'] = ingest_module
            spec.loader.exec_module(ingest_module)
            
            # Ejecutar ingesta
            final_version, inserted_count = ingest_module.ingest_plan_from_csv(tmp_path, plan_version)
            
            # Refrescar vistas materializadas si existen
            from app.db.connection import get_db
            with get_db() as conn:
                refresh_cursor = conn.cursor()
                try:
                    # Refrescar vista materializada de real si existe
                    refresh_cursor.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_matviews 
                            WHERE schemaname = 'ops' 
                            AND matviewname = 'mv_real_trips_monthly'
                        )
                    """)
                    if refresh_cursor.fetchone()[0]:
                        refresh_cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly")
                        logger.info("Vista materializada ops.mv_real_trips_monthly refrescada")
                    
                    conn.commit()
                except Exception as e:
                    # No es crítico si falla el refresh
                    logger.warning(f"No se pudo refrescar vistas materializadas: {e}")
                finally:
                    refresh_cursor.close()
            
            return {
                "success": True,
                "plan_version": final_version,
                "rows_inserted": inserted_count,
                "source_file_name": file.filename,
                "uploaded_at": datetime.now(),
                "replaced_previous": replace_all,
                "message": f"Plan ingerido exitosamente: {inserted_count} registros con versión {final_version}" + 
                          (". Planes anteriores fueron borrados." if replace_all else ". Planes anteriores se mantienen (append-only).") +
                          " Vistas actualizadas automáticamente."
            }
        finally:
            # Limpiar archivo temporal
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Error al subir plan Ruta 27: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")

@router.post("/upload", response_model=PlanUploadResponse)
async def upload_plan(file: UploadFile = File(...)):
    """
    [DEPRECATED] Sube un archivo Excel del Plan (formato complejo) y lo procesa.
    Usar /plan/upload_simple para plantillas simples.
    Separa en 3 tablas: valid, out_of_universe, missing.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="El archivo debe ser Excel (.xlsx o .xls)")
    
    try:
        from app.services.ops_universe_service import clear_cache
        clear_cache()
        
        file_content = await file.read()
        file_hash = calculate_file_hash(file_content)
        
        valid_rows, out_of_universe_rows, missing_combos = parse_proyeccion_sheet(
            file_content, 
            file.filename
        )
        
        rows_valid = save_plan_rows(valid_rows, file.filename, file_hash, 'plan_long_valid')
        rows_out_of_universe = save_plan_rows(out_of_universe_rows, file.filename, file_hash, 'plan_long_out_of_universe')
        rows_missing = save_plan_rows(missing_combos, file.filename, file_hash, 'plan_long_missing')
        
        return PlanUploadResponse(
            rows_valid=rows_valid,
            rows_out_of_universe=rows_out_of_universe,
            missing_combos_count=len(missing_combos),
            source_file_name=file.filename,
            uploaded_at=datetime.now(),
            file_hash=file_hash
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al subir plan: {e}")
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")

@router.get("/summary/monthly")
async def get_monthly_plan_summary(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    line_of_business: Optional[str] = Query(None),
    year: Optional[int] = Query(None)
):
    """
    Obtiene resumen mensual de Plan en formato pivot.
    """
    from app.services.summary_service import get_plan_monthly_summary
    try:
        data = get_plan_monthly_summary(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=year
        )
        return {
            "data": data,
            "total_periods": len(data)
        }
    except Exception as e:
        logger.error(f"Error al obtener resumen mensual de Plan: {e}")
        raise

@router.get("/out_of_universe")
async def get_out_of_universe(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    line_of_business: Optional[str] = Query(None),
    year: Optional[int] = Query(None)
):
    """
    Obtiene datos del plan que están fuera del universo operativo.
    """
    try:
        data = get_plan_data(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=year,
            table_name='plan_long_out_of_universe'
        )
        return {
            "data": data,
            "total_rows": len(data)
        }
    except Exception as e:
        logger.error(f"Error al obtener datos fuera de universo: {e}")
        raise

@router.get("/missing")
async def get_missing(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    line_of_business: Optional[str] = Query(None)
):
    """
    Obtiene combinaciones operativas que no tienen plan.
    """
    try:
        data = get_plan_data(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=None,
            table_name='plan_long_missing'
        )
        return {
            "data": data,
            "total_rows": len(data)
        }
    except Exception as e:
        logger.error(f"Error al obtener datos faltantes: {e}")
        raise


@router.post("/upload_control_loop_projection")
async def upload_control_loop_projection(
    file: UploadFile = File(...),
    plan_version: Optional[str] = Query(
        None,
        description="Versión del plan (ej. control_loop_2026_Q1). Si se omite, se genera un id con timestamp.",
    ),
):
    """
    Carga aditiva de la plantilla agregada (Excel: hojas TRIPS, REVENUE, DRIVERS; o CSV equivalente).
    Transformación wide→long, mapping de líneas, staging en `staging.control_loop_plan_metric_long`.
    No modifica Omniview ni plan_long_*.
    """
    fn = (file.filename or "").lower()
    if not fn.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Archivo debe ser .xlsx, .xls o .csv")
    try:
        from app.services.control_loop_upload_service import run_control_loop_upload

        content = await file.read()
        return run_control_loop_upload(content, file.filename, plan_version=plan_version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("upload_control_loop_projection")
        raise HTTPException(status_code=500, detail=str(e))

