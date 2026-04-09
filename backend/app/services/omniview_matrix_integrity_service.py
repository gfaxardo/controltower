"""
Omniview Matrix — validación de integridad operativa y trust (Confidence / Data Trust).

Expone run_omniview_matrix_integrity_checks(), trust operativo OK|warning|blocked,
payload para API/UI y bundle para Confidence Engine.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
import threading
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from psycopg2.extras import RealDictCursor

from app.services.omniview_playbooks import contextualize_playbook, playbook_for_issue_code

from app.db.connection import get_db, get_db_drill

logger = logging.getLogger(__name__)

# Respuesta del endpoint matrix-operational-trust: evita re-ejecutar toda la auditoría en cada poll de UI.
MATRIX_TRUST_API_CACHE_TTL_SEC = 45.0
_matrix_trust_api_cache: tuple[float, dict[str, Any]] | None = None
_matrix_trust_api_lock = threading.Lock()

# Contrato Matrix (alineado a requerimientos producto)
MIN_DISTINCT_MONTHS = 13
MIN_DISTINCT_WEEKS = 6
MIN_DISTINCT_DAYS = 14
GAP_LOOKBACK_DAYS = 90
REVENUE_REL_EPS = 0.005  # 0.5% relativo
REVENUE_ABS_EPS = 5.0  # moneda local

# Trust operativo (producto): severity técnica del hallazgo puede diferir del nivel UI.
OPERATIONAL_BLOCKED_CODES = frozenset(
    {
        "FACTS_UNREADABLE",
        "ROLLUP_MISMATCH",
        "MONTH_TRIPS_MISMATCH",
        "MONTH_REVENUE_MISMATCH",
        "REVENUE_WITHOUT_COMPLETED",
        "NEGATIVE_REVENUE_ROWS",  # inconsistencia revenue / signo
    }
)
OPERATIONAL_WARNING_CODES = frozenset(
    {
        "DAY_FACT_DATE_GAPS",
        "DERIVED_BEHIND_SOURCE",
        "DERIVED_AHEAD_OF_BOUNDED_SOURCE",
        "SOURCE_MAX_UNAVAILABLE",
        "GAP_QUERY_FAILED",
        "NO_DAY_FACT",
        "MONTHS_BELOW_MIN",
        "WEEKS_BELOW_MIN",
        "DAYS_BELOW_MIN",
        "MONTH_COMPARE_SKIPPED",
        "MONTH_COMPARE_FAILED",
        "ROLLUP_CHECK_FAILED",
    }
)

# Prioridad global (banner / priorización): mayor = más crítico para el negocio.
CODE_SEVERITY_WEIGHT: dict[str, int] = {
    "FACTS_UNREADABLE": 100,
    "ROLLUP_MISMATCH": 96,
    "MONTH_TRIPS_MISMATCH": 94,
    "MONTH_REVENUE_MISMATCH": 94,
    "REVENUE_WITHOUT_COMPLETED": 88,
    "NEGATIVE_REVENUE_ROWS": 78,
    "DERIVED_BEHIND_SOURCE": 62,
    "DERIVED_AHEAD_OF_BOUNDED_SOURCE": 45,
    "DAY_FACT_DATE_GAPS": 58,
    "SOURCE_MAX_UNAVAILABLE": 52,
    "GAP_QUERY_FAILED": 48,
    "MONTH_COMPARE_FAILED": 55,
    "ROLLUP_CHECK_FAILED": 50,
    "MONTH_COMPARE_SKIPPED": 40,
    "NO_DAY_FACT": 55,
    "MONTHS_BELOW_MIN": 60,
    "WEEKS_BELOW_MIN": 58,
    "DAYS_BELOW_MIN": 56,
}

DEFAULT_ACTION_PLAYBOOK: dict[str, str] = {
    "action": "Revisar integridad de la capa Business Slice (facts + loader).",
    "query": "SELECT COUNT(*), MAX(trip_date) FROM ops.real_business_slice_day_fact;",
    "process": "Ejecutar validate_omniview_matrix_integrity y audit_business_slice_trust; escalar a datos si persiste.",
}

ACTION_PLAYBOOK: dict[str, dict[str, str]] = {
    "FACTS_UNREADABLE": {
        "action": "Verificar vistas ops.real_business_slice_*_fact y migraciones 116/119.",
        "query": "SELECT to_regclass('ops.real_business_slice_day_fact'), to_regclass('ops.real_business_slice_month_fact');",
        "process": "Red desplegar migraciones; validar permisos de app a ops; reintentar lectura.",
    },
    "DAY_FACT_DATE_GAPS": {
        "action": "Backfill de días faltantes en day_fact para el rango afectado.",
        "query": "SELECT missing_date FROM (…) — usar script validate_omniview_matrix_integrity o GAP query en servicio.",
        "process": "Ejecutar load/incremental day para meses afectados; revisar jobs y logs ETL.",
    },
    "ROLLUP_MISMATCH": {
        "action": "Alinear suma de líneas month_fact vs resolved para el mes indicado.",
        "query": "SELECT month, SUM(trips_completed), SUM(revenue_yego_net) FROM ops.real_business_slice_month_fact WHERE month = :mes_cerrado GROUP BY 1;",
        "process": "Auditar duplicados dims / mapping business_slice; re-run carga mensual incremental.",
    },
    "MONTH_TRIPS_MISMATCH": {
        "action": "Reconciliar viajes completados: month_fact vs v_real_trips_business_slice_resolved.",
        "query": "SELECT trip_month, COUNT(*) FILTER (WHERE completed_flag) FROM ops.v_real_trips_business_slice_resolved WHERE trip_month = :mes_cerrado AND resolution_status='resolved' GROUP BY 1;",
        "process": "Re-cargar mes en month_fact; revisar filtros de completado y resolución.",
    },
    "MONTH_REVENUE_MISMATCH": {
        "action": "Reconciliar revenue neto entre month_fact y viajes resueltos.",
        "query": "SELECT trip_month, SUM(revenue_yego_net) FILTER (WHERE completed_flag) FROM ops.v_real_trips_business_slice_resolved WHERE resolution_status='resolved' GROUP BY 1;",
        "process": "Revisar reglas de comisión/proxy; re-ejecutar load_business_slice_mes.",
    },
    "REVENUE_WITHOUT_COMPLETED": {
        "action": "Corregir filas con revenue sin viajes completados (definición Matrix).",
        "query": "SELECT trip_date, city, business_slice_name, trips_completed, revenue_yego_net FROM ops.real_business_slice_day_fact WHERE trip_date >= CURRENT_DATE - 400 AND COALESCE(trips_completed,0)=0 AND revenue_yego_net IS NOT NULL AND revenue_yego_net <> 0 LIMIT 50;",
        "process": "Ajustar agregación day_fact alineada a completed_flag en fuente.",
    },
    "NEGATIVE_REVENUE_ROWS": {
        "action": "Investigar revenue negativo en day_fact (reversiones / signo).",
        "query": "SELECT trip_date, city, business_slice_name, revenue_yego_net FROM ops.real_business_slice_day_fact WHERE trip_date >= CURRENT_DATE - 400 AND revenue_yego_net < 0 LIMIT 50;",
        "process": "Validar negocio y ETL; excluir o corregir anomalías documentadas.",
    },
    "DERIVED_BEHIND_SOURCE": {
        "action": "Reducir lag entre facts derivados y enriched_base.",
        "query": "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact; SELECT MAX(trip_date) FROM ops.v_real_trips_enriched_base WHERE trip_date >= CURRENT_DATE - 400;",
        "process": "Ejecutar incremental loaders day/week; revisar ventanas y TZ.",
    },
}

CONFIDENCE_PILLAR_WEIGHTS: dict[str, float] = {
    "coverage": 0.25,
    "freshness": 0.20,
    "consistency": 0.55,
}

CONFIDENCE_COVERAGE_BANDS: tuple[tuple[float, float], ...] = (
    (99.0, 100.0),
    (97.0, 90.0),
    (95.0, 80.0),
    (90.0, 65.0),
    (80.0, 45.0),
    (0.0, 20.0),
)

CONFIDENCE_CONSISTENCY_DEDUCTIONS: dict[str, float] = {
    "FACTS_UNREADABLE": 95.0,
    "ROLLUP_MISMATCH": 70.0,
    "MONTH_REVENUE_MISMATCH": 60.0,
    "MONTH_TRIPS_MISMATCH": 55.0,
    "REVENUE_WITHOUT_COMPLETED": 50.0,
    "NEGATIVE_REVENUE_ROWS": 35.0,
    "ROLLUP_CHECK_FAILED": 20.0,
    "MONTH_COMPARE_FAILED": 18.0,
}

CONFIDENCE_HARD_CAP_RULES: tuple[dict[str, Any], ...] = (
    {
        "code": "FACTS_UNREADABLE",
        "max_score": 15,
        "reason": "No se puede confiar en la lectura base de facts.",
    },
    {
        "code": "ROLLUP_MISMATCH",
        "max_score": 35,
        "reason": "La suma de líneas no cuadra con el universo resolved.",
    },
    {
        "code": "MONTH_TRIPS_MISMATCH",
        "max_score": 40,
        "reason": "Los viajes mensuales no reconcilian contra la fuente canon.",
    },
    {
        "code": "MONTH_REVENUE_MISMATCH",
        "max_score": 40,
        "reason": "El revenue mensual no reconcilia contra la fuente canon.",
    },
    {
        "code": "REVENUE_WITHOUT_COMPLETED",
        "max_score": 45,
        "reason": "Existe revenue sin viajes completados en la definición operativa.",
    },
    {
        "code": "DAY_FACT_DATE_GAPS",
        "max_score": 55,
        "min_gap_count": 7,
        "reason": "Huecos severos en day_fact dentro de la ventana operativa.",
    },
)

DECISION_MODE_BLOCKING_CODES = frozenset(
    {
        "FACTS_UNREADABLE",
        "ROLLUP_MISMATCH",
        "MONTH_TRIPS_MISMATCH",
        "MONTH_REVENUE_MISMATCH",
        "REVENUE_WITHOUT_COMPLETED",
    }
)

CONFIDENCE_DECISION_THRESHOLDS: dict[str, int] = {
    "safe_min": 80,
    "blocked_max_exclusive": 45,
    "persist_score_delta": 5,
}

EARLY_WARNING_THRESHOLDS: dict[str, float] = {
    "freshness_drop": 15.0,
    "coverage_drop": 15.0,
    "gap_increase": 3.0,
}

ISSUE_CLUSTER_CONFIG: dict[str, dict[str, Any]] = {
    "freshness_pipeline": {
        "label": "Freshness / pipeline",
        "description": "Incidencias de lag, huecos o lectura base que anticipan degradación operativa.",
        "codes": frozenset(
            {
                "FACTS_UNREADABLE",
                "DERIVED_BEHIND_SOURCE",
                "DERIVED_AHEAD_OF_BOUNDED_SOURCE",
                "SOURCE_MAX_UNAVAILABLE",
                "DAY_FACT_DATE_GAPS",
                "GAP_QUERY_FAILED",
            }
        ),
    },
    "reconciliation": {
        "label": "Reconciliación canon",
        "description": "Descuadres entre rollups/facts y el universo canon resolved.",
        "codes": frozenset(
            {
                "ROLLUP_MISMATCH",
                "MONTH_TRIPS_MISMATCH",
                "MONTH_REVENUE_MISMATCH",
                "ROLLUP_CHECK_FAILED",
                "MONTH_COMPARE_FAILED",
            }
        ),
    },
    "coverage_range": {
        "label": "Coverage / rango",
        "description": "Cobertura temporal insuficiente o huecos que debilitan lectura ejecutiva.",
        "codes": frozenset(
            {
                "NO_DAY_FACT",
                "MONTHS_BELOW_MIN",
                "WEEKS_BELOW_MIN",
                "DAYS_BELOW_MIN",
                "MONTH_COMPARE_SKIPPED",
            }
        ),
    },
    "revenue_semantics": {
        "label": "Revenue semantics",
        "description": "Revenue con semántica de negocio inconsistente respecto a viajes completados.",
        "codes": frozenset(
            {
                "REVENUE_WITHOUT_COMPLETED",
                "NEGATIVE_REVENUE_ROWS",
            }
        ),
    },
}

OMNIVIEW_ISSUE_ACTION_STATUSES = frozenset({"executed", "resolved"})


def _iso_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def derive_operational_trust(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    OK | warning | blocked según reglas de control operativo.
    Gaps y freshness crítico → warning; rollup/revenue → blocked.
    """
    blocked_hits: list[dict[str, Any]] = []
    warning_hits: list[dict[str, Any]] = []
    for f in findings:
        code = (f.get("code") or "").strip()
        if code in OPERATIONAL_BLOCKED_CODES:
            blocked_hits.append(f)
            continue
        if code in OPERATIONAL_WARNING_CODES:
            warning_hits.append(f)
            continue
        if f.get("severity") == "error" and code not in OPERATIONAL_BLOCKED_CODES:
            warning_hits.append(f)
        elif f.get("severity") == "warn":
            warning_hits.append(f)

    def _sort_hits(h: list[dict[str, Any]]) -> None:
        h.sort(key=lambda x: int(x.get("severity_weight") or 0), reverse=True)

    if blocked_hits:
        status = "blocked"
        _sort_hits(blocked_hits)
        lead = blocked_hits[0]
    elif warning_hits:
        status = "warning"
        _sort_hits(warning_hits)
        lead = warning_hits[0]
    else:
        status = "ok"
        lead = None

    msg = "Data Matrix validada"
    if status == "blocked":
        msg = lead.get("message", "Integridad Matrix: bloqueado") if lead else "Bloqueado"
    elif status == "warning":
        msg = lead.get("message", "Integridad Matrix: revisar") if lead else "Advertencia"

    return {
        "status": status,
        "message": msg,
        "blocked_count": len(blocked_hits),
        "warning_count": len(warning_hits),
        "blocked_findings": [{"code": x.get("code"), "message": x.get("message")} for x in blocked_hits],
        "warning_findings": [{"code": x.get("code"), "message": x.get("message")} for x in warning_hits],
    }


