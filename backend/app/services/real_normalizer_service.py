from app.adapters.real_repo import get_real_monthly_data
import logging
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

def get_real_monthly_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year: Optional[int] = None
) -> List[Dict]:
    """
    Obtiene resumen mensual de Real en formato pivot (NO long crudo).
    Retorna lista con period, trips_real, revenue_real (nullable).
    """
    try:
        trips_data = get_real_monthly_data(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=year,
            metric='trips'
        )
        
        revenue_data = []
        try:
            revenue_data = get_real_monthly_data(
                country=country,
                city=city,
                line_of_business=line_of_business,
                year=year,
                metric='revenue'
            )
        except Exception as e:
            logger.warning(f"No se pudo obtener revenue: {e}")
        
        summary_by_period = defaultdict(lambda: {'trips_real': None, 'revenue_real': None})
        
        for row in trips_data:
            period = row.get('period')
            if period:
                summary_by_period[period]['trips_real'] = row.get('value', 0)
        
        for row in revenue_data:
            period = row.get('period')
            if period:
                summary_by_period[period]['revenue_real'] = row.get('value', 0)
        
        result = []
        for period in sorted(summary_by_period.keys()):
            result.append({
                'period': period,
                'trips_real': summary_by_period[period]['trips_real'],
                'revenue_real': summary_by_period[period]['revenue_real']
            })
        
        logger.info(f"Resumen mensual generado: {len(result)} períodos")
        return result
        
    except Exception as e:
        logger.error(f"Error al generar resumen mensual de Real: {e}")
        raise




