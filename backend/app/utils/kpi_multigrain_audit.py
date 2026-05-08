"""
Utilidades puras para auditoría KPI multi-grain (sin I/O).
Usadas por scripts/audit_kpi_consistency_multigrain.py y tests.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple


def recompute_avg_ticket(ticket_sum_completed: Optional[float], ticket_count_completed: Optional[float]) -> Optional[float]:
    """avg_ticket = sum(ticket) / count(trips), no promedio de promedios."""
    ts = float(ticket_sum_completed or 0)
    tc = float(ticket_count_completed or 0)
    if tc <= 0:
        return None
    return ts / tc


def diff_pct(expected: float, actual: float) -> Optional[float]:
    if expected == 0 and actual == 0:
        return 0.0
    base = max(abs(expected), abs(actual))
    if base == 0:
        return None
    return (actual - expected) / base * 100.0


def map_validation_status_to_audit(status: str) -> str:
    """Mapa status validate_kpi_grain_consistency → esquema P2."""
    s = (status or "").strip().lower()
    if s in ("ok", "warning", "fail"):
        return s
    if s == "expected_non_comparable":
        return "not_certified"
    return "not_certified"


def explain_iso_week_full_sum_vs_calendar_month() -> str:
    """
    Documentación: semanas ISO completas que tocan un mes calendario incluyen días fuera del mes.
    Por tanto SUM(weekly full ISO) no debe exigirse igual al mensual (informativo).
    """
    return (
        "expected_by_grain: weekly_sum_full_iso incluye días fuera del mes calendario "
        "(cruce ISO ↔ mes); la base canónica para KPIs aditivos es SUM(daily en mes)."
    )


def trips_completed_must_exclude_cancelled() -> str:
    """Contrato: columnas trips_completed vs trips_cancelled separadas en facts Omniview."""
    return (
        "KPI principal usa trips_completed; trips_cancelled es columna distinta y no se suma "
        "en el numerador de volumen completado."
    )


def active_drivers_not_sum_of_days() -> str:
    """active_drivers es semi-aditivo (distinct por periodo en la fuente), no SUM(daily)."""
    return (
        "semi_additive_distinct: active_drivers mensual no debe igualar SUM(active_drivers diarios); "
        "se valida rango vs max(daily) en el validator."
    )
