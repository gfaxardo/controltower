"""
FASE 4.3 — Decision Policy Engine (solo priorización informada).

No ejecuta acciones ni llama APIs externas. Heurística explícita (sin ML).

Suggestion Engine propone contextual_suggestions → este motor prioriza QUÉ hacer primero por entidad.
"""
from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from app.services.projection_suggestion_engine_service import ACTION_CATALOG

logger = logging.getLogger(__name__)

_NS_DECISION = uuid.UUID("a73d4fc2-98b6-41d3-9336-61d4c3b92f01")

POLICY_VERSION = "v1"
POLICY_TYPE = "heuristic_weighted_policy"

_W_IMPACT = 0.34
_W_SPEED = 0.18
_W_COMPLEXITY_INV = 0.16  # menor complejidad operativa ⇒ mayor contribución
_W_CONFIDENCE = 0.23
_W_COST = 0.09

_LARGE_GAP_PCT = 10.0
_LARGE_GAP_TRIPS = 2500.0

_SPEED_NUM = {"fast": 92.0, "medium": 68.0, "slow": 45.0}
_COST_NUM = {"low": 90.0, "medium": 65.0, "high": 40.0}
_CONF_NUM = {"high": 94.0, "medium": 62.0, "low": 28.0}

_COMPLEXITY_FROM_ACTION = {
    "productivity_reactivation": 22.0,
    "productivity_incentive": 30.0,
    "volume_onboarding_followup": 18.0,
    "volume_scouts_push": 38.0,
    "ticket_mix_review": 45.0,
    "data_review": 40.0,
    "opportunity_replicate_winner": 42.0,
}


def merge_integrity_with_decision_policy_check(
    integrity_status: Dict[str, Any],
    decision_check: str,
) -> Dict[str, Any]:
    ch = dict(integrity_status.get("checks") or {})
    ch["decision_policy_engine"] = decision_check
    return {**integrity_status, "checks": ch}


def _norm_conf(c: Optional[str]) -> str:
    s = str(c or "medium").strip().lower()
    return s if s in ("high", "medium", "low") else "medium"


def _stable_recommendation_id(entity: str) -> str:
    return str(uuid.uuid5(_NS_DECISION, f"projection_decision|{entity}|{POLICY_VERSION}"))


