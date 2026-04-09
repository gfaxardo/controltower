"""
Confidence Engine — Motor central de confianza por vista/dominio.
Calcula freshness, completeness, consistency y confidence_score (0-100).
Data Trust delega aquí; no inventar ok cuando falta señal.
Completeness y consistency reales vía confidence_signals.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.config.source_of_truth_registry import (
    SOURCE_OF_TRUTH,
    get_primary_source,
    get_registry_entry,
    get_source_mode,
)

logger = logging.getLogger(__name__)

# Pesos del score (documentados). Total 100.
WEIGHT_FRESHNESS = 40
WEIGHT_COMPLETENESS = 30
WEIGHT_CONSISTENCY = 30

# Umbrales trust_status por score
THRESHOLD_OK = 80
THRESHOLD_WARNING = 50
# score >= 80 -> ok; 50 <= score < 80 -> warning; < 50 -> blocked

# Regla crítica: forzar blocked si completeness=missing o consistency=major_diff
FORCE_BLOCKED_IF_COMPLETENESS_MISSING = True
FORCE_BLOCKED_IF_CONSISTENCY_MAJOR = True

# Stale: driver lifecycle si last_completed_ts > este número de días
DRIVER_LIFECYCLE_STALE_DAYS = 7


def get_confidence_status(view_name: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Estado de confianza por vista. Usa señales reales; si falta señal -> unknown, no inventar ok.

    Retorna:
      source_of_truth, source_mode,
      freshness_status (fresh|stale|missing|unknown),
      completeness_status (full|partial|missing|unknown),
      consistency_status (validated|minor_diff|major_diff|unknown),
      confidence_score (0-100),
      trust_status (ok|warning|blocked),
      message, last_update, details.
    """
    view_name = (view_name or "").strip().lower()
    if view_name not in SOURCE_OF_TRUTH:
        return _fallback_response(
            view_name,
            "Vista no reconocida en registry",
            source_of_truth=None,
            source_mode="unknown",
        )

    try:
        entry = get_registry_entry(view_name)
        primary = get_primary_source(view_name)
        source_mode = get_source_mode(view_name)

        if view_name == "omniview_matrix":
            from app.services.omniview_matrix_integrity_service import (
                get_confidence_bundle_omniview_matrix,
            )

            return get_confidence_bundle_omniview_matrix()

        # Resumen: combina real_lob + plan_vs_real
        if view_name == "resumen":
            return _resumen_confidence()

        freshness_status, freshness_score, last_update = _signal_freshness(view_name, entry)
        completeness_status, completeness_score, completeness_detail = _signal_completeness_real(view_name, filters)
        consistency_status, consistency_score, consistency_detail = _signal_consistency_real(view_name)

        score = freshness_score + completeness_score + consistency_score
        trust_status = _score_to_trust(score)

        # Regla crítica: forzar blocked si completeness=missing o consistency=major_diff
        if FORCE_BLOCKED_IF_COMPLETENESS_MISSING and completeness_status == "missing":
            trust_status = "blocked"
        if FORCE_BLOCKED_IF_CONSISTENCY_MAJOR and consistency_status == "major_diff":
            trust_status = "blocked"

        message = _build_message(view_name, trust_status, freshness_status, consistency_status, primary)

        # Logging cuando no todo está bien (no saturar)
        if completeness_status != "full" or consistency_status not in ("validated", "minor_diff"):
            cov = completeness_detail.get("coverage_ratio")
            diff = consistency_detail.get("diff_ratio")
            try:
                cov_f = float(cov) if cov is not None else 0.0
            except (TypeError, ValueError):
                cov_f = 0.0
            try:
                diff_f = float(diff) if diff is not None else 0.0
            except (TypeError, ValueError):
                diff_f = 0.0
            logger.info(
                "[CONFIDENCE_ENGINE] view=%s completeness=%s (%.2f) consistency=%s (%.4f)",
                view_name, completeness_status, cov_f, consistency_status, diff_f,
            )

        details = {
            "freshness_score": freshness_score,
            "completeness_score": completeness_score,
            "consistency_score": consistency_score,
            "completeness": completeness_detail,
            "consistency": consistency_detail,
        }

        return {
            "source_of_truth": primary,
            "source_mode": source_mode,
            "freshness_status": freshness_status,
            "completeness_status": completeness_status,
            "consistency_status": consistency_status,
            "confidence_score": min(100, max(0, int(score))),
            "trust_status": trust_status,
            "message": message,
            "last_update": last_update,
            "details": details,
        }
    except Exception as e:
        logger.debug("confidence_engine %s: %s", view_name, e)
        return _fallback_response(
            view_name,
            "Estado de data no disponible",
            source_of_truth=get_primary_source(view_name),
            source_mode=get_source_mode(view_name),
        )


