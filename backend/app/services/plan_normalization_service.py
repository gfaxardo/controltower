"""
Plan Normalization Service — Fase 3.3.B

Capa formal y auditable de normalización de PLAN.

Pipeline:
    plan_raw (ops.plan_trips_monthly)
        → normalize_geo   (country/city → formato canónico FACT)
        → normalize_lob   (raw_lob → canonical_lob via _EXCEL_ALIASES)
        → resolve_tajada  (canonical_lob → business_slice_name via reglas activas DB)
        → resolution_status: resolved | unresolved | ambiguous

Trazabilidad por fila:
    raw_country, raw_city, raw_lob
    canonical_country, canonical_city, canonical_lob_base
    business_slice_name (resolved)
    resolution_status, resolution_source, resolution_note

Endpoints que consumen este servicio:
    GET /plan/unmapped-summary?plan_version=...
    GET /plan/mapping-audit?plan_version=...
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from psycopg2.extras import RealDictCursor

from app.config.control_loop_lob_mapping import (
    list_alias_map_for_audit,
    resolve_excel_line_to_canonical,
)
from app.contracts.data_contract import remove_accents
from app.db.connection import get_db
from app.services.control_loop_business_slice_resolve import (
    load_map_fallback_rows,
    load_rules_index_for_geos,
    resolve_to_business_slice_name,
)

logger = logging.getLogger(__name__)

# ── Constantes de normalización geográfica ───────────────────────────────────
_COUNTRY_NORM = {
    "peru": "pe", "perú": "pe", "pe": "pe",
    "colombia": "co", "col": "co", "co": "co",
}
_COUNTRY_FULL = {"pe": "peru", "co": "colombia"}
_COUNTRY_FOR_RULES = {"pe": "Perú", "co": "Colombia"}


def _norm_country_code(raw: str) -> str:
    return _COUNTRY_NORM.get((raw or "").strip().lower(), (raw or "").strip().lower())


def _country_full(code: str) -> str:
    return _COUNTRY_FULL.get(code, code)


def _country_for_rules(raw: str) -> str:
    code = _norm_country_code(raw)
    return _COUNTRY_FOR_RULES.get(code, raw)


def _city_canonical(raw: str) -> str:
    return remove_accents((raw or "").strip()).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Carga de plan desde ops.plan_trips_monthly
# ─────────────────────────────────────────────────────────────────────────────

def _load_plan_rows(plan_version: str) -> List[Dict[str, Any]]:
    """Carga todas las filas del plan para plan_version desde ops.plan_trips_monthly."""
    sql = """
        SELECT
            plan_version,
            month            AS period_date,
            country,
            city,
            lob_base         AS raw_lob,
            projected_trips,
            projected_revenue,
            projected_drivers AS projected_active_drivers,
            created_at
        FROM ops.plan_trips_monthly
        WHERE plan_version = %s
        ORDER BY month, country, city, lob_base
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, [plan_version])
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Resolución fila a fila con trazabilidad completa
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_row(
    row: Dict[str, Any],
    idx,
    map_rows: List[dict],
) -> Dict[str, Any]:
    """Resuelve una fila de plan a tajada canónica con trazabilidad completa."""
    raw_country = str(row.get("country") or "")
    raw_city    = str(row.get("city") or "")
    raw_lob     = str(row.get("raw_lob") or "")

    # ── Normalización geográfica ──────────────────────────────────────────
    country_code  = _norm_country_code(raw_country)
    country_full  = _country_full(country_code)   # "peru"/"colombia"
    country_rules = _country_for_rules(raw_country)  # "Perú"/"Colombia"
    city_canonical = _city_canonical(raw_city)    # "lima"/"bogota"

    # ── Normalización LOB ─────────────────────────────────────────────────
    canon_key, norm_key = resolve_excel_line_to_canonical(raw_lob)
    plan_line_key = canon_key or raw_lob

    # ── Resolución a tajada (business_slice_name) ─────────────────────────
    bsn, source = resolve_to_business_slice_name(
        idx, map_rows,
        country_rules, raw_city,   # formato reglas: "Perú" + city exacta
        raw_lob, plan_line_key,
    )
    is_resolved = bool(bsn) and source not in ("unresolved", "")

    resolution_note = None
    if not is_resolved:
        if not canon_key:
            resolution_note = f"raw_lob_not_found_in_alias_map: '{norm_key}'"
        else:
            resolution_note = f"canonical_lob='{canon_key}' no tiene business_slice_name activo para {country_rules}/{raw_city}"

    period_date = row.get("period_date")
    period_str = period_date.strftime("%Y-%m") if hasattr(period_date, "strftime") else str(period_date)[:7]

    return {
        # ── Trazabilidad raw ─────────────────────────────────────────────
        "raw_country":       raw_country,
        "raw_city":          raw_city,
        "raw_lob":           raw_lob,
        # ── Normalización ────────────────────────────────────────────────
        "canonical_country":    country_full,
        "canonical_city":       city_canonical,
        "canonical_lob_base":   canon_key,
        "normalized_lob_key":   norm_key,
        # ── Resolución a tajada ──────────────────────────────────────────
        "business_slice_name":  bsn,
        "resolution_status":    "resolved" if is_resolved else "unresolved",
        "resolution_source":    source if is_resolved else "no_match",
        "resolution_note":      resolution_note,
        # ── Contexto ────────────────────────────────────────────────────
        "period":               period_str,
        "projected_trips":      row.get("projected_trips"),
        "projected_revenue":    row.get("projected_revenue"),
        "projected_active_drivers": row.get("projected_active_drivers"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# API pública del servicio
# ─────────────────────────────────────────────────────────────────────────────

def get_plan_resolution_report(plan_version: str) -> Dict[str, Any]:
    """Carga el plan y ejecuta el pipeline completo de resolución.

    Retorna:
        {
          "plan_version": str,
          "total_rows": int,
          "resolved": int,
          "unresolved": int,
          "coverage_pct": float,
          "rows": [...]   # todas las filas con trazabilidad
        }
    """
    rows = _load_plan_rows(plan_version)
    if not rows:
        return {
            "plan_version": plan_version,
            "total_rows": 0,
            "resolved": 0,
            "unresolved": 0,
            "coverage_pct": None,
            "rows": [],
            "message": f"No hay filas de plan para plan_version='{plan_version}'",
        }

    # Preparar índice de reglas para todas las geos del plan
    geos: Set[Tuple[str, str]] = set()
    for r in rows:
        co_rules = _country_for_rules(str(r.get("country") or ""))
        ci_raw   = str(r.get("city") or "")
        geos.add((co_rules, ci_raw))

    idx      = load_rules_index_for_geos(geos)
    map_rows = load_map_fallback_rows()

    resolved_rows   = []
    unresolved_rows = []

    for row in rows:
        result = _resolve_row(row, idx, map_rows)
        if result["resolution_status"] == "resolved":
            resolved_rows.append(result)
        else:
            unresolved_rows.append(result)

    total     = len(rows)
    n_res     = len(resolved_rows)
    n_unres   = len(unresolved_rows)
    coverage  = round(n_res / total * 100.0, 2) if total > 0 else None

    return {
        "plan_version": plan_version,
        "total_rows":   total,
        "resolved":     n_res,
        "unresolved":   n_unres,
        "coverage_pct": coverage,
        "rows": resolved_rows + unresolved_rows,
    }


def get_plan_unmapped_summary(plan_version: str) -> Dict[str, Any]:
    """Devuelve únicamente las filas no mapeadas con su motivo.

    Usado por GET /plan/unmapped-summary.
    """
    report = get_plan_resolution_report(plan_version)
    unresolved = [r for r in report["rows"] if r["resolution_status"] == "unresolved"]

    # Agrupar por (raw_country, raw_city, raw_lob) para dedup
    seen: Set[Tuple[str, str, str]] = set()
    unique_pairs = []
    for r in unresolved:
        key = (r["raw_country"], r["raw_city"], r["raw_lob"])
        if key not in seen:
            seen.add(key)
            unique_pairs.append(r)

    return {
        "plan_version":      plan_version,
        "count_rows":        report["unresolved"],
        "count_unique_pairs": len(unique_pairs),
        "coverage_pct":      report["coverage_pct"],
        "items":             unique_pairs,
    }


def get_plan_mapping_audit(plan_version: str) -> Dict[str, Any]:
    """Devuelve auditoría de cobertura completa del plan.

    Usado por GET /plan/mapping-audit.
    """
    report = get_plan_resolution_report(plan_version)

    # Agrupar por resolution_source para ver distribución
    by_source: Dict[str, int] = {}
    for r in report["rows"]:
        src = r["resolution_source"] or "unknown"
        by_source[src] = by_source.get(src, 0) + 1

    # Clasificar en alertas de cobertura
    coverage = report["coverage_pct"]
    if coverage is None:
        alert_level = "no_data"
    elif coverage >= 99:
        alert_level = "ok"
    elif coverage >= 95:
        alert_level = "warning"
    else:
        alert_level = "critical"

    # Alias map disponible
    alias_map_size = len(list_alias_map_for_audit())

    return {
        "plan_version":    plan_version,
        "total_rows":      report["total_rows"],
        "resolved":        report["resolved"],
        "unresolved":      report["unresolved"],
        "coverage_pct":    coverage,
        "alert_level":     alert_level,
        "by_resolution_source": by_source,
        "alias_map_size":  alias_map_size,
        "thresholds": {
            "warning_below_pct": 99,
            "critical_below_pct": 95,
        },
        "unresolved_items": [
            r for r in report["rows"] if r["resolution_status"] == "unresolved"
        ],
    }


def _audit_safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_projection_integrity_audit(
    plan_version: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Auditoría de integridad de la proyección derivada: semanal + diario,
    alineación temporal, conservación, volatilidad, shares poco razonables, fallback.
    """
    from datetime import date

    from app.services.projection_expected_progress_service import get_omniview_projection

    today = date.today()
    y = year if year is not None else today.year
    mo = month if month is not None else today.month

    proj_w = get_omniview_projection(
        plan_version,
        grain="weekly",
        year=y,
        month=mo,
    )
    proj_d = get_omniview_projection(
        plan_version,
        grain="daily",
        year=y,
        month=mo,
    )
    meta_w = proj_w.get("meta") or {}
    data_w = proj_w.get("data") or []
    meta_d = proj_d.get("meta") or {}
    data_d = proj_d.get("data") or []

    issues: List[Dict[str, Any]] = []

    for r in data_w:
        if r.get("comparison_status") == "missing_plan":
            issues.append(
                {
                    "city": r.get("city"),
                    "business_slice": r.get("business_slice_name"),
                    "month": r.get("month"),
                    "issue_type": "temporal_alignment_issues",
                    "severity": "warning",
                    "observed_value": "missing_plan",
                    "expected_range": "matched|plan_without_real",
                    "note": "Ejecución real sin fila de plan resuelta para tajada/mes",
                }
            )

    cons = meta_w.get("conservation") or {}
    mdp = cons.get("max_drift_pct")
    if mdp is not None:
        try:
            mdp_f = float(mdp)
        except (TypeError, ValueError):
            mdp_f = 0.0
        if mdp_f > 5.0 and len(data_w) > 0:
            sev = "critical"
        elif mdp_f > 1.0 and len(data_w) > 0:
            sev = "warning"
        else:
            sev = None
        if sev:
            issues.append(
                {
                    "city": None,
                    "business_slice": None,
                    "month": f"{y}-{mo:02d}",
                    "issue_type": "conservation_issues",
                    "severity": sev,
                    "observed_value": mdp_f,
                    "expected_range": "<= 1.0 (post reconcile)",
                    "note": "Deriva relativa entre suma semanal y plan mensual",
                }
            )

    qa_w = meta_w.get("qa_checks") or {}
    for chk in qa_w.get("checks") or []:
        if not isinstance(chk, dict):
            continue
        if chk.get("name") == "volatility_week_plan_vs_avg":
            for a in (chk.get("anomalies") or [])[:200]:
                ratio = _audit_safe_float(a.get("ratio_to_slice_avg")) or 0.0
                sev = "warning" if ratio > 2.0 else "info"
                issues.append(
                    {
                        "city": a.get("city"),
                        "business_slice": a.get("business_slice_name"),
                        "month": None,
                        "issue_type": "weekly_volatility_issues",
                        "severity": sev,
                        "observed_value": a.get("ratio_to_slice_avg"),
                        "expected_range": "<= 1.5",
                        "note": f"week_start={a.get('week_start')}",
                    }
                )

    # Shares semanales relativos al total mensual derivado (misma tajada/mes)
    grp_w: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in data_w:
        key = (r.get("month"), (r.get("country") or "").strip().lower(), (r.get("city") or "").strip().lower(), (r.get("business_slice_name") or "").strip().lower())
        grp_w[key].append(r)
    for _key, grp in grp_w.items():
        grp.sort(key=lambda x: (x.get("week_start") or ""))
        total = sum((_audit_safe_float(x.get("trips_completed_projected_total")) or 0.0) for x in grp)
        if total <= 0:
            continue
        for x in grp:
            wv = _audit_safe_float(x.get("trips_completed_projected_total")) or 0.0
            share = wv / total
            if share < 0.10 or share > 0.40:
                issues.append(
                    {
                        "city": x.get("city"),
                        "business_slice": x.get("business_slice_name"),
                        "month": x.get("month"),
                        "issue_type": "unreasonable_week_share",
                        "severity": "warning",
                        "observed_value": round(share, 4),
                        "expected_range": "[0.10, 0.40]",
                        "note": f"week_start={x.get('week_start')}",
                    }
                )

    qa_d = meta_d.get("qa_checks") or {}
    for chk in qa_d.get("checks") or []:
        if not isinstance(chk, dict):
            continue
        if chk.get("name") == "volatility_daily_plan_vs_avg":
            for a in (chk.get("anomalies") or [])[:300]:
                ratio = _audit_safe_float(a.get("ratio_to_slice_avg")) or 0.0
                sev = "warning" if ratio > 2.0 else "info"
                issues.append(
                    {
                        "city": a.get("city"),
                        "business_slice": a.get("business_slice_name"),
                        "month": None,
                        "issue_type": "daily_volatility_issues",
                        "severity": sev,
                        "observed_value": a.get("ratio_to_slice_avg"),
                        "expected_range": "<= 1.5",
                        "note": f"trip_date={a.get('trip_date')}",
                    }
                )

    grp_d: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in data_d:
        key = (r.get("month"), (r.get("country") or "").strip().lower(), (r.get("city") or "").strip().lower(), (r.get("business_slice_name") or "").strip().lower())
        grp_d[key].append(r)
    for _key, grp in grp_d.items():
        total = sum((_audit_safe_float(x.get("trips_completed_projected_total")) or 0.0) for x in grp)
        if total <= 0:
            continue
        nd = len(grp)
        uniform = 1.0 / nd if nd > 0 else 0.0
        for x in grp:
            dv = _audit_safe_float(x.get("trips_completed_projected_total")) or 0.0
            share = dv / total
            if share < 0.02 or share > 0.25:
                issues.append(
                    {
                        "city": x.get("city"),
                        "business_slice": x.get("business_slice_name"),
                        "month": x.get("month"),
                        "issue_type": "unreasonable_day_share",
                        "severity": "info",
                        "observed_value": round(share, 4),
                        "expected_range": "[0.02, 0.25]",
                        "note": f"trip_date={x.get('trip_date')} (~uniform={uniform:.4f})",
                    }
                )

    plan_drv = meta_w.get("plan_derivation") or {}
    fb = plan_drv.get("fallback_level_summary") or {}
    n5 = int(fb.get("5", 0) or 0)
    total_fb = sum(int(fb.get(k, 0) or 0) for k in fb)
    if total_fb > 0 and n5 / total_fb > 0.5:
        issues.append(
            {
                "city": None,
                "business_slice": None,
                "month": f"{y}-{mo:02d}",
                "issue_type": "fallback_global_overuse",
                "severity": "warning",
                "observed_value": {"level_5_cells": n5, "total_cells": total_fb},
                "expected_range": "minoría nivel 5",
                "note": "Alto uso de curva lineal/fallback (nivel 5)",
            }
        )

    by_severity: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for i in issues:
        sev = str(i.get("severity") or "info")
        typ = str(i.get("issue_type") or "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_type[typ] = by_type.get(typ, 0) + 1

    return {
        "as_of": today.isoformat(),
        "plan_version": plan_version,
        "year": y,
        "month": mo,
        "issues": issues,
        "summary": {
            "total": len(issues),
            "by_severity": by_severity,
            "by_type": by_type,
        },
        "projection_meta_snapshot": {
            "conservation": cons,
            "qa_checks_weekly": qa_w,
            "qa_checks_daily": qa_d,
            "plan_derivation": plan_drv,
        },
    }
