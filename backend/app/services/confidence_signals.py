"""
Señales reales de completeness y consistency para el Confidence Engine.
No inventar ok cuando falta señal; unknown y score bajo.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Completeness: días/semanas/meses esperados para calcular ratio
REAL_LOB_EXPECTED_DAYS = 7
RESUMEN_EXPECTED_MONTHS = 12
SUPPLY_EXPECTED_WEEKS = 4
DRIVER_LIFECYCLE_EXPECTED_WEEKS = 8

# Umbrales coverage_ratio -> status
RATIO_FULL = 1.0
RATIO_PARTIAL = 0.70


def get_completeness_status(view_name: str, _filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    full | partial | missing | unknown.
    coverage_ratio, expected_periods, actual_periods.
    """
    view_name = (view_name or "").strip().lower()
    default = {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": 0, "actual_periods": 0}

    try:
        if view_name == "real_lob":
            return _completeness_real_lob()
        if view_name == "resumen":
            return _completeness_resumen()
        if view_name == "plan_vs_real":
            return _completeness_plan_vs_real()
        if view_name == "supply":
            return _completeness_supply()
        if view_name == "driver_lifecycle":
            return _completeness_driver_lifecycle()
    except Exception as e:
        logger.debug("get_completeness_status %s: %s", view_name, e)

    return default


def _completeness_real_lob() -> Dict[str, Any]:
    """Últimos N días: count distinct trip_date vs expected."""
    today = date.today()
    start = today - timedelta(days=REAL_LOB_EXPECTED_DAYS)
    expected = REAL_LOB_EXPECTED_DAYS
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COUNT(DISTINCT trip_date) AS actual
                FROM ops.mv_real_lob_day_v2
                WHERE trip_date >= %s AND trip_date <= %s
                """,
                (start, today),
            )
            row = cur.fetchone()
            actual = int(row["actual"]) if row and row.get("actual") is not None else 0
            cur.close()
        ratio = actual / expected if expected else 0.0
        status = "full" if ratio >= RATIO_FULL else "partial" if ratio >= RATIO_PARTIAL else "missing"
        return {"status": status, "coverage_ratio": round(ratio, 4), "expected_periods": expected, "actual_periods": actual}
    except Exception as e:
        logger.debug("_completeness_real_lob: %s", e)
        return {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": expected, "actual_periods": 0}


def _completeness_resumen() -> Dict[str, Any]:
    """Meses esperados vs presentes en mv_real_monthly_canonical_hist (últimos 12 meses)."""
    today = date.today()
    first_day_this_month = today.replace(day=1)
    start_month = first_day_this_month - timedelta(days=365)
    expected = 12
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COUNT(DISTINCT month_start) AS actual
                FROM ops.mv_real_monthly_canonical_hist
                WHERE month_start >= %s AND month_start < %s
                """,
                (start_month, first_day_this_month),
            )
            row = cur.fetchone()
            actual = int(row["actual"]) if row and row.get("actual") is not None else 0
            cur.close()
        ratio = actual / expected if expected else 0.0
        status = "full" if ratio >= RATIO_FULL else "partial" if ratio >= RATIO_PARTIAL else "missing"
        return {"status": status, "coverage_ratio": round(ratio, 4), "expected_periods": expected, "actual_periods": actual}
    except Exception as e:
        logger.debug("_completeness_resumen: %s", e)
        return {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": expected, "actual_periods": 0}


def _completeness_plan_vs_real() -> Dict[str, Any]:
    """Usar data_completeness del parity audit."""
    try:
        from app.services.plan_vs_real_service import get_latest_parity_audit

        audit = get_latest_parity_audit(scope=None)
        if not audit:
            return {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": 0, "actual_periods": 0}
        comp = (audit.get("data_completeness") or "").upper()
        if comp == "FULL":
            return {"status": "full", "coverage_ratio": 1.0, "expected_periods": 1, "actual_periods": 1}
        if comp == "PARTIAL":
            return {"status": "partial", "coverage_ratio": 0.7, "expected_periods": 1, "actual_periods": 1}
        return {"status": "unknown", "coverage_ratio": 0.5, "expected_periods": 1, "actual_periods": 0}
    except Exception as e:
        logger.debug("_completeness_plan_vs_real: %s", e)
        return {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": 0, "actual_periods": 0}


def _completeness_supply() -> Dict[str, Any]:
    """Semanas esperadas vs presentes en mv_supply_segments_weekly (últimas 4 semanas)."""
    today = date.today()
    last_monday = today - timedelta(days=today.weekday())
    start_week = last_monday - timedelta(days=7 * (SUPPLY_EXPECTED_WEEKS - 1))
    expected = SUPPLY_EXPECTED_WEEKS
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COUNT(DISTINCT week_start) AS actual
                FROM ops.mv_supply_segments_weekly
                WHERE week_start >= %s AND week_start <= %s
                """,
                (start_week, last_monday),
            )
            row = cur.fetchone()
            actual = int(row["actual"]) if row and row.get("actual") is not None else 0
            cur.close()
        ratio = actual / expected if expected else 0.0
        status = "full" if ratio >= RATIO_FULL else "partial" if ratio >= RATIO_PARTIAL else "missing"
        return {"status": status, "coverage_ratio": round(ratio, 4), "expected_periods": expected, "actual_periods": actual}
    except Exception as e:
        logger.debug("_completeness_supply: %s", e)
        return {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": expected, "actual_periods": 0}


def _completeness_driver_lifecycle() -> Dict[str, Any]:
    """Semanas esperadas vs presentes en mv_driver_lifecycle_weekly_kpis."""
    today = date.today()
    last_monday = today - timedelta(days=today.weekday())
    start_week = last_monday - timedelta(days=7 * (DRIVER_LIFECYCLE_EXPECTED_WEEKS - 1))
    expected = DRIVER_LIFECYCLE_EXPECTED_WEEKS
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COUNT(DISTINCT week_start) AS actual
                FROM ops.mv_driver_lifecycle_weekly_kpis
                WHERE week_start >= %s AND week_start <= %s
                """,
                (start_week, last_monday),
            )
            row = cur.fetchone()
            actual = int(row["actual"]) if row and row.get("actual") is not None else 0
            cur.close()
        ratio = actual / expected if expected else 0.0
        status = "full" if ratio >= RATIO_FULL else "partial" if ratio >= RATIO_PARTIAL else "missing"
        return {"status": status, "coverage_ratio": round(ratio, 4), "expected_periods": expected, "actual_periods": actual}
    except Exception as e:
        logger.debug("_completeness_driver_lifecycle: %s", e)
        return {"status": "unknown", "coverage_ratio": 0.0, "expected_periods": expected, "actual_periods": 0}


def get_consistency_status(view_name: str, _filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    validated | minor_diff | major_diff | unknown.
    diff_ratio cuando aplica.
    """
    view_name = (view_name or "").strip().lower()
    default = {"status": "unknown", "diff_ratio": None}

    try:
        if view_name == "plan_vs_real":
            return _consistency_plan_vs_real()
        if view_name == "real_lob":
            return _consistency_real_lob()
        if view_name == "resumen":
            return _consistency_resumen()
        if view_name == "supply":
            return _consistency_supply()
        if view_name == "driver_lifecycle":
            return _consistency_driver_lifecycle()
    except Exception as e:
        logger.debug("get_consistency_status %s: %s", view_name, e)

    return default


def _consistency_plan_vs_real() -> Dict[str, Any]:
    """Parity audit: MATCH -> validated, MINOR_DIFF -> minor_diff, MAJOR_DIFF -> major_diff."""
    try:
        from app.services.plan_vs_real_service import get_latest_parity_audit

        audit = get_latest_parity_audit(scope=None)
        if not audit:
            return {"status": "unknown", "diff_ratio": None}
        diagnosis = (audit.get("diagnosis") or "").upper()
        max_diff_pct = audit.get("max_diff_pct")
        diff_ratio = (float(max_diff_pct) / 100.0) if max_diff_pct is not None else None
        if diagnosis == "MATCH":
            return {"status": "validated", "diff_ratio": 0.0 if diff_ratio is None else diff_ratio}
        if diagnosis == "MINOR_DIFF":
            return {"status": "minor_diff", "diff_ratio": diff_ratio}
        if diagnosis == "MAJOR_DIFF":
            return {"status": "major_diff", "diff_ratio": diff_ratio}
        return {"status": "unknown", "diff_ratio": diff_ratio}
    except Exception as e:
        logger.debug("_consistency_plan_vs_real: %s", e)
        return {"status": "unknown", "diff_ratio": None}


def _consistency_real_lob() -> Dict[str, Any]:
    """Comparar SUM(completed_trips) hourly vs day para ayer. diff_ratio = |sum_h - sum_d| / sum_d."""
    yesterday = date.today() - timedelta(days=1)
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COALESCE(SUM(completed_trips), 0)::float AS s
                FROM ops.mv_real_lob_hour_v2 WHERE trip_date = %s
                """,
                (yesterday,),
            )
            row_h = cur.fetchone()
            cur.execute(
                """
                SELECT COALESCE(SUM(completed_trips), 0)::float AS s
                FROM ops.mv_real_lob_day_v2 WHERE trip_date = %s
                """,
                (yesterday,),
            )
            row_d = cur.fetchone()
            cur.close()
        sum_h = float(row_h["s"]) if row_h and row_h.get("s") is not None else 0.0
        sum_d = float(row_d["s"]) if row_d and row_d.get("s") is not None else 0.0
        if sum_d == 0:
            if sum_h == 0:
                return {"status": "validated", "diff_ratio": 0.0}
            return {"status": "unknown", "diff_ratio": None}
        diff_ratio = abs(sum_h - sum_d) / sum_d
        if diff_ratio < 0.01:
            return {"status": "validated", "diff_ratio": round(diff_ratio, 4)}
        if diff_ratio <= 0.05:
            return {"status": "minor_diff", "diff_ratio": round(diff_ratio, 4)}
        return {"status": "major_diff", "diff_ratio": round(diff_ratio, 4)}
    except Exception as e:
        logger.debug("_consistency_real_lob: %s", e)
        return {"status": "unknown", "diff_ratio": None}


def _consistency_resumen() -> Dict[str, Any]:
    """Resumen = combinación real_lob + plan_vs_real; peor consistency de los dos."""
    lob = get_consistency_status("real_lob", None)
    pvr = get_consistency_status("plan_vs_real", None)
    slob = lob.get("status") or "unknown"
    spvr = pvr.get("status") or "unknown"
    if slob == "major_diff" or spvr == "major_diff":
        return {"status": "major_diff", "diff_ratio": pvr.get("diff_ratio") or lob.get("diff_ratio")}
    if slob == "minor_diff" or spvr == "minor_diff":
        return {"status": "minor_diff", "diff_ratio": pvr.get("diff_ratio") or lob.get("diff_ratio")}
    if slob == "validated" and spvr == "validated":
        return {"status": "validated", "diff_ratio": 0.0}
    return {"status": "unknown", "diff_ratio": None}


def _consistency_supply() -> Dict[str, Any]:
    """Supply: segmentos derivan de mv_driver_segments_weekly; validado si hay data reciente."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM ops.mv_supply_segments_weekly
                WHERE week_start >= current_date - interval '28 days'
                """
            )
            row = cur.fetchone()
            n = int(row["n"]) if row and row.get("n") is not None else 0
            cur.close()
        if n > 0:
            return {"status": "validated", "diff_ratio": 0.0}
        return {"status": "unknown", "diff_ratio": None}
    except Exception as e:
        logger.debug("_consistency_supply: %s", e)
        return {"status": "unknown", "diff_ratio": None}


def _consistency_driver_lifecycle() -> Dict[str, Any]:
    """Driver lifecycle: validado si hay filas en base recientes."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM ops.mv_driver_lifecycle_base
                WHERE last_completed_ts >= current_timestamp - interval '14 days'
                """
            )
            row = cur.fetchone()
            n = int(row["n"]) if row and row.get("n") is not None else 0
            cur.close()
        if n > 0:
            return {"status": "validated", "diff_ratio": 0.0}
        return {"status": "unknown", "diff_ratio": None}
    except Exception as e:
        logger.debug("_consistency_driver_lifecycle: %s", e)
        return {"status": "unknown", "diff_ratio": None}