def _fallback_response(
    view_name: str,
    message: str,
    source_of_truth: Optional[str] = None,
    source_mode: str = "unknown",
) -> Dict[str, Any]:
    """Respuesta cuando falla el engine: warning, score bajo."""
    return {
        "source_of_truth": source_of_truth,
        "source_mode": source_mode,
        "freshness_status": "unknown",
        "completeness_status": "unknown",
        "consistency_status": "unknown",
        "confidence_score": 40,
        "trust_status": "warning",
        "message": message,
        "last_update": None,
        "details": {},
    }


def _score_to_trust(score: float) -> str:
    if score >= THRESHOLD_OK:
        return "ok"
    if score >= THRESHOLD_WARNING:
        return "warning"
    return "blocked"


def _build_message(
    view_name: str,
    trust_status: str,
    freshness_status: str,
    consistency_status: str,
    primary: Optional[str],
) -> str:
    if trust_status == "ok":
        return "Data validada"
    if trust_status == "blocked":
        if consistency_status == "major_diff":
            return "Paridad no validada (diferencias mayores)"
        return "Data no confiable"
    if freshness_status == "stale" or freshness_status == "missing":
        return "Data parcial (actualización pendiente)"
    if consistency_status == "unknown" and view_name == "plan_vs_real":
        return "Data parcial (paridad no validada)"
    return "Data en transición"


def _signal_freshness(view_name: str, entry: Optional[Dict[str, Any]]) -> tuple[str, float, Optional[str]]:
    """fresh|stale|missing|unknown, score 0-40, last_update."""
    # unknown por defecto; no inventar ok
    default = ("unknown", WEIGHT_FRESHNESS * 0.5, None)

    try:
        if view_name == "real_lob":
            from app.services.data_freshness_service import get_freshness_global_status
            row = get_freshness_global_status(group="operational")
            status = (row.get("status") or "").strip()
            last_checked = row.get("last_checked")
            ts = last_checked.isoformat() if hasattr(last_checked, "isoformat") else str(last_checked) if last_checked else None
            if status == "sin_datos" or not row.get("dataset_name"):
                return ("missing", 0, None)
            if status == "falta_data" or status == "atrasada":
                return ("stale", WEIGHT_FRESHNESS * 0.4, ts)
            if status in ("fresca", "parcial_esperada"):
                return ("fresh", WEIGHT_FRESHNESS, ts)
            return ("unknown", WEIGHT_FRESHNESS * 0.5, ts)

        if view_name == "plan_vs_real":
            from app.services.plan_vs_real_service import get_latest_parity_audit
            audit = get_latest_parity_audit(scope=None)
            if not audit:
                return ("unknown", WEIGHT_FRESHNESS * 0.5, None)
            run_at = audit.get("run_at")
            ts = run_at.isoformat() if hasattr(run_at, "isoformat") else str(run_at) if run_at else None
            return ("fresh", WEIGHT_FRESHNESS, ts)

        if view_name == "supply":
            from app.services.supply_service import get_supply_freshness
            fresh = get_supply_freshness()
            if not fresh:
                return ("unknown", WEIGHT_FRESHNESS * 0.5, None)
            status = fresh.get("status") if isinstance(fresh, dict) else None
            last_refresh = fresh.get("last_refresh") if isinstance(fresh, dict) else None
            ts = last_refresh.isoformat() if hasattr(last_refresh, "isoformat") else str(last_refresh) if last_refresh else None
            if status == "stale":
                return ("stale", WEIGHT_FRESHNESS * 0.4, ts)
            if status == "fresh":
                return ("fresh", WEIGHT_FRESHNESS, ts)
            return ("unknown", WEIGHT_FRESHNESS * 0.5, ts)

        if view_name == "driver_lifecycle":
            from app.db.connection import get_db
            from psycopg2.extras import RealDictCursor
            with get_db() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                try:
                    cur.execute("SELECT MAX(last_completed_ts) AS max_ts FROM ops.mv_driver_lifecycle_base")
                    row = cur.fetchone()
                    max_ts = row.get("max_ts") if row else None
                finally:
                    cur.close()
            if not max_ts:
                return ("missing", 0, None)
            now = datetime.now(timezone.utc)
            if hasattr(max_ts, "tzinfo") and max_ts.tzinfo is None and hasattr(max_ts, "replace"):
                max_ts = max_ts.replace(tzinfo=timezone.utc)
            ts = max_ts.isoformat() if hasattr(max_ts, "isoformat") else str(max_ts)
            cutoff = now - timedelta(days=DRIVER_LIFECYCLE_STALE_DAYS)
            if max_ts < cutoff:
                return ("stale", WEIGHT_FRESHNESS * 0.4, ts)
            return ("fresh", WEIGHT_FRESHNESS, ts)

        if view_name in ("real_vs_projection", "behavioral_alerts", "leakage", "real_margin_quality"):
            # Sin señal de freshness específica -> unknown, score medio
            return ("unknown", WEIGHT_FRESHNESS * 0.5, None)
    except Exception as e:
        logger.debug("_signal_freshness %s: %s", view_name, e)

    return default


