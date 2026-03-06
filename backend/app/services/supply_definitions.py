"""
Definiciones oficiales de métricas del módulo Driver Supply Dynamics.
Usado por documentación, tooltips y validación. No modifica MVs ni cálculos.
"""
from __future__ import annotations

from datetime import date
from typing import Union


# ─── Definiciones oficiales (texto para UI y docs) ─────────────────────────

DEFINITIONS = {
    "active_supply": "Conductores con al menos un viaje en la semana (active_drivers en mv_supply_weekly).",
    "active_drivers": "Conductores con al menos un viaje en la semana; mismo concepto que active_supply.",
    "week_supply": "Suma de viajes realizados por conductores activos en la semana (trips en el periodo).",
    "churned": "Conductores activos la semana pasada (N-1) que no registraron viajes esta semana (N).",
    "reactivated": "Conductores que vuelven a registrar viajes tras al menos una semana inactiva.",
    "growth_rate": "(active_supply_semana_N - active_supply_semana_N-1) / active_supply_semana_N-1. Tasa de crecimiento semanal.",
    "activations": "Conductores que aparecen por primera vez en la semana (primera semana con viajes en el park).",
    "net_growth": "Activations + Reactivated - Churned; variación neta de supply.",
    "segments": "Clasificación por viajes/semana según ops.driver_segment_config: FT, PT, CASUAL, OCCASIONAL, DORMANT.",
    "migration": "Cambio de segmento entre semanas: upgrade, downgrade, drop, revival (nuevo), lateral (estable).",
}


def format_iso_week(week_start: Union[date, str, None]) -> str:
    """
    Convierte week_start (fecha de inicio de semana, típicamente lunes) a formato S{week}-{year}.
    Ejemplo: 2026-02-03 → S6-2026
    """
    if week_start is None:
        return ""
    if isinstance(week_start, str):
        try:
            week_start = date.fromisoformat(week_start[:10])
        except (ValueError, TypeError):
            return str(week_start)[:10]
    if not hasattr(week_start, "isocalendar"):
        return str(week_start)[:10]
    iso = week_start.isocalendar()
    year = iso.year
    week = iso.week
    return f"S{week}-{year}"


def get_definitions() -> dict[str, str]:
    """Devuelve el diccionario de definiciones para el endpoint /ops/supply/definitions."""
    return dict(DEFINITIONS)