def build_affected_period_keys(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Claves de periodo alineadas a Matrix (month YYYY-MM-01, week_start lunes, trip_date)."""
    monthly: set[str] = set()
    weekly: set[str] = set()
    daily: set[str] = set()

    for f in findings:
        code = f.get("code") or ""
        ev = f.get("evidence")
        if not isinstance(ev, dict):
            ev = {}
        if code == "DAY_FACT_DATE_GAPS":
            for ds in ev.get("sample") or []:
                try:
                    d = date.fromisoformat(str(ds)[:10])
                    daily.add(d.isoformat())
                    monthly.add(date(d.year, d.month, 1).isoformat())
                    weekly.add(_iso_monday(d).isoformat())
                except (TypeError, ValueError):
                    continue
        if code in ("ROLLUP_MISMATCH", "MONTH_TRIPS_MISMATCH", "MONTH_REVENUE_MISMATCH"):
            p = ev.get("period")
            if p:
                s = str(p)[:10]
                monthly.add(s)

    return {
        "monthly": sorted(monthly),
        "weekly": sorted(weekly),
        "daily": sorted(daily),
    }


def _finding_operational_ui_status(f: dict[str, Any]) -> str | None:
    code = (f.get("code") or "").strip()
    if code in OPERATIONAL_BLOCKED_CODES:
        return "blocked"
    if code in OPERATIONAL_WARNING_CODES:
        return "warning"
    if f.get("severity") == "error" and code not in OPERATIONAL_BLOCKED_CODES:
        return "warning"
    if f.get("severity") == "warn":
        return "warning"
    return None


def _period_keys_from_finding(f: dict[str, Any]) -> dict[str, list[str]]:
    monthly: set[str] = set()
    weekly: set[str] = set()
    daily: set[str] = set()
    code = f.get("code") or ""
    ev = f.get("evidence")
    if not isinstance(ev, dict):
        ev = {}
    if code == "DAY_FACT_DATE_GAPS":
        for ds in ev.get("sample") or []:
            try:
                d = date.fromisoformat(str(ds)[:10])
                daily.add(d.isoformat())
                monthly.add(date(d.year, d.month, 1).isoformat())
                weekly.add(_iso_monday(d).isoformat())
            except (TypeError, ValueError):
                continue
    if code in ("ROLLUP_MISMATCH", "MONTH_TRIPS_MISMATCH", "MONTH_REVENUE_MISMATCH"):
        p = ev.get("period")
        if p:
            monthly.add(str(p)[:10])
    return {
        "monthly": sorted(monthly),
        "weekly": sorted(weekly),
        "daily": sorted(daily),
    }


def pick_primary_issue(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Hallazgo operativo con mayor peso (para banner accionable)."""
    best: dict[str, Any] | None = None
    best_score = -1
    for f in findings:
        op = _finding_operational_ui_status(f)
        if not op:
            continue
        w = int(f.get("severity_weight") or CODE_SEVERITY_WEIGHT.get(f.get("code") or "", 35))
        bonus = 2000 if op == "blocked" else 500
        score = w + bonus
        if score > best_score:
            best_score = score
            tr = f.get("trace") if isinstance(f.get("trace"), dict) else {}
            ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
            per_v = tr.get("period") or ev.get("period")
            per_s = str(per_v)[:10] if per_v else None
            nav: dict[str, Any] = {}
            if tr.get("city"):
                nav["focus_city"] = tr["city"]
            if tr.get("lob"):
                nav["focus_business_slice"] = tr["lob"]
            if per_s:
                nav["focus_period"] = per_s
            best = {
                "code": f.get("code"),
                "message": f.get("message"),
                "trust_status": op,
                "severity_weight": w,
                "trace": {
                    "city": tr.get("city"),
                    "lob": tr.get("lob"),
                    "period": per_s,
                    "metrics": tr.get("metrics"),
                },
                "nav": nav,
                "impact": f.get("impact"),
                "evidence": ev,
                "action_engine": f.get("action_engine"),
            }
    return best


def build_affected_segments(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Segmentos afectados (ciudad / LOB / periodo / métrica) — no bloquean toda la Matrix salvo scope global."""
    segments: list[dict[str, Any]] = []
    for f in findings:
        op = _finding_operational_ui_status(f)
        if not op:
            continue
        code = f.get("code") or ""
        tr = f.get("trace") if isinstance(f.get("trace"), dict) else {}
        period_keys = _period_keys_from_finding(f)
        city = tr.get("city")
        lob = tr.get("lob")
        metrics = tr.get("metrics")
        period_single = tr.get("period")

        global_codes = frozenset(
            {
                "FACTS_UNREADABLE",
                "NO_DAY_FACT",
                "MONTHS_BELOW_MIN",
                "WEEKS_BELOW_MIN",
                "DAYS_BELOW_MIN",
                "MONTH_COMPARE_SKIPPED",
                "SOURCE_MAX_UNAVAILABLE",
                "GAP_QUERY_FAILED",
                "MONTH_COMPARE_FAILED",
                "ROLLUP_CHECK_FAILED",
                "DERIVED_BEHIND_SOURCE",
                "DERIVED_AHEAD_OF_BOUNDED_SOURCE",
            }
        )
        scope = "global" if code in global_codes else "segment"

        nav: dict[str, Any] = {}
        if city:
            nav["focus_city"] = city
        if lob:
            nav["focus_business_slice"] = lob
        if period_single:
            nav["focus_period"] = str(period_single)[:10]
        elif period_keys["monthly"]:
            nav["focus_period"] = period_keys["monthly"][-1]
        cluster = cluster_config_for_code(code)

        segments.append(
            {
                "code": code,
                "issue_key": build_issue_key(
                    code,
                    city,
                    lob,
                    str(nav.get("focus_period"))[:10] if nav.get("focus_period") else None,
                    [str(x) for x in metrics] if isinstance(metrics, list) else [],
                ),
                "trust_status": op,
                "severity_weight": int(f.get("severity_weight") or 0),
                "message": f.get("message"),
                "scope": scope,
                "city": city,
                "lob": lob,
                "metrics": metrics,
                "period_keys": period_keys,
                "cluster_key": cluster["cluster_key"],
                "cluster_label": cluster["cluster_label"],
                "evidence": f.get("evidence"),
                "action_engine": f.get("action_engine"),
                "nav": nav,
            }
        )
    return segments


def _worse_trust(a: str | None, b: str) -> str:
    rank = {"ok": 0, "warning": 1, "blocked": 2}
    if not a:
        return b
    return a if rank.get(a, 0) >= rank.get(b, 0) else b


def rollup_trust_scopes(segments: list[dict[str, Any]], global_status: str) -> dict[str, Any]:
    cities: dict[str, str] = {}
    lobs: dict[str, str] = {}
    periods: dict[str, str] = {}
    for s in segments:
        st = s.get("trust_status") or "warning"
        if s.get("city"):
            c = str(s["city"])
            cities[c] = _worse_trust(cities.get(c), st)
        if s.get("lob"):
            l = str(s["lob"])
            lobs[l] = _worse_trust(lobs.get(l), st)
        for kk, lst in (s.get("period_keys") or {}).items():
            if not isinstance(lst, list):
                continue
            for p in lst:
                periods[f"{kk}:{p}"] = _worse_trust(periods.get(f"{kk}:{p}"), st)
    return {
        "global": global_status,
        "cities": cities,
        "lobs": lobs,
        "periods_flat": periods,
    }


def global_insights_hard_blocked(segments: list[dict[str, Any]]) -> bool:
    """Solo hechos ilegibles bloquean insights en toda la Matrix; el resto es por segmento."""
    for s in segments:
        if s.get("code") == "FACTS_UNREADABLE":
            return True
    return False


def compute_impact_summary(findings: list[dict[str, Any]], snap: dict[str, Any]) -> dict[str, Any]:
    """% aproximado de viajes / revenue tocados por incidencias (ventana alineada a validación)."""
    pct_trips = pct_rev = 0.0
    basis_parts: list[str] = []
    is_estimate = True
    try:
        totals = _q_one(
            """
            SELECT
                COALESCE(SUM(trips_completed), 0)::numeric AS tt,
                COALESCE(SUM(ABS(revenue_yego_net)), 0)::numeric AS tr
            FROM ops.real_business_slice_day_fact
            WHERE trip_date >= CURRENT_DATE - 400
            """
        )
        tt = float(totals.get("tt") or 0)
        tr = float(totals.get("tr") or 0)
    except Exception:
        tt = tr = 0.0

    gap_affected_trips = 0.0
    gap_affected_rev = 0.0
    for f in findings:
        if f.get("code") != "DAY_FACT_DATE_GAPS":
            continue
        try:
            gap_imp = _q_one(
                """
                WITH b AS (
                    SELECT MAX(trip_date)::date AS mx FROM ops.real_business_slice_day_fact
                ),
                series AS (
                    SELECT generate_series(
                        (SELECT mx FROM b) - %s::int,
                        (SELECT mx FROM b),
                        '1 day'::interval
                    )::date AS d
                ),
                present AS (
                    SELECT DISTINCT trip_date AS d FROM ops.real_business_slice_day_fact
                    WHERE trip_date >= (SELECT mx - %s::int FROM b)
                ),
                missing AS (
                    SELECT s.d AS missing_date
                    FROM series s
                    LEFT JOIN present p ON p.d = s.d
                    WHERE p.d IS NULL
                )
                SELECT
                    COALESCE(SUM(f.trips_completed), 0)::numeric AS gt,
                    COALESCE(SUM(ABS(f.revenue_yego_net)), 0)::numeric AS gr
                FROM ops.real_business_slice_day_fact f
                JOIN missing m ON m.missing_date = f.trip_date
                """,
                [GAP_LOOKBACK_DAYS, GAP_LOOKBACK_DAYS],
            )
            gap_affected_trips = float(gap_imp.get("gt") or 0)
            gap_affected_rev = float(gap_imp.get("gr") or 0)
            basis_parts.append("huecos day_fact")
        except Exception:
            ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
            n = int(ev.get("gap_count") or 0)
            if tt > 0 and n > 0:
                gap_affected_trips = min(tt, tt * (n / max(1, GAP_LOOKBACK_DAYS)) * 0.5)
            basis_parts.append("huecos (estimado)")

    month_blocked_trips = month_blocked_rev = 0.0
    for f in findings:
        code = f.get("code") or ""
        if code not in ("MONTH_TRIPS_MISMATCH", "MONTH_REVENUE_MISMATCH", "ROLLUP_MISMATCH"):
            continue
        ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
        per = ev.get("period")
        if not per:
            continue
        try:
            row = _q_one(
                """
                SELECT
                    COALESCE(SUM(trips_completed), 0)::numeric AS mt,
                    COALESCE(SUM(ABS(revenue_yego_net)), 0)::numeric AS mr
                FROM ops.real_business_slice_month_fact
                WHERE month = %s::date
                """,
                [str(per)[:10]],
            )
            month_blocked_trips = max(month_blocked_trips, float(row.get("mt") or 0))
            month_blocked_rev = max(month_blocked_rev, float(row.get("mr") or 0))
            basis_parts.append(f"mes agregado {str(per)[:7]}")
        except Exception:
            continue

    bad_rev_rows = 0.0
    for f in findings:
        if f.get("code") != "REVENUE_WITHOUT_COMPLETED":
            continue
        ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
        try:
            n_bad = int(ev.get("n") or 0)
            if n_bad <= 0:
                continue
            row_d = _q_one(
                """
                SELECT COUNT(*)::bigint AS n
                FROM ops.real_business_slice_day_fact
                WHERE trip_date >= CURRENT_DATE - 400
                """
            )
            n_tot = int(row_d.get("n") or 1)
            # Proxy: exposición de revenue ~ proporcional a share de filas anómalas
            bad_rev_rows = tr * min(1.0, n_bad / max(1, n_tot)) if tr > 0 else 0.0
        except (TypeError, ValueError):
            pass
        basis_parts.append("filas revenue sin completados")

    if tt > 0:
        pct_trips = min(100.0, 100.0 * (gap_affected_trips + month_blocked_trips) / tt)
    elif month_blocked_trips > 0:
        pct_trips = 100.0
        is_estimate = True
    if tr > 0:
        pct_rev = min(100.0, 100.0 * (gap_affected_rev + month_blocked_rev + bad_rev_rows) / tr)
    elif month_blocked_rev > 0:
        pct_rev = 100.0

    if not basis_parts:
        is_estimate = False
        basis = "Sin desglose automático de filas afectadas (incidencia estructural o cobertura)."
    else:
        basis = "Estimación a partir de: " + ", ".join(sorted(set(basis_parts))) + f" (MAX day_fact {snap.get('day_fact_max', '—')})."

    return {
        "pct_trips_affected": round(pct_trips, 2),
        "pct_revenue_affected": round(pct_rev, 2),
        "basis": basis,
        "is_estimate": is_estimate,
    }


def _finding_impact_pct_for_priority(code: str, impact_summary: dict[str, Any]) -> float:
    """% de impacto alineado al tipo de hallazgo (viajes vs revenue vs mixto)."""
    pt = float(impact_summary.get("pct_trips_affected") or 0)
    pr = float(impact_summary.get("pct_revenue_affected") or 0)
    trip_codes = {
        "MONTH_TRIPS_MISMATCH",
        "DAY_FACT_DATE_GAPS",
        "MONTHS_BELOW_MIN",
        "WEEKS_BELOW_MIN",
        "DAYS_BELOW_MIN",
    }
    rev_codes = {
        "MONTH_REVENUE_MISMATCH",
        "NEGATIVE_REVENUE_ROWS",
        "REVENUE_WITHOUT_COMPLETED",
    }
    c = (code or "").strip()
    in_t = c in trip_codes
    in_r = c in rev_codes
    if in_t and not in_r:
        return pt
    if in_r and not in_t:
        return pr
    return max(pt, pr)


def build_executive_trust_banner(
    findings: list[dict[str, Any]],
    impact_summary: dict[str, Any] | None,
    operational_status: str,
) -> dict[str, Any]:
    """
    Payload ejecutivo: prioridad = severity_weight × impacto (%), inconsistencia principal + acción.
    status: OK | WARNING | BLOCKED
    """
    os_map = {"ok": "OK", "warning": "WARNING", "blocked": "BLOCKED"}
    raw_st = (operational_status or "warning").lower()
    status = os_map.get(raw_st, "WARNING")
    im = impact_summary or {}
    pt = float(im.get("pct_trips_affected") or 0)
    pr = float(im.get("pct_revenue_affected") or 0)
    impact_pct_display = round(max(pt, pr), 2)

    best_f: dict[str, Any] | None = None
    best_pri = -1.0
    for f in findings:
        op = _finding_operational_ui_status(f)
        if not op:
            continue
        w = float(f.get("severity_weight") or CODE_SEVERITY_WEIGHT.get(f.get("code") or "", 40))
        ip = _finding_impact_pct_for_priority(str(f.get("code") or ""), im)
        pri = w * ip
        if pri > best_pri:
            best_pri = pri
            best_f = f

    if not best_f and status != "OK":
        for f in findings:
            if _finding_operational_ui_status(f):
                best_f = f
                ip = _finding_impact_pct_for_priority(str(f.get("code") or ""), im)
                w = float(f.get("severity_weight") or CODE_SEVERITY_WEIGHT.get(f.get("code") or "", 40))
                best_pri = w * ip
                break

    if status == "OK":
        return {
            "status": "OK",
            "impact_pct": 0.0,
            "priority_score": 0.0,
            "main_issue": None,
            "action": "Sin incidencias que requieran acción ejecutiva inmediata.",
            "playbook": None,
        }

    if not best_f:
        return {
            "status": status,
            "impact_pct": impact_pct_display,
            "priority_score": 0.0,
            "main_issue": None,
            "action": im.get("basis") or "Revisar panel de hallazgos en el motor de integridad Matrix.",
            "playbook": None,
        }

    tr = best_f.get("trace") if isinstance(best_f.get("trace"), dict) else {}
    ev = best_f.get("evidence") if isinstance(best_f.get("evidence"), dict) else {}
    per_v = tr.get("period") or ev.get("period")
    per_s = str(per_v)[:10] if per_v else None
    metrics = tr.get("metrics")
    m_one = metrics[0] if isinstance(metrics, list) and len(metrics) > 0 else None
    ae = best_f.get("action_engine") or {}
    action = str(ae.get("action") or best_f.get("suggested_fix") or "")

    code_main = str(best_f.get("code") or "").strip()
    pb_ctx = {
        "period": per_s,
        "city": tr.get("city"),
        "lob": tr.get("lob"),
        "metric": m_one,
    }
    pb = playbook_for_issue_code(code_main)
    if pb and (not (pb.get("recommended_action") or "").strip()) and action:
        pb = dict(pb)
        pb["recommended_action"] = action
    pb = contextualize_playbook(pb, pb_ctx)

    return {
        "status": status,
        "impact_pct": impact_pct_display,
        "priority_score": round(best_pri, 4),
        "main_issue": {
            "code": best_f.get("code"),
            "description": best_f.get("message"),
            "city": tr.get("city"),
            "lob": tr.get("lob"),
            "period": per_s,
            "metric": m_one,
        },
        "action": (pb.get("recommended_action") if pb else None) or action,
        "playbook": pb,
    }


def map_trust_status_to_decision_mode(operational_status: str) -> str:
    """Modo decisión operativa: SAFE | CAUTION | BLOCKED."""
    s = (operational_status or "warning").lower()
    if s == "ok":
        return "SAFE"
    if s == "blocked":
        return "BLOCKED"
    return "CAUTION"


def _to_date_any(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def period_anchor_from_snap(snap: dict[str, Any]) -> date:
    """Mes ancla para historial (primer día del mes del fact más reciente)."""
    m = snap.get("month_fact_max") or snap.get("day_fact_max")
    d = _to_date_any(m)
    if not d:
        return date.today().replace(day=1)
    return date(d.year, d.month, 1)


def _pct(v: Any) -> float:
    try:
        return max(0.0, min(100.0, float(v or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _coverage_band_score(coverage_pct: float) -> float:
    for min_pct, score in CONFIDENCE_COVERAGE_BANDS:
        if coverage_pct >= min_pct:
            return score
    return 20.0


def _finding_gap_count(f: dict[str, Any]) -> int:
    ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
    try:
        return int(ev.get("gap_count") or 0)
    except (TypeError, ValueError):
        return 0


def evaluate_confidence_hard_cap(findings: list[dict[str, Any]]) -> dict[str, Any] | None:
    selected: dict[str, Any] | None = None
    for rule in CONFIDENCE_HARD_CAP_RULES:
        for f in findings:
            if str(f.get("code") or "") != rule["code"]:
                continue
            min_gap_count = rule.get("min_gap_count")
            if min_gap_count is not None and _finding_gap_count(f) < int(min_gap_count):
                continue
            cand = {
                "code": rule["code"],
                "max_score": int(rule["max_score"]),
                "reason": rule["reason"],
            }
            if selected is None or cand["max_score"] < selected["max_score"]:
                selected = cand
    return selected


def collect_decision_hard_blockers(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for f in findings:
        code = str(f.get("code") or "")
        if code in DECISION_MODE_BLOCKING_CODES:
            blockers.append(
                {
                    "code": code,
                    "message": f.get("message"),
                }
            )
    return blockers


def _parse_jsonish(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def cluster_config_for_code(code: str) -> dict[str, Any]:
    c = str(code or "")
    for key, cfg in ISSUE_CLUSTER_CONFIG.items():
        if c in cfg["codes"]:
            return {
                "cluster_key": key,
                "cluster_label": cfg["label"],
                "cluster_description": cfg["description"],
            }
    return {
        "cluster_key": "other",
        "cluster_label": "Otros",
        "cluster_description": "Incidencias operativas no agrupadas en un cluster principal.",
    }


def _evidence_snapshot(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        return {}
    keep: dict[str, Any] = {}
    scalar_keys = {
        "gap_count",
        "lag_days",
        "day_fact_max",
        "source_max",
        "period",
        "rows_trips",
        "total_trips",
        "trips_diff",
        "rows_revenue",
        "total_revenue",
        "rev_diff",
        "n",
    }
    for key in scalar_keys:
        if evidence.get(key) is not None:
            keep[key] = evidence.get(key)
    sample = evidence.get("sample")
    if isinstance(sample, list) and sample:
        keep["sample"] = sample[:5]
    return keep


def build_issue_key(
    code: str,
    city: str | None = None,
    lob: str | None = None,
    period_key: str | None = None,
    metrics: list[str] | None = None,
) -> str:
    m = ",".join(sorted(str(x) for x in (metrics or []) if x))
    return "|".join(
        [
            str(code or ""),
            str(city or "*"),
            str(lob or "*"),
            str(period_key or "*"),
            m or "*",
        ]
    )


def build_issue_snapshots(
    segments: list[dict[str, Any]],
    impact_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    snaps: list[dict[str, Any]] = []
    for s in segments:
        code = str(s.get("code") or "")
        nav = s.get("nav") if isinstance(s.get("nav"), dict) else {}
        period_key = nav.get("focus_period")
        metrics = s.get("metrics") if isinstance(s.get("metrics"), list) else []
        cluster = cluster_config_for_code(code)
        snaps.append(
            {
                "issue_key": build_issue_key(
                    code,
                    s.get("city"),
                    s.get("lob"),
                    str(period_key)[:10] if period_key else None,
                    [str(x) for x in metrics],
                ),
                "code": code,
                "trust_status": s.get("trust_status"),
                "city": s.get("city"),
                "lob": s.get("lob"),
                "period_key": str(period_key)[:10] if period_key else None,
                "metrics": [str(x) for x in metrics],
                "severity_weight": int(s.get("severity_weight") or 0),
                "impact_pct": round(_finding_impact_pct_for_priority(code, impact_summary), 2),
                "cluster_key": cluster["cluster_key"],
                "cluster_label": cluster["cluster_label"],
                "cluster_description": cluster["cluster_description"],
                "message": s.get("message"),
                "evidence": _evidence_snapshot(s.get("evidence")),
            }
        )
    return snaps


def _history_payload_issue_snapshots(row: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _parse_jsonish(row.get("payload"))
    snaps = payload.get("issue_snapshots")
    return snaps if isinstance(snaps, list) else []


def _history_payload_confidence(row: dict[str, Any]) -> dict[str, Any]:
    payload = _parse_jsonish(row.get("payload"))
    conf = payload.get("confidence")
    return conf if isinstance(conf, dict) else {}


def build_early_warnings(
    current_decision: dict[str, Any],
    current_issue_snapshots: list[dict[str, Any]],
    recent_history_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if not recent_history_rows:
        return warnings

    prev = recent_history_rows[0]
    prev_conf = _history_payload_confidence(prev)
    curr_conf = current_decision.get("confidence") or {}

    prev_fresh = prev_conf.get("freshness")
    curr_fresh = curr_conf.get("freshness")
    if prev_fresh is not None and curr_fresh is not None and float(curr_fresh) <= float(prev_fresh) - EARLY_WARNING_THRESHOLDS["freshness_drop"]:
        warnings.append(
            {
                "type": "freshness_deterioration",
                "severity": "warning",
                "message": f"Freshness cae de {round(float(prev_fresh), 1)} a {round(float(curr_fresh), 1)}: revisar lag de incremental antes de bloqueo.",
            }
        )

    prev_cov = prev_conf.get("coverage")
    curr_cov = curr_conf.get("coverage")
    if prev_cov is not None and curr_cov is not None and float(curr_cov) <= float(prev_cov) - EARLY_WARNING_THRESHOLDS["coverage_drop"]:
        warnings.append(
            {
                "type": "coverage_drop",
                "severity": "warning",
                "message": f"Coverage baja de {round(float(prev_cov), 1)} a {round(float(curr_cov), 1)}: revisar mapping y rango mínimo disponible.",
            }
        )

    prev_um = prev_conf.get("unmapped_trips_global")
    curr_um = curr_conf.get("unmapped_trips_global")
    if (
        prev_um is not None
        and curr_um is not None
        and int(prev_um) >= 0
        and int(curr_um) > int(prev_um) + max(50, int(prev_um) * 0.1)
    ):
        warnings.append(
            {
                "type": "unmapped_increase",
                "severity": "warning",
                "message": f"Viajes no mapeados suben de {int(prev_um)} a {int(curr_um)}: revisar reglas park/tipo/works_terms.",
            }
        )

    prev_map = prev_conf.get("mapping_coverage_pct")
    curr_map = curr_conf.get("mapping_coverage_pct")
    if (
        prev_map is not None
        and curr_map is not None
        and float(curr_map) < float(prev_map) - 2.0
    ):
        warnings.append(
            {
                "type": "mapping_coverage_drop",
                "severity": "warning",
                "message": f"Cobertura de mapping cae de {round(float(prev_map), 1)}% a {round(float(curr_map), 1)}%.",
            }
        )

    def _gap_total(snaps: list[dict[str, Any]]) -> int:
        total = 0
        for snap in snaps:
            if snap.get("code") != "DAY_FACT_DATE_GAPS":
                continue
            ev = snap.get("evidence") if isinstance(snap.get("evidence"), dict) else {}
            try:
                total += int(ev.get("gap_count") or 0)
            except (TypeError, ValueError):
                continue
        return total

    current_gap_total = _gap_total(current_issue_snapshots)
    prev_gap_total = _gap_total(_history_payload_issue_snapshots(prev))
    if current_gap_total >= max(1, prev_gap_total + int(EARLY_WARNING_THRESHOLDS["gap_increase"])):
        warnings.append(
            {
                "type": "gaps_increase",
                "severity": "warning",
                "message": f"Gap count sube de {prev_gap_total} a {current_gap_total}: activar backfill diario antes de que afecte más periodos.",
            }
        )

    return warnings[:4]


def build_issue_history_summary(
    current_issue_snapshots: list[dict[str, Any]],
    recent_history_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    history_index: dict[str, Any] = {}
    rows_chrono = sorted(
        recent_history_rows,
        key=lambda x: str(x.get("evaluated_at") or x.get("period_key") or ""),
    )
    for snap in current_issue_snapshots:
        issue_key = str(snap.get("issue_key") or "")
        code = str(snap.get("code") or "")
        matches: list[dict[str, Any]] = []
        for row in rows_chrono:
            row_snaps = _history_payload_issue_snapshots(row)
            matched = None
            for rs in row_snaps:
                if str(rs.get("issue_key") or "") == issue_key:
                    matched = rs
                    break
            if matched is None:
                for rs in row_snaps:
                    if str(rs.get("code") or "") == code:
                        matched = rs
                        break
            if matched is not None:
                matches.append(
                    {
                        "period_key": row.get("period_key"),
                        "evaluated_at": row.get("evaluated_at"),
                        "decision_mode": row.get("decision_mode"),
                        "confidence_score": row.get("confidence_score"),
                        "trust_status": matched.get("trust_status"),
                        "impact_pct": matched.get("impact_pct"),
                    }
                )

        first_seen = matches[0]["evaluated_at"] if matches else "actual_run"
        last_seen = matches[-1]["evaluated_at"] if matches else "actual_run"
        trend = "new"
        if len(matches) >= 2:
            first_mode = str(matches[0].get("decision_mode") or "")
            last_mode = str(matches[-1].get("decision_mode") or "")
            first_score = int(matches[0].get("confidence_score") or 0)
            last_score = int(matches[-1].get("confidence_score") or 0)
            if last_mode == "BLOCKED" and (first_mode != "BLOCKED" or last_score < first_score):
                trend = "worsening"
            elif first_mode == "BLOCKED" and last_mode != "BLOCKED":
                trend = "improving"
            else:
                trend = "stable"
        elif len(matches) == 1:
            trend = "recurring"

        history_index[issue_key] = {
            "issue_key": issue_key,
            "code": code,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "occurrences": len(matches) + 1,
            "trend": trend,
            "timeline": matches[-5:],
        }
    return history_index


def build_issue_clusters(
    issue_snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    for snap in issue_snapshots:
        key = str(snap.get("cluster_key") or "other")
        row = clusters.setdefault(
            key,
            {
                "cluster_key": key,
                "cluster_label": snap.get("cluster_label"),
                "cluster_description": snap.get("cluster_description"),
                "worst_status": snap.get("trust_status"),
                "severity_weight_sum": 0,
                "combined_impact_pct": 0.0,
                "issue_codes": [],
                "issue_count": 0,
            },
        )
        row["issue_count"] += 1
        row["severity_weight_sum"] += int(snap.get("severity_weight") or 0)
        row["combined_impact_pct"] = min(
            100.0,
            float(row["combined_impact_pct"]) + float(snap.get("impact_pct") or 0.0),
        )
        if str(snap.get("code") or "") not in row["issue_codes"]:
            row["issue_codes"].append(str(snap.get("code") or ""))
        if (snap.get("trust_status") == "blocked") or (
            row["worst_status"] != "blocked" and snap.get("trust_status") == "warning"
        ):
            row["worst_status"] = snap.get("trust_status")

    out = list(clusters.values())
    out.sort(
        key=lambda x: (
            1 if x.get("worst_status") == "blocked" else 0,
            float(x.get("combined_impact_pct") or 0),
            int(x.get("severity_weight_sum") or 0),
        ),
        reverse=True,
    )
    return out[:6]


def compute_confidence_signals(
    findings: list[dict[str, Any]],
    snap: dict[str, Any],
    impact_summary: dict[str, Any],
) -> dict[str, Any]:
    """
    Tres pilares 0–100 con sesgo operativo:
    consistency (55%), coverage (25%), freshness (20%).
    Luego aplica caps duros si hay hallazgos que invalidan confianza ejecutiva.
    """
    im = impact_summary or {}
    pt = _pct(im.get("pct_trips_affected"))
    pr = _pct(im.get("pct_revenue_affected"))
    exposure = max(pt, pr)
    coverage_pct = max(0.0, 100.0 - exposure)
    mapping_cov_pct: float | None = None
    unmapped_trips_global: int | None = None
    try:
        from app.services.business_slice_service import get_business_slice_coverage_summary

        cs = get_business_slice_coverage_summary()
        tr = float(
            cs.get("total_trips_real_raw")
            or cs.get("total_trips_real")
            or cs.get("total_trips")
            or 0
        )
        mp = float(cs.get("mapped_trips") or 0)
        unmapped_trips_global = int(cs.get("unmapped_trips") or 0)
        if tr > 0:
            mapping_cov_pct = (mp / tr) * 100.0
            coverage_pct = min(coverage_pct, mapping_cov_pct)
            # Volumen sin mapear relevante: castiga lectura de confianza sin mezclar con OPEN/STALE de período.
            if unmapped_trips_global and unmapped_trips_global > 0:
                um_ratio = float(unmapped_trips_global) / float(tr)
                if um_ratio >= 0.05:
                    coverage_pct = min(coverage_pct, mapping_cov_pct * 0.92)
                if um_ratio >= 0.10:
                    coverage_pct = min(coverage_pct, mapping_cov_pct * 0.82)
    except Exception:
        pass
    coverage = _coverage_band_score(coverage_pct)
    for f in findings:
        code = f.get("code") or ""
        if code in ("MONTHS_BELOW_MIN", "WEEKS_BELOW_MIN", "DAYS_BELOW_MIN", "NO_DAY_FACT"):
            coverage = min(coverage, 35.0)
        if code == "DAY_FACT_DATE_GAPS":
            n = _finding_gap_count(f)
            if n >= 14:
                coverage = min(coverage, 20.0)
            elif n >= 7:
                coverage = min(coverage, 45.0)
            elif n > 0:
                coverage = min(coverage, 65.0)

    freshness = 100.0
    dmax = _to_date_any(snap.get("day_fact_max"))
    smax = _to_date_any(snap.get("source_trip_max_bounded"))
    if dmax and smax and smax >= dmax:
        lag = (smax - dmax).days
        if lag <= 1:
            freshness = 95.0
        elif lag == 2:
            freshness = 80.0
        elif lag <= 5:
            freshness = 55.0
        elif lag <= 10:
            freshness = 30.0
        else:
            freshness = 15.0
    elif dmax and not smax:
        freshness = 65.0
    elif not dmax:
        freshness = 10.0

    for f in findings:
        code = f.get("code") or ""
        if code == "DERIVED_BEHIND_SOURCE":
            lag = 0
            ev = f.get("evidence") if isinstance(f.get("evidence"), dict) else {}
            try:
                lag = int(ev.get("lag_days") or 0)
            except (TypeError, ValueError):
                lag = 0
            if lag <= 2:
                freshness = min(freshness, 80.0)
            elif lag <= 5:
                freshness = min(freshness, 55.0)
            else:
                freshness = min(freshness, 25.0)
        elif code == "DERIVED_AHEAD_OF_BOUNDED_SOURCE":
            freshness = min(freshness, 85.0)
        elif code == "SOURCE_MAX_UNAVAILABLE":
            freshness = min(freshness, 65.0)
        elif code == "FACTS_UNREADABLE":
            freshness = min(freshness, 5.0)
        elif code == "DAY_FACT_DATE_GAPS":
            n = _finding_gap_count(f)
            if n >= 14:
                freshness = min(freshness, 30.0)
            elif n >= 7:
                freshness = min(freshness, 45.0)

    consistency = 100.0
    for f in findings:
        code = (f.get("code") or "").strip()
        cat = f.get("category") or ""
        sev = f.get("severity")
        if code in CONFIDENCE_CONSISTENCY_DEDUCTIONS:
            consistency -= CONFIDENCE_CONSISTENCY_DEDUCTIONS[code]
        elif cat in ("consistency", "revenue") and sev == "error":
            consistency -= 18.0
        elif cat in ("consistency", "revenue") and sev == "warn":
            consistency -= 8.0
    consistency = max(0.0, consistency)

    weighted = (
        coverage * CONFIDENCE_PILLAR_WEIGHTS["coverage"]
        + freshness * CONFIDENCE_PILLAR_WEIGHTS["freshness"]
        + consistency * CONFIDENCE_PILLAR_WEIGHTS["consistency"]
    )
    base_score = int(max(0, min(100, round(weighted))))
    hard_cap = evaluate_confidence_hard_cap(findings)
    confidence_score = min(base_score, hard_cap["max_score"]) if hard_cap else base_score

    out_sig = {
        "coverage": round(coverage, 1),
        "freshness": round(freshness, 1),
        "consistency": round(consistency, 1),
        "coverage_basis_pct": round(coverage_pct, 1),
        "score_before_caps": base_score,
        "hard_cap": hard_cap,
        "weights": dict(CONFIDENCE_PILLAR_WEIGHTS),
        "confidence_score": confidence_score,
    }
    if mapping_cov_pct is not None:
        out_sig["mapping_coverage_pct"] = round(mapping_cov_pct, 1)
    if unmapped_trips_global is not None:
        out_sig["unmapped_trips_global"] = unmapped_trips_global
    return out_sig


def build_operational_decision(
    findings: list[dict[str, Any]],
    snap: dict[str, Any],
    impact_summary: dict[str, Any],
    operational_status: str,
) -> dict[str, Any]:
    signals = compute_confidence_signals(findings, snap, impact_summary)
    score = int(signals["confidence_score"])
    blockers = collect_decision_hard_blockers(findings)
    has_signal_findings = any(
        f.get("severity") in ("warn", "error") or (f.get("code") in OPERATIONAL_WARNING_CODES)
        for f in findings
    )
    if blockers or score < CONFIDENCE_DECISION_THRESHOLDS["blocked_max_exclusive"]:
        mode = "BLOCKED"
    elif score >= CONFIDENCE_DECISION_THRESHOLDS["safe_min"] and not has_signal_findings and operational_status == "ok":
        mode = "SAFE"
    else:
        mode = "CAUTION"
    return {
        "decision_mode": mode,
        "derived_from_status": map_trust_status_to_decision_mode(operational_status),
        "hard_blockers": blockers,
        "confidence": {
            "score": signals["confidence_score"],
            "coverage": signals["coverage"],
            "freshness": signals["freshness"],
            "consistency": signals["consistency"],
            "coverage_basis_pct": signals["coverage_basis_pct"],
            "score_before_caps": signals["score_before_caps"],
            "hard_cap": signals["hard_cap"],
            "weights": signals["weights"],
        },
    }


def fetch_trust_history_recent(limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT id, period_key, evaluated_at, decision_mode, confidence_score,
                       coverage_score, freshness_score, consistency_score, top_codes
                FROM ops.omniview_matrix_trust_history
                ORDER BY evaluated_at DESC
                LIMIT %s
                """,
                [limit],
            )
            for r in cur.fetchall():
                d = dict(r)
                if d.get("evaluated_at"):
                    d["evaluated_at"] = d["evaluated_at"].isoformat()
                if d.get("period_key"):
                    d["period_key"] = str(d["period_key"])
                rows.append(d)
            cur.close()
    except Exception as e:
        logger.debug("fetch_trust_history_recent: %s", e)
    return rows


def fetch_trust_history_timeline(limit: int = 24) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT
                    id,
                    period_key,
                    evaluated_at,
                    decision_mode,
                    confidence_score,
                    coverage_score,
                    freshness_score,
                    consistency_score,
                    top_codes,
                    payload
                FROM ops.omniview_matrix_trust_history
                ORDER BY evaluated_at DESC
                LIMIT %s
                """,
                [limit],
            )
            for r in cur.fetchall():
                d = dict(r)
                if d.get("evaluated_at"):
                    d["evaluated_at"] = d["evaluated_at"].isoformat()
                if d.get("period_key"):
                    d["period_key"] = str(d["period_key"])
                rows.append(d)
            cur.close()
    except Exception as e:
        logger.debug("fetch_trust_history_timeline: %s", e)
    return rows


def fetch_latest_trust_history_comparable(period_key: date) -> dict[str, Any] | None:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT
                    id,
                    period_key,
                    evaluated_at,
                    decision_mode,
                    confidence_score,
                    payload->>'primary_issue_code' AS primary_issue_code
                FROM ops.omniview_matrix_trust_history
                WHERE period_key = %s
                ORDER BY evaluated_at DESC
                LIMIT 1
                """,
                [period_key],
            )
            row = cur.fetchone()
            cur.close()
            if not row:
                return None
            d = dict(row)
            if d.get("evaluated_at"):
                d["evaluated_at"] = d["evaluated_at"].isoformat()
            if d.get("period_key"):
                d["period_key"] = str(d["period_key"])
            return d
    except Exception as e:
        logger.debug("fetch_latest_trust_history_comparable: %s", e)
        return None


