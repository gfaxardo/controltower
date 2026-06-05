"""
CF-H1L.2 — Post-Migration Serving Integrity Guard

Validacion liviana (solo COUNT) de que los fact tables tengan datos
para los periodos cerrados recientes. No ejecuta refresh, no bloquea startup.

Checks:
  1. day_fact tiene filas para el ultimo mes cerrado
  2. month_fact tiene filas para el ultimo mes cerrado
  3. week_fact tiene filas para las ultimas semanas cerradas (ISO)
  4. fact vs serving no tiene huefanos criticos (serving sin fact)

Retorna: status (ok/warning/blocked), grain, missing_periods, fact_rows,
         serving_rows, remediation.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from app.services.business_slice_service import (
    FACT_DAILY,
    FACT_WEEKLY,
    FACT_MONTHLY,
)

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_BLOCKED = "blocked"
STATUS_ERROR = "error"

SERVING_TABLE = "serving.omniview_projection_daily_fact"

CLOSED_WEEKS_COUNT = 5
CLOSED_MONTHS_COUNT = 2


def _iso_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _closed_iso_weeks(count: int = CLOSED_WEEKS_COUNT) -> List[date]:
    today = date.today()
    current_monday = _iso_monday(today)
    weeks = []
    for i in range(1, count + 1):
        weeks.append(current_monday - timedelta(weeks=i))
    return sorted(weeks)


def _closed_months(count: int = CLOSED_MONTHS_COUNT) -> List[date]:
    today = date.today()
    months = []
    cursor = date(today.year, today.month, 1)
    for _ in range(count):
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
        months.append(cursor)
    return sorted(months)


def _worse(a: str, b: str) -> str:
    order = {STATUS_OK: 0, STATUS_WARNING: 1, STATUS_BLOCKED: 2, STATUS_ERROR: 3}
    return a if order.get(a, 0) >= order.get(b, 0) else b


def validate_omniview_serving_integrity() -> Dict[str, Any]:
    today = date.today()
    closed_months = _closed_months(CLOSED_MONTHS_COUNT)
    closed_weeks = _closed_iso_weeks(CLOSED_WEEKS_COUNT)

    overall_status = STATUS_OK
    checks: List[Dict[str, Any]] = []
    missing_periods: List[Dict[str, Any]] = []

    try:
        with get_db() as conn:
            cur = conn.cursor()

            for mon in closed_months:
                mon_str = mon.isoformat()
                cur.execute(
                    f"SELECT COUNT(*)::bigint FROM {FACT_DAILY} "
                    f"WHERE trip_date >= %s::date AND trip_date < (%s::date + interval '1 month')::date",
                    (mon_str, mon_str),
                )
                day_n = (cur.fetchone() or (0,))[0]

                cur.execute(
                    f"SELECT COUNT(*)::bigint FROM {FACT_MONTHLY} "
                    f"WHERE month = %s::date",
                    (mon_str,),
                )
                mon_n = (cur.fetchone() or (0,))[0]

                check_status = STATUS_OK
                if day_n == 0 and mon_n == 0:
                    check_status = STATUS_BLOCKED
                    missing_periods.append({
                        "grain": "month",
                        "period": mon_str,
                        "day_fact_rows": int(day_n),
                        "month_fact_rows": int(mon_n),
                    })
                elif day_n == 0:
                    check_status = STATUS_BLOCKED
                    missing_periods.append({
                        "grain": "month",
                        "period": mon_str,
                        "day_fact_rows": int(day_n),
                        "month_fact_rows": int(mon_n),
                    })
                elif mon_n == 0:
                    check_status = STATUS_WARNING
                    missing_periods.append({
                        "grain": "month",
                        "period": mon_str,
                        "day_fact_rows": int(day_n),
                        "month_fact_rows": int(mon_n),
                    })

                overall_status = _worse(overall_status, check_status)
                checks.append({
                    "grain": "month",
                    "period": mon_str,
                    "day_fact_rows": int(day_n),
                    "month_fact_rows": int(mon_n),
                    "status": check_status,
                })

            for ws in closed_weeks:
                ws_str = ws.isoformat()
                cur.execute(
                    f"SELECT COUNT(*)::bigint FROM {FACT_WEEKLY} "
                    f"WHERE week_start = %s::date",
                    (ws_str,),
                )
                wk_n = (cur.fetchone() or (0,))[0]

                cur.execute(
                    f"SELECT COUNT(*)::bigint FROM {SERVING_TABLE} "
                    f"WHERE grain = 'weekly' AND period_key::date = %s::date",
                    (ws_str,),
                )
                sv_n = (cur.fetchone() or (0,))[0]

                check_status = STATUS_OK
                if wk_n == 0 and sv_n > 0:
                    check_status = STATUS_BLOCKED
                    missing_periods.append({
                        "grain": "week",
                        "period": ws_str,
                        "week_fact_rows": int(wk_n),
                        "serving_rows": int(sv_n),
                    })
                elif wk_n == 0:
                    check_status = STATUS_BLOCKED
                    missing_periods.append({
                        "grain": "week",
                        "period": ws_str,
                        "week_fact_rows": int(wk_n),
                        "serving_rows": int(sv_n),
                    })
                elif sv_n == 0:
                    check_status = STATUS_WARNING
                    missing_periods.append({
                        "grain": "week",
                        "period": ws_str,
                        "week_fact_rows": int(wk_n),
                        "serving_rows": int(sv_n),
                    })

                overall_status = _worse(overall_status, check_status)
                checks.append({
                    "grain": "week",
                    "period": ws_str,
                    "week_fact_rows": int(wk_n),
                    "serving_rows": int(sv_n),
                    "status": check_status,
                })

            cur.close()
    except Exception as e:
        logger.error("Omniview serving integrity guard: DB error: %s", e)
        return {
            "status": STATUS_ERROR,
            "overall": STATUS_ERROR,
            "message": f"Error validando integridad de serving facts: {e}",
            "checks": [],
            "missing_periods": [],
            "closed_months": [m.isoformat() for m in closed_months],
            "closed_weeks": [w.isoformat() for w in closed_weeks],
            "evaluated_at": today.isoformat(),
            "remediation": "Verificar conexion a base de datos y reintentar validacion.",
        }

    if overall_status == STATUS_OK:
        message = "Todos los facts tienen datos para los periodos cerrados recientes."
        remediation_text = None
    elif overall_status == STATUS_BLOCKED:
        blocked_grains = sorted(set(p["grain"] for p in missing_periods if p.get("week_fact_rows", 0) == 0 or p.get("day_fact_rows", 0) == 0))
        message = (
            f"BLOCKED: {len(missing_periods)} periodo(s) sin datos en fact tables "
            f"({', '.join(blocked_grains)}). "
            f"Ejecutar refresh de los grains afectados."
        )
        remediation_text = (
            "Ejecutar refresh_omniview_real_slice_incremental con --grain day "
            "y/o --grain week para los periodos faltantes. "
            "Verificar que el scheduler este activo (CT_SCHEDULER_ENABLED)."
        )
    else:
        message = (
            f"WARNING: {len(missing_periods)} periodo(s) con datos incompletos "
            f"en fact tables. Revisar y considerar refresh preventivo."
        )
        remediation_text = (
            "Algunos periodos tienen serving sin fact o viceversa. "
            "Revisar si es esperado (periodo abierto) o requiere refresh."
        )

    if overall_status == STATUS_BLOCKED:
        logger.warning(
            "Serving integrity BLOCKED: missing=%d periods=%s remediation=%s",
            len(missing_periods),
            [(p["grain"], p["period"]) for p in missing_periods[:10]],
            remediation_text,
        )
    elif overall_status == STATUS_WARNING:
        logger.warning(
            "Serving integrity WARNING: %d period(s) with issues",
            len(missing_periods),
        )
    else:
        logger.info("Serving integrity: OK")

    return {
        "status": overall_status,
        "overall": overall_status,
        "message": message,
        "checks": checks,
        "missing_periods": missing_periods,
        "closed_months": [m.isoformat() for m in closed_months],
        "closed_weeks": [w.isoformat() for w in closed_weeks],
        "evaluated_at": today.isoformat(),
        "remediation": remediation_text,
    }
