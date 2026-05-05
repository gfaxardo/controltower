"""
FASE 3.7 — Estado de integridad para Omniview vs Proyección (solo meta, aditivo).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_has_pop(r: Dict[str, Any]) -> bool:
    pop = r.get("period_over_period")
    return isinstance(pop, dict)


def build_projection_integrity_status(
    *,
    display_rows: List[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
    ytd_alerts: Any,
    had_resolved_plan: bool,
    matched_count: int,
    plan_without_real_count: int,
) -> Dict[str, Any]:
    """
    Deriva meta.integrity_status sin tocar filas ni contratos existentes.
    """
    issues: List[str] = []
    n = len(display_rows)

    # --- ytd_summary ---
    if ytd_summary is None:
        chk_ytd = "missing"
    elif not isinstance(ytd_summary, dict):
        chk_ytd = "error"
        issues.append("ytd_summary no es un objeto válido")
    elif ytd_summary.get("error"):
        chk_ytd = "error"
        issues.append(f"YTD en error: {ytd_summary.get('error')}")
    else:
        chk_ytd = "ok"

    # --- period_over_period ---
    if n == 0:
        chk_pop = "missing"
    else:
        ok_pop = sum(1 for r in display_rows if _row_has_pop(r))
        if ok_pop == 0:
            chk_pop = "missing"
            issues.append("Ninguna fila incluye period_over_period")
        elif ok_pop < n:
            chk_pop = "partial"
            issues.append(f"period_over_period ausente en {n - ok_pop} de {n} filas")
        else:
            chk_pop = "ok"

    # --- ytd_alerts ---
    if not isinstance(ytd_alerts, list):
        chk_alerts = "error"
        issues.append("ytd_alerts no es una lista")
    elif len(ytd_alerts) == 0:
        chk_alerts = "empty"
    else:
        chk_alerts = "ok"

    # --- data_rows ---
    if n > 0:
        chk_data = "ok"
    else:
        chk_data = "empty"
        if had_resolved_plan:
            issues.append("Sin filas en data pese a plan resuelto para el alcance")

    checks = {
        "ytd_summary": chk_ytd,
        "period_over_period": chk_pop,
        "ytd_alerts": chk_alerts,
        "data_rows": chk_data,
    }

    broken = False
    if chk_ytd in ("missing", "error"):
        broken = True
        if chk_ytd == "missing":
            issues.append("meta.ytd_summary ausente")
    if had_resolved_plan and n == 0:
        broken = True
    if n > 0 and chk_pop == "missing":
        broken = True

    warning = False
    if not broken:
        if chk_pop == "partial":
            warning = True
        if matched_count == 0 and plan_without_real_count > 0 and n > 0:
            warning = True
            issues.append("Sin filas matched con real; solo plan o plan_without_real")

    if broken:
        status = "broken"
        can_make_decisions = False
    elif warning:
        status = "warning"
        can_make_decisions = True
    else:
        status = "ok"
        can_make_decisions = True

    # De-duplicate issues preserving order
    seen = set()
    uniq_issues: List[str] = []
    for it in issues:
        if it not in seen:
            seen.add(it)
            uniq_issues.append(it)

    return {
        "status": status,
        "can_make_decisions": can_make_decisions,
        "issues": uniq_issues,
        "checked_at": _utc_iso(),
        "checks": checks,
    }


def safe_build_projection_integrity_status(
    *,
    display_rows: List[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
    ytd_alerts: Any,
    had_resolved_plan: bool,
    matched_count: int,
    plan_without_real_count: int,
) -> Dict[str, Any]:
    try:
        return build_projection_integrity_status(
            display_rows=display_rows,
            ytd_summary=ytd_summary,
            ytd_alerts=ytd_alerts,
            had_resolved_plan=had_resolved_plan,
            matched_count=matched_count,
            plan_without_real_count=plan_without_real_count,
        )
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("safe_build_projection_integrity_status: %s", exc, exc_info=True)
        return {
            "status": "warning",
            "can_make_decisions": True,
            "issues": [f"No se pudo calcular integridad: {exc!s}"],
            "checked_at": _utc_iso(),
            "checks": {
                "ytd_summary": "error",
                "period_over_period": "error",
                "ytd_alerts": "error",
                "data_rows": "error",
            },
        }
