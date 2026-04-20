"""
Sanitizador global de respuestas JSON.

Convierte recursivamente valores no serializables en JSON-compliant None:
  - float NaN / +Inf / -Inf
  - numpy.floating (float64, float32, etc.) → float Python o None si NaN/Inf
  - numpy.integer → int Python
  - numpy.bool_   → bool Python
  - numpy.ndarray → lista Python (luego sanitiza cada elemento)
  - decimal.Decimal → float Python

Patrones de uso:
    from app.utils.json_sanitizer import sanitize_for_json
    return sanitize_for_json({"data": rows, ...})
"""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any

try:
    import numpy as _np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False


def sanitize_for_json(obj: Any) -> Any:  # noqa: C901 (función necesariamente grande)
    """Convierte recursivamente valores no JSON-serializables a None (o tipo base Python).

    Casos manejados:
    - float NaN/Inf/-Inf           → None
    - numpy.floating NaN/Inf/-Inf  → None; otros → float()
    - numpy.integer                → int()
    - numpy.bool_                  → bool()
    - numpy.ndarray                → list (recursivo)
    - decimal.Decimal válido       → float(); inválido → None
    - dict                         → dict (recursivo)
    - list / tuple                 → list (recursivo)
    - todo lo demás                → sin cambio
    """
    # ── numpy types ──────────────────────────────────────────────────────────
    if _NUMPY_AVAILABLE:
        if isinstance(obj, _np.floating):
            if _np.isnan(obj) or _np.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, _np.integer):
            return int(obj)
        if isinstance(obj, _np.bool_):
            return bool(obj)
        if isinstance(obj, _np.ndarray):
            return [sanitize_for_json(v) for v in obj.tolist()]

    # ── float nativo Python ───────────────────────────────────────────────────
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # ── Decimal ───────────────────────────────────────────────────────────────
    if isinstance(obj, Decimal):
        try:
            f = float(obj)
            return None if (math.isnan(f) or math.isinf(f)) else f
        except (InvalidOperation, OverflowError):
            return None

    # ── Contenedores ─────────────────────────────────────────────────────────
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]

    return obj


def safe_div(numerator: Any, denominator: Any, scale: float = 1.0, round_digits: int = 4) -> Any:
    """División segura que devuelve None en lugar de NaN/Inf/ZeroDivisionError.

    Uso típico:
        attainment_pct = safe_div(actual, expected, scale=100.0, round_digits=2)
        delta_pct      = safe_div(real - plan, plan, scale=100.0, round_digits=4)
    """
    if numerator is None or denominator is None:
        return None
    try:
        d = float(denominator)
        if d == 0.0:
            return None
        n = float(numerator)
        result = (n / d) * scale
        if math.isnan(result) or math.isinf(result):
            return None
        return round(result, round_digits)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
