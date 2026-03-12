"""
Servicio de Freshness & Coverage: lectura de ops.data_freshness_audit y ops.data_freshness_expectations.
Expone la última ejecución por dataset y alertas accionables para UI/API.

Regla global "Falta data": solo mostrar "Falta data" cuando derived_max_date es NULL o <= current_date - 2.
Es decir: si la última data es ayer -> NO falta data; si es antes de ayer -> SÍ falta data.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

# Regla global: cutoff = 1 día; "no falta data" cuando derived_max_date >= today - FRESHNESS_CUTOFF_DAYS
FRESHNESS_CUTOFF_DAYS = 1
# Primario para el banner global (el que más importa para Control Tower)
PRIMARY_DATASET = "real_lob_drill"
FALLBACK_DATASETS = ("real_lob", "trips_2026")


def _serialize_date(v: Any) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    return str(v)[:10]


def _serialize_ts(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def get_freshness_audit(latest_only: bool = True) -> list[dict[str, Any]]:
    """
    Devuelve los registros de auditoría de freshness.
    Si latest_only=True (default), una fila por dataset (la más reciente por checked_at).
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if latest_only:
                cur.execute("""
                    SELECT DISTINCT ON (dataset_name)
                        dataset_name, source_object, derived_object, grain,
                        source_max_date, derived_max_date, expected_latest_date,
                        lag_days, missing_expected_days, status, alert_reason, checked_at
                    FROM ops.data_freshness_audit
                    ORDER BY dataset_name, checked_at DESC
                """)
            else:
                cur.execute("""
                    SELECT dataset_name, source_object, derived_object, grain,
                           source_max_date, derived_max_date, expected_latest_date,
                           lag_days, missing_expected_days, status, alert_reason, checked_at
                    FROM ops.data_freshness_audit
                    ORDER BY checked_at DESC, dataset_name
                    LIMIT 200
                """)
            rows = cur.fetchall()
            out = []
            for r in rows:
                out.append({
                    "dataset_name": r["dataset_name"],
                    "source_object": r["source_object"],
                    "derived_object": r["derived_object"],
                    "grain": r["grain"],
                    "source_max_date": _serialize_date(r["source_max_date"]),
                    "derived_max_date": _serialize_date(r["derived_max_date"]),
                    "expected_latest_date": _serialize_date(r["expected_latest_date"]),
                    "lag_days": r["lag_days"],
                    "missing_expected_days": r["missing_expected_days"],
                    "status": r["status"],
                    "alert_reason": r["alert_reason"],
                    "checked_at": _serialize_ts(r["checked_at"]),
                })
            return out
        except Exception as e:
            logger.warning("get_freshness_audit: %s", e)
            return []
        finally:
            cur.close()


def get_freshness_alerts() -> dict[str, Any]:
    """
    Resumen de alertas: lista de datasets con status distinto de OK y mensaje accionable.
    Incluye summary (total, por status) y lista de alertas con explicación.
    """
    audit = get_freshness_audit(latest_only=True)
    alerts = []
    for a in audit:
        status = a.get("status") or "unknown"
        if status == "OK":
            continue
        reason = a.get("alert_reason") or ""
        dataset = a.get("dataset_name") or "?"
        # Mensaje accionable
        if status in ("LAGGING", "DERIVED_STALE"):
            msg = f"La fuente {a.get('source_object')} tiene data hasta {a.get('source_max_date')}, pero {a.get('derived_object')} solo hasta {a.get('derived_max_date')}."
        elif status == "SOURCE_STALE":
            msg = f"La fuente {a.get('source_object')} está atrasada: tiene data hasta {a.get('source_max_date')}; se esperaba hasta {a.get('expected_latest_date')}."
        elif status == "MISSING_EXPECTED_DATA":
            msg = f"Se esperaba data para {a.get('expected_latest_date')} y no existe o está incompleta en el dataset '{dataset}'."
        elif status == "PARTIAL_EXPECTED":
            msg = f"El periodo actual está abierto; se considera parcial, no error. {reason}"
        else:
            msg = reason or f"Dataset {dataset}: {status}"
        alerts.append({
            "dataset_name": dataset,
            "status": status,
            "alert_reason": reason,
            "message": msg,
            "source_max_date": a.get("source_max_date"),
            "derived_max_date": a.get("derived_max_date"),
            "expected_latest_date": a.get("expected_latest_date"),
            "lag_days": a.get("lag_days"),
            "missing_expected_days": a.get("missing_expected_days"),
        })

    by_status = {}
    for a in audit:
        s = a.get("status") or "unknown"
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "summary": {
            "total_datasets": len(audit),
            "ok": by_status.get("OK", 0),
            "alerts_count": len(alerts),
            "by_status": by_status,
        },
        "alerts": alerts,
        "last_checked": audit[0]["checked_at"] if audit else None,
    }