def _signal_completeness_real(view_name: str, filters: Optional[Dict[str, Any]]) -> tuple[str, float, Dict[str, Any]]:
    """full|partial|missing|unknown, score 0-30, detail dict. Usa confidence_signals.get_completeness_status."""
    from app.services.confidence_signals import get_completeness_status

    detail = get_completeness_status(view_name, filters)
    status = (detail.get("status") or "unknown").strip().lower()
    ratio = detail.get("coverage_ratio")
    if status == "full":
        return ("full", WEIGHT_COMPLETENESS, detail)
    if status == "partial":
        return ("partial", WEIGHT_COMPLETENESS * 0.6, detail)
    if status == "missing":
        return ("missing", 0.0, detail)
    return ("unknown", WEIGHT_COMPLETENESS * 0.5, detail)


def _signal_consistency_real(view_name: str) -> tuple[str, float, Dict[str, Any]]:
    """validated|minor_diff|major_diff|unknown, score 0-30, detail dict. Usa confidence_signals.get_consistency_status."""
    from app.services.confidence_signals import get_consistency_status

    detail = get_consistency_status(view_name, None)
    status = (detail.get("status") or "unknown").strip().lower()
    if status == "validated":
        return ("validated", WEIGHT_CONSISTENCY, detail)
    if status == "minor_diff":
        return ("minor_diff", WEIGHT_CONSISTENCY * 0.6, detail)
    if status == "major_diff":
        return ("major_diff", 0.0, detail)
    return ("unknown", WEIGHT_CONSISTENCY * 0.5, detail)


def _resumen_confidence() -> Dict[str, Any]:
    """Resumen = combinación real_lob + plan_vs_real. Peor estado gana; score = mínimo de ambos."""
    lob = get_confidence_status("real_lob", None)
    pvr = get_confidence_status("plan_vs_real", None)
    slob = lob.get("trust_status") or "warning"
    spvr = pvr.get("trust_status") or "warning"

    if slob == "blocked" or spvr == "blocked":
        trust_status = "blocked"
        message = "Resumen: datos no confiables (Real LOB o Plan vs Real con paridad bloqueada)."
    elif slob == "warning" or spvr == "warning":
        trust_status = "warning"
        message = "Resumen: datos parciales (Real LOB o Plan vs Real en transición)."
    else:
        trust_status = "ok"
        message = "Data validada (Real LOB + Plan vs Real)"

    score_lob = lob.get("confidence_score", 50)
    score_pvr = pvr.get("confidence_score", 50)
    score = min(score_lob, score_pvr)

    # Completeness/consistency: peor de los dos
    clob = lob.get("completeness_status") or "unknown"
    cpvr = pvr.get("completeness_status") or "unknown"
    completeness_status = "missing" if "missing" in (clob, cpvr) else "partial" if "partial" in (clob, cpvr) else "full" if (clob == "full" and cpvr == "full") else "unknown"
    xlob = lob.get("consistency_status") or "unknown"
    xpvr = pvr.get("consistency_status") or "unknown"
    consistency_status = "major_diff" if "major_diff" in (xlob, xpvr) else "minor_diff" if "minor_diff" in (xlob, xpvr) else "validated" if (xlob == "validated" and xpvr == "validated") else "unknown"

    return {
        "source_of_truth": get_primary_source("resumen"),
        "source_mode": "canonical",
        "freshness_status": lob.get("freshness_status") if score_lob <= score_pvr else pvr.get("freshness_status"),
        "completeness_status": completeness_status,
        "consistency_status": consistency_status,
        "confidence_score": min(100, max(0, int(score))),
        "trust_status": trust_status,
        "message": message,
        "last_update": pvr.get("last_update") or lob.get("last_update"),
        "details": {
            "real_lob_trust": slob,
            "plan_vs_real_trust": spvr,
            "real_lob_score": score_lob,
            "plan_vs_real_score": score_pvr,
        },
    }


def get_confidence_summary() -> Dict[str, Any]:
    """Resumen de confianza de todas las vistas registradas (para GET /ops/data-confidence/summary)."""
    views = list(SOURCE_OF_TRUTH.keys())
    results = []
    for v in views:
        try:
            r = get_confidence_status(v, None)
            results.append({
                "view": v,
                "source_of_truth": r.get("source_of_truth"),
                "source_mode": r.get("source_mode"),
                "trust_status": r.get("trust_status"),
                "confidence_score": r.get("confidence_score"),
                "completeness_status": r.get("completeness_status"),
                "consistency_status": r.get("consistency_status"),
                "message": (r.get("message") or "")[:80],
            })
        except Exception as e:
            logger.debug("confidence summary %s: %s", v, e)
            results.append({
                "view": v,
                "source_of_truth": get_primary_source(v),
                "source_mode": get_source_mode(v),
                "trust_status": "warning",
                "confidence_score": 40,
                "completeness_status": "unknown",
                "consistency_status": "unknown",
                "message": "Estado no disponible",
            })
    return {"views": results}
