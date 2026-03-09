"""
Normalización canónica de service_type para Real LOB.
Replica la lógica de ops.normalized_service_type() / ops.validated_service_type() (migración 072).

Pipeline: unaccent → lower → trim → + → _plus → espacios/guiones → _ → solo [a-z0-9_]
Rechazo (UNCLASSIFIED): NULL/vacío, contiene coma, >30 chars, >3 palabras antes de normalizar.
"""
import re
import unicodedata
from typing import Optional

MAX_LENGTH = 30
MAX_WORDS = 3  # >3 palabras en el raw → UNCLASSIFIED (frases descriptivas)


def _unaccent(s: str) -> str:
    """Quitar acentos/diacríticos: NFD + filtrar combining characters."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalized_service_type(raw_value: Optional[str]) -> str:
    """
    Normaliza: unaccent, lower, trim, + → _plus, espacios/guiones → _, solo [a-z0-9_].
    Económico → economico, confort+ → confort_plus, tuk-tuk → tuk_tuk.
    """
    if raw_value is None:
        return ""
    s = _unaccent(raw_value).strip().lower()
    s = s.replace("+", "_plus")
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    if s == "expres":
        s = "express"
    return s


def validated_service_type(raw_value: Optional[str]) -> str:
    """
    Valida sobre el raw (coma, longitud, palabras) y devuelve el valor normalizado.
    UNCLASSIFIED si: NULL/vacío, contiene coma, >30 chars, >3 palabras.
    """
    if raw_value is None or not raw_value.strip():
        return "UNCLASSIFIED"
    s = raw_value.strip()
    if "," in s:
        return "UNCLASSIFIED"
    if len(s) > MAX_LENGTH:
        return "UNCLASSIFIED"
    if len(s.split()) > MAX_WORDS:
        return "UNCLASSIFIED"
    norm = normalized_service_type(raw_value)
    return norm if norm else "UNCLASSIFIED"
