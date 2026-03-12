"""
Servicio de integridad y observabilidad del Control Tower.
Lee ops.v_control_tower_integrity_report y ops.data_integrity_audit para API y dashboard.
"""
from __future__ import annotations

from typing import Any

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor


def get_integrity_report() -> list[dict[str, Any]]:
    """Devuelve el reporte global de integridad (ops.v_control_tower_integrity_report)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT check_name, status, severity, details
                FROM ops.v_control_tower_integrity_report
                ORDER BY check_name
            """)
            rows = cur.fetchall()
            return [
                {
                    "check_name": r["check_name"],
                    "status": r["status"],
                    "severity": r["severity"],
                    "details": r["details"],
                }
                for r in rows
            ]
        except Exception:
            return []
        finally:
            cur.close()


def get_system_health() -> dict[str, Any]:
    """
    Estado del sistema para el dashboard System Health: integridad, freshness, ingestión, MVs.
    Combina v_control_tower_integrity_report, última ejecución de data_integrity_audit y resumen.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Reporte de integridad
            cur.execute("""
                SELECT check_name, status, severity, details
                FROM ops.v_control_tower_integrity_report
                ORDER BY check_name
            """)
            checks = [dict(r) for r in cur.fetchall()]

            # Última ejecución de auditoría (timestamp)
            cur.execute("""
                SELECT MAX(timestamp) AS last_audit_ts
                FROM ops.data_integrity_audit
            """)
            row = cur.fetchone()
            last_audit_ts = row["last_audit_ts"] if row and row.get("last_audit_ts") else None
            if last_audit_ts and hasattr(last_audit_ts, "isoformat"):
                last_audit_ts = last_audit_ts.isoformat()

            # Resumen por severidad
            critical = sum(1 for c in checks if (c.get("severity") or c.get("status")) == "CRITICAL")
            warning = sum(1 for c in checks if (c.get("severity") or c.get("status")) == "WARNING")
            ok = sum(1 for c in checks if (c.get("status") or "") == "OK")

            return {
                "integrity": {
                    "checks": checks,
                    "summary": {"ok": ok, "warning": warning, "critical": critical},
                    "overall": "CRITICAL" if critical else ("WARNING" if warning else "OK"),
                },
                "last_audit_ts": last_audit_ts,
                "mv_freshness": _get_mv_freshness(cur),
                "ingestion_summary": _get_ingestion_summary(cur),
            }
        except Exception:
            return {
                "integrity": {"checks": [], "summary": {"ok": 0, "warning": 0, "critical": 0}, "overall": "UNKNOWN"},
                "last_audit_ts": None,
                "mv_freshness": [],
                "ingestion_summary": [],
            }
        finally:
            cur.close()


def _get_mv_freshness(cur) -> list[dict]:
    try:
        cur.execute("SELECT view_name, last_period_start, lag_hours, status FROM ops.v_mv_freshness")
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("last_period_start") and hasattr(d["last_period_start"], "isoformat"):
                d["last_period_start"] = d["last_period_start"].isoformat()[:10]
            out.append(d)
        return out
    except Exception:
        return []


def _get_ingestion_summary(cur) -> list[dict]:
    """Últimos meses por fuente (trips_all, trips_2026) para detectar caídas."""
    try:
        cur.execute("""
            SELECT fuente, mes, viajes, viajes_b2b, drivers, parks
            FROM ops.v_ingestion_audit
            ORDER BY fuente, mes DESC
            LIMIT 24
        """)
        rows = cur.fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("mes") and hasattr(d["mes"], "isoformat"):
                d["mes"] = d["mes"].isoformat()[:10]
            out.append(d)
        return out
    except Exception:
        return []
