from fastapi import APIRouter, Query
from app.services.core_service import get_core_monthly_summary
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/core", tags=["core"])

@router.get("/summary/monthly")
async def get_monthly_core_summary(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    line_of_business: Optional[str] = Query(None),
    year_real: int = Query(2025),
    year_plan: int = Query(2026)
):
    """
    Obtiene resumen mensual combinado de Plan y Real con deltas y status.
    """
    try:
        data = get_core_monthly_summary(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year_real=year_real,
            year_plan=year_plan
        )
        return {
            "data": data,
            "total_periods": len(data)
        }
    except Exception as e:
        logger.error(f"Error al obtener resumen mensual CORE: {e}")
        raise




