"""
Omniview Freshness Governance Service — CF-H1J.7 Extended

Consulta liviana de frescura: RAW → day_fact → week_fact → month_fact → projection.
Usa MAX(date) con índices existentes. Sin scans pesados.

Reglas:
  - Daily:    lag <= 1 → OK,  2-3 → WARNING, >3 → BLOCKED
  - Weekly:   último week_start ≤ 7d del raw → OK
  - Monthly:  último month_start = mes actual o anterior → OK
  - Projection: alineado con day_fact → OK

CF-H1J.7 Extension — Per-grain freshness with cross-validation:
  - raw_max, day_max, week_max, month_max
  - serving_daily_max, serving_weekly_max, serving_monthly_max
  - Cross-validation: raw > day → blocked, day > week → blocked, etc.
  - serving without week_fact → breach
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
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
STATUS_BREACH = "breach"

SERVING_TABLE = "serving.omniview_projection_daily_fact"


def _status_from_lag(lag: Optional[int], thresholds: tuple = (1, 3)) -> str:
    if lag is None:
        return STATUS_ERROR
    if lag <= thresholds[0]:
        return STATUS_OK
    if lag <= thresholds[1]:
        return STATUS_WARNING
    return STATUS_BLOCKED


def _worst_status(*statuses: str) -> str:
    order = {STATUS_OK: 0, STATUS_WARNING: 1, STATUS_BLOCKED: 2, STATUS_BREACH: 3, STATUS_ERROR: 4}
    worst = STATUS_OK
    for s in statuses:
        if order.get(s, 0) > order.get(worst, 0):
            worst = s
    return worst


def _iso_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _expected_closed_week_start(today: date) -> date:
    current_monday = _iso_monday(today)
    return current_monday - timedelta(weeks=1)


def _expected_closed_month_start(today: date) -> date:
    if today.month == 1:
        return date(today.year - 1, 12, 1)
    return date(today.year, today.month - 1, 1)


def get_omniview_freshness_governance() -> Dict[str, Any]:
    today = date.today()
    result: Dict[str, Any] = {
        "status": STATUS_OK,
        "raw": {},
        "facts": {},
        "serving": {},
        "cross_validation": {},
        "message": "",
        "remediation": None,
    }

    try:
        with get_db() as conn:
            cur = conn.cursor()

            raw_max_str = None
            day_max_str = None
            wk_max_str = None
            mo_max_str = None

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

            # 5. SERVING daily
            try:
                cur.execute(
                    f"SELECT MAX(period_key::date) FROM {SERVING_TABLE} WHERE grain = 'daily' AND period_key::date <= CURRENT_DATE"
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
                result["serving"]["daily"] = {
                    "max_date": proj_max_str,
                    "lag_days": lag_p,
                    "status": _status_from_lag(lag_p),
                }
            except Exception as e:
                logger.warning("Freshness governance: serving daily error: %s", e)
                result["serving"]["daily"] = {
                    "max_date": None,
                    "lag_days": None,
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            # 6. SERVING weekly
            try:
                cur.execute(
                    f"SELECT MAX(period_key::date) FROM {SERVING_TABLE} WHERE grain = 'weekly' AND period_key::date <= CURRENT_DATE"
                )
                row = cur.fetchone()
                sw_max = row[0] if row else None
                if sw_max and hasattr(sw_max, "isoformat"):
                    sw_max_str = sw_max.isoformat()
                else:
                    sw_max_str = str(sw_max)[:10] if sw_max else None
                expected_ws = _expected_closed_week_start(today)
                lag_sw = (
                    (today - date.fromisoformat(sw_max_str)).days
                    if sw_max_str
                    else None
                )
                sw_ok = lag_sw is not None and lag_sw <= 7
                result["serving"]["weekly"] = {
                    "max_week_start": sw_max_str,
                    "lag_days": lag_sw,
                    "expected_closed_week": expected_ws.isoformat(),
                    "status": STATUS_OK if sw_ok else STATUS_WARNING if lag_sw and lag_sw <= 10 else STATUS_BLOCKED,
                }
            except Exception as e:
                logger.warning("Freshness governance: serving weekly error: %s", e)
                result["serving"]["weekly"] = {
                    "max_week_start": None,
                    "lag_days": None,
                    "expected_closed_week": _expected_closed_week_start(today).isoformat(),
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            # 7. SERVING monthly
            try:
                cur.execute(
                    f"SELECT MAX(period_key::date) FROM {SERVING_TABLE} WHERE grain = 'monthly' AND period_key::date <= CURRENT_DATE"
                )
                row = cur.fetchone()
                sm_max = row[0] if row else None
                if sm_max and hasattr(sm_max, "isoformat"):
                    sm_max_str = sm_max.isoformat()
                else:
                    sm_max_str = str(sm_max)[:10] if sm_max else None
                expected_m = _expected_closed_month_start(today)
                sm_ok = (
                    sm_max_str is not None
                    and date.fromisoformat(sm_max_str) >= expected_m
                )
                result["serving"]["monthly"] = {
                    "max_month_start": sm_max_str,
                    "expected_closed_month": expected_m.isoformat(),
                    "status": STATUS_OK if sm_ok else STATUS_WARNING,
                }
            except Exception as e:
                logger.warning("Freshness governance: serving monthly error: %s", e)
                result["serving"]["monthly"] = {
                    "max_month_start": None,
                    "expected_closed_month": _expected_closed_month_start(today).isoformat(),
                    "status": STATUS_ERROR,
                    "error": str(e)[:100],
                }

            cur.close()

    except Exception as e:
        logger.exception("Freshness governance: fatal error")
        result["status"] = STATUS_ERROR
        result["message"] = str(e)[:200]
        return result

    # ── CF-H1J.7 Cross-validation rules ──
    cv_findings = []

    raw_d = result["raw"].get("max_date")
    day_d = result["facts"].get("daily", {}).get("max_date")
    week_d = result["facts"].get("weekly", {}).get("max_week_start")
    month_d = result["facts"].get("monthly", {}).get("max_month_start")
    sw_d = result["serving"].get("weekly", {}).get("max_week_start")
    sm_d = result["serving"].get("monthly", {}).get("max_month_start")

    if raw_d and day_d:
        try:
            rd = date.fromisoformat(raw_d)
            dd = date.fromisoformat(day_d)
            if rd > dd:
                cv_findings.append({
                    "rule": "raw_vs_day",
                    "status": STATUS_BLOCKED,
                    "message": f"RAW max ({raw_d}) > day_fact max ({day_d}). day_fact is behind raw source.",
                })
        except (ValueError, TypeError):
            pass

    if day_d and week_d:
        try:
            dd = date.fromisoformat(day_d)
            wd = date.fromisoformat(week_d)
            expected = _expected_closed_week_start(today)
            if wd < expected:
                cv_findings.append({
                    "rule": "day_vs_week_closed",
                    "status": STATUS_BLOCKED,
                    "message": f"Week_fact max ({week_d}) < expected closed week ({expected.isoformat()}). Closed weeks missing from week_fact.",
                })
        except (ValueError, TypeError):
            pass

    if month_d:
        try:
            md = date.fromisoformat(month_d + "-01" if len(month_d) == 7 else month_d)
            expected_m = _expected_closed_month_start(today)
            if md < expected_m:
                cv_findings.append({
                    "rule": "month_vs_expected",
                    "status": STATUS_BLOCKED,
                    "message": f"Month_fact max ({month_d}) < expected closed month ({expected_m.isoformat()}).",
                })
        except (ValueError, TypeError):
            pass

    if sw_d and week_d:
        try:
            swd = date.fromisoformat(sw_d)
            wd = date.fromisoformat(week_d)
            if swd > wd:
                cv_findings.append({
                    "rule": "serving_weekly_vs_week_fact",
                    "status": STATUS_BREACH,
                    "message": f"Serving weekly max ({sw_d}) > week_fact max ({week_d}). Serving has weeks not in canonical week_fact.",
                })
        except (ValueError, TypeError):
            pass

    if week_d and sw_d:
        try:
            wd = date.fromisoformat(week_d)
            swd = date.fromisoformat(sw_d)
            if wd > swd:
                cv_findings.append({
                    "rule": "week_fact_vs_serving_weekly",
                    "status": STATUS_WARNING,
                    "message": f"Week_fact max ({week_d}) > serving weekly max ({sw_d}). Serving weekly is behind week_fact.",
                })
        except (ValueError, TypeError):
            pass

    result["cross_validation"] = {
        "findings": cv_findings,
        "count": len(cv_findings),
    }

    # Aggregate status
    statuses = [
        result["facts"].get("daily", {}).get("status", STATUS_ERROR),
        result["facts"].get("weekly", {}).get("status", STATUS_ERROR),
        result["facts"].get("monthly", {}).get("status", STATUS_ERROR),
        result["serving"].get("daily", {}).get("status", STATUS_ERROR),
        result["serving"].get("weekly", {}).get("status", STATUS_ERROR),
        result["serving"].get("monthly", {}).get("status", STATUS_ERROR),
    ]
    for cv in cv_findings:
        statuses.append(cv.get("status", STATUS_WARNING))
    agg = _worst_status(*statuses)
    result["status"] = agg

    if agg == STATUS_OK:
        result["message"] = "Omniview freshness OK"
        result["remediation"] = None
    elif agg == STATUS_BREACH:
        result["message"] = (
            "BREACH: serving weekly tiene datos que week_fact no respalda. "
            "La UI puede mostrar datos sin fuente canónica."
        )
        result["remediation"] = (
            "1. Verificar week_fact para semanas faltantes. "
            "2. Ejecutar python -m scripts.refresh_omniview_real_slice_incremental "
            "--start-date <fecha> --end-date <fecha> --grain week. "
            "3. NO ejecutar legacy refresh con --force."
        )
    elif agg == STATUS_WARNING:
        result["message"] = (
            "Algunas capas de serving presentan atraso leve. "
            "Verificar con health check."
        )
        result["remediation"] = (
            "Ejecutar python -m scripts.refresh_omniview_real_slice_incremental "
            "--start-date <fecha_inicio> --end-date <fecha_fin> --grain all"
        )
    elif agg == STATUS_BLOCKED:
        result["message"] = (
            "Serving facts desactualizadas. El RAW tiene datos, "
            "pero Omniview todavia no fue refrescado."
        )
        result["remediation"] = (
            "Ejecutar python -m scripts.refresh_omniview_real_slice_incremental "
            "--start-date <fecha_inicio> --end-date <fecha_fin> --grain all. "
            "El script legacy refresh_omniview_real_slice.py --force es NO-GO: "
            "escanea 65M filas via vista enriquecida. Usar el incremental."
        )
    else:
        result["message"] = "Error consultando freshness"
        result["remediation"] = "Revisar logs del backend"

    return result
