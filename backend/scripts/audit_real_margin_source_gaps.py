"""
FASE 2 — Auditoría de huecos de margen en fuente (REAL).

Reglas:
- Completado + margen NULL = anomalía principal (hueco de fuente).
- Cancelado + margen NULL = normal, no alertar.
- Cancelado + margen presente = anomalía secundaria de consistencia.

Fuente: ops.v_real_trip_fact_v2 (trip_date, trip_outcome_norm, margin_total, country, lob_group, park_id, real_tipo_servicio_norm).

Uso: cd backend && python -m scripts.audit_real_margin_source_gaps [--days 90] [--persist]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run(days_recent: int = 90, persist: bool = False) -> tuple[dict, int]:
    """
    Ejecuta queries de diagnóstico y devuelve resumen + código de salida.
    persist: si True y existe tabla ops.real_margin_quality_audit, escribe hallazgos.
    """
    from app.db.connection import init_db_pool
    from app.services.real_margin_quality_constants import (
        ALERT_CODE_PRIMARY,
        ALERT_CODE_SECONDARY,
        severity_cancelled_with_margin,
        severity_completed_without_margin,
    )
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    today = date.today()
    start_date = today - timedelta(days=days_recent)

    summary = {
        "days_recent": days_recent,
        "start_date": start_date.isoformat(),
        "end_date": today.isoformat(),
        "daily": [],
        "by_dimension": {},
        "top_combinations": [],
        "aggregate": None,
        "severity_primary": "OK",
        "severity_secondary": "OK",
        "has_margin_source_gap": False,
        "has_cancelled_with_margin_issue": False,
        "exit_severity": "OK",
    }

    from app.db.connection import get_db
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ─── 1) Agregado global en ventana (para severidad y resumen) ───
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
        if row:
            ct = int(row["completed_trips"] or 0)
            ctm = int(row["completed_trips_with_margin"] or 0)
            ctwom = int(row["completed_trips_without_margin"] or 0)
            cancel = int(row["cancelled_trips"] or 0)
            cancel_m = int(row["cancelled_trips_with_margin"] or 0)
            pct_wo = (100.0 * ctwom / ct) if ct else 0.0
            pct_cancel_m = (100.0 * cancel_m / cancel) if cancel else 0.0
            coverage_pct = (100.0 * ctm / ct) if ct else 100.0
            summary["aggregate"] = {
                "completed_trips": ct,
                "completed_trips_with_margin": ctm,
                "completed_trips_without_margin": ctwom,
                "completed_without_margin_pct": round(pct_wo, 4),
                "cancelled_trips": cancel,
                "cancelled_trips_with_margin": cancel_m,
                "cancelled_with_margin_pct": round(pct_cancel_m, 4),
                "margin_coverage_pct": round(coverage_pct, 2),
            }
            summary["severity_primary"] = severity_completed_without_margin(ct, ctwom, ctm)
            summary["severity_secondary"] = severity_cancelled_with_margin(cancel, cancel_m)
            summary["has_margin_source_gap"] = summary["severity_primary"] != "OK"
            summary["has_cancelled_with_margin_issue"] = summary["severity_secondary"] != "OK"
            if summary["severity_primary"] == "CRITICAL" or summary["severity_secondary"] == "CRITICAL":
                summary["exit_severity"] = "CRITICAL"
            elif summary["severity_primary"] == "WARNING" or summary["severity_secondary"] == "WARNING":
                summary["exit_severity"] = "WARNING"
            elif summary["severity_primary"] == "INFO":
                summary["exit_severity"] = "INFO"

        # ─── 2) Diario últimos N días ───
        cur.execute("""
            SELECT
                v.trip_date::date AS grain_date,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed') AS completed_trips,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NOT NULL) AS completed_trips_with_margin,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) AS completed_trips_without_margin,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'cancelled') AS cancelled_trips,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'cancelled' AND v.margin_total IS NOT NULL) AS cancelled_trips_with_margin
            FROM ops.v_real_trip_fact_v2 v
            WHERE v.trip_date >= %s AND v.trip_date <= %s
            GROUP BY v.trip_date::date
            ORDER BY v.trip_date::date DESC
            LIMIT 200
        """, (start_date, today))
        rows = cur.fetchall()
        for r in rows:
            ct = int(r["completed_trips"] or 0)
            ctwom = int(r["completed_trips_without_margin"] or 0)
            cancel = int(r["cancelled_trips"] or 0)
            cancel_m = int(r["cancelled_trips_with_margin"] or 0)
            pct_wo = (100.0 * ctwom / ct) if ct else 0.0
            pct_cm = (100.0 * cancel_m / cancel) if cancel else 0.0
            summary["daily"].append({
                "grain_date": r["grain_date"].isoformat() if hasattr(r["grain_date"], "isoformat") else str(r["grain_date"])[:10],
                "completed_trips": ct,
                "completed_trips_with_margin": int(r["completed_trips_with_margin"] or 0),
                "completed_trips_without_margin": ctwom,
                "completed_without_margin_pct": round(pct_wo, 4),
                "cancelled_trips": cancel,
                "cancelled_trips_with_margin": cancel_m,
                "cancelled_with_margin_pct": round(pct_cm, 4),
                "margin_coverage_pct": round((100.0 * (ct - ctwom) / ct), 2) if ct else 100.0,
            })

        # ─── 3) Por dimensión: país ───
        cur.execute("""
            SELECT
                COALESCE(v.country, '') AS country,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed') AS completed_trips,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) AS completed_trips_without_margin
            FROM ops.v_real_trip_fact_v2 v
            WHERE v.trip_date >= %s AND v.trip_date <= %s
            GROUP BY COALESCE(v.country, '')
            ORDER BY COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) DESC
        """, (start_date, today))
        summary["by_dimension"]["country"] = [dict(r) for r in cur.fetchall()]

        # ─── 4) Por dimensión: LOB ───
        cur.execute("""
            SELECT
                COALESCE(v.lob_group, '') AS lob_group,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed') AS completed_trips,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) AS completed_trips_without_margin
            FROM ops.v_real_trip_fact_v2 v
            WHERE v.trip_date >= %s AND v.trip_date <= %s
            GROUP BY COALESCE(v.lob_group, '')
            ORDER BY COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) DESC
        """, (start_date, today))
        summary["by_dimension"]["lob"] = [dict(r) for r in cur.fetchall()]

        # ─── 5) Top combinaciones: fecha + país + LOB (ordenado por completed_trips_without_margin DESC) ───
        cur.execute("""
            SELECT
                v.trip_date::date AS grain_date,
                COALESCE(v.country, '') AS country,
                COALESCE(v.lob_group, '') AS lob_group,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed') AS completed_trips,
                COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) AS completed_trips_without_margin
            FROM ops.v_real_trip_fact_v2 v
            WHERE v.trip_date >= %s AND v.trip_date <= %s
            GROUP BY v.trip_date::date, COALESCE(v.country, ''), COALESCE(v.lob_group, '')
            HAVING COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) > 0
            ORDER BY COUNT(*) FILTER (WHERE v.trip_outcome_norm = 'completed' AND v.margin_total IS NULL) DESC
            LIMIT 50
        """, (start_date, today))
        rows = cur.fetchall()
        summary["top_combinations"] = []
        for r in rows:
            summary["top_combinations"].append({
                "grain_date": r["grain_date"].isoformat() if hasattr(r["grain_date"], "isoformat") else str(r["grain_date"])[:10],
                "country": r["country"],
                "lob_group": r["lob_group"],
                "completed_trips": int(r["completed_trips"] or 0),
                "completed_trips_without_margin": int(r["completed_trips_without_margin"] or 0),
            })

        cur.close()

    # ─── Persistencia (FASE 3): si existe tabla y persist=True ───
    if persist and summary.get("aggregate"):
        _persist_findings(summary)

    return summary, 0 if summary.get("exit_severity") == "OK" else (2 if summary.get("exit_severity") == "CRITICAL" else 1)


def _persist_findings(summary: dict) -> None:
    """Escribe en ops.real_margin_quality_audit si la tabla existe."""
    from app.db.connection import get_db
    from app.services.real_margin_quality_constants import ALERT_CODE_PRIMARY, ALERT_CODE_SECONDARY

    agg = summary.get("aggregate")
    if not agg:
        return
    try:
        with get_db() as conn:
            cur = conn.cursor()
            # Comprobar si existe la tabla
            cur.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'ops' AND table_name = 'real_margin_quality_audit'
            """)
            if not cur.fetchone():
                cur.close()
                return
            # Insertar hallazgo principal (agregado)
            severity_primary = summary.get("severity_primary", "OK")
            # Deduplicación: borrar hallazgos del mismo alert_code y grain_date del día actual
            grain_d = summary.get("end_date")
            cur.execute(
                "DELETE FROM ops.real_margin_quality_audit WHERE alert_code = %s AND grain_date = %s AND detected_at::date = current_date",
                (ALERT_CODE_PRIMARY, grain_d),
            )
            cur.execute(
                "DELETE FROM ops.real_margin_quality_audit WHERE alert_code = %s AND grain_date = %s AND detected_at::date = current_date",
                (ALERT_CODE_SECONDARY, grain_d),
            )
            if severity_primary != "OK":
                msg = (
                    f"Se detectaron {agg['completed_trips_without_margin']} viajes completados sin comisión/margen en fuente "
                    f"en los últimos {summary.get('days_recent', 0)} días ({agg['completed_without_margin_pct']}% de completados). "
                    "Esto afecta la confiabilidad del margen en REAL."
                )
                cur.execute("""
                    INSERT INTO ops.real_margin_quality_audit
                    (alert_code, severity, detected_at, grain_date, affected_trips, denominator_trips, pct, message_humano_legible, metadata)
                    VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s)
                """, (
                    ALERT_CODE_PRIMARY,
                    severity_primary,
                    summary.get("end_date"),
                    agg["completed_trips_without_margin"],
                    agg["completed_trips"],
                    round(agg["completed_without_margin_pct"], 4),
                    msg,
                    json.dumps({"days_recent": summary.get("days_recent"), "margin_coverage_pct": agg.get("margin_coverage_pct")}),
                ))
            # Anomalía secundaria
            severity_secondary = summary.get("severity_secondary", "OK")
            if severity_secondary != "OK":
                msg_sec = (
                    f"Se detectaron {agg['cancelled_trips_with_margin']} viajes cancelados con comisión/margen en fuente "
                    f"({agg['cancelled_with_margin_pct']}% de cancelados). Anomalía de consistencia."
                )
                cur.execute("""
                    INSERT INTO ops.real_margin_quality_audit
                    (alert_code, severity, detected_at, grain_date, affected_trips, denominator_trips, pct, message_humano_legible, metadata)
                    VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s)
                """, (
                    ALERT_CODE_SECONDARY,
                    severity_secondary,
                    summary.get("end_date"),
                    agg["cancelled_trips_with_margin"],
                    agg["cancelled_trips"],
                    round(agg["cancelled_with_margin_pct"], 4),
                    msg_sec,
                    json.dumps({"days_recent": summary.get("days_recent")}),
                ))
            conn.commit()
            cur.close()
    except Exception as e:
        logger.warning("No se pudo persistir en real_margin_quality_audit: %s", e)


