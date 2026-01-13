from app.adapters.plan_repo import get_plan_data
import logging
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

def get_plan_monthly_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict]:
    """
    Obtiene resumen mensual de Plan en formato pivot.
    Retorna lista con period, trips_plan, revenue_plan.
    """
    # #region agent log
    import json
    import time
    LOG_PATH = r"c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\.cursor\debug.log"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H7","location":"summary_service.py:get_plan_monthly_summary","message":"Inicio get_plan_monthly_summary","data":{"country":country,"city":city,"line_of_business":line_of_business,"year":year},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
            f.write("\n")
    except: pass
    # #endregion
    
    try:
        plan_data = get_plan_data(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=year,
            table_name='plan_long_valid'
        )
        
        # #region agent log
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                json.dump({"sessionId":"debug-session","runId":"post-fix","hypothesisId":"H7","location":"summary_service.py:get_plan_monthly_summary","message":"Datos obtenidos de plan_long_valid","data":{"rows_count":len(plan_data),"sample_periods":[r.get('period') for r in plan_data[:5]]},"timestamp":int(time.time()*1000)}, f, ensure_ascii=False)
                f.write("\n")
        except: pass
        # #endregion
        
        summary_by_period = defaultdict(lambda: {'trips_plan': None, 'revenue_plan': None})
        
        for row in plan_data:
            period = row.get('period')
            metric = row.get('metric')
            plan_value = row.get('plan_value', 0)
            
            if period and metric:
                if metric == 'trips':
                    summary_by_period[period]['trips_plan'] = plan_value
                elif metric == 'revenue':
                    summary_by_period[period]['revenue_plan'] = plan_value
        
        result = []
        for period in sorted(summary_by_period.keys()):
            result.append({
                'period': period,
                'trips_plan': summary_by_period[period]['trips_plan'],
                'revenue_plan': summary_by_period[period]['revenue_plan']
            })
        
        logger.info(f"Resumen mensual de Plan generado: {len(result)} períodos")
        return result
        
    except Exception as e:
        logger.error(f"Error al generar resumen mensual de Plan: {e}")
        raise

