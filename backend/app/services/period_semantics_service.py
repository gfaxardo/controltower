"""
Semántica temporal reutilizable: última semana/mes cerrados, semana/mes actual abiertos, labels para UI.
Usado por comparativos WoW/MoM, drill y vista diaria. Semana = ISO (lunes a domingo).
"""
from datetime import date, timedelta
from typing import Any, Dict, Optional


def _iso_week_start(d: date) -> date:
    """Lunes de la semana ISO que contiene d."""
    # Monday = 0, Sunday = 6
    return d - timedelta(days=d.weekday())


def _iso_week_number(d: date) -> int:
    """Número de semana ISO (1-53)."""
    return d.isocalendar().week


def _iso_year(d: date) -> int:
    """Año ISO (puede diferir del año calendario en semana 1)."""
    return d.isocalendar().year


def get_last_closed_day(reference: Optional[date] = None) -> date:
    """Último día considerado cerrado (p. ej. ayer respecto a reference)."""
    ref = reference or date.today()
    return ref - timedelta(days=1)


def get_last_closed_week(reference: Optional[date] = None) -> date:
    """Lunes de la última semana ISO completamente terminada (semana anterior a la actual)."""
    ref = reference or date.today()
    current_monday = _iso_week_start(ref)
    return current_monday - timedelta(days=7)


def get_current_open_week(reference: Optional[date] = None) -> date:
    """Lunes de la semana ISO actual (abierta/parcial)."""
    ref = reference or date.today()
    return _iso_week_start(ref)


def get_last_closed_month(reference: Optional[date] = None) -> date:
    """Primer día del último mes calendario completamente terminado."""
    ref = reference or date.today()
    first_current = ref.replace(day=1)
    # Mes anterior: restar un mes
    if first_current.month == 1:
        return first_current.replace(year=first_current.year - 1, month=12)
    return first_current.replace(month=first_current.month - 1)


def get_current_open_month(reference: Optional[date] = None) -> date:
    """Primer día del mes calendario actual (abierto/parcial)."""
    ref = reference or date.today()
    return ref.replace(day=1)


def format_week_label(week_start: date, closed: bool) -> str:
    """Label para UI: S{week}-{year} — Cerrada | Abierta (parcial)."""
    iso_w = _iso_week_number(week_start)
    iso_y = _iso_year(week_start)
    suffix = " — Cerrada" if closed else " — Abierta (parcial)"
    return f"S{iso_w}-{iso_y}{suffix}"


def format_month_label(month_start: date, closed: bool) -> str:
    """Label para UI: Mmm YYYY — Cerrado | Abierto (parcial)."""
    months = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
    m = month_start.month
    y = month_start.year
    name = months[m - 1] if 1 <= m <= 12 else str(m)
    suffix = " — Cerrado" if closed else " — Abierto (parcial)"
    return f"{name} {y}{suffix}"


def get_period_semantics(reference: Optional[date] = None) -> Dict[str, Any]:
    """
    Devuelve todas las entidades semánticas y labels para API/UI.
    reference: fecha de referencia (default: hoy).
    """
    ref = reference or date.today()
    last_closed_day = get_last_closed_day(ref)
    last_closed_week = get_last_closed_week(ref)
    current_open_week = get_current_open_week(ref)
    last_closed_month = get_last_closed_month(ref)
    current_open_month = get_current_open_month(ref)

    def _d(x: date) -> str:
        return x.isoformat()

    return {
        "reference_date": _d(ref),
        "last_closed_day": _d(last_closed_day),
        "last_closed_week": _d(last_closed_week),
        "last_closed_week_label": format_week_label(last_closed_week, closed=True),
        "current_open_week": _d(current_open_week),
        "current_open_week_label": format_week_label(current_open_week, closed=False),
        "last_closed_month": _d(last_closed_month),
        "last_closed_month_label": format_month_label(last_closed_month, closed=True),
        "current_open_month": _d(current_open_month),
        "current_open_month_label": format_month_label(current_open_month, closed=False),
        "definitions": {
            "last_closed_week": "Lunes de la última semana ISO completamente terminada (semana anterior a la actual).",
            "current_open_week": "Lunes de la semana ISO actual (parcial).",
            "last_closed_month": "Primer día del último mes calendario completamente terminado.",
            "current_open_month": "Primer día del mes calendario actual (parcial).",
        },
    }
