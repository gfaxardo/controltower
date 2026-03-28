"""
Decision Engine — Convierte Data Trust + Confidence Engine en decisiones operativas.
Fuente única de verdad: Confidence Engine. No duplica lógica; interpretable y reversible.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config.source_of_truth_registry import REGISTERED_VIEWS, SOURCE_OF_TRUTH
from app.config.view_criticality import get_view_criticality

logger = logging.getLogger(__name__)

# --- Reglas de gobierno (Fase 8) ---
# 1. Ninguna vista crítica puede estar en OK si confidence < 80
MIN_CONFIDENCE_FOR_CRITICAL_OK = 80
# 2. Si decision = STOP_DECISIONS → no mostrarse como OK en UI (reason explícito)
# 3. Decisiones explicables (reason)
# 4. No lógica oculta fuera de este engine


def get_decision_signal(view_name: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Señal de decisión operativa por vista.
    Usa Confidence Engine como fuente única; aplica criticality y reglas de gobierno.

    Retorna:
      view, trust_status, confidence_score, criticality, action, priority,
      message, reason, last_update, details.
    """
    view_name = (view_name or "").strip().lower()
    if view_name not in SOURCE_OF_TRUTH:
        return _decision_fallback(
            view_name,
            action="MONITOR",
            priority="P3",
            reason="view_not_registered",
            message="Vista no registrada",
        )

    from app.services.confidence_engine import get_confidence_status

    conf = get_confidence_status(view_name, filters)
    trust_status = conf.get("trust_status") or "warning"
    confidence_score = int(conf.get("confidence_score") or 0)
    completeness_status = (conf.get("completeness_status") or "unknown").strip().lower()
    consistency_status = (conf.get("consistency_status") or "unknown").strip().lower()
    criticality = get_view_criticality(view_name)
    last_update = conf.get("last_update")
    details = dict(conf.get("details") or {})

    # --- Forzados (reglas adicionales) ---
    if completeness_status == "missing" and criticality == "critical":
        action, priority, reason = "STOP_DECISIONS", "P0", "completeness_missing"
        message = _build_decision_message(
            view_name, action, conf, completeness_status, consistency_status, details
        )
        _log_decision(view_name, action, priority, reason)
        return _decision_response(
            view_name, trust_status, confidence_score, criticality,
            action, priority, message, reason, last_update, details,
        )
    if consistency_status == "major_diff":
        action, priority, reason = "STOP_DECISIONS", "P0", "consistency_major_diff"
        message = _build_decision_message(
            view_name, action, conf, completeness_status, consistency_status, details
        )
        _log_decision(view_name, action, priority, reason)
        return _decision_response(
            view_name, trust_status, confidence_score, criticality,
            action, priority, message, reason, last_update, details,
        )
    if confidence_score < 40:
        action, priority, reason = "STOP_DECISIONS", "P0", "confidence_below_40"
        message = _build_decision_message(
            view_name, action, conf, completeness_status, consistency_status, details
        )
        _log_decision(view_name, action, priority, reason)
        return _decision_response(
            view_name, trust_status, confidence_score, criticality,
            action, priority, message, reason, last_update, details,
        )

    # --- Regla: vista crítica no puede estar OK si confidence < 80 ---
    if criticality == "critical" and confidence_score < MIN_CONFIDENCE_FOR_CRITICAL_OK:
        if trust_status == "ok":
            trust_status = "warning"
        # Luego aplicar matriz normal

    # --- Matriz trust_status × criticality ---
    if trust_status == "blocked":
        if criticality == "critical":
            action, priority, reason = "STOP_DECISIONS", "P0", "blocked_critical"
        elif criticality == "high":
            action, priority, reason = "LIMIT_DECISIONS", "P1", "blocked_high"
        elif criticality == "medium":
            action, priority, reason = "MONITOR", "P2", "blocked_medium"
        else:
            action, priority, reason = "MONITOR", "P2", "blocked_low"
    elif trust_status == "warning":
        if criticality == "critical":
            action, priority, reason = "USE_WITH_CAUTION", "P1", "warning_critical"
        elif criticality == "high":
            action, priority, reason = "MONITOR_CLOSELY", "P2", "warning_high"
        else:
            action, priority, reason = "MONITOR", "P2", "warning_medium_low"
    else:
        action, priority, reason = "OPERATE_NORMAL", "P3", "ok"

    message = _build_decision_message(
        view_name, action, conf, completeness_status, consistency_status, details
    )
    _log_decision(view_name, action, priority, reason)
    return _decision_response(
        view_name, trust_status, confidence_score, criticality,
        action, priority, message, reason, last_update, details,
    )


