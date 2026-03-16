"""
Servicio de calidad de margen en fuente (REAL).
Lee ops.real_margin_quality_audit y/o calcula agregados recientes para API y UI.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.db.connection import get_db
from app.services.real_margin_quality_constants import (
    severity_cancelled_with_margin,
    severity_completed_without_margin,
)
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

DEFAULT_DAYS_RECENT = 90


def _serialize_date(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


def get_margin_quality_summary(days_recent: int = DEFAULT_DAYS_RECENT) -> dict[str, Any]:
    """
    Resumen actual: agregado en ventana reciente + severidad + flags.
    Incluye: aggregate, severity_primary, severity_secondary, has_margin_source_gap,
    margin_coverage_incomplete, has_cancelled_with_margin_issue, margin_quality_status.
    """
    today = date.today()
    start_date = today - timedelta(days=days_recent)
    out: dict[str, Any] = {
        "aggregate": None,
        "severity_primary": "OK",
        "severity_secondary": "OK",
        "has_margin_source_gap": False,
        "margin_coverage_incomplete": False,
        "has_cancelled_with_margin_issue": False,
        "margin_quality_status": "OK",
        "days_recent": days_recent,
        "start_date": _serialize_date(start_date),
        "end_date": _serialize_date(today),
    }
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE trip_outcome_norm = 'completed') AS completed_trips,
                    COUNT(*) FILTER (WHERE trip_outcome_norm = 'completed' AND margin_total IS NOT NULL) AS completed_trips_with_margin,
                    COUNT(*) FILTER (WHERE trip_outcome_norm = 'completed' AND margin_total IS NULL) AS completed_trips_without_margin,
                    COUNT(*) FILTER (WHERE trip_outcome_norm = 'cancelled') AS cancelled_trips,
                    COUNT(*) FILTER (WHERE trip_outcome_norm = 'cancelled' AND margin_total IS NOT NULL) AS cancelled_trips_with_margin
                FROM ops.v_real_trip_fact_v2 v
                WHERE v.trip_date >= %s AND v.trip_date <= %s
            """, (start_date, today))
            row = cur.fetchone()
            cur.close()
        if not row:
            return out
        ct = int(row["completed_trips"] or 0)
        ctm = int(row["completed_trips_with_margin"] or 0)
        ctwom = int(row["completed_trips_without_margin"] or 0)
        cancel = int(row["cancelled_trips"] or 0)
        cancel_m = int(row["cancelled_trips_with_margin"] or 0)
        pct_wo = (100.0 * ctwom / ct) if ct else 0.0
        pct_cancel_m = (100.0 * cancel_m / cancel) if cancel else 0.0
        coverage_pct = (100.0 * ctm / ct) if ct else 100.0
        out["aggregate"] = {
            "completed_trips": ct,
            "completed_trips_with_margin": ctm,
            "completed_trips_without_margin": ctwom,
            "completed_without_margin_pct": round(pct_wo, 4),
            "cancelled_trips": cancel,
            "cancelled_trips_with_margin": cancel_m,
            "cancelled_with_margin_pct": round(pct_cancel_m, 4),
            "margin_coverage_pct": round(coverage_pct, 2),
        }
        out["severity_primary"] = severity_completed_without_margin(ct, ctwom, ctm)
        out["severity_secondary"] = severity_cancelled_with_margin(cancel, cancel_m)
        out["has_margin_source_gap"] = out["severity_primary"] != "OK"
        out["margin_coverage_incomplete"] = out["severity_primary"] != "OK"
        out["has_cancelled_with_margin_issue"] = out["severity_secondary"] != "OK"
        if out["severity_primary"] == "CRITICAL" or out["severity_secondary"] == "CRITICAL":
            out["margin_quality_status"] = "CRITICAL"
        elif out["severity_primary"] == "WARNING" or out["severity_secondary"] == "WARNING":
            out["margin_quality_status"] = "WARNING"
        elif out["severity_primary"] == "INFO":
            out["margin_quality_status"] = "INFO"
        return out
    except Exception as e:
        logger.warning("get_margin_quality_summary: %s", e)
        return out