def should_persist_omniview_trust_history(
    previous_row: dict[str, Any] | None,
    decision: dict[str, Any],
    primary_issue_code: str | None,
) -> tuple[bool, str]:
    if not previous_row:
        return True, "no_comparable_record"

    prev_mode = str(previous_row.get("decision_mode") or "")
    curr_mode = str(decision.get("decision_mode") or "")
    if prev_mode != curr_mode:
        return True, "decision_mode_changed"

    prev_issue = str(previous_row.get("primary_issue_code") or "")
    curr_issue = str(primary_issue_code or "")
    if prev_issue != curr_issue:
        return True, "primary_issue_changed"

    prev_score = int(previous_row.get("confidence_score") or 0)
    curr_score = int((decision.get("confidence") or {}).get("score") or 0)
    if abs(curr_score - prev_score) >= CONFIDENCE_DECISION_THRESHOLDS["persist_score_delta"]:
        return True, "confidence_score_delta"

    return False, "no_significant_change"


def fetch_recent_issue_actions(issue_keys: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if issue_keys:
                cur.execute(
                    """
                    SELECT
                        id, issue_key, issue_code, city, lob, period_key, metric,
                        action_status, action_label, notes, executed_at, resolved_at
                    FROM ops.omniview_matrix_issue_action_log
                    WHERE issue_key = ANY(%s)
                    ORDER BY executed_at DESC
                    LIMIT %s
                    """,
                    [issue_keys, limit],
                )
            else:
                cur.execute(
                    """
                    SELECT
                        id, issue_key, issue_code, city, lob, period_key, metric,
                        action_status, action_label, notes, executed_at, resolved_at
                    FROM ops.omniview_matrix_issue_action_log
                    ORDER BY executed_at DESC
                    LIMIT %s
                    """,
                    [limit],
                )
            for r in cur.fetchall():
                d = dict(r)
                if d.get("executed_at"):
                    d["executed_at"] = d["executed_at"].isoformat()
                if d.get("resolved_at"):
                    d["resolved_at"] = d["resolved_at"].isoformat()
                if d.get("period_key"):
                    d["period_key"] = str(d["period_key"])
                rows.append(d)
            cur.close()
    except Exception as e:
        logger.debug("fetch_recent_issue_actions: %s", e)
    return rows


def log_omniview_issue_action(
    issue_payload: dict[str, Any],
    action_status: str,
    notes: str | None = None,
) -> dict[str, Any]:
    st = str(action_status or "").strip().lower()
    if st not in OMNIVIEW_ISSUE_ACTION_STATUSES:
        raise ValueError(f"action_status inválido: {action_status}")

    issue_key = str(issue_payload.get("issue_key") or "").strip()
    issue_code = str(issue_payload.get("code") or "").strip()
    if not issue_key or not issue_code:
        raise ValueError("issue_key y code son obligatorios")

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO ops.omniview_matrix_issue_action_log (
                issue_key, issue_code, city, lob, period_key, metric,
                action_status, action_label, notes, resolved_at, payload
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                CASE WHEN %s = 'resolved' THEN now() ELSE NULL END,
                %s::jsonb
            )
            RETURNING
                id, issue_key, issue_code, city, lob, period_key, metric,
                action_status, action_label, notes, executed_at, resolved_at
            """,
            [
                issue_key,
                issue_code,
                issue_payload.get("city"),
                issue_payload.get("lob"),
                issue_payload.get("period_key"),
                issue_payload.get("metric"),
                st,
                issue_payload.get("action_label"),
                notes,
                st,
                json.dumps(issue_payload, ensure_ascii=False, default=str),
            ],
        )
        row = dict(cur.fetchone())
        conn.commit()
        cur.close()
        if row.get("executed_at"):
            row["executed_at"] = row["executed_at"].isoformat()
        if row.get("resolved_at"):
            row["resolved_at"] = row["resolved_at"].isoformat()
        if row.get("period_key"):
            row["period_key"] = str(row["period_key"])
        return row


def persist_omniview_trust_history(
    period_key: date,
    decision: dict[str, Any],
    findings: list[dict[str, Any]],
    slim_payload: dict[str, Any],
) -> int | None:
    try:
        codes: list[str] = []
        for f in findings:
            c = f.get("code")
            if c:
                codes.append(str(c))
        top_codes = list(dict.fromkeys(codes))[:24]
        conf = decision.get("confidence") or {}
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO ops.omniview_matrix_trust_history (
                    period_key, decision_mode, confidence_score,
                    coverage_score, freshness_score, consistency_score,
                    top_codes, payload
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                ) RETURNING id
                """,
                [
                    period_key,
                    decision["decision_mode"],
                    int(conf.get("score") or 0),
                    conf.get("coverage"),
                    conf.get("freshness"),
                    conf.get("consistency"),
                    top_codes,
                    json.dumps(slim_payload, ensure_ascii=False, default=str),
                ],
            )
            rid = cur.fetchone()[0]
            conn.commit()
            cur.close()
            return int(rid)
    except Exception as e:
        logger.warning("persist_omniview_trust_history: %s", e, exc_info=True)
        return None


