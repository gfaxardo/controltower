"""
Servicio para lógica de negocio del universo LOB (Fase 2C+).
"""

from app.adapters.lob_universe_repo import (
    get_lob_universe_check,
    get_real_without_plan_lob,
    get_lob_mapping_quality_checks,
    get_unmatched_by_location,
    get_lob_catalog
)
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

def get_universe_lob_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_name: Optional[str] = None
) -> Dict:
    """
    Obtiene resumen del universo LOB con KPIs.
    Si no hay plan catalog, funciona en modo REAL-only.
    """
    try:
        universe_data = get_lob_universe_check(
            country=country,
            city=city,
            lob_name=lob_name
        )
        
        quality_metrics = get_lob_mapping_quality_checks()
        
        # Verificar si hay plan catalog
        from app.adapters.lob_universe_repo import get_lob_catalog
        catalog = get_lob_catalog(status='active')
        has_plan_catalog = len(catalog) > 0
        
        # Calcular KPIs adicionales
        total_lob_plan = len(universe_data)
        lob_with_real = len([u for u in universe_data if u.get('exists_in_real')])
        lob_without_real = len([u for u in universe_data if u.get('coverage_status') == 'PLAN_ONLY'])
        total_real_trips = sum([u.get('real_trips', 0) for u in universe_data])
        count_ok = len([u for u in universe_data if u.get('coverage_status') == 'OK'])
        count_plan_only = len([u for u in universe_data if u.get('coverage_status') == 'PLAN_ONLY'])
        count_real_only = len([u for u in universe_data if u.get('coverage_status') == 'REAL_ONLY'])
        total_coverage = total_lob_plan or 1
        pct_real_only = round(100.0 * count_real_only / total_coverage, 2)
        
        return {
            "universe": universe_data,
            "has_plan_catalog": has_plan_catalog,
            "kpis": {
                "total_lob_plan": total_lob_plan,
                "lob_with_real": lob_with_real,
                "lob_without_real": lob_without_real,
                "pct_lob_with_real": round(100.0 * lob_with_real / total_lob_plan if total_lob_plan > 0 else 0, 2),
                "total_real_trips": total_real_trips,
                "pct_unmatched": quality_metrics.get('pct_unmatched', 0),
                "total_unmatched": quality_metrics.get('total_unmatched', 0),
                "total_trips": quality_metrics.get('total_trips', 0),
                "count_ok": count_ok,
                "count_plan_only": count_plan_only,
                "count_real_only": count_real_only,
                "pct_real_only": pct_real_only
            },
            "quality_metrics": quality_metrics
        }
        
    except Exception as e:
        if "does not exist" in str(e).lower():
            logger.debug("Resumen universo LOB: vistas/tablas Phase 2C no existen aún: %s", e)
        else:
            logger.error(f"Error al obtener resumen universo LOB: {e}")
        raise

def get_unmatched_trips_summary(
    country: Optional[str] = None,
    city: Optional[str] = None
) -> Dict:
    """
    Obtiene resumen de viajes sin mapeo a LOB del plan.
    """
    try:
        unmatched_data = get_real_without_plan_lob(
            country=country,
            city=city
        )
        
        unmatched_by_location = get_unmatched_by_location()
        
        total_unmatched = sum([u.get('trips_count', 0) for u in unmatched_data])
        
        return {
            "unmatched_trips": unmatched_data,
            "unmatched_by_location": unmatched_by_location,
            "total_unmatched": total_unmatched,
            "total_groups": len(unmatched_data)
        }
        
    except Exception as e:
        if "does not exist" in str(e).lower():
            logger.debug("Resumen viajes unmatched: vistas Phase 2C no existen aún: %s", e)
        else:
            logger.error(f"Error al obtener resumen de viajes unmatched: {e}")
        raise