def get_margin_quality_findings(limit: int = 20) -> list[dict[str, Any]]:
    """Últimos hallazgos persistidos en ops.real_margin_quality_audit (vacío si la tabla no existe)."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'ops' AND table_name = 'real_margin_quality_audit'
            """)
            if not cur.fetchone():
                cur.close()
                return []
            cur.execute("""
                SELECT id, alert_code, severity, detected_at, grain_date,
                       affected_trips, denominator_trips, pct, message_humano_legible, dimensions, metadata
                FROM ops.real_margin_quality_audit
                ORDER BY detected_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            cur.close()
        return [
            {
                "id": r["id"],
                "alert_code": r["alert_code"],
                "severity": r["severity"],
                "detected_at": r["detected_at"].isoformat() if hasattr(r["detected_at"], "isoformat") else str(r["detected_at"]),
                "grain_date": _serialize_date(r["grain_date"]),
                "affected_trips": r["affected_trips"],
                "denominator_trips": r["denominator_trips"],
                "pct": float(r["pct"]) if r["pct"] is not None else None,
                "message_humano_legible": r["message_humano_legible"],
                "dimensions": r["dimensions"],
                "metadata": r["metadata"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("get_margin_quality_findings: %s", e)
        return []


def get_affected_period_dates(days_recent: int = DEFAULT_DAYS_RECENT) -> dict[str, list[str]]:
    """
    Fechas (día/semana/mes) con cobertura de margen incompleta para marcar en drill.
    Devuelve listas de fechas en ISO (YYYY-MM-DD): affected_days, affected_week_dates, affected_month_dates.
    """
    today = date.today()
    start_date = today - timedelta(days=days_recent)
    out: dict[str, list[str]] = {"affected_days": [], "affected_week_dates": [], "affected_month_dates": []}
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT
                    v.trip_date::date AS grain_date,
                    COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed') AS completed_trips,
                    COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) AS completed_trips_without_margin
                FROM ops.v_real_trip_fact_v2 v
                WHERE v.trip_date >= %s AND v.trip_date <= %s
                GROUP BY v.trip_date::date
            """, (start_date, today))
            rows = cur.fetchall()
            cur.close()
        days_set = set()
        weeks_set = set()
        months_set = set()
        for r in rows:
            ct = int(r["completed_trips"] or 0)
            ctwom = int(r["completed_trips_without_margin"] or 0)
            if ct > 0 and ctwom > 0:
                d = r["grain_date"]
                if hasattr(d, "isoformat"):
                    d_str = d.isoformat()[:10]
                else:
                    d_str = str(d)[:10]
                days_set.add(d_str)
                # week_start (lunes) y month_start
                try:
                    dt = d if isinstance(d, date) else datetime.strptime(d_str, "%Y-%m-%d").date()
                    w = dt - timedelta(days=dt.weekday())
                    weeks_set.add(w.isoformat()[:10])
                    m = dt.replace(day=1)
                    months_set.add(m.isoformat()[:10])
                except (ValueError, TypeError):
                    pass
        out["affected_days"] = sorted(days_set)
        out["affected_week_dates"] = sorted(weeks_set)
        out["affected_month_dates"] = sorted(months_set)
    except Exception as e:
        logger.warning("get_affected_period_dates: %s", e)
    return out


def get_margin_quality_full(days_recent: int = DEFAULT_DAYS_RECENT, findings_limit: int = 20) -> dict[str, Any]:
    """
    Payload completo para GET /ops/real/margin-quality:
    summary (resumen + flags) + findings (últimos hallazgos) + affected period dates para badges en drill.
    """
    summary = get_margin_quality_summary(days_recent=days_recent)
    findings = get_margin_quality_findings(limit=findings_limit)
    affected = get_affected_period_dates(days_recent=days_recent)
    return {
        **summary,
        "findings": findings,
        "affected_days": affected["affected_days"],
        "affected_week_dates": affected["affected_week_dates"],
        "affected_month_dates": affected["affected_month_dates"],
    }
