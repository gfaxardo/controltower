from fastapi import APIRouter, Query
from app.services.real_normalizer_service import get_real_monthly_summary
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/real", tags=["real"])

@router.get("/summary/monthly")
async def get_monthly_real_summary(
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    line_of_business: Optional[str] = Query(None),
    year: Optional[int] = Query(None)
):
    """
    Obtiene resumen mensual de Real en formato pivot.
    Retorna period, trips_real, revenue_real (nullable).
    """
    try:
        data = get_real_monthly_summary(
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
        logger.error(f"Error al obtener resumen mensual de Real: {e}")
        raise