def get_freshness_expectations() -> list[dict[str, Any]]:
    """Devuelve la config de expectativas (ops.data_freshness_expectations) para admin/documentación."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            try:
                cur.execute("""
                    SELECT dataset_name, grain, expected_delay_days, source_object, derived_object,
                           active, owner, alert_threshold_days, notes
                    FROM ops.data_freshness_expectations
                    ORDER BY dataset_name
                """)
            except Exception:
                cur.execute("""
                    SELECT dataset_name, grain, expected_delay_days, source_object, derived_object,
                           active, owner, alert_threshold_days
                    FROM ops.data_freshness_expectations
                    ORDER BY dataset_name
                """)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("get_freshness_expectations: %s", e)
            return []
        finally:
            cur.close()


def get_freshness_global_status() -> dict[str, Any]:
    """
    Estado global de frescura para el banner de UI.
    Usa la última fila de data_freshness_audit del dataset primario (real_lob_drill o fallback).
    Regla: Falta data solo si derived_max_date es None o <= today - 2.
    """
    today = date.today()
    yesterday = today - timedelta(days=FRESHNESS_CUTOFF_DAYS)
    cutoff_missing = today - timedelta(days=2)  # derived_max_date <= este día -> falta data

    audit = get_freshness_audit(latest_only=True)
    # Preferir primary dataset, luego fallbacks
    row = None
    for name in (PRIMARY_DATASET,) + FALLBACK_DATASETS:
        for a in audit:
            if a.get("dataset_name") == name:
                row = a
                break
        if row is not None:
            break
    if not row:
        row = audit[0] if audit else None

    if not row:
        return {
            "status": "sin_datos",
            "label": "Sin datos",
            "message": "No hay auditoría de frescura. Ejecute POST /ops/data-freshness/run o scripts.run_data_freshness_audit.",
            "derived_max_date": None,
            "source_max_date": None,
            "expected_latest_date": None,
            "dataset_name": None,
        }

    derived = row.get("derived_max_date")
    if isinstance(derived, str):
        try:
            derived = date(int(derived[:4]), int(derived[5:7]), int(derived[8:10]))
        except (ValueError, TypeError):
            derived = None
    source = row.get("source_max_date")
    expected = row.get("expected_latest_date")
    audit_status = (row.get("status") or "").strip()

    # Aplicar regla global: falta_data solo si derived_max_date <= today - 2
    if derived is None:
        status = "falta_data"
        label = "Falta data"
        message = "No hay fecha de datos en el derivado. Ejecute refresh/backfill del dataset."
    elif derived <= cutoff_missing:
        status = "falta_data"
        label = "Falta data"
        message = f"Última data en vista: {derived.isoformat()}. Se esperaba al menos hasta ayer ({yesterday.isoformat()})."
    elif derived >= yesterday:
        if audit_status == "PARTIAL_EXPECTED":
            status = "parcial_esperada"
            label = "Parcial esperada"
            message = f"Última data en vista: {derived.isoformat()}. Periodo actual abierto; datos al día."
        else:
            status = "fresca"
            label = "Fresca"
            message = f"Última data en vista: {derived.isoformat()}."
    else:
        status = "atrasada"
        label = "Atrasada"
        message = f"Última data en vista: {derived.isoformat()}. Un día de retraso respecto a lo esperado."

    return {
        "status": status,
        "label": label,
        "message": message,
        "derived_max_date": row.get("derived_max_date"),
        "source_max_date": row.get("source_max_date"),
        "expected_latest_date": row.get("expected_latest_date"),
        "dataset_name": row.get("dataset_name"),
        "lag_days": row.get("lag_days"),
        "last_checked": row.get("checked_at"),
    }