def _decision_response(
    view_name: str,
    trust_status: str,
    confidence_score: int,
    criticality: str,
    action: str,
    priority: str,
    message: str,
    reason: str,
    last_update: Any,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "view": view_name,
        "trust_status": trust_status,
        "confidence_score": confidence_score,
        "criticality": criticality,
        "action": action,
        "priority": priority,
        "message": message,
        "reason": reason,
        "last_update": last_update,
        "details": details,
    }


def _decision_fallback(
    view_name: str,
    action: str,
    priority: str,
    reason: str,
    message: str,
) -> Dict[str, Any]:
    return {
        "view": view_name or "unknown",
        "trust_status": "warning",
        "confidence_score": 40,
        "criticality": "low",
        "action": action,
        "priority": priority,
        "message": message,
        "reason": reason,
        "last_update": None,
        "details": {},
    }


def _build_decision_message(
    view_name: str,
    action: str,
    conf: Dict[str, Any],
    completeness_status: str,
    consistency_status: str,
    details: Dict[str, Any],
) -> str:
    """Mensaje corto, accionable, entendible por negocio. No técnico innecesario."""
    if action == "OPERATE_NORMAL":
        return "Puedes operar con normalidad"
    if action == "STOP_DECISIONS":
        if completeness_status == "missing":
            cov = details.get("completeness", {}).get("coverage_ratio")
            if cov is not None:
                try:
                    pct = int(round(float(cov) * 100))
                    return f"Data incompleta ({pct}% cobertura últimos 7 días)"
                except (TypeError, ValueError):
                    pass
            return "Data incompleta; no tomar decisiones"
        if consistency_status == "major_diff":
            diff = details.get("consistency", {}).get("diff_ratio")
            if diff is not None:
                try:
                    pct = round(float(diff) * 100, 1)
                    return f"Diferencia detectada entre fuentes ({pct}%)"
                except (TypeError, ValueError):
                    pass
            return "Paridad plan vs real con diferencias mayores"
        return "Detente: data no confiable"
    if action == "LIMIT_DECISIONS":
        return "Limitar decisiones basadas en esta vista"
    if action == "USE_WITH_CAUTION":
        return "Usar con cuidado; verificar antes de decidir"
    if action == "MONITOR_CLOSELY":
        return "Monitorear de cerca antes de operar"
    if action == "MONITOR":
        return "Monitorear; impacto limitado"
    return conf.get("message") or "Revisar estado de la data"


def _log_decision(view_name: str, action: str, priority: str, reason: str) -> None:
    """Log solo casos relevantes (STOP/LIMIT/CAUTION); evitar ruido."""
    if action in ("STOP_DECISIONS", "LIMIT_DECISIONS", "USE_WITH_CAUTION"):
        logger.info(
            "[DECISION_ENGINE] view=%s action=%s priority=%s reason=%s",
            view_name, action, priority, reason,
        )


def get_decision_signal_summary() -> List[Dict[str, Any]]:
    """
    Resumen de señales de decisión para todas las vistas registradas.
    Para GET /ops/decision-signal/summary.
    """
    result = []
    for view in REGISTERED_VIEWS:
        try:
            sig = get_decision_signal(view, None)
            result.append({
                "view": sig.get("view"),
                "action": sig.get("action"),
                "priority": sig.get("priority"),
            })
        except Exception as e:
            logger.debug("decision_signal_summary %s: %s", view, e)
            result.append({"view": view, "action": "MONITOR", "priority": "P3"})
    return result
