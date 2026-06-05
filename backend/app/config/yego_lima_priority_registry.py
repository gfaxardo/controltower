"""
LG-2.3 V1 — Lima Growth Priority Registry.

Canonical priority order for daily capacity allocation.
Deterministic only. No AI. No scoring. No prediction.

MANTENIMIENTO:
  - Para reordenar prioridades, modificar PRIORITY_RANK.
  - Para agregar un programa, agregar entrada en PRIORITY_RANK y PROGRAM_DISPLAY_NAMES.
  - El número menor = mayor prioridad (1 = primero en recibir capacidad).
  - No hardcodear prioridades en otros archivos; importar desde aquí.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

PRIORITY_RANK: Dict[str, int] = {
    "PROGRAM_HIGH_VALUE_RECOVERY": 1,
    "PROGRAM_CHURN_PREVENTION": 2,
    "PROGRAM_14_90": 3,
    "PROGRAM_ACTIVE_GROWTH": 4,
}

PROGRAM_DISPLAY_NAMES: Dict[str, str] = {
    "PROGRAM_HIGH_VALUE_RECOVERY": "High Value Recovery",
    "PROGRAM_CHURN_PREVENTION": "Churn Prevention",
    "PROGRAM_14_90": "14/90",
    "PROGRAM_ACTIVE_GROWTH": "Active Growth",
}

PRIORITY_ORDER: List[Tuple[str, int]] = sorted(
    PRIORITY_RANK.items(), key=lambda item: item[1]
)


def get_priority_rank(program_code: str) -> int:
    return PRIORITY_RANK.get(program_code, 999)


def get_display_name(program_code: str) -> str:
    return PROGRAM_DISPLAY_NAMES.get(program_code, program_code)


def list_priority_order_for_audit() -> List[Dict[str, object]]:
    return [
        {
            "rank": rank,
            "program_code": code,
            "display_name": get_display_name(code),
        }
        for code, rank in PRIORITY_ORDER
    ]