def main():
    ap = argparse.ArgumentParser(description="Auditoría: huecos de margen en fuente REAL (completados sin margen, cancelados con margen)")
    ap.add_argument("--days", type=int, default=90, help="Días atrás para ventana")
    ap.add_argument("--persist", action="store_true", help="Persistir hallazgos en ops.real_margin_quality_audit si existe la tabla")
    args = ap.parse_args()
    summary, code = run(days_recent=args.days, persist=args.persist)

    # Resumen legible
    print("\n" + "=" * 60)
    print("AUDITORÍA: Huecos de margen en fuente (REAL)")
    print("=" * 60)
    agg = summary.get("aggregate")
    if agg:
        print(f"  Ventana: últimos {summary['days_recent']} días")
        print(f"  Completados: {agg['completed_trips']} | Con margen: {agg['completed_trips_with_margin']} | Sin margen: {agg['completed_trips_without_margin']}")
        print(f"  completed_without_margin_pct: {agg['completed_without_margin_pct']}% | margin_coverage_pct: {agg['margin_coverage_pct']}%")
        print(f"  Cancelados: {agg['cancelled_trips']} | Con margen (anomalía): {agg['cancelled_trips_with_margin']} ({agg['cancelled_with_margin_pct']}%)")
        print(f"  Severidad principal (completados sin margen): {summary['severity_primary']}")
        print(f"  Severidad secundaria (cancelados con margen): {summary['severity_secondary']}")
    if summary.get("top_combinations"):
        print("\n  Top combinaciones (fecha + país + LOB) por completed_trips_without_margin:")
        for c in summary["top_combinations"][:10]:
            print(f"    {c['grain_date']} | {c['country']} | {c['lob_group']} | sin_margen={c['completed_trips_without_margin']}")
    print("=" * 60 + "\n")
    sys.exit(code)


if __name__ == "__main__":
    main()
