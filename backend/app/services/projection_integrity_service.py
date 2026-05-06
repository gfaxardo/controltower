"""
FASE 3.7 — Estado de integridad para Omniview vs Proyección (solo meta, aditivo).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_has_pop(r: Dict[str, Any]) -> bool:
    pop = r.get("period_over_period")
    return isinstance(pop, dict)


def _row_has_ytd_slice(r: Dict[str, Any]) -> bool:
    y = r.get("ytd_slice")
    return isinstance(y, dict) and "slice_key" in y


def _authoritative_total_ok(auth: Any) -> bool:
    if not isinstance(auth, dict):
        return False
    t = auth.get("total")
    if not isinstance(t, dict) or t.get("row_type") != "total":
        return False
    ys = t.get("ytd_slice")
    if not isinstance(ys, dict) or "slice_key" not in ys:
        return False
    if ys.get("metric_trace", {}).get("insufficient_data"):
        return False
    return True


def _city_keys_from_rows(display_rows: List[Dict[str, Any]]) -> Set[str]:
    out: Set[str] = set()
    for r in display_rows:
        co = str(r.get("country") or "")
        ci = str(r.get("city") or "")
        out.add(f"{co}::{ci}")
    return out


def build_projection_integrity_status(
    *,
    display_rows: List[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
    ytd_alerts: Any,
    had_resolved_plan: bool,
    matched_count: int,
    plan_without_real_count: int,
    authoritative_ytd: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deriva meta.integrity_status sin tocar filas ni contratos existentes.
    """
    issues: List[str] = []
    n = len(display_rows)
    chk_ytd_slice = "n/a"

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

    # --- ytd_slice (FASE 3.8) ---
    if n > 0:
        ok_ys = sum(1 for r in display_rows if _row_has_ytd_slice(r))
        if ok_ys == 0:
            chk_ytd_slice = "missing"
            issues.append("ytd_slice ausente en todas las filas")
        elif ok_ys < n:
            chk_ytd_slice = "partial"
            issues.append(f"ytd_slice ausente en {n - ok_ys} de {n} filas")
        else:
            chk_ytd_slice = "ok"

    # --- authoritative_aggregation (FASE 3.8B) ---
    chk_authoritative_aggregation = "n/a"
    if n > 0:
        if not _authoritative_total_ok(authoritative_ytd):
            chk_authoritative_aggregation = "missing"
            issues.append(
                "meta.authoritative_ytd ausente o incompleto: el cliente no debe recomponer YTD agregado",
            )
        else:
            ok_rt = sum(
                1
                for r in display_rows
                if r.get("row_type") in ("lob", "subfleet")
            )
            if ok_rt < n:
                chk_authoritative_aggregation = "partial"
                issues.append(
                    f"row_type incompleto en {n - ok_rt} de {n} filas (se esperaba lob|subfleet)",
                )
            else:
                by_city = authoritative_ytd.get("by_city") if isinstance(authoritative_ytd, dict) else None
                if isinstance(by_city, dict):
                    needed = _city_keys_from_rows(display_rows)
                    missing_city = [k for k in needed if k not in ("", "::") and k not in by_city]
                    if missing_city:
                        chk_authoritative_aggregation = "partial"
                        issues.append(
                            "authoritative_ytd.by_city sin entrada para algunas ciudades del data",
                        )
                    else:
                        chk_authoritative_aggregation = "ok"
                else:
                    chk_authoritative_aggregation = "partial"
                    issues.append("authoritative_ytd.by_city no es un objeto válido")

    checks = {
        "ytd_summary": chk_ytd,
        "period_over_period": chk_pop,
        "ytd_alerts": chk_alerts,
        "data_rows": chk_data,
        "ytd_slice": chk_ytd_slice,
        "authoritative_aggregation": chk_authoritative_aggregation,
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
    if n > 0 and chk_ytd_slice == "missing":
        broken = True
    if n > 0 and chk_authoritative_aggregation == "missing":
        broken = True

    warning = False
    if not broken:
        if chk_pop == "partial":
            warning = True
        if chk_ytd_slice == "partial":
            warning = True
        if chk_authoritative_aggregation == "partial":
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
    authoritative_ytd: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        return build_projection_integrity_status(
            display_rows=display_rows,
            ytd_summary=ytd_summary,
            ytd_alerts=ytd_alerts,
            had_resolved_plan=had_resolved_plan,
            matched_count=matched_count,
            plan_without_real_count=plan_without_real_count,
            authoritative_ytd=authoritative_ytd,
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
                "ytd_slice": "error",
                "authoritative_aggregation": "error",
            },
        }
