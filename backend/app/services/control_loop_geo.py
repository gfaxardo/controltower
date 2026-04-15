"""Normalización país/ciudad alineada con vistas reales (pe/co + city key)."""
from __future__ import annotations

import math

from app.contracts.data_contract import normalize_city_std, normalize_country_std


def _is_blank(raw) -> bool:
    if raw is None:
        return True
    if isinstance(raw, float) and (math.isnan(raw) or math.isinf(raw)):
        return True
    try:
        import pandas as pd

        if pd.isna(raw):
            return True
    except Exception:
        pass
    return str(raw).strip() == ""


def normalize_country_control_loop(raw) -> str:
    if _is_blank(raw):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    u = s.upper()
    if u in ("PE", "PERU", "PERÚ"):
        return "pe"
    if u in ("CO", "COL", "COLOMBIA"):
        return "co"
    n = normalize_country_std(s)
    if n in ("peru", "pe"):
        return "pe"
    if n in ("colombia", "co"):
        return "co"
    if len(u) == 2 and u.isalpha():
        return u.lower()
    return n or s.lower()


def normalize_city_control_loop(raw) -> str:
    if _is_blank(raw):
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    return normalize_city_std(s) or s.lower()
