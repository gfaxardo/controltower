"""Sanitizador de respuestas JSON — convierte NaN/Infinity a None."""
import math
from typing import Any


def sanitize_for_json(obj: Any) -> Any:
    """Convierte recursivamente float NaN/Inf/-Inf a None para ser JSON-compliant."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    return obj
