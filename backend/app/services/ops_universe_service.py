from app.adapters.real_repo import get_ops_universe_data
import logging
from typing import List, Dict, Set, Tuple, Optional

logger = logging.getLogger(__name__)

_ops_universe_cache: List[Dict] = None
_cache_filters: Optional[Tuple[Optional[str], Optional[str]]] = None

def get_ops_universe(country: Optional[str] = None, city: Optional[str] = None) -> List[Dict]:
    """
    Obtiene el universo operativo: combinaciones (country, city, line_of_business)
    con actividad real en 2025.
    Soporta filtros opcionales por country y city.
    """
    global _ops_universe_cache, _cache_filters
    
    current_filters = (country, city)
    
    if _ops_universe_cache is not None and _cache_filters == current_filters:
        return _ops_universe_cache
    
    try:
        universe = get_ops_universe_data(country=country, city=city)
        _ops_universe_cache = universe
        _cache_filters = current_filters
        filter_msg = ""
        if country:
            filter_msg += f" country={country}"
        if city:
            filter_msg += f" city={city}"
        logger.info(f"Universo operativo cargado: {len(universe)} combinaciones{filter_msg}")
        return universe
    except Exception as e:
        logger.error(f"Error al obtener universo operativo: {e}")
        raise

def get_ops_universe_set() -> Set[Tuple[str, str, str]]:
    """
    Retorna el universo operativo como un set de tuplas (country_std, city_std, line_of_business_std).
    Usa claves canónicas normalizadas para comparaciones.
    """
    universe = get_ops_universe()
    return {
        (
            row.get('country_std', ''),
            row.get('city_std', ''),
            row.get('line_of_business_std', '')
        )
        for row in universe
    }

def is_in_universe(country: str, city: str, line_of_business: str) -> bool:
    """
    Verifica si una combinación (country, city, line_of_business) está en el universo operativo.
    DEPRECATED: Esta función no normaliza. Usar get_ops_universe_set() directamente con valores normalizados.
    """
    from app.contracts.data_contract import normalize_country_std, normalize_city_std, normalize_line_of_business_std
    universe_set = get_ops_universe_set()
    country_std = normalize_country_std(country or '')
    city_std = normalize_city_std(city or '')
    line_std = normalize_line_of_business_std(line_of_business or '')
    return (country_std, city_std, line_std) in universe_set

def clear_cache():
    """Limpia la caché del universo operativo."""
    global _ops_universe_cache, _cache_filters
    _ops_universe_cache = None
    _cache_filters = None
    logger.info("Caché de universo operativo limpiada")

