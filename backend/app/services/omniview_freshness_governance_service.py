"""
Omniview Freshness Governance Service

Consulta liviana de frescura: RAW → day_fact → week_fact → month_fact → projection.
Usa MAX(date) con índices existentes. Sin scans pesados.

Reglas:
  - Daily:    lag <= 1 → OK,  2-3 → WARNING, >3 → BLOCKED
  - Weekly:   último week_start ≤ 7d del raw → OK
  - Monthly:  último month_start = mes actual o anterior → OK
  - Projection: alineado con day_fact → OK
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

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


def _status_from_lag(lag: Optional[int], thresholds: tuple = (1, 3)) -> str:
    if lag is None:
        return STATUS_ERROR
    if lag <= thresholds[0]:
        return STATUS_OK
    if lag <= thresholds[1]:
        return STATUS_WARNING
    return STATUS_BLOCKED


def _worst_status(*statuses: str) -> str:
    order = {STATUS_OK: 0, STATUS_WARNING: 1, STATUS_BLOCKED: 2, STATUS_ERROR: 3}
    worst = STATUS_OK
    for s in statuses:
        if order.get(s, 0) > order.get(worst, 0):
            worst = s
    return worst


def get_omniview_freshness_governance() -> Dict[str, Any]:
    today = date.today()
    result: Dict[str, Any] = {
        "status": STATUS_OK,
        "raw": {},
        "facts": {},
        "message": "",
        "remediation": None,
    }

    try:
        with get_db() as conn:
            cur = conn.cursor()

            # 1. RAW
            try:
                cur.execute(
                    "SELECT MAX(fecha_inicio_viaje::date) FROM public.trips_2026"
                )
                row = cur.fetchone()
                raw_max = row[0] if row else None
                if raw_max and hasattr(raw_max, "isoformat"):
                    raw_max_str = raw_max.isoformat()
                else:
                    raw_max_str = str(raw_max)[:10] if raw_max else None
                result["raw"] = {"max_date": raw_max_str}
            except Exception as e:
                logger.warning("Freshness governance: raw source error: %s", e)
                result["raw"] = {"max_date": None, "error": str(e)[:100]}

            # 2. FACT_DAILY
            try:
                cur.execute(f"SELECT MAX(trip_date) FROM {FACT_DAILY}")
                row = cur.fetchone()
                day_max = row[0] if row else None
                if day_max and hasattr(day_max, "isoformat"):
                    day_max_str = day_max.isoformat()
                else:
                    day_max_str = str(day_max)[:10] if day_max else None
                lag_d = (
                    (today - date.fromisoformat(day_max_str)).days
                    if day_max_str
                    else None
                )
                result["facts"]["daily"] = {
                    "max_date": day_max_str,
                    "lag_days": lag_d,
                    "status": _status_from_lag(lag_d),
                }
            except Exception as e:
                logger.warning("Freshness governance: day_fact error: %s", e)
                result["facts"]["daily"] = {
                    "max_date": None,
                    "lag_days": None,
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            # 3. FACT_WEEKLY
            try:
                cur.execute(f"SELECT MAX(week_start) FROM {FACT_WEEKLY}")
                row = cur.fetchone()
                wk_max = row[0] if row else None
                if wk_max and hasattr(wk_max, "isoformat"):
                    wk_max_str = wk_max.isoformat()
                else:
                    wk_max_str = str(wk_max)[:10] if wk_max else None
                lag_w = (
                    (today - date.fromisoformat(wk_max_str)).days
                    if wk_max_str
                    else None
                )
                wk_ok = lag_w is not None and lag_w <= 7
                result["facts"]["weekly"] = {
                    "max_week_start": wk_max_str,
                    "lag_days": lag_w,
                    "status": STATUS_OK if wk_ok else STATUS_WARNING if lag_w and lag_w <= 10 else STATUS_BLOCKED,
                }
            except Exception as e:
                logger.warning("Freshness governance: week_fact error: %s", e)
                result["facts"]["weekly"] = {
                    "max_week_start": None,
                    "lag_days": None,
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            # 4. FACT_MONTHLY
            try:
                cur.execute(f"SELECT MAX(month) FROM {FACT_MONTHLY}")
                row = cur.fetchone()
                mo_max = row[0] if row else None
                if mo_max and hasattr(mo_max, "isoformat"):
                    mo_max_str = mo_max.isoformat()
                else:
                    mo_max_str = str(mo_max)[:10] if mo_max else None
                today_month = date(today.year, today.month, 1)
                if mo_max_str:
                    mo_ok = date.fromisoformat(mo_max_str + "-01" if len(mo_max_str) == 7 else mo_max_str) >= date(today.year, today.month - 1 if today.month > 1 else 12, 1)
                else:
                    mo_ok = False
                result["facts"]["monthly"] = {
                    "max_month_start": mo_max_str,
                    "status": STATUS_OK if mo_ok else STATUS_WARNING,
                }
            except Exception as e:
                logger.warning("Freshness governance: month_fact error: %s", e)
                result["facts"]["monthly"] = {
                    "max_month_start": None,
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            # 5. PROJECTION SERVING (daily)
            try:
                cur.execute(
                    "SELECT MAX(period_key::date) FROM serving.omniview_projection_daily_fact WHERE grain = 'daily' AND period_key::date <= CURRENT_DATE"
                )
                row = cur.fetchone()
                proj_max = row[0] if row else None
                if proj_max and hasattr(proj_max, "isoformat"):
                    proj_max_str = proj_max.isoformat()
                else:
                    proj_max_str = str(proj_max)[:10] if proj_max else None
                lag_p = (
                    (today - date.fromisoformat(proj_max_str)).days
                    if proj_max_str
                    else None
                )
                result["facts"]["projection_daily"] = {
                    "max_date": proj_max_str,
                    "lag_days": lag_p,
                    "status": _status_from_lag(lag_p),
                }
            except Exception as e:
                logger.warning("Freshness governance: projection error: %s", e)
                result["facts"]["projection_daily"] = {
                    "max_date": None,
                    "lag_days": None,
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            cur.close()

    except Exception as e:
        logger.exception("Freshness governance: fatal error")
        result["status"] = STATUS_ERROR
        result["message"] = str(e)[:200]
        return result

    # Aggregate status
    statuses = [
        result["facts"].get("daily", {}).get("status", STATUS_ERROR),
        result["facts"].get("weekly", {}).get("status", STATUS_ERROR),
        result["facts"].get("monthly", {}).get("status", STATUS_ERROR),
        result["facts"].get("projection_daily", {}).get("status", STATUS_ERROR),
    ]
    agg = _worst_status(*statuses)
    result["status"] = agg

    if agg == STATUS_OK:
        result["message"] = "Omniview freshness OK"
        result["remediation"] = None
    elif agg == STATUS_WARNING:
        result["message"] = (
            "Algunas capas de serving presentan atraso leve. "
            "Verificar con health check."
        )
        result["remediation"] = (
            "Ejecutar python -m scripts.refresh_omniview_real_slice --force "
            "y luego python -m scripts.check_omniview_serving_freshness"
        )
    elif agg == STATUS_BLOCKED:
        result["message"] = (
            "Serving facts desactualizadas. El RAW tiene datos, "
            "pero Omniview todavia no fue refrescado."
        )
        result["remediation"] = (
            "Ejecutar python -m scripts.refresh_omniview_real_slice --force "
            "y luego python -m scripts.check_omniview_serving_freshness"
        )
    else:
        result["message"] = "Error consultando freshness"
        result["remediation"] = "Revisar logs del backend"

    return result
