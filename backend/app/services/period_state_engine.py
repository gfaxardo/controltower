"""
Period State Engine — estados operativos por grano (OPEN, CLOSED, PARTIAL, STALE).

Usa la fecha máxima disponible en la capa slice (day_fact MAX) como referencia de
carga frente a la expectativa calendario del periodo. No sustituye comparativos
parciales equivalentes del backend (comparison_context).
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any, Optional

# Tolerancia pipeline: si max_data >= ref_date - N, consideramos el grano "al día".
_PIPELINE_LAG_DAYS = 1


def _parse_iso_date(s: str | None) -> Optional[date]:
    if not s:
        return None
    t = str(s).strip()[:10]
    try:
        y, m, d = int(t[0:4]), int(t[5:7]), int(t[8:10])
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _month_bounds(d: date) -> tuple[date, date]:
    last = monthrange(d.year, d.month)[1]
    return date(d.year, d.month, 1), date(d.year, d.month, last)


def _iso_week_bounds(week_start: date) -> tuple[date, date]:
    return week_start, week_start + timedelta(days=6)


def compute_period_state_record(
    grain: str,
    period_key: str,
    actual_max_date: date | None,
    ref_date: date | None = None,
) -> dict[str, Any]:
    """
    Devuelve un registro estable para Matrix / Trust.

    period_key: monthly -> YYYY-MM-DD (primer día del mes, como en facts);
                weekly -> YYYY-MM-DD (lunes ISO, como week_start);
                daily -> YYYY-MM-DD.
    """
    g = (grain or "monthly").strip().lower()
    today = ref_date or date.today()
    am = actual_max_date
    pk = str(period_key or "").strip()[:10]
    pd = _parse_iso_date(pk)
    if not pd:
        ams = am.isoformat() if am else None
        return {
            "period_key": pk,
            "grain": g,
            "period_status": "STALE",
            "expected_through_date": None,
            "expected_end_of_period": None,
            "actual_max_date": ams,
            "actual_max_date_in_period": ams,
            "is_comparable": False,
            "completeness_ratio": None,
            "notes": "period_key_inválido",
        }

    if g == "monthly":
        ms, me = _month_bounds(pd)
        if today < ms:
            return _record(
                pk, g, "FUTURE", me, am, False, None, "Periodo futuro", expected_end_of_period=me
            )
        if ms <= today <= me:
            # Mes en curso: OPEN si la carga va al día; si no, PARTIAL.
            exp = min(today, me)
            comp = _completeness_month(ms, exp, am)
            if am is None or am < ms:
                status = "PARTIAL"
            elif am < exp - timedelta(days=_PIPELINE_LAG_DAYS):
                status = "PARTIAL"
            else:
                status = "OPEN"
            return _record(
                pk,
                g,
                status,
                exp,
                am,
                False,
                comp,
                "Mes en curso",
                expected_end_of_period=me,
            )
        # Mes cerrado calendario: CLOSED solo si la carga llega al fin esperado (fin de mes).
        if am is not None and am >= me:
            return _record(pk, g, "CLOSED", me, am, True, 1.0, "Mes completo en slice", expected_end_of_period=me)
        return _record(
            pk,
            g,
            "STALE",
            me,
            am,
            False,
            _completeness_month(ms, me, am),
            "Mes histórico sin cobertura completa en slice",
            expected_end_of_period=me,
        )

    if g == "weekly":
        ws, we = _iso_week_bounds(pd)
        if today < ws:
            return _record(pk, g, "FUTURE", we, am, False, None, "Semana futura", expected_end_of_period=we)
        if ws <= today <= we:
            exp = min(today, we)
            comp = _completeness_week(ws, exp, am)
            if am is None or am < ws:
                status = "PARTIAL"
            elif am < exp - timedelta(days=_PIPELINE_LAG_DAYS):
                status = "PARTIAL"
            else:
                status = "OPEN"
            return _record(
                pk,
                g,
                status,
                exp,
                am,
                False,
                comp,
                "Semana ISO en curso",
                expected_end_of_period=we,
            )
        if am is not None and am >= we:
            return _record(pk, g, "CLOSED", we, am, True, 1.0, "Semana cerrada en slice", expected_end_of_period=we)
        return _record(
            pk,
            g,
            "STALE",
            we,
            am,
            False,
            _completeness_week(ws, we, am),
            "Semana histórica incompleta en slice",
            expected_end_of_period=we,
        )

    # daily
    if pd > today:
        return _record(pk, g, "FUTURE", pd, am, False, None, "Día futuro", expected_end_of_period=pd)
    if pd == today:
        if am is not None and am >= today - timedelta(days=_PIPELINE_LAG_DAYS):
            status = "OPEN"
        else:
            status = "PARTIAL"
        return _record(
            pk,
            g,
            status,
            today,
            am,
            False,
            1.0 if am and am >= pd else 0.0,
            "Día en curso",
            expected_end_of_period=pd,
        )
    # Día pasado: CLOSED solo si actual_max cubre el fin esperado (el día).
    if am is not None and am >= pd:
        return _record(pk, g, "CLOSED", pd, am, True, 1.0, "Día cerrado", expected_end_of_period=pd)
    return _record(
        pk,
        g,
        "STALE",
        pd,
        am,
        False,
        None,
        "Día histórico sin fila completa en slice",
        expected_end_of_period=pd,
    )


def _completeness_month(ms: date, exp: date, am: date | None) -> float | None:
    if am is None:
        return 0.0
    days = max(1, (exp - ms).days + 1)
    got = max(0, (min(am, exp) - ms).days + 1)
    return round(min(1.0, got / float(days)), 4)


def _completeness_week(ws: date, exp: date, am: date | None) -> float | None:
    if am is None:
        return 0.0
    days = max(1, (exp - ws).days + 1)
    got = max(0, (min(am, exp) - ws).days + 1)
    return round(min(1.0, got / float(days)), 4)


def _through_iso(x: date | str | None) -> str | None:
    if x is None:
        return None
    if isinstance(x, date):
        return x.isoformat()[:10]
    return str(x)[:10]


def _record(
    period_key: str,
    grain: str,
    status: str,
    expected_through: date | str | None,
    am: date | None,
    comparable: bool,
    completeness: float | None,
    notes: str,
    *,
    expected_end_of_period: date | None = None,
) -> dict[str, Any]:
    ams = am.isoformat() if am else None
    eep = expected_end_of_period.isoformat()[:10] if expected_end_of_period else None
    return {
        "period_key": period_key,
        "grain": grain,
        "period_status": status,
        "expected_through_date": _through_iso(expected_through),
        "expected_end_of_period": eep,
        "actual_max_date": ams,
        "actual_max_date_in_period": ams,
        "is_comparable": comparable,
        "completeness_ratio": completeness,
        "notes": notes,
    }


def extract_period_keys_from_rows(grain: str, rows: list[dict[str, Any]]) -> list[str]:
    """Claves únicas de periodo a partir de filas Matrix (excluye bucket UNMAPPED)."""
    g = (grain or "monthly").strip().lower()
    keys: list[str] = []
    seen: set[str] = set()
    col = "month" if g == "monthly" else "week_start" if g == "weekly" else "trip_date"
    for r in rows:
        if r.get("is_unmapped_bucket"):
            continue
        v = r.get(col)
        if v is None:
            continue
        pk = v.isoformat()[:10] if hasattr(v, "isoformat") else str(v)[:10]
        if pk not in seen:
            seen.add(pk)
            keys.append(pk)
    return sorted(keys)


def build_period_states_payload(
    grain: str,
    rows: list[dict[str, Any]],
    slice_max_trip_date: str | None,
    per_period_max_dates: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    """Lista de registros para meta.period_states.

    per_period_max_dates: MAX(trip_date) en day_fact dentro de cada clave de periodo
    (mes / semana ISO / día). Si falta una clave, se usa slice_max_trip_date como
    respaldo (solo compatibilidad; preferir siempre el mapa por período).
    """
    am_global = _parse_iso_date(slice_max_trip_date)
    keys = extract_period_keys_from_rows(grain, rows)
    ppm = per_period_max_dates or {}
    out: list[dict[str, Any]] = []
    for pk in keys:
        raw = ppm.get(pk)
        if raw is not None and str(raw).strip() != "":
            am = _parse_iso_date(str(raw))
        else:
            am = am_global
        out.append(compute_period_state_record(grain, pk, am))
    return out