def _alert_for_entity(entity: str, ytd_alerts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    en = str(entity or "").strip()
    best: Optional[Dict[str, Any]] = None
    for a in ytd_alerts:
        if not isinstance(a, dict):
            continue
        if str(a.get("entity") or "").strip() == en:
            return a
        if best is None and en and str(a.get("entity") or "") in en:
            best = a
    return best


def _severe_volume_context(alert: Optional[Dict[str, Any]]) -> bool:
    if not alert:
        return False
    try:
        gp = abs(float(alert.get("gap_pct") or 0.0))
    except (TypeError, ValueError):
        gp = 0.0
    try:
        gt = abs(float(alert.get("gap_trips") or 0.0))
    except (TypeError, ValueError):
        gt = 0.0
    return gp >= _LARGE_GAP_PCT or gt >= _LARGE_GAP_TRIPS


def _sf(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _priority_boost(ctx: Dict[str, Any]) -> float:
    """Señal explícita del suggestion engine (0–100), peso modesto sobre el blend de impacto."""
    p = _sf(ctx.get("priority_score"))
    if p is None:
        return 50.0
    return float(max(0.0, min(100.0, p)))


def _impact_blend(ctx: Dict[str, Any]) -> float:
    lev = float(ctx.get("operational_leverage_score") or 0.0)
    rec = ctx.get("estimated_recovery") or {}
    gap_pct = _sf(rec.get("potential_gap_recovery_pct"))
    pool = ctx.get("operational_pool") or {}
    tc = float(pool.get("total_candidates") or 0)
    pool_part = min(95.0, 18.0 + (tc**0.5) * 3.8)
    gap_part = min(92.0, 45.0 + abs(gap_pct or 0) * 4.6) if gap_pct is not None else 48.0
    pri = _priority_boost(ctx)
    # priority_score entra como refuerzo acotado (auditable en factors via impacto compuesto)
    raw = lev * 0.46 + gap_part * 0.29 + pool_part * 0.19 + pri * 0.06
    return float(max(0.0, min(100.0, raw)))


def _confidence_integrity_modifier(integrity_status: Dict[str, Any]) -> float:
    """Multiplicador sobre componente confianza (warning penaliza parcialmente)."""
    if str(integrity_status.get("status") or "") == "warning":
        return 0.88
    return 1.0


def _cost_efficiency_score(cat: Dict[str, Any], impact_approx: float) -> float:
    cost = str(cat.get("cost") or "medium")
    cn = _COST_NUM.get(cost, 62.0)
    # Heurística: mejor si cost bajo impacto medio-alto declarado por catálogo
    ei = str(cat.get("expected_impact") or "medium")
    boost = {"high": 8.0, "medium_high": 6.0, "medium": 0.0, "preventive": -12.0, "low": -10.0}.get(
        ei,
        0.0,
    )
    blended = cn * 0.65 + min(impact_approx, 100.0) * 0.35 + boost
    return float(max(0.0, min(100.0, blended)))


def _action_adjustments(
    action_type: str,
    *,
    principal_driver: Optional[str],
    severe_vol: bool,
    onboarding_followup_exist: bool,
    onboarding_pending: Optional[int],
) -> Tuple[float, List[str]]:
    """
    Bonus/penalty explícitos (no ML): retorna (delta_puntos sobre score bruto antes de clamp, razones texto).
    """
    pd = (principal_driver or "").strip().lower() or None
    delta = 0.0
    reasons: List[str] = []
    if action_type == "volume_scouts_push":
        if severe_vol:
            delta += 16.0
            reasons.append("Bonificación scouts: volumen severo declarado por alerta.")
        elif pd == "volume":
            delta += 6.0
            reasons.append("Refuerzo leve scouts: driver principal volumen.")
        if pd == "productivity":
            delta -= 28.0
            reasons.append("Penalización scouts: causa principal clasificada como productividad.")
        if onboarding_followup_exist and not severe_vol:
            delta -= 12.0
            reasons.append("Penalización scouts: existe seguimiento onboarding como alternativa más rápida.")
        if (
            severe_vol
            and onboarding_pending is not None
            and onboarding_pending < 40
            and onboarding_followup_exist
        ):
            delta += 14.0
            reasons.append("Bonificación scouts: funnel onboarding pequeño ante brecha de volumen grande.")
    elif action_type == "volume_onboarding_followup":
        if pd == "volume":
            delta += 8.0
            reasons.append("Bonus onboarding seguimiento: driver volumen.")
    elif action_type in ("productivity_reactivation", "productivity_incentive"):
        delta += 6.0
        reasons.append("Bonus productividad: típicamente más rápido de activar vs captación de campo.")
        if pd == "productivity":
            delta += 10.0
            reasons.append("Alineación con driver causal productividad de la alerta.")
    elif action_type == "ticket_mix_review":
        delta -= 8.0
        reasons.append("Penalización leve revisión ticket: menor velocidad efectiva esperada.")
    return delta, reasons


def _compute_decision_score_and_factors(
    ctx: Dict[str, Any],
    *,
    integrity_status: Dict[str, Any],
    alert: Optional[Dict[str, Any]],
    onboarding_followup_exist: bool,
    severe_vol: bool,
    onboarding_pending: Optional[int],
) -> Tuple[float, Dict[str, float], Dict[str, float]]:
    cat = ACTION_CATALOG.get(str(ctx.get("action_type") or ""), {})
    pd = (
        None
        if not alert
        else str(alert.get("principal_driver") or "").strip().lower()
    )
    if pd in ("unknown", "", "none"):
        pd = None

    adj, _ = _action_adjustments(
        str(ctx.get("action_type") or ""),
        principal_driver=pd,
        severe_vol=severe_vol,
        onboarding_followup_exist=onboarding_followup_exist,
        onboarding_pending=onboarding_pending,
    )

    impact_approx = _impact_blend(ctx)

    spd = float(_SPEED_NUM.get(str(cat.get("speed") or "medium"), 68.0))
    cmp_pen = float(_COMPLEXITY_FROM_ACTION.get(str(ctx.get("action_type") or ""), 35.0))
    cmp_score = float(max(0.0, 100.0 - cmp_pen))
    cn = float(_CONF_NUM.get(_norm_conf(ctx.get("confidence")), 55.0) * _confidence_integrity_modifier(integrity_status))
    eff = float(_cost_efficiency_score(cat if cat else {}, impact_approx))

    base = (
        impact_approx * _W_IMPACT
        + spd * _W_SPEED
        + cmp_score * _W_COMPLEXITY_INV
        + cn * _W_CONFIDENCE
        + eff * _W_COST
    )

    boosted = float(max(5.0, min(100.0, base + adj)))

    # Regla QA: confidence bajo → ningún puntaje alto “creditable” como fuerte recomendación
    if _norm_conf(ctx.get("confidence")) == "low":
        boosted = min(boosted, 52.0)

    breakdown = {"pre_adjust_score": round(base, 2), "policy_adjustment_delta": round(adj, 2)}
    factors = {
        "impact_score": round(impact_approx, 2),
        "speed_score": round(spd, 2),
        "operational_complexity_score": round(cmp_score, 2),
        "confidence_score": round(cn, 2),
        "cost_efficiency_score": round(eff, 2),
    }
    return round(boosted, 2), factors, breakdown


def _why_selected_text(
    winner: Dict[str, Any],
    runner: Optional[Dict[str, Any]],
    *,
    adjustment_reasons: List[str],
    alert: Optional[Dict[str, Any]],
) -> str:
    wf = winner.get("decision_factors") or {}
    w_at = str(winner.get("action_type") or "")
    w_name = str(winner.get("_action_name") or w_at)
    cat_w = ACTION_CATALOG.get(w_at, {})
    parts: List[str] = []

    spd_lbl = str(cat_w.get("speed") or "medium")
    cost_lbl = str(cat_w.get("cost") or "medium")
    parts.append(
        f"Se priorizó «{w_name}» porque el impacto operativo ponderado es alto ({wf.get('impact_score')}), "
        f"la velocidad esperada del catálogo es {spd_lbl} (factor {wf.get('speed_score')}), "
        f"el costo operativo referido es {cost_lbl} y la confianza calibrada queda en {wf.get('confidence_score')}."
    )

    if runner:
        rn = str(runner.get("_action_name") or runner.get("action_type"))
        r_at = str(runner.get("action_type") or "")
        cat_r = ACTION_CATALOG.get(r_at, {})
        rl = runner.get("decision_score")
        rf = runner.get("decision_factors") or {}
        if r_at == "volume_scouts_push" and w_at == "productivity_reactivation":
            parts.append(
                f" «{rn}» queda en segundo plano (score ~{rl}): captación de campo suele tener maduración más lenta "
                f"(velocidad {cat_r.get('speed', 'medium')}) frente a la reactivación directa de conductores existentes."
            )
        elif w_at == "volume_scouts_push" and r_at == "productivity_reactivation":
            parts.append(
                f" «{rn}» supera a reactivación aquí porque la brecha de volumen es severa y el apalancamiento de scouts "
                f"compensa la mayor complejidad (impacto competidor {rf.get('impact_score')})."
            )
        else:
            parts.append(
                f" Frente a «{rn}» (score ~{rl}), esta opción gana en el mix velocidad / complejidad / confianza "
                f"(impacto alternativa {rf.get('impact_score')})."
            )

    if adjustment_reasons:
        parts.append(" Ajustes explícitos v1: " + "; ".join(adjustment_reasons[:3]) + ".")
    if alert and str(alert.get("principal_driver") or "").lower() in ("volume", "productivity", "ticket"):
        parts.append(
            f" La alerta etiqueta causa `{alert.get('principal_driver')}` como orientación; "
            "no dispara ejecución automática."
        )
    return "".join(parts)[:890]


def _why_not_other(
    winner: Dict[str, Any],
    others_sorted: List[Dict[str, Any]],
) -> List[str]:
    wf = winner.get("decision_factors") or {}
    w_at = str(winner.get("action_type"))
    w_spd = float(wf.get("speed_score") or 0.0)
    w_cmp = float(wf.get("operational_complexity_score") or 0.0)
    w_imp = float(wf.get("impact_score") or 0.0)
    w_cf = float(wf.get("confidence_score") or 0.0)
    out: List[str] = []
    for o in others_sorted[:5]:
        at = str(o.get("action_type"))
        nm = str(o.get("_action_name"))
        ds = float(o.get("decision_score") or 0.0)
        if at == w_at:
            continue
        of = o.get("decision_factors") or {}
        o_spd = float(of.get("speed_score") or 0.0)
        o_cmp = float(of.get("operational_complexity_score") or 0.0)
        o_imp = float(of.get("impact_score") or 0.0)
        o_cf = float(of.get("confidence_score") or 0.0)
        reasons: List[str] = []
        if ds < float(winner.get("decision_score") or 0.0) - 0.5:
            reasons.append(f"score compuesto inferior (~{ds} vs ~{winner.get('decision_score')})")
        if o_spd + 1.0 < w_spd:
            reasons.append(
                f"menor velocidad esperada del catálogo (velocidad factor {o_spd:.0f} vs {w_spd:.0f})"
            )
        if o_cmp + 1.0 < w_cmp:
            reasons.append(
                f"mayor complejidad operativa relativa (simplicidad {o_cmp:.0f} vs {w_cmp:.0f})"
            )
        if o_imp + 2.0 < w_imp:
            reasons.append(f"impacto operativo proyectado más bajo ({o_imp:.0f} vs {w_imp:.0f})")
        if o_cf + 2.0 < w_cf:
            reasons.append(f"menor confianza calibrada ({o_cf:.0f} vs {w_cf:.0f})")
        if not reasons:
            reasons.append("empate técnico resuelto por desempate complejidad/velocidad/confianza")
        out.append(f"'{nm}' ({at}) queda atrás: " + "; ".join(reasons) + ".")
    return out[:6]


def _expected_benefit_text(ctx: Dict[str, Any]) -> str:
    rec = ctx.get("estimated_recovery") or {}
    cr = ctx.get("contextual_reasoning") or {}
    parts: List[str] = []
    if rec.get("potential_trips_recovered_weekly") is not None:
        parts.append(f"Recuperación de viajes ~{rec.get('potential_trips_recovered_weekly')} trips/sem (metodo {rec.get('recovery_method')}).")
    if cr.get("expected_operational_effect"):
        parts.append(str(cr.get("expected_operational_effect"))[:260])
    if not parts:
        parts.append("Beneficio esperado sólo cualitativo: revisión operativa prioritizada sin promesa financiera.")
    return " ".join(parts)[:780]


def _tradeoffs(cat: Dict[str, Any]) -> List[str]:
    tp: List[str] = []
    if str(cat.get("cost") or "").lower() == "medium":
        tp.append("Costo operativo medio: coordina budgets antes de ejecutar campo/incentivos.")
    if str(cat.get("speed") or "").lower() != "fast":
        tp.append("Maduración más lenta: resultados pueden tardar varias semanas.")
    tp.append("Requiere validación manual: política sólo ordena opciones.")
    tp.append(f"Complejidad canales: '{cat.get('channel_suggested', '—')}'.")
    return tp[:5]


def _onboarding_pending_estimate(bucket: List[Dict[str, Any]]) -> Optional[int]:
    for it in bucket:
        if str(it.get("action_type")) == "volume_onboarding_followup":
            op = it.get("operational_pool") or {}
            tc = op.get("total_candidates")
            if tc is None:
                return None
            try:
                return int(tc)
            except (TypeError, ValueError):
                return None
    return None


def _filtered_valid_contextual_suggestions(raw: Any) -> List[Dict[str, Any]]:
    """Entradas con las que la política puede puntuar (auditable vía checks.partial si faltan campos)."""
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if not str(item.get("action_type") or "").strip():
            continue
        out.append(item)
    return out


def _incomplete_inputs_for_policy(cs: Dict[str, Any]) -> bool:
    """Señales mínimas para explicación auditável; no bloquea el score."""
    if not isinstance(cs.get("contextual_reasoning"), dict):
        return True
    er = cs.get("estimated_recovery")
    if er is not None and not isinstance(er, dict):
        return True
    return False


def build_projection_decision_recommendations(
    *,
    contextual_suggestions: Any,
    integrity_status: Dict[str, Any],
    ytd_alerts: Any,
    grain: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    _ = grain
    st_int = str(integrity_status.get("status") or "")
    if st_int == "broken":
        return [], "missing"
    if not isinstance(contextual_suggestions, list) or len(contextual_suggestions) == 0:
        return [], "missing"

    filtered = _filtered_valid_contextual_suggestions(contextual_suggestions)
    if not filtered:
        return [], "missing"

    alerts_list: List[Dict[str, Any]] = [a for a in (ytd_alerts or []) if isinstance(a, dict)]

    by_entity: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in filtered:
        ent = str(item.get("entity") or "—")
        by_entity[ent].append(item)

    outputs: List[Dict[str, Any]] = []
    any_partial = False

    for entity, bucket in sorted(by_entity.items(), key=lambda x: x[0]):
        if not bucket:
            continue

        enriched: List[Dict[str, Any]] = []
        alert = _alert_for_entity(entity, alerts_list)
        severe_vol = _severe_volume_context(alert)

        onboarding_exists = any(
            str(it.get("action_type")) == "volume_onboarding_followup" for it in bucket
        )
        onboarding_pending = _onboarding_pending_estimate(bucket)

        for cs in bucket:
            action_type = str(cs.get("action_type") or "")
            cat = ACTION_CATALOG.get(action_type, {})

            ds, factors, score_breakdown = _compute_decision_score_and_factors(
                cs,
                integrity_status=integrity_status,
                alert=alert,
                onboarding_followup_exist=onboarding_exists,
                severe_vol=severe_vol,
                onboarding_pending=onboarding_pending,
            )

            copy_item = dict(cs)
            copy_item["decision_score"] = ds
            copy_item["decision_factors"] = factors
            copy_item["_score_breakdown"] = score_breakdown
            copy_item["_action_name"] = str(cat.get("name") or cs.get("recommended_action_name") or action_type)
            enriched.append(copy_item)

        # Orden estable: primero por score descendente; desempates: menor complejidad, mayor velocidad, mayor confianza
        enriched.sort(
            key=lambda z: (
                -float(z.get("decision_score") or 0.0),
                float((z.get("decision_factors") or {}).get("operational_complexity_score") or 0),
                -float((z.get("decision_factors") or {}).get("speed_score") or 0),
                -float((z.get("decision_factors") or {}).get("confidence_score") or 0),
            ),
        )

        worst_conf_all_low = all(_norm_conf(x.get("confidence")) == "low" for x in enriched)

        winner = enriched[0]
        runner_up = enriched[1] if len(enriched) > 1 else None

        winner_action = str(winner.get("action_type"))
        pd = (
            None
            if not alert
            else str(alert.get("principal_driver") or "").strip().lower()
        )
        if pd in ("unknown", "", "none"):
            pd = None
        _, winner_adj_reasons = _action_adjustments(
            winner_action,
            principal_driver=pd,
            severe_vol=severe_vol,
            onboarding_followup_exist=onboarding_exists,
            onboarding_pending=onboarding_pending,
        )

        principal_status = "recommended"
        if worst_conf_all_low:
            principal_status = "alternative"
            any_partial = True
        elif _norm_conf(winner.get("confidence")) == "low":
            principal_status = "alternative"
            any_partial = True

        if _incomplete_inputs_for_policy(winner):
            any_partial = True

        inputs_used = [
            "contextual_suggestions[].operational_leverage_score",
            "contextual_suggestions[].estimated_recovery.potential_gap_recovery_pct",
            "contextual_suggestions[].estimated_recovery.potential_trips_recovered_weekly",
            "contextual_suggestions[].operational_pool.total_candidates",
            "contextual_suggestions[].confidence",
            "contextual_suggestions[].priority_score",
            "contextual_suggestions[].contextual_reasoning",
            "projection_suggestion_engine.ACTION_CATALOG(cost,speed,expected_impact)",
            "ytd_alerts[].entity_gap_principal_driver_optional",
            f"integration integrity_status.status={integrity_status.get('status')}",
        ]

        policy_trace = {
            "policy_version": POLICY_VERSION,
            "policy_type": POLICY_TYPE,
            "inputs_used": inputs_used,
            "weights": {
                "impact_w": _W_IMPACT,
                "speed_w": _W_SPEED,
                "inverse_complexity_w": _W_COMPLEXITY_INV,
                "confidence_w": _W_CONFIDENCE,
                "cost_efficiency_w": _W_COST,
            },
            "decision_score_breakdown": winner.get("_score_breakdown"),
        }

        win_ds = float(winner.get("decision_score") or 0.0)
        alternatives_list: List[Dict[str, Any]] = []
        for x in enriched[1:8]:
            ds = float(x.get("decision_score") or 0.0)
            gap = win_ds - ds
            alternatives_list.append(
                {
                    "action_type": str(x.get("action_type")),
                    "action_name": str(x.get("_action_name")),
                    "decision_score": ds,
                    "decision_status": "alternative"
                    if gap <= 18.0
                    else "not_recommended",
                },
            )

        reco: Dict[str, Any] = {
            "recommendation_id": _stable_recommendation_id(entity),
            "entity": entity,
            "recommended_action": {
                "action_type": winner_action,
                "action_name": winner.get("_action_name"),
            },
            "decision_status": principal_status,
            "decision_score": float(winner.get("decision_score") or 0.0),
            "decision_reasoning": {
                "why_selected": _why_selected_text(
                    winner,
                    runner_up,
                    adjustment_reasons=winner_adj_reasons,
                    alert=alert,
                ),
                "expected_operational_benefit": _expected_benefit_text(winner),
                "main_tradeoffs": _tradeoffs(ACTION_CATALOG.get(winner_action, {})),
                "why_not_other_actions": _why_not_other(winner, enriched),
            },
            "decision_factors": winner.get("decision_factors"),
            "decision_constraints": {
                "requires_manual_validation": True,
                "execution_enabled": False,
                "data_confidence": _norm_conf(winner.get("confidence")),
            },
            "alternatives": alternatives_list,
            "policy_trace": policy_trace,
            "contextual_suggestion_id": winner.get("suggestion_id"),
        }

        if not reco.get("policy_trace"):
            any_partial = True

        outputs.append(reco)

    if filtered and not outputs:
        return [], "missing"

    if not outputs:
        return [], "missing"

    check = "ok"
    if any_partial:
        check = "partial"
    if str(integrity_status.get("status") or "") == "warning":
        check = "partial" if check == "ok" else check

    return outputs, check


def safe_build_projection_decision_recommendations(
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], str]:
    try:
        return build_projection_decision_recommendations(**kwargs)
    except Exception as exc:
        logger.warning("safe_build_projection_decision_recommendations: %s", exc, exc_info=True)
        return [], "missing"
