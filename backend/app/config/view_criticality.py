"""
View Criticality — Criticidad operativa por vista.
Usado por el Decision Engine para priorizar acciones (P0–P3).
Valores permitidos: critical | high | medium | low
"""
from __future__ import annotations

from typing import Dict

VALID_CRITICALITY = ("critical", "high", "medium", "low")

VIEW_CRITICALITY: Dict[str, str] = {
    "real_lob": "critical",
    "resumen": "critical",
    "plan_vs_real": "critical",
    "real_vs_projection": "critical",
    "supply": "high",
    "driver_lifecycle": "high",
    "behavioral_alerts": "medium",
    "leakage": "medium",
    "real_margin_quality": "high",
}


def get_view_criticality(view_name: str) -> str:
    """
    Devuelve la criticidad de la vista: critical | high | medium | low.
    Si la vista no está definida, devuelve "low" (no bloquear por vistas no registradas).
    """
    key = (view_name or "").strip().lower()
    out = VIEW_CRITICALITY.get(key, "low")
    if out not in VALID_CRITICALITY:
        return "low"
    return out
