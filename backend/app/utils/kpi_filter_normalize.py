"""
Normalización de filtros para ops.real_business_slice_*_fact.

Los facts usan valores reales en BD (p. ej. country='peru', city='lima');
los escenarios de CLI suelen usar códigos ('pe', 'co'). No se modifican datos
base: solo se traduce el filtro a la forma que coincide con la columna.
"""
from __future__ import annotations

from typing import Optional

# Alias comunes → token canónico minúsculas (debe coincidir con heurística SQL case-insensitive)
_COUNTRY_ALIASES = {
    "pe": "peru",
    "per": "peru",
    "co": "colombia",
}


def normalize_country_token(raw: Optional[str]) -> Optional[str]:
    """Devuelve identificador de país en minúsculas para comparar con lower(country)."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    k = s.lower()
    return _COUNTRY_ALIASES.get(k, k)


def normalize_city_token(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    return s or None


def normalize_business_slice_token(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    return s or None