def build_auto_recommendations(
    findings: list[dict[str, Any]],
    recent_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Patrones simples sobre hallazgos actuales + historial reciente."""
    recs: list[dict[str, Any]] = []
    from collections import Counter

    code_counts: Counter[str] = Counter()
    for f in findings:
        c = f.get("code")
        if c:
            code_counts[str(c)] += 1
    for code, n in code_counts.items():
        if n >= 2:
            recs.append(
                {
                    "type": "multi_finding",
                    "code": code,
                    "message": f"Múltiples incidencias ({n}) con código {code}: revisar pipeline y jobs de carga antes del siguiente corte.",
                }
            )

    if len(recent_history) >= 3:
        modes = [str(r.get("decision_mode") or "").upper() for r in recent_history[:3]]
        if modes == ["BLOCKED", "BLOCKED", "BLOCKED"]:
            recs.append(
                {
                    "type": "persistent_blocked",
                    "message": "BLOCKED en las 3 evaluaciones más recientes: conviene war room / priorizar datos antes de decisiones ejecutivas.",
                }
            )
        elif all(m == "CAUTION" for m in modes):
            recs.append(
                {
                    "type": "caution_streak",
                    "message": "CAUTION repetido: planificar hardening ETL, ampliar cobertura de pruebas y backfill preventivo.",
                }
            )

    if any(str(f.get("code")) == "DAY_FACT_DATE_GAPS" for f in findings) and any(
        str(r.get("decision_mode")) == "CAUTION" for r in recent_history[:2]
    ):
        recs.append(
            {
                "type": "pattern_gaps_and_history",
                "message": "Huecos en day_fact con historial de cautela: auditar incremental diario y alertas de carga.",
            }
        )

    return recs[:8]


def get_matrix_operational_trust_api_payload() -> dict[str, Any]:
    """Respuesta liviana para UI Matrix (banner + hints)."""
    global _matrix_trust_api_cache
    now = time.monotonic()
    with _matrix_trust_api_lock:
        if _matrix_trust_api_cache is not None:
            ts, payload = _matrix_trust_api_cache
            if (now - ts) < MATRIX_TRUST_API_CACHE_TTL_SEC:
                logger.debug(
                    "matrix-operational-trust: cache hit age=%.1fs ttl=%ss",
                    now - ts,
                    MATRIX_TRUST_API_CACHE_TTL_SEC,
                )
                return copy.deepcopy(payload)
    try:
        full = run_omniview_matrix_integrity_checks()
    except Exception as e:
        logger.warning("get_matrix_operational_trust_api_payload: %s", e, exc_info=True)
        return {
            "trust_status": "warning",
            "message": "No se pudo evaluar integridad Matrix",
            "operational_trust": {"status": "warning", "message": str(e)},
            "operational_decision": {
                "decision_mode": "CAUTION",
                "confidence": {"score": 0, "coverage": 0, "freshness": 0, "consistency": 0},
            },
            "trust_recommendations": [],
            "early_warnings": [],
            "issue_history": {},
            "issue_clusters": [],
            "issue_actions_recent": [],
            "trust_history_recent": [],
            "trust_history_timeline": [],
            "trust_history_persisted": False,
            "trust_history_persist_reason": "evaluation_failed",
            "affected_period_keys": {"monthly": [], "weekly": [], "daily": []},
            "affected_segments": [],
            "issue_snapshots": [],
            "primary_issue": None,
            "impact_summary": None,
            "trust_scopes": {"global": "warning", "cities": {}, "lobs": {}, "periods_flat": {}},
            "global_insights_blocked": False,
            "findings": [],
            "executive": {
                "status": "WARNING",
                "impact_pct": 0.0,
                "priority_score": 0.0,
                "main_issue": None,
                "action": "No se pudo evaluar integridad Matrix.",
            },
            "error": str(e),
        }
    op = full["operational_trust"]
    out = {
        "trust_status": op["status"],
        "message": op["message"],
        "operational_trust": op,
        "operational_decision": full.get("operational_decision"),
        "trust_recommendations": full.get("trust_recommendations") or [],
        "early_warnings": full.get("early_warnings") or [],
        "issue_history": full.get("issue_history") or {},
        "issue_clusters": full.get("issue_clusters") or [],
        "issue_actions_recent": full.get("issue_actions_recent") or [],
        "trust_history_recent": full.get("trust_history_recent") or [],
        "trust_history_timeline": full.get("trust_history_timeline") or [],
        "trust_history_period_key": full.get("trust_history_period_key"),
        "trust_history_insert_id": full.get("trust_history_insert_id"),
        "trust_history_persisted": full.get("trust_history_persisted", False),
        "trust_history_persist_reason": full.get("trust_history_persist_reason"),
        "affected_period_keys": full["affected_period_keys"],
        "affected_segments": full.get("affected_segments") or [],
        "issue_snapshots": full.get("issue_snapshots") or [],
        "primary_issue": full.get("primary_issue"),
        "impact_summary": full.get("impact_summary"),
        "trust_scopes": full.get("trust_scopes") or {},
        "global_insights_blocked": full.get("global_insights_blocked", False),
        "findings": full["findings"],
        "executive": full.get("executive"),
        "snapshot": full.get("snapshot", {}),
    }
    with _matrix_trust_api_lock:
        _matrix_trust_api_cache = (time.monotonic(), copy.deepcopy(out))
    return out


def run_omniview_matrix_integrity_checks() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    snap = check_freshness(findings)
    check_temporal_range(findings, snap)
    check_revenue(findings)
    check_consistency(findings)

    tech_ok = not any(f["severity"] == "error" for f in findings)
    operational = derive_operational_trust(findings)
    affected = build_affected_period_keys(findings)
    segments = build_affected_segments(findings)
    primary_issue = pick_primary_issue(findings)
    impact_summary = compute_impact_summary(findings, snap)
    trust_scopes = rollup_trust_scopes(segments, operational["status"])
    hard_block = global_insights_hard_blocked(segments)
    executive = build_executive_trust_banner(findings, impact_summary, operational["status"])
    operational_decision = build_operational_decision(
        findings, snap, impact_summary, operational["status"]
    )
    trust_history_recent = fetch_trust_history_recent(12)
    trust_history_timeline = fetch_trust_history_timeline(24)
    issue_snapshots = build_issue_snapshots(segments, impact_summary)
    early_warnings = build_early_warnings(
        operational_decision,
        issue_snapshots,
        trust_history_timeline,
    )
    issue_history = build_issue_history_summary(issue_snapshots, trust_history_timeline)
    issue_clusters = build_issue_clusters(issue_snapshots)
    trust_recommendations = build_auto_recommendations(findings, trust_history_recent)
    period_key = period_anchor_from_snap(snap)
    primary_issue_code = (primary_issue or {}).get("code")
    slim_history_payload = {
        "operational_status": operational["status"],
        "decision_mode": operational_decision.get("decision_mode"),
        "derived_from_status": operational_decision.get("derived_from_status"),
        "confidence": operational_decision.get("confidence"),
        "primary_issue_code": primary_issue_code,
        "findings_count": len(findings),
        "issue_snapshots": issue_snapshots,
        "early_warnings": early_warnings,
        "recommendations_preview": trust_recommendations[:3],
    }
    latest_comparable = fetch_latest_trust_history_comparable(period_key)
    should_persist_history, persist_reason = should_persist_omniview_trust_history(
        latest_comparable,
        operational_decision,
        primary_issue_code,
    )
    trust_history_insert_id = (
        persist_omniview_trust_history(
            period_key, operational_decision, findings, slim_history_payload
        )
        if should_persist_history
        else None
    )
    if trust_history_insert_id:
        trust_history_recent = fetch_trust_history_recent(12)
        trust_history_timeline = fetch_trust_history_timeline(24)
    issue_actions_recent = fetch_recent_issue_actions(
        [str(x.get("issue_key") or "") for x in issue_snapshots if x.get("issue_key")],
        20,
    )
    insights_blocked = hard_block or operational_decision.get("decision_mode") == "BLOCKED"

    summary = {
        "technical_ok": tech_ok,
        "findings_count": len(findings),
        "technical_errors": sum(1 for f in findings if f["severity"] == "error"),
        "technical_warnings": sum(1 for f in findings if f["severity"] == "warn"),
    }
    return {
        "summary": summary,
        "operational_trust": operational,
        "operational_decision": operational_decision,
        "trust_recommendations": trust_recommendations,
        "early_warnings": early_warnings,
        "issue_history": issue_history,
        "issue_clusters": issue_clusters,
        "issue_actions_recent": issue_actions_recent,
        "trust_history_recent": trust_history_recent,
        "trust_history_timeline": trust_history_timeline,
        "trust_history_period_key": period_key.isoformat(),
        "trust_history_insert_id": trust_history_insert_id,
        "trust_history_persisted": bool(trust_history_insert_id),
        "trust_history_persist_reason": persist_reason,
        "affected_period_keys": affected,
        "affected_segments": segments,
        "issue_snapshots": issue_snapshots,
        "primary_issue": primary_issue,
        "impact_summary": impact_summary,
        "trust_scopes": trust_scopes,
        "global_insights_blocked": insights_blocked,
        "executive": executive,
        "snapshot": {k: str(v) if isinstance(v, (date, Decimal)) else v for k, v in snap.items()},
        "findings": findings,
    }


def get_confidence_bundle_omniview_matrix() -> dict[str, Any]:
    """Misma forma que get_confidence_status para Data Trust."""
    full = run_omniview_matrix_integrity_checks()
    op_status = full["operational_trust"]["status"]
    od = full.get("operational_decision") or {}
    conf = od.get("confidence") or {}
    pillar_f = conf.get("freshness")
    pillar_c_cov = conf.get("coverage")
    pillar_c_cons = conf.get("consistency")
    score = int(conf.get("score")) if conf.get("score") is not None else None

    if op_status == "blocked":
        trust_status = "blocked"
        freshness_status = "missing"
        completeness_status = "partial"
        consistency_status = "major_diff"
        if score is None:
            score = 25
    elif op_status == "warning":
        trust_status = "warning"
        freshness_status = "stale"
        completeness_status = "partial"
        consistency_status = "minor_diff"
        if score is None:
            score = 60
    else:
        trust_status = "ok"
        freshness_status = "fresh"
        completeness_status = "full"
        consistency_status = "validated"
        if score is None:
            score = 92

    pi_msg = (full.get("primary_issue") or {}).get("message")
    msg = pi_msg or full["operational_trust"].get("message") or "Data Matrix"

    def _scale_pillar(p: Any, ok: float, mid: float) -> int:
        if p is None:
            return int(ok) if trust_status == "ok" else int(mid)
        try:
            return int(max(0, min(100, round(float(p) * 0.4))))
        except (TypeError, ValueError):
            return int(mid)

    fs = _scale_pillar(pillar_f, 40, 20)
    cs_cov = _scale_pillar(pillar_c_cov, 30, 18)
    cs_cons = _scale_pillar(pillar_c_cons, 30, 12)

    return {
        "source_of_truth": "ops.real_business_slice_month_fact",
        "source_mode": "canonical",
        "freshness_status": freshness_status,
        "completeness_status": completeness_status,
        "consistency_status": consistency_status,
        "confidence_score": score,
        "trust_status": trust_status,
        "message": msg,
        "last_update": None,
        "details": {
            "omniview_matrix_integrity": full,
            "operational_decision": od,
            "primary_issue": full.get("primary_issue"),
            "impact_summary": full.get("impact_summary"),
            "trust_scopes": full.get("trust_scopes"),
            "affected_segments": full.get("affected_segments"),
            "executive": full.get("executive"),
            "freshness_score": fs,
            "completeness_score": cs_cov,
            "consistency_score": cs_cons,
        },
    }


def _q_all(sql: str, params: list[Any] | None = None, drill: bool = False) -> list[dict[str, Any]]:
    ctx = get_db_drill if drill else get_db
    with ctx() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or [])
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


def _q_one(sql: str, params: list[Any] | None = None, drill: bool = False) -> dict[str, Any]:
    r = _q_all(sql, params, drill=drill)
    return r[0] if r else {}


def _add(
    findings: list[dict[str, Any]],
    severity: str,
    category: str,
    code: str,
    message: str,
    impact: str,
    suggested_fix: str,
    evidence: Any = None,
    trace: dict[str, Any] | None = None,
) -> None:
    pb = ACTION_PLAYBOOK.get(code, DEFAULT_ACTION_PLAYBOOK)
    tr = trace if isinstance(trace, dict) else {}
    findings.append(
        {
            "severity": severity,
            "category": category,
            "code": code,
            "message": message,
            "impact": impact,
            "suggested_fix": suggested_fix,
            "evidence": evidence,
            "trace": {
                "city": tr.get("city"),
                "lob": tr.get("lob"),
                "period": tr.get("period"),
                "metrics": tr.get("metrics"),
            },
            "severity_weight": CODE_SEVERITY_WEIGHT.get(code, 40),
            "action_engine": {
                "action": pb["action"],
                "suggested_query": pb["query"],
                "process": pb["process"],
            },
        }
    )


def check_freshness(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """MAX(trip_date) facts vs fuente enriquecida; lag y huecos recientes."""
    snap: dict[str, Any] = {}
    try:
        snap["day_fact_max"] = _q_one(
            "SELECT MAX(trip_date)::date AS d FROM ops.real_business_slice_day_fact"
        ).get("d")
        snap["week_fact_max_start"] = _q_one(
            "SELECT MAX(week_start)::date AS d FROM ops.real_business_slice_week_fact"
        ).get("d")
        snap["month_fact_max"] = _q_one(
            "SELECT MAX(month)::date AS d FROM ops.real_business_slice_month_fact"
        ).get("d")
    except Exception as e:
        _add(
            findings,
            "error",
            "freshness",
            "FACTS_UNREADABLE",
            f"No se pudieron leer MAX en facts: {e}",
            "Imposible auditar Matrix; riesgo de datos obsoletos o migraciones pendientes.",
            "Verificar migraciones 116/119 y existencia de ops.real_business_slice_*_fact.",
            str(e),
        )
        return snap

    # Fuente: ventana acotada para no full-scan (ajustable por env)
    recent = int(os.environ.get("OMNIVIEW_VALIDATION_SOURCE_DAYS", "400"))
    try:
        src = _q_one(
            f"""
            SELECT MAX(trip_date)::date AS d
            FROM ops.v_real_trips_enriched_base
            WHERE trip_date >= CURRENT_DATE - %s::int
            """,
            [recent],
            drill=True,
        )
        snap["source_trip_max_bounded"] = src.get("d")
    except Exception as e:
        snap["source_trip_max_bounded"] = None
        _add(
            findings,
            "warn",
            "freshness",
            "SOURCE_MAX_UNAVAILABLE",
            f"MAX(trip_date) en enriched_base (acotado) falló: {e}",
            "No se compara lag exacto vs canon; revisar conexión drill o timeout.",
            "Ejecutar con get_db_drill y/o subir timeout de sesión; o revisar vista.",
            str(e),
        )

    dmax = snap.get("day_fact_max")
    smax = snap.get("source_trip_max_bounded")
    if dmax and smax and dmax < smax:
        lag = (smax - dmax).days
        _add(
            findings,
            "warn" if lag <= 2 else "error",
            "freshness",
            "DERIVED_BEHIND_SOURCE",
            f"day_fact MAX ({dmax}) va {lag}d por detrás de enriched MAX en ventana ({smax}).",
            "STALE/incompletos en Matrix diario/semanal; comparativos y KPIs subestimados.",
            "Ejecutar backfill day_fact/week_fact para el rango faltante; revisar jobs incrementales.",
            {"lag_days": lag, "day_fact_max": str(dmax), "source_max": str(smax)},
        )
    elif dmax and smax and dmax > smax:
        _add(
            findings,
            "warn",
            "freshness",
            "DERIVED_AHEAD_OF_BOUNDED_SOURCE",
            f"day_fact MAX ({dmax}) > enriched MAX acotado ({smax}); posible ventana SOURCE_DAYS muy corta o offset de TZ.",
            "Falso positivo en auditoría o lectura inconsistente.",
            "Aumentar OMNIVIEW_VALIDATION_SOURCE_DAYS o usar MAX sin filtro en mantenimiento controlado.",
            None,
        )

    # Gaps en day_fact (últimos GAP_LOOKBACK_DAYS hasta max)
    if dmax:
        try:
            gap_rows = _q_all(
                """
                WITH b AS (
                    SELECT MAX(trip_date)::date AS mx FROM ops.real_business_slice_day_fact
                ),
                series AS (
                    SELECT generate_series(
                        (SELECT mx FROM b) - %s::int,
                        (SELECT mx FROM b),
                        '1 day'::interval
                    )::date AS d
                ),
                present AS (
                    SELECT DISTINCT trip_date AS d FROM ops.real_business_slice_day_fact
                    WHERE trip_date >= (SELECT mx - %s::int FROM b)
                )
                SELECT s.d AS missing_date
                FROM series s
                LEFT JOIN present p ON p.d = s.d
                WHERE p.d IS NULL
                ORDER BY 1
                """,
                [GAP_LOOKBACK_DAYS, GAP_LOOKBACK_DAYS],
            )
            if gap_rows:
                misses = [str(r["missing_date"]) for r in gap_rows[:30]]
                _add(
                    findings,
                    "error",
                    "freshness",
                    "DAY_FACT_DATE_GAPS",
                    f"Se detectaron {len(gap_rows)} día(s) sin filas en day_fact en lookback {GAP_LOOKBACK_DAYS}d (muestra: {misses[:5]}).",
                    "Series diarias/semanales con huecos; WoW y rollups pueden quedar desalineados.",
                    "Re-ejecutar load_business_slice_day_for_month para meses afectados; verificar fallos parciales.",
                    {"gap_count": len(gap_rows), "sample": misses},
                )
        except Exception as e:
            _add(
                findings,
                "warn",
                "freshness",
                "GAP_QUERY_FAILED",
                f"No se pudo calcular gaps: {e}",
                "Huecos desconocidos.",
                "Revisar permisos o tamaño de serie; reducir GAP_LOOKBACK_DAYS en env.",
                str(e),
            )

    return snap


def check_temporal_range(findings: list[dict[str, Any]], snap: dict[str, Any]) -> None:
    """Cobertura mínima de periodos distintos en facts (Matrix)."""
    dmax = snap.get("day_fact_max")
    if not dmax:
        _add(
            findings,
            "warn",
            "temporal_range",
            "NO_DAY_FACT",
            "Sin MAX(trip_date) en day_fact; no se valida rango mínimo.",
            "Matrix diario/semanal vacío o no cargado.",
            "Backfill day_fact.",
            None,
        )
        return

    if isinstance(dmax, str):
        dmax = date.fromisoformat(dmax[:10])

    row = _q_one(
        """
        WITH ref AS (SELECT MAX(trip_date)::date AS mx FROM ops.real_business_slice_day_fact)
        SELECT
            COUNT(DISTINCT date_trunc('month', trip_date)::date)::int AS months_n,
            COUNT(DISTINCT date_trunc('week', trip_date)::date)::int AS weeks_n,
            COUNT(DISTINCT trip_date)::int AS days_n
        FROM ops.real_business_slice_day_fact, ref
        WHERE trip_date <= ref.mx
          AND trip_date >= ref.mx - interval '400 days'
        """
    )
    months_n = int(row.get("months_n") or 0)
    weeks_n = int(row.get("weeks_n") or 0)
    days_n = int(row.get("days_n") or 0)

    row_recent = _q_one(
        """
        WITH ref AS (SELECT MAX(trip_date)::date AS mx FROM ops.real_business_slice_day_fact)
        SELECT
            COUNT(DISTINCT date_trunc('month', trip_date)::date) FILTER (
                WHERE trip_date >= (date_trunc('month', ref.mx)::date - interval '12 months')
            )::int AS months_trailing,
            COUNT(DISTINCT date_trunc('week', trip_date)::date) FILTER (
                WHERE trip_date >= ref.mx - interval '35 days'
            )::int AS weeks_trailing,
            COUNT(DISTINCT trip_date) FILTER (
                WHERE trip_date >= ref.mx - interval '13 days'
            )::int AS days_trailing
        FROM ops.real_business_slice_day_fact, ref
        """
    )
    mt = int(row_recent.get("months_trailing") or 0)
    wt = int(row_recent.get("weeks_trailing") or 0)
    dt = int(row_recent.get("days_trailing") or 0)

    evidence = {
        "day_fact_max": str(dmax),
        "distinct_months_400d": months_n,
        "distinct_weeks_400d": weeks_n,
        "distinct_days_400d": days_n,
        "trailing_months_matrix_window": mt,
        "trailing_weeks_matrix_window": wt,
        "trailing_days_matrix_window": dt,
        "expected_min_months": MIN_DISTINCT_MONTHS,
        "expected_min_weeks": MIN_DISTINCT_WEEKS,
        "expected_min_days": MIN_DISTINCT_DAYS,
    }

    if mt < MIN_DISTINCT_MONTHS:
        _add(
            findings,
            "error",
            "temporal_range",
            "MONTHS_BELOW_MIN",
            f"Solo {mt} mes(es) distintos en ventana mensual default (requerido ≥ {MIN_DISTINCT_MONTHS}).",
            "API mensual sin año puede no cubrir MoM ni análisis de tendencia.",
            "Ampliar backfill mensual; verificar filtro month >= date_trunc - 12 meses en servicio.",
            evidence,
        )
    if wt < MIN_DISTINCT_WEEKS:
        _add(
            findings,
            "error",
            "temporal_range",
            "WEEKS_BELOW_MIN",
            f"Solo {wt} semana(s) distinta(s) en ventana semanal default (requerido ≥ {MIN_DISTINCT_WEEKS}).",
            "WoW truncado o sin historia suficiente.",
            "Backfill week_fact; verificar ventana semanal en get_business_slice_weekly.",
            evidence,
        )
    if dt < MIN_DISTINCT_DAYS:
        _add(
            findings,
            "error",
            "temporal_range",
            "DAYS_BELOW_MIN",
            f"Solo {dt} día(s) con datos en ventana 14d (requerido ≥ {MIN_DISTINCT_DAYS}).",
            "Series diarias incompletas; comparativos DoW débiles.",
            "Backfill day_fact reciente; revisar ingestión de viajes.",
            evidence,
        )


def check_revenue(findings: list[dict[str, Any]]) -> None:
    """fact vs raw (resolved); signo; revenue sin completados."""
    neg = _q_one(
        """
        SELECT
            COUNT(*)::bigint AS n_neg,
            COUNT(*) FILTER (WHERE revenue_yego_net < 0)::bigint AS n_neg_strict
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= CURRENT_DATE - 400
        """
    )
    n_neg = int(neg.get("n_neg_strict") or 0)
    if n_neg > 0:
        _add(
            findings,
            "warn",
            "revenue",
            "NEGATIVE_REVENUE_ROWS",
            f"Hay {n_neg} fila(s) day_fact con revenue_yego_net < 0 en ventana reciente.",
            "Media/suma de revenue pueden desviarse del negocio esperado (comisiones normalmente ≥ 0).",
            "Auditar signo en enriched_base y reglas de comisión; excluir reversiones anómalas o corregir ETL.",
            dict(neg),
            trace={"metrics": ["revenue_yego_net"]},
        )

    bad_alloc = _q_one(
        """
        SELECT COUNT(*)::bigint AS n
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= CURRENT_DATE - 400
          AND COALESCE(trips_completed, 0) = 0
          AND revenue_yego_net IS NOT NULL
          AND revenue_yego_net <> 0
        """
    )
    nba = int(bad_alloc.get("n") or 0)
    if nba > 0:
        _add(
            findings,
            "error",
            "revenue",
            "REVENUE_WITHOUT_COMPLETED",
            f"{nba} fila(s) con revenue distinto de cero pero trips_completed = 0 (posible inclusión indebida fuera de completados).",
            "Revenue inflado o inconsistente con definición Matrix (completados).",
            "Revisar agregación en loader day_fact: SUM(revenue) debe ser solo FILTER (WHERE completed_flag) alineado a resolved.",
            dict(bad_alloc),
            trace={"metrics": ["revenue_yego_net", "commission_pct", "trips_per_driver", "avg_ticket"]},
        )

    # Comparar último mes cerrado con datos en ambos lados
    try:
        cmp_rows = _q_all(
            """
            WITH last_m AS (
                SELECT MAX(month)::date AS m
                FROM ops.real_business_slice_month_fact
                WHERE month < date_trunc('month', CURRENT_DATE)::date
            ),
            fsum AS (
                SELECT
                    SUM(f.trips_completed)::numeric AS tc,
                    SUM(f.revenue_yego_net)::numeric AS rev
                FROM ops.real_business_slice_month_fact f
                JOIN last_m ON f.month = last_m.m
            ),
            rsum AS (
                SELECT
                    COUNT(*) FILTER (WHERE r.completed_flag)::numeric AS tc,
                    SUM(r.revenue_yego_net) FILTER (WHERE r.completed_flag)::numeric AS rev
                FROM ops.v_real_trips_business_slice_resolved r
                JOIN last_m ON r.trip_month = last_m.m
                WHERE r.resolution_status = 'resolved'
            )
            SELECT
                last_m.m::text AS period,
                fsum.tc AS fact_trips,
                rsum.tc AS raw_trips,
                fsum.rev AS fact_rev,
                rsum.rev AS raw_rev
            FROM last_m, fsum, rsum
            """,
            drill=True,
        )
        if not cmp_rows:
            _add(
                findings,
                "warn",
                "revenue",
                "MONTH_COMPARE_SKIPPED",
                "No hubo fila de comparación month_fact vs resolved (¿sin mes cerrado?).",
                "Comparación revenue omitida.",
                "Cargar al menos un mes cerrado en month_fact.",
                None,
            )
            return
        r0 = cmp_rows[0]
        period = r0.get("period")
        ft = float(r0["fact_trips"] or 0)
        rt = float(r0["raw_trips"] or 0)
        fr = float(r0["fact_rev"] or 0)
        rr = float(r0["raw_rev"] or 0)
        trips_ok = rt > 0 and abs(ft - rt) <= max(1.0, 0.001 * rt)
        rev_ok = rr == 0 or abs(fr - rr) <= max(REVENUE_ABS_EPS, REVENUE_REL_EPS * abs(rr))
        if not trips_ok:
            _add(
                findings,
                "error",
                "revenue",
                "MONTH_TRIPS_MISMATCH",
                f"Mes {period}: SUM trips month_fact ({ft}) vs raw completados ({rt}).",
                "Totales Matrix no coinciden con fuente; rankings y deltas incorrectos.",
                "Re-cargar mes en month_fact; revisar chunks omitidos o dims.",
                r0,
                trace={
                    "period": str(period)[:10] if period else None,
                    "metrics": ["trips_completed"],
                },
            )
        if not rev_ok:
            _add(
                findings,
                "error",
                "revenue",
                "MONTH_REVENUE_MISMATCH",
                f"Mes {period}: SUM revenue month_fact ({fr}) vs raw ({rr}).",
                "Revenue ejecutivo desalineado respecto a viajes resueltos.",
                "Verificar loader y proxy vs real en enriched; re-run load_business_slice_month.",
                r0,
                trace={
                    "period": str(period)[:10] if period else None,
                    "metrics": ["revenue_yego_net"],
                },
            )
    except Exception as e:
        _add(
            findings,
            "warn",
            "revenue",
            "MONTH_COMPARE_FAILED",
            f"Fallo comparando month_fact vs resolved: {e}",
            "Integridad revenue no verificada automáticamente.",
            "Ejecutar en ventana de mantenimiento o con statement_timeout=0 en drill.",
            str(e),
        )


def check_consistency(findings: list[dict[str, Any]]) -> None:
    """Suma de filas fact vs agregado raw por periodo reciente (viajes/revenue)."""
    try:
        rows = _q_all(
            """
            WITH periods AS (
                SELECT month
                FROM ops.real_business_slice_month_fact
                GROUP BY month
                ORDER BY month DESC
                LIMIT 3
            ),
            rows_sum AS (
                SELECT
                    f.month AS period_key,
                    SUM(f.trips_completed)::numeric AS rows_trips,
                    SUM(f.revenue_yego_net)::numeric AS rows_revenue
                FROM ops.real_business_slice_month_fact f
                JOIN periods p ON p.month = f.month
                GROUP BY f.month
            ),
            raw_tot AS (
                SELECT
                    r.trip_month AS period_key,
                    COUNT(*) FILTER (WHERE r.completed_flag)::numeric AS total_trips,
                    SUM(r.revenue_yego_net) FILTER (WHERE r.completed_flag)::numeric AS total_revenue
                FROM ops.v_real_trips_business_slice_resolved r
                JOIN periods p ON p.month = r.trip_month
                WHERE r.resolution_status = 'resolved'
                GROUP BY r.trip_month
            )
            SELECT
                rs.period_key::text AS period,
                rs.rows_trips,
                rt.total_trips,
                (rs.rows_trips - rt.total_trips) AS trips_diff,
                rs.rows_revenue,
                rt.total_revenue,
                (rs.rows_revenue - rt.total_revenue) AS rev_diff
            FROM rows_sum rs
            JOIN raw_tot rt USING (period_key)
            """,
            drill=True,
        )
        for r in rows:
            td = float(r.get("trips_diff") or 0)
            rd = float(r.get("rev_diff") or 0)
            rr = float(r.get("total_revenue") or 0)
            trip_bad = abs(td) > max(1.0, 0.001 * float(r.get("total_trips") or 0))
            rev_bad = (
                abs(rd) > max(REVENUE_ABS_EPS, REVENUE_REL_EPS * abs(rr))
                if rr
                else abs(rd) > REVENUE_ABS_EPS
            )
            if trip_bad or rev_bad:
                mlist: list[str] = []
                if trip_bad:
                    mlist.append("trips_completed")
                if rev_bad:
                    mlist.append("revenue_yego_net")
                per = r.get("period")
                _add(
                    findings,
                    "error",
                    "consistency",
                    "ROLLUP_MISMATCH",
                    f"Periodo {r.get('period')}: diff viajes={td}, diff revenue={rd}.",
                    "Totales Matrix (suma de líneas) no igualan universo resolved por mes.",
                    "Auditar dims duplicadas o faltantes en mapping; re-run carga mensual incremental.",
                    dict(r),
                    trace={"period": str(per)[:10] if per else None, "metrics": mlist},
                )
    except Exception as e:
        _add(
            findings,
            "warn",
            "consistency",
            "ROLLUP_CHECK_FAILED",
            str(e),
            "Consistencia suma vs total no verificada.",
            "Reintentar con conexión drill y más tiempo; usar audit_business_slice_trust --section matrix_consistency.",
            str(e),
        )


def run_cli_main() -> None:
    """CLI: `python -m scripts.validate_omniview_matrix_integrity` delega aquí."""
    parser = argparse.ArgumentParser(description="Validar integridad Omniview Matrix")
    parser.add_argument("--json", action="store_true", help="Salida solo JSON")
    args = parser.parse_args()

    full = run_omniview_matrix_integrity_checks()
    findings = full["findings"]
    op = full["operational_trust"]
    tech = full["summary"]

    summary = {
        "technical_ok": tech["technical_ok"],
        "operational_status": op["status"],
        "findings_count": tech["findings_count"],
        "technical_errors": tech["technical_errors"],
        "technical_warnings": tech["technical_warnings"],
    }
    report = {
        "summary": summary,
        "operational_trust": op,
        "operational_decision": full.get("operational_decision"),
        "trust_recommendations": full.get("trust_recommendations") or [],
        "snapshot": full["snapshot"],
        "affected_period_keys": full["affected_period_keys"],
        "executive": full.get("executive"),
        "findings": findings,
    }

    exit_ok = op["status"] == "ok"
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        sys.exit(0 if exit_ok else (2 if op["status"] == "blocked" else 1))

    print("=== Omniview Matrix — validación de integridad ===\n")
    print(f"Trust operativo: {op['status'].upper()}  |  técnico errors={tech['technical_errors']}\n")
    print("Snapshot:")
    for k, v in full["snapshot"].items():
        print(f"  {k}: {v}")
    print()
    if not findings:
        print("Sin hallazgos.\n")
    else:
        print("Hallazgos:\n")
        for i, f in enumerate(findings, 1):
            print(f"--- [{i}] {f['severity'].upper()} | {f['category']} | {f['code']} ---")
            print(f"  Mensaje: {f['message']}")
            print(f"  Impacto: {f['impact']}")
            print(f"  Fix:     {f['suggested_fix']}")
            if f.get("evidence") is not None:
                print(f"  Evidencia: {f['evidence']}")
            print()
    sys.exit(0 if exit_ok else (2 if op["status"] == "blocked" else 1))
