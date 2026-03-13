"""
Normalización canónica de service_type para Real LOB.
Alineado con canon.normalize_real_tipo_servicio() (migración 080): misma lógica para
unificar confort+/confort plus, tuk_tuk/tuk-tuk, express/mensajería → delivery.

Pipeline: unaccent → lower → trim → + → _plus → espacios/guiones → _ → clave canónica.
Claves canónicas: economico, comfort, comfort_plus, tuk_tuk, delivery, minivan, premier, cargo, moto, etc.
"""
import re
import unicodedata
from typing import Optional

MAX_LENGTH = 30
MAX_WORDS = 3  # >3 palabras en el raw → UNCLASSIFIED (frases descriptivas)

# Mapeo clave normalizada (sin acentos, _plus, _) → clave canónica única (080)
_CANONICAL_MAP = {
    "economico": "economico",
    "confort": "comfort",
    "comfort": "comfort",
    "confort_plus": "comfort_plus",
    "comfort_plus": "comfort_plus",
    "tuk_tuk": "tuk_tuk",
    "tuktuk": "tuk_tuk",
    "express": "delivery",
    "expres": "delivery",
    "mensajeria": "delivery",
    "envios": "delivery",
    "minivan": "minivan",
    "premier": "premier",
    "standard": "standard",
    "start": "start",
    "xl": "xl",
    "economy": "economy",
    "cargo": "cargo",
    "moto": "moto",
    "taxi_moto": "taxi_moto",
}


def _unaccent(s: str) -> str:
    """Quitar acentos/diacríticos: NFD + filtrar combining characters."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalized_key(raw_value: Optional[str]) -> str:
    """Clave intermedia: unaccent, lower, trim, + → _plus, espacios/guiones → _, solo [a-z0-9_]."""
    if raw_value is None:
        return ""
    s = _unaccent(raw_value).strip().lower()
    s = s.replace("+", "_plus")
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    if s == "expres":
        s = "express"
    return s


def normalized_service_type(raw_value: Optional[str]) -> str:
    """
    Normaliza: unaccent, lower, trim, + → _plus, espacios/guiones → _, solo [a-z0-9_].
    (Mantiene compatibilidad con callers que esperan clave intermedia; para canónico usar canonical_service_type.)
    """
    return _normalized_key(raw_value)


def canonical_service_type(raw_value: Optional[str]) -> str:
    """
    Clave canónica REAL (alineada con canon.normalize_real_tipo_servicio).
    Variantes equivalentes colapsan: confort+/confort plus → comfort_plus; tuk_tuk/tuk-tuk → tuk_tuk; express/mensajería → delivery.
    """
    if raw_value is None or not str(raw_value).strip():
        return ""
    if len(str(raw_value).strip()) > MAX_LENGTH:
        return "UNCLASSIFIED"
    key = _normalized_key(raw_value)
    return _CANONICAL_MAP.get(key, key)


def validated_service_type(raw_value: Optional[str]) -> str:
    """
    Valida sobre el raw (coma, longitud, palabras) y devuelve el valor normalizado.
    UNCLASSIFIED si: NULL/vacío, contiene coma, >30 chars, >3 palabras.
    """
    if raw_value is None or not str(raw_value).strip():
        return "UNCLASSIFIED"
    s = str(raw_value).strip()
    if "," in s:
        return "UNCLASSIFIED"
    if len(s) > MAX_LENGTH:
        return "UNCLASSIFIED"
    if len(s.split()) > MAX_WORDS:
        return "UNCLASSIFIED"
    norm = _normalized_key(raw_value)
    return norm if norm else "UNCLASSIFIED"
