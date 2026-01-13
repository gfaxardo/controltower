from app.services.summary_service import get_plan_monthly_summary
from app.services.real_normalizer_service import get_real_monthly_summary
import logging
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

def get_core_monthly_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    line_of_business: Optional[str] = None,
    year_real: int = 2025,
    year_plan: int = 2026
) -> List[Dict]:
    """
    Obtiene resumen mensual combinado de Plan y Real con deltas y status.
    Retorna lista con period, trips_plan, revenue_plan, trips_real, revenue_real,
    delta_trips_abs, delta_trips_pct, delta_revenue_abs, delta_revenue_pct, comparison_status.
    """
    try:
        plan_data = get_plan_monthly_summary(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=year_plan
        )
        
        real_data = get_real_monthly_summary(
            country=country,
            city=city,
            line_of_business=line_of_business,
            year=year_real
        )
        
        combined_by_period = defaultdict(lambda: {
            'trips_plan': None,
            'revenue_plan': None,
            'trips_real': None,
            'revenue_real': None
        })
        
        for row in plan_data:
            period = row.get('period')
            if period:
                combined_by_period[period]['trips_plan'] = row.get('trips_plan')
                combined_by_period[period]['revenue_plan'] = row.get('revenue_plan')
        
        for row in real_data:
            period = row.get('period')
            if period:
                combined_by_period[period]['trips_real'] = row.get('trips_real')
                combined_by_period[period]['revenue_real'] = row.get('revenue_real')
        
        result = []
        for period in sorted(combined_by_period.keys()):
            period_year = int(period.split('-')[0]) if period and '-' in period else None
            
            row_data = combined_by_period[period]
            trips_plan = row_data['trips_plan']
            revenue_plan = row_data['revenue_plan']
            trips_real = row_data['trips_real']
            revenue_real = row_data['revenue_real']
            
            # Reglas de comparación:
            # 1. NUNCA calcular deltas si year_real != year_plan
            # 2. Solo calcular deltas cuando year_real == year_plan, combo está en universo, y existe real
            # 3. Nunca comparar si reason = NOT_IN_UNIVERSE_YET (pero esto no aplica aquí porque solo vemos plan_long_valid)
            
            if year_real != year_plan:
                # Años diferentes: no comparar
                comparison_status = 'NOT_COMPARABLE'
                delta_trips_abs = None
                delta_trips_pct = None
                delta_revenue_abs = None
                delta_revenue_pct = None
            elif trips_plan is not None and trips_real is not None:
                # Mismo año, ambos tienen datos: COMPARABLE
                comparison_status = 'COMPARABLE'
                delta_trips_abs = trips_real - trips_plan
                delta_trips_pct = ((trips_real / trips_plan) - 1) * 100 if trips_plan and trips_plan != 0 else None
                
                if revenue_plan is not None and revenue_real is not None:
                    delta_revenue_abs = revenue_real - revenue_plan
                    delta_revenue_pct = ((revenue_real / revenue_plan) - 1) * 100 if revenue_plan and revenue_plan != 0 else None
                else:
                    delta_revenue_abs = None
                    delta_revenue_pct = None
            elif trips_plan is not None and (trips_real is None and revenue_real is None):
                # Plan existe pero no hay real: NO_REAL_YET
                comparison_status = 'NO_REAL_YET'
                delta_trips_abs = None
                delta_trips_pct = None
                delta_revenue_abs = None
                delta_revenue_pct = None
            else:
                # Sin datos suficientes: NOT_COMPARABLE
                comparison_status = 'NOT_COMPARABLE'
                delta_trips_abs = None
                delta_trips_pct = None
                delta_revenue_abs = None
                delta_revenue_pct = None
            
            result.append({
                'period': period,
                'trips_plan': trips_plan,
                'revenue_plan': revenue_plan,
                'trips_real': trips_real,
                'revenue_real': revenue_real,
                'delta_trips_abs': delta_trips_abs,
                'delta_trips_pct': delta_trips_pct,
                'delta_revenue_abs': delta_revenue_abs,
                'delta_revenue_pct': delta_revenue_pct,
                'comparison_status': comparison_status
            })
        
        logger.info(f"Resumen mensual CORE generado: {len(result)} períodos")
        return result
        
    except Exception as e:
        logger.error(f"Error al generar resumen mensual CORE: {e}")
        raise

