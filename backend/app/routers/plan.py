from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.services.plan_parser_service import parse_proyeccion_sheet_legacy as parse_proyeccion_sheet, parse_simple_template
from app.services.plan_parser_service import _separate_by_universe, _find_missing_combos
from app.adapters.plan_repo import save_plan_rows, save_plan_rows_raw, calculate_file_hash, get_plan_data
from app.models.schemas import PlanUploadResponse
from typing import Optional, List, Dict
from datetime import datetime
import logging

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

