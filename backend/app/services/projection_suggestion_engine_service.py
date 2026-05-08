"""
FASE 4.1 — Motor de sugerencias operativas para Omniview vs Proyección.

Solo propone acciones; no ejecuta nada, no envía mensajes ni crea campañas/tareas.
Catálogo en código (sin BD). Aditivo.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_NS_SUGGESTIONS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

ACTION_CATALOG: Dict[str, Dict[str, Any]] = {
    "productivity_reactivation": {
        "name": "Reactivar conductores de baja actividad",
        "driver": "productivity",
        "channel_suggested": "WhatsApp / llamadas",
        "owner_suggested": "SAC / Retención",
        "cost": "low",
        "speed": "fast",
        "expected_impact": "medium_high",
        "description": (
            "Contactar conductores con baja actividad reciente para recuperar productividad."
        ),
    },
    "productivity_incentive": {
        "name": "Incentivo corto por viajes",
        "driver": "productivity",
        "channel_suggested": "WhatsApp / campaña",
        "owner_suggested": "Operaciones / Marketing",
        "cost": "medium",
        "speed": "fast",
        "expected_impact": "high",
        "description": "Lanzar incentivo temporal para recuperar viajes por conductor.",
    },
    "volume_scouts_push": {
        "name": "Refuerzo de scouts / captación",
        "driver": "volume",
        "channel_suggested": "scouts / campo / pauta",
        "owner_suggested": "Supply",
        "cost": "medium",
        "speed": "medium",
        "expected_impact": "medium",
        "description": "Aumentar captación donde falta volumen de conductores o viajes.",
    },
    "volume_onboarding_followup": {
        "name": "Seguimiento a registrados sin primer viaje",
        "driver": "volume",
        "channel_suggested": "llamadas / WhatsApp",
        "owner_suggested": "Onboarding",
        "cost": "low",
        "speed": "fast",
        "expected_impact": "medium",
        "description": "Contactar registros recientes que aún no hicieron primer viaje.",
    },
    "ticket_mix_review": {
        "name": "Revisar mix / ticket promedio",
        "driver": "ticket",
        "channel_suggested": "análisis operativo",
        "owner_suggested": "Revenue / Operaciones",
        "cost": "low",
        "speed": "medium",
        "expected_impact": "medium",
        "description": (
            "Revisar si la caída viene por menor ticket, tipo de viaje o composición de LOB."
        ),
    },
    "data_review": {
        "name": "Revisar calidad de data",
        "driver": "unknown",
        "channel_suggested": "auditoría",
        "owner_suggested": "Data / Operaciones",
        "cost": "low",
        "speed": "fast",
        "expected_impact": "preventive",
        "description": "Revisar integridad si la causa no es clara.",
    },
    "opportunity_replicate_winner": {
        "name": "Replicar práctica ganadora",
        "driver": "opportunity",
        "channel_suggested": "análisis operativo",
        "owner_suggested": "Operaciones",
        "cost": "low",
        "speed": "medium",
        "expected_impact": "medium",
        "description": "Revisar qué está funcionando en este slice para replicarlo en otros.",
    },
}

# Umbral "gap grande" para refuerzo de captación (volumen)
_LARGE_GAP_PCT = 10.0
_LARGE_GAP_TRIPS = 2500.0


def _entity_type_from_alert(alert: Dict[str, Any]) -> str:
    dim = str(alert.get("dimension") or "").strip().lower()
    if dim == "country":
        return "country"
    if dim == "city":
        return "city"
    if dim == "lob":
        return "city_lob"
    return dim or "unknown"


def _driver_raw(alert: Dict[str, Any]) -> Optional[str]:
    d = alert.get("principal_driver")
    if d is None:
        return None
    s = str(d).strip().lower()
    return s if s else None


def _is_unknown_driver(driver: Optional[str]) -> bool:
    return driver is None or driver in ("unknown", "none", "")


def _confidence(
    *,
    integrity_status: Dict[str, Any],
    alert: Dict[str, Any],
    level: str,
) -> str:
    st = str(integrity_status.get("status") or "")
    drv = _driver_raw(alert)
    gap_pct = alert.get("gap_pct")

    if level == "opportunity":
        if st == "warning":
            return "medium"
        return "high" if gap_pct is not None else "medium"

    if _is_unknown_driver(drv):
        return "low"
    if st == "warning":
        return "medium"
    if gap_pct is None:
        return "medium"
    if st == "ok" and drv in ("volume", "productivity", "ticket"):
        return "high"
    return "medium"


def _score_gap_pct_points(alert: Dict[str, Any]) -> float:
    try:
        gp = abs(float(alert.get("gap_pct")))
    except (TypeError, ValueError):
        return 0.0
    return min(25.0, gp * 0.25)


def _score_gap_trips_points(alert: Dict[str, Any]) -> float:
    try:
        gt = abs(float(alert.get("gap_trips")))
    except (TypeError, ValueError):
        return 0.0
    return min(25.0, gt / 400.0)


def _level_base_points(level: str) -> int:
    if level == "critical":
        return 40
    if level == "warning":
        return 25
    if level == "opportunity":
        return 15
    return 0


def _confidence_bonus(confidence: str) -> int:
    if confidence == "high":
        return 10
    if confidence == "medium":
        return 5
    return 0


def _priority_score(level: str, alert: Dict[str, Any], confidence: str) -> int:
    raw = (
        float(_level_base_points(level))
        + _score_gap_pct_points(alert)
        + _score_gap_trips_points(alert)
        + float(_confidence_bonus(confidence))
    )
    return int(max(0, min(100, round(raw))))


def _large_volume_gap(alert: Dict[str, Any]) -> bool:
    try:
        gp = abs(float(alert.get("gap_pct") or 0.0))
    except (TypeError, ValueError):
        gp = 0.0
    try:
        gt = abs(float(alert.get("gap_trips") or 0.0))
    except (TypeError, ValueError):
        gt = 0.0
    return gp >= _LARGE_GAP_PCT or gt >= _LARGE_GAP_TRIPS


def _stable_suggestion_id(action_id: str, alert: Dict[str, Any], suffix: str = "") -> str:
    ent = str(alert.get("entity") or "")
    lv = str(alert.get("level") or "")
    dim = str(alert.get("dimension") or "")
    base = f"{action_id}|{ent}|{lv}|{dim}|{suffix}"
    return str(uuid.uuid5(_NS_SUGGESTIONS, base))


def _pacing_es(pacing: Any) -> str:
    m = {
        "behind": "atrasado respecto al plan",
        "ahead": "adelantado respecto al plan",
        "on_track": "en ritmo con el plan",
    }
    if pacing is None:
        return "sin pacing claro"
    return m.get(str(pacing), str(pacing).replace("_", " "))


def _trend_es(trend: Any) -> str:
    m = {
        "deteriorating": "deterioro",
        "improving": "mejora",
        "flat": "estable",
    }
    if trend is None:
        return "tendencia no clara"
    return m.get(str(trend), str(trend))


def _driver_es(driver_code: str) -> str:
    m = {
        "productivity": "productividad",
        "volume": "volumen",
        "ticket": "ticket / mix",
        "opportunity": "oportunidad de réplica",
        "unknown": "causa poco clara (revisar data)",
    }
    return m.get(driver_code, driver_code)


def _why_text(alert: Dict[str, Any], principal_out: str) -> str:
    pacing = _pacing_es(alert.get("pacing_vs_expected"))
    trend = _trend_es(alert.get("ytd_trend"))
    drv = _driver_es(principal_out)
    if str(alert.get("level")) == "opportunity":
        return (
            f"El slice está {pacing} con tendencia de {trend}; hay una práctica ganadora "
            f"({drv}) que puede replicarse."
        )
    return (
        f"El slice está {pacing} y con tendencia de {trend}; "
        f"el gap principal parece venir de {drv}."
    )


def _pick_actions_for_alert(alert: Dict[str, Any]) -> List[str]:
    level = str(alert.get("level") or "")
    if level == "opportunity":
        return ["opportunity_replicate_winner"]

    drv = _driver_raw(alert)
    if _is_unknown_driver(drv):
        return ["data_review"]

    if drv == "productivity":
        out = ["productivity_reactivation"]
        if level == "critical":
            out.append("productivity_incentive")
        return out

    if drv == "volume":
        out = ["volume_onboarding_followup"]
        if _large_volume_gap(alert):
            out.append("volume_scouts_push")
        return out

    if drv == "ticket":
        return ["ticket_mix_review"]

    return ["data_review"]


def _next_step_label(action_id: str) -> str:
    if action_id == "productivity_reactivation":
        return "Ver conductores de baja actividad"
    if action_id == "productivity_incentive":
        return "Diseñar incentivo y alcance"
    if action_id in ("volume_scouts_push", "volume_onboarding_followup"):
        return "Ver funnel de captación / primer viaje"
    if action_id == "ticket_mix_review":
        return "Ver desglose ticket / LOB"
    if action_id == "data_review":
        return "Auditar integridad y fuentes"
    if action_id == "opportunity_replicate_winner":
        return "Documentar práctica ganadora"
    return "Revisar datos del slice"


def _principal_driver_out(alert: Dict[str, Any], level: str) -> str:
    if level == "opportunity":
        return "opportunity"
    d = _driver_raw(alert)
    if _is_unknown_driver(d):
        return "unknown"
    return d or "unknown"


def _sort_suggestions(items: List[Dict[str, Any]]) -> None:
    def _rk(level: str) -> int:
        if level == "critical":
            return 0
        if level == "warning":
            return 1
        if level == "opportunity":
            return 2
        return 3

    items.sort(
        key=lambda s: (
            _rk(str(s.get("level") or "")),
            -float(s.get("priority_score") or 0),
        ),
    )


def build_projection_suggestions(
    *,
    integrity_status: Dict[str, Any],
    ytd_alerts: Any,
    display_rows: Optional[List[Dict[str, Any]]] = None,
    grain: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Genera meta.suggestions y meta.suggestions_status.
    """
    _ = display_rows  # reservado para enriquecimiento futuro con ytd_slice
    _ = grain
    _ = filters

    st = str(integrity_status.get("status") or "")

    if st == "broken":
        return [], {"status": "disabled", "reason": "integrity_broken"}

    if not isinstance(ytd_alerts, list) or len(ytd_alerts) == 0:
        return [], {"status": "empty", "reason": "no_ytd_alerts"}

    suggestions: List[Dict[str, Any]] = []

    for alert in ytd_alerts:
        if not isinstance(alert, dict):
            continue
        level = str(alert.get("level") or "")
        if level not in ("critical", "warning", "opportunity"):
            continue

        actions = _pick_actions_for_alert(alert)
        principal_out = _principal_driver_out(alert, level)

        for i, action_id in enumerate(actions):
            cat = ACTION_CATALOG.get(action_id)
            if not cat:
                logger.warning("build_projection_suggestions: acción desconocida %s", action_id)
                continue

            conf = _confidence(integrity_status=integrity_status, alert=alert, level=level)
            prio = _priority_score(level, alert, conf)
            suffix = str(i) if len(actions) > 1 else ""

            sug: Dict[str, Any] = {
                "suggestion_id": _stable_suggestion_id(action_id, alert, suffix),
                "entity": str(alert.get("entity") or "—"),
                "entity_type": _entity_type_from_alert(alert),
                "level": level,
                "principal_driver": principal_out,
                "recommended_action_id": action_id,
                "recommended_action_name": cat["name"],
                "why": _why_text(alert, principal_out),
                "expected_impact": cat["expected_impact"],
                "speed": cat["speed"],
                "cost": cat["cost"],
                "owner_suggested": cat["owner_suggested"],
                "channel_suggested": cat["channel_suggested"],
                "confidence": conf,
                "source_alert": dict(alert),
                "next_step_label": _next_step_label(action_id),
                "execution_enabled": False,
                "priority_score": prio,
            }
            suggestions.append(sug)

    _sort_suggestions(suggestions)

    status_payload: Dict[str, Any] = {
        "status": "partial" if st == "warning" else "ok",
        "reason": "integrity_warning" if st == "warning" else None,
    }
    if not suggestions:
        return [], {"status": "empty", "reason": "no_suggestions"}

    return suggestions, status_payload


def safe_build_projection_suggestions(
    *,
    integrity_status: Dict[str, Any],
    ytd_alerts: Any,
    display_rows: Optional[List[Dict[str, Any]]] = None,
    grain: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    try:
        return build_projection_suggestions(
            integrity_status=integrity_status,
            ytd_alerts=ytd_alerts,
            display_rows=display_rows,
            grain=grain,
            filters=filters,
        )
    except Exception as exc:
        logger.warning("safe_build_projection_suggestions: %s", exc, exc_info=True)
        ist = str(integrity_status.get("status") or "")
        if ist == "broken":
            return [], {"status": "disabled", "reason": "integrity_broken"}
        return [], {"status": "empty", "reason": "suggestion_engine_error"}
