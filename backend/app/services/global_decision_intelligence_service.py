"""
FASE 4.4 — Global Decision Intelligence Layer (sólo priorización estratégica).

Capa heurística que ordena ENTRE entidades. No ejecuta acciones, no envía
campañas, no automatiza workflows ni llama APIs externas.

Suggestion Engine propone → Decision Policy Engine elige por entidad →
Global Decision Intelligence Layer prioriza ENTRE entidades.

Sólo lee outputs ya construidos en `meta`:
  - decision_recommendations
  - contextual_suggestions
  - ytd_summary
  - ytd_alerts
  - integrity_status

No recalcula contextual_suggestions, no recalcula recovery, no recalcula
forecast. Aditivo: produce `meta.global_decision_queue` y registra
`integrity_status.checks.global_decision_engine`.
"""
from __future__ import annotations

import logging
import math
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.services.projection_suggestion_engine_service import ACTION_CATALOG

logger = logging.getLogger(__name__)

POLICY_VERSION = "v1"
POLICY_TYPE = "global_heuristic_priority_engine"

_NS_GLOBAL = uuid.UUID("c6d3a89f-1f0f-4b71-9d2a-6dc70a3a9f44")

# Pesos del score global (suman 1.0). Auditables vía global_policy_trace.weights.
_W_LOCAL = 0.30
_W_IMPACT = 0.22
_W_URGENCY = 0.16
_W_REACHABILITY = 0.14
_W_FEASIBILITY = 0.10
_W_STRATEGIC = 0.08

# ---------------------------------------------------------------------------
# Strategic weights extensibles. Multiplicadores aplicados sobre componente
# `strategic_weight` (0..100); por defecto 1.0 (= 50/100). Pueden encadenarse
# (país x ciudad x lob). No es hardcode rígido en lógica dispersa: para cambiar
# prioridades estratégicas basta editar este diccionario.
# ---------------------------------------------------------------------------
STRATEGIC_WEIGHT_RULES: Dict[str, Dict[str, float]] = {
    "country": {
        "peru": 1.20,
        "perú": 1.20,
        "colombia": 1.05,
    },
    "city": {
        "lima": 1.30,
    },
    "lob": {
        "auto regular": 1.15,
        "delivery": 1.05,
    },
}

# Mapping action_type → portfolio_role.
_PORTFOLIO_ROLE_BY_ACTION: Dict[str, str] = {
    "productivity_reactivation": "quick_win",
    "productivity_incentive": "quick_win",
    "volume_onboarding_followup": "quick_win",
    "volume_scouts_push": "growth",
    "opportunity_replicate_winner": "growth",
    "ticket_mix_review": "structural",
    "data_review": "defensive",
}

# Resource profile por acción.
_RESOURCE_PROFILE_BY_ACTION: Dict[str, Dict[str, Any]] = {
    "productivity_reactivation": {
        "estimated_operational_load": "low",
        "required_team_type": ["outbound", "crm"],
    },
    "productivity_incentive": {
        "estimated_operational_load": "medium",
        "required_team_type": ["crm", "marketing_ops"],
    },
    "volume_onboarding_followup": {
        "estimated_operational_load": "low",
        "required_team_type": ["outbound", "onboarding"],
    },
    "volume_scouts_push": {
        "estimated_operational_load": "high",
        "required_team_type": ["field_supply"],
    },
    "ticket_mix_review": {
        "estimated_operational_load": "medium",
        "required_team_type": ["analytics", "revenue_ops"],
    },
    "data_review": {
        "estimated_operational_load": "low",
        "required_team_type": ["analytics"],
    },
    "opportunity_replicate_winner": {
        "estimated_operational_load": "medium",
        "required_team_type": ["ops_strategy"],
    },
}

_SPEED_NUM = {"fast": 92.0, "medium": 65.0, "slow": 38.0}
_COST_NUM = {"low": 92.0, "medium": 60.0, "high": 32.0}
_CONF_NUM = {"high": 95.0, "medium": 60.0, "low": 25.0}

_SATURATION_ACTION_THRESHOLD = 3
_SATURATION_TEAM_THRESHOLD = 4


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _sf(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(max(lo, min(hi, x)))


def _stable_rank_id(entity: str, action_type: str) -> str:
    return str(uuid.uuid5(_NS_GLOBAL, f"global|{entity}|{action_type}|{POLICY_VERSION}"))


def merge_integrity_with_global_decision_check(
    integrity_status: Dict[str, Any],
    global_check: str,
) -> Dict[str, Any]:
    ch = dict(integrity_status.get("checks") or {})
    ch["global_decision_engine"] = global_check
    return {**integrity_status, "checks": ch}


# ---------------------------------------------------------------------------
# Resolución de identidad de entidad (country / city / lob / segment)
# ---------------------------------------------------------------------------


def _alert_for_reco(
    reco: Dict[str, Any],
    ytd_alerts: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Match exacto por etiqueta entity y, en su defecto, prefijo razonable."""
    entity_label = str(reco.get("entity") or "").strip()
    if not entity_label:
        return None
    for a in ytd_alerts:
        if not isinstance(a, dict):
            continue
        if str(a.get("entity") or "").strip() == entity_label:
            return a
    e_norm = _norm(entity_label)
    for a in ytd_alerts:
        if not isinstance(a, dict):
            continue
        if _norm(a.get("entity") or "") == e_norm:
            return a
    return None


def _segment_from_ctx(ctx_lookup: Optional[Dict[str, Any]]) -> Optional[str]:
    """Etiqueta de segmento dominante (mayor masa) si el contextual lo expone."""
    if not isinstance(ctx_lookup, dict):
        return None
    pool = ctx_lookup.get("operational_pool") or {}
    segs = pool.get("segments") if isinstance(pool, dict) else None
    if not isinstance(segs, list) or not segs:
        return None
    dominant = max(
        (s for s in segs if isinstance(s, dict)),
        key=lambda s: int(s.get("drivers") or 0),
        default=None,
    )
    if not dominant:
        return None
    return (
        str(dominant.get("display_name") or dominant.get("segment_id") or "").strip()
        or None
    )


def _entity_struct(
    reco: Dict[str, Any],
    alert: Optional[Dict[str, Any]],
    ctx_lookup: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    country: Optional[str] = None
    city: Optional[str] = None
    lob: Optional[str] = None
    if alert and isinstance(alert, dict):
        country = (str(alert.get("country") or "").strip() or None)
        city = (str(alert.get("city") or "").strip() or None)
        lob = (str(alert.get("business_slice") or "").strip() or None)
    segment = _segment_from_ctx(ctx_lookup)
    return {
        "country": country,
        "city": city,
        "lob": lob,
        "segment": segment,
        "label": str(reco.get("entity") or "").strip(),
    }


# ---------------------------------------------------------------------------
# Componentes del score
# ---------------------------------------------------------------------------


def _business_impact(
    *,
    reco: Dict[str, Any],
    ctx: Optional[Dict[str, Any]],
    alert: Optional[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
) -> float:
    leverage = _sf((ctx or {}).get("operational_leverage_score")) or 0.0
    rec = (ctx or {}).get("estimated_recovery") or {}
    gap_pct = abs(_sf((alert or {}).get("gap_pct")) or 0.0)
    gap_trips = abs(_sf((alert or {}).get("gap_trips")) or 0.0)
    portfolio_real = abs(_sf((ytd_summary or {}).get("ytd_real_trips")) or 0.0)

    # Normaliza brecha vs portfolio real (si conocido) para escalar tamaño operativo.
    if portfolio_real > 0:
        share = min(1.0, gap_trips / portfolio_real)
    else:
        share = 0.0
    portfolio_part = 18.0 + share * 70.0  # 18..88

    gap_part = min(95.0, 32.0 + gap_pct * 4.0)
    leverage_part = min(100.0, max(0.0, leverage))
    recovery_pct = abs(_sf(rec.get("potential_gap_recovery_pct")) or 0.0)
    recovery_part = min(95.0, 30.0 + recovery_pct * 3.5) if recovery_pct else 35.0

    raw = (
        leverage_part * 0.34
        + gap_part * 0.27
        + portfolio_part * 0.22
        + recovery_part * 0.17
    )
    return _clip(raw)


def _remaining_period_pressure(
    ytd_summary: Optional[Dict[str, Any]],
    filters: Optional[Dict[str, Any]],
) -> float:
    """0..100. Más alto si queda menos tiempo del año/mes para cerrar gap."""
    f = filters or {}
    month = f.get("month")
    try:
        month = int(month) if month is not None else None
    except (TypeError, ValueError):
        month = None
    if month and 1 <= month <= 12:
        # Mes filtrado → presión proporcional al avance dentro del año.
        return _clip(35.0 + (month / 12.0) * 55.0)
    tp = str((ytd_summary or {}).get("through_period") or "")
    # Formato "YYYY-MM" o "YYYY-MM-DD".
    if len(tp) >= 7 and tp[4] == "-":
        try:
            mm = int(tp[5:7])
            return _clip(30.0 + (mm / 12.0) * 55.0)
        except ValueError:
            pass
    return 50.0


def _urgency(
    *,
    alert: Optional[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
    filters: Optional[Dict[str, Any]],
) -> float:
    if not alert:
        return 35.0
    trend = _norm(alert.get("ytd_trend"))
    pacing = _norm(alert.get("pacing_vs_expected"))
    gap_pct = abs(_sf(alert.get("gap_pct")) or 0.0)
    base = 35.0
    if trend == "deteriorating":
        base += 25.0
    elif trend == "improving":
        base -= 8.0
    if pacing == "behind":
        base += 18.0
    elif pacing == "ahead":
        base -= 10.0
    base += min(30.0, gap_pct * 2.5)
    pressure = _remaining_period_pressure(ytd_summary, filters)
    base = base * 0.78 + pressure * 0.22
    return _clip(base)


def _reachability(ctx: Optional[Dict[str, Any]]) -> float:
    if not isinstance(ctx, dict):
        return 32.0
    rec = ctx.get("estimated_recovery") or {}
    pct = abs(_sf(rec.get("potential_gap_recovery_pct")) or 0.0)
    weekly = abs(_sf(rec.get("potential_trips_recovered_weekly")) or 0.0)
    pct_part = min(95.0, 25.0 + pct * 4.2) if pct else 30.0
    weekly_part = min(95.0, 25.0 + math.sqrt(weekly) * 6.5) if weekly else 32.0
    return _clip(pct_part * 0.62 + weekly_part * 0.38)


def _feasibility(reco: Dict[str, Any]) -> float:
    factors = reco.get("decision_factors") or {}
    speed = _sf(factors.get("speed_score"))
    complexity_simplicity = _sf(factors.get("operational_complexity_score"))
    cat = ACTION_CATALOG.get(str((reco.get("recommended_action") or {}).get("action_type") or ""), {})
    cat_speed = _SPEED_NUM.get(str(cat.get("speed") or "medium"), 65.0)
    cat_cost = _COST_NUM.get(str(cat.get("cost") or "medium"), 60.0)
    spd = speed if speed is not None else cat_speed
    smp = complexity_simplicity if complexity_simplicity is not None else 60.0
    return _clip(spd * 0.42 + smp * 0.36 + cat_cost * 0.22)


def _strategic_weight_score(entity: Dict[str, Any]) -> Tuple[float, float]:
    """Devuelve (component_0_100, multiplier) usando STRATEGIC_WEIGHT_RULES."""
    mult = 1.0
    co = _norm(entity.get("country"))
    ci = _norm(entity.get("city"))
    lo = _norm(entity.get("lob"))
    if co and co in STRATEGIC_WEIGHT_RULES["country"]:
        mult *= STRATEGIC_WEIGHT_RULES["country"][co]
    if ci and ci in STRATEGIC_WEIGHT_RULES["city"]:
        mult *= STRATEGIC_WEIGHT_RULES["city"][ci]
    if lo and lo in STRATEGIC_WEIGHT_RULES["lob"]:
        mult *= STRATEGIC_WEIGHT_RULES["lob"][lo]
    component = _clip(50.0 * mult)
    return component, mult


def _confidence_label(reco: Dict[str, Any], ctx: Optional[Dict[str, Any]]) -> str:
    cons = reco.get("decision_constraints") or {}
    dc = str(cons.get("data_confidence") or "").strip().lower()
    if dc in ("high", "medium", "low"):
        return dc
    cc = str((ctx or {}).get("confidence") or "").strip().lower()
    return cc if cc in ("high", "medium", "low") else "medium"


# ---------------------------------------------------------------------------
# Reasoning textual (no genérico)
# ---------------------------------------------------------------------------


def _why_prioritized(
    *,
    rank_hint: int,
    entity: Dict[str, Any],
    action_name: str,
    impact: float,
    urgency: float,
    reachability: float,
    feasibility: float,
    strategic_mult: float,
    alert: Optional[Dict[str, Any]],
) -> str:
    label = entity.get("label") or "—"
    parts: List[str] = []
    parts.append(
        f"Posición global #{rank_hint} para «{label}»: combina impacto operativo "
        f"({impact:.0f}/100), urgencia ({urgency:.0f}/100) y alcanzabilidad de "
        f"recuperación ({reachability:.0f}/100)."
    )
    if alert:
        gp = _sf(alert.get("gap_pct"))
        gt = _sf(alert.get("gap_trips"))
        if gp is not None:
            parts.append(f" Brecha actual ~{gp:.1f}% YTD.")
        if gt is not None and abs(gt) >= 100:
            parts.append(f" Volumen de brecha ~{abs(gt):,.0f} trips.")
        trend = _norm(alert.get("ytd_trend"))
        pacing = _norm(alert.get("pacing_vs_expected"))
        if trend == "deteriorating":
            parts.append(" Tendencia YTD en deterioro empuja la urgencia al alza.")
        elif trend == "improving":
            parts.append(" Tendencia YTD mejorando contiene la urgencia.")
        if pacing == "behind":
            parts.append(" Pacing vs plan: por debajo.")
    if strategic_mult > 1.0:
        parts.append(
            f" Peso estratégico configurado x{strategic_mult:.2f} (ver STRATEGIC_WEIGHT_RULES)."
        )
    elif strategic_mult < 1.0:
        parts.append(
            f" Peso estratégico configurado x{strategic_mult:.2f} (slice no priorizado)."
        )
    parts.append(f" Acción priorizada: {action_name}.")
    return "".join(parts)[:780]


def _expected_business_impact_text(
    ctx: Optional[Dict[str, Any]],
    alert: Optional[Dict[str, Any]],
) -> str:
    rec = (ctx or {}).get("estimated_recovery") or {}
    parts: List[str] = []
    weekly = _sf(rec.get("potential_trips_recovered_weekly"))
    pct = _sf(rec.get("potential_gap_recovery_pct"))
    if weekly is not None:
        parts.append(f"Recuperación potencial ~{weekly:,.0f} trips/sem.")
    if pct is not None:
        parts.append(f"Cierre estimado de brecha ~{pct:.1f}% (orden de magnitud).")
    if alert and _sf(alert.get("gap_trips")) is not None:
        parts.append(
            f"Brecha actual ~{abs(float(alert['gap_trips'])):,.0f} trips: "
            "el impacto se concentra donde el gap absoluto es mayor."
        )
    if not parts:
        parts.append(
            "Impacto cualitativo: priorización informativa sin promesa cuantitativa."
        )
    return " ".join(parts)[:560]


def _strategic_relevance_text(entity: Dict[str, Any], strategic_mult: float) -> str:
    bits: List[str] = []
    if entity.get("country"):
        bits.append(str(entity["country"]))
    if entity.get("city"):
        bits.append(str(entity["city"]))
    if entity.get("lob"):
        bits.append(str(entity["lob"]))
    head = " · ".join(bits) if bits else (entity.get("label") or "—")
    if strategic_mult >= 1.10:
        return (
            f"{head} marcado como slice de prioridad estratégica (multiplicador "
            f"x{strategic_mult:.2f}). Relevante para metas globales."
        )
    if strategic_mult <= 0.95:
        return (
            f"{head} sin multiplicador estratégico positivo (x{strategic_mult:.2f}); "
            "se considera por impacto operativo, no por relevancia institucional."
        )
    return (
        f"{head} con peso estratégico neutro (x{strategic_mult:.2f}); "
        "ranking gobernado por impacto, urgencia y alcance."
    )


def _urgency_text(alert: Optional[Dict[str, Any]], urgency: float) -> str:
    if not alert:
        return f"Urgencia derivada de heurística temporal (score {urgency:.0f}/100); sin alerta YTD enlazada."
    trend = _norm(alert.get("ytd_trend")) or "—"
    pacing = _norm(alert.get("pacing_vs_expected")) or "—"
    return (
        f"Tendencia YTD: {trend}; pacing: {pacing}. "
        f"Score urgencia compuesto {urgency:.0f}/100, ponderado por tiempo restante del periodo."
    )


def _execution_feasibility_text(reco: Dict[str, Any], feasibility: float) -> str:
    cat = ACTION_CATALOG.get(str((reco.get("recommended_action") or {}).get("action_type") or ""), {})
    speed = str(cat.get("speed") or "—")
    cost = str(cat.get("cost") or "—")
    return (
        f"Velocidad declarada del catálogo: {speed}; costo: {cost}. "
        f"Score de viabilidad operativa {feasibility:.0f}/100 (ejecución manual; layer informativo)."
    )


# ---------------------------------------------------------------------------
# Riesgos
# ---------------------------------------------------------------------------


def _risk_confidence(conf: str) -> str:
    if conf == "low":
        return (
            "Confianza baja: la decisión local fue marcada con datos limitados; "
            "evita acciones costosas hasta validación manual."
        )
    if conf == "medium":
        return "Confianza media: validar supuestos del contextual antes de ejecutar."
    return "Confianza alta sobre los inputs declarados."


def _risk_complexity(reco: Dict[str, Any]) -> str:
    cat = ACTION_CATALOG.get(str((reco.get("recommended_action") or {}).get("action_type") or ""), {})
    speed = str(cat.get("speed") or "medium")
    if speed == "slow":
        return "Maduración lenta: la acción tarda en mostrar resultados, no esperar quick wins."
    if speed == "medium":
        return "Maduración media: planificar ventana de seguimiento."
    return "Maduración rápida: bajo costo de espera."


# ---------------------------------------------------------------------------
# Construcción principal
# ---------------------------------------------------------------------------


def _filtered_recos(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        if not str(r.get("entity") or "").strip():
            continue
        act = r.get("recommended_action") or {}
        if not str(act.get("action_type") or "").strip():
            continue
        out.append(r)
    return out


def _ctx_lookup_index(contextual_suggestions: Any) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    if not isinstance(contextual_suggestions, list):
        return idx
    for c in contextual_suggestions:
        if not isinstance(c, dict):
            continue
        sid = str(c.get("suggestion_id") or "").strip()
        if sid:
            idx[sid] = c
    return idx


def build_global_decision_queue(
    *,
    decision_recommendations: Any,
    contextual_suggestions: Any = None,
    ytd_summary: Optional[Dict[str, Any]] = None,
    ytd_alerts: Any = None,
    integrity_status: Optional[Dict[str, Any]] = None,
    grain: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    _ = grain  # parámetro inerte (auditable, no calcula negocio)
    integrity = integrity_status or {}
    if str(integrity.get("status") or "") == "broken":
        return [], "missing"

    recos = _filtered_recos(decision_recommendations)
    if not recos:
        return [], "missing"

    ctx_idx = _ctx_lookup_index(contextual_suggestions)
    alerts_list: List[Dict[str, Any]] = [
        a for a in (ytd_alerts or []) if isinstance(a, dict)
    ]

    seen_keys: set = set()
    raw_items: List[Dict[str, Any]] = []
    any_partial = False
    low_conf_count = 0

    for reco in recos:
        entity_label = str(reco.get("entity") or "").strip()
        action_type = str((reco.get("recommended_action") or {}).get("action_type") or "")
        action_name = str(
            (reco.get("recommended_action") or {}).get("action_name") or action_type
        )
        dedup_key = (entity_label.lower(), action_type.lower())
        prev = next((r for r in raw_items if r["_dedup_key"] == dedup_key), None)
        if prev:
            # ante duplicado conservar mayor decision_score
            prev_score = float(prev["_local"] or 0.0)
            cur_score = float(_sf(reco.get("decision_score")) or 0.0)
            if cur_score <= prev_score:
                continue
            raw_items = [r for r in raw_items if r["_dedup_key"] != dedup_key]

        ctx_lookup = ctx_idx.get(str(reco.get("contextual_suggestion_id") or "").strip())
        alert = _alert_for_reco(reco, alerts_list)
        entity = _entity_struct(reco, alert, ctx_lookup)

        local = _clip(float(_sf(reco.get("decision_score")) or 0.0))
        impact = _business_impact(
            reco=reco, ctx=ctx_lookup, alert=alert, ytd_summary=ytd_summary
        )
        urgency = _urgency(alert=alert, ytd_summary=ytd_summary, filters=filters)
        reachability = _reachability(ctx_lookup)
        feasibility = _feasibility(reco)
        strategic, strategic_mult = _strategic_weight_score(entity)

        composite = (
            local * _W_LOCAL
            + impact * _W_IMPACT
            + urgency * _W_URGENCY
            + reachability * _W_REACHABILITY
            + feasibility * _W_FEASIBILITY
            + strategic * _W_STRATEGIC
        )

        conf = _confidence_label(reco, ctx_lookup)
        if conf == "low":
            low_conf_count += 1
            composite = min(composite, 50.0) - 4.0
        elif conf == "medium":
            composite -= 1.5

        composite = _clip(composite)

        if alert is None and not (ctx_lookup and ctx_lookup.get("estimated_recovery")):
            any_partial = True

        raw_items.append(
            {
                "_dedup_key": dedup_key,
                "_entity_label": entity_label,
                "_entity": entity,
                "_action_type": action_type,
                "_action_name": action_name,
                "_local": local,
                "_impact": impact,
                "_urgency": urgency,
                "_reachability": reachability,
                "_feasibility": feasibility,
                "_strategic": strategic,
                "_strategic_mult": strategic_mult,
                "_composite": composite,
                "_conf": conf,
                "_reco": reco,
                "_ctx": ctx_lookup,
                "_alert": alert,
            }
        )
        seen_keys.add(dedup_key)

    if not raw_items:
        return [], "missing"

    raw_items.sort(
        key=lambda x: (
            -float(x["_composite"]),
            -float(x["_local"]),
            -float(x["_impact"]),
            x["_entity_label"].lower(),
        )
    )

    # Saturation pass
    action_counts = Counter(r["_action_type"] for r in raw_items)
    team_counts: Counter = Counter()
    for r in raw_items:
        rp = _RESOURCE_PROFILE_BY_ACTION.get(r["_action_type"], {})
        for tt in rp.get("required_team_type") or []:
            team_counts[tt] += 1

    saturated_actions = {
        a for a, c in action_counts.items() if c >= _SATURATION_ACTION_THRESHOLD
    }
    saturated_teams = {
        t for t, c in team_counts.items() if c >= _SATURATION_TEAM_THRESHOLD
    }
    saturation_global_warning = bool(saturated_actions or saturated_teams)
    if saturation_global_warning:
        any_partial = True

    queue_out: List[Dict[str, Any]] = []
    inputs_used = [
        "decision_recommendations[].decision_score",
        "decision_recommendations[].decision_constraints.data_confidence",
        "decision_recommendations[].decision_factors",
        "decision_recommendations[].recommended_action.action_type",
        "contextual_suggestions[].operational_leverage_score",
        "contextual_suggestions[].estimated_recovery.potential_gap_recovery_pct",
        "contextual_suggestions[].estimated_recovery.potential_trips_recovered_weekly",
        "contextual_suggestions[].operational_pool.segments(top_by_drivers)",
        "contextual_suggestions[].confidence",
        "ytd_alerts[].gap_pct",
        "ytd_alerts[].gap_trips",
        "ytd_alerts[].ytd_trend",
        "ytd_alerts[].pacing_vs_expected",
        "ytd_summary.through_period",
        "ytd_summary.ytd_real_trips",
        f"integrity_status.status={integrity.get('status')}",
        "STRATEGIC_WEIGHT_RULES(country|city|lob)",
        "ACTION_CATALOG(speed,cost) (read-only)",
    ]
    weights = {
        "local_decision_strength_w": _W_LOCAL,
        "business_impact_w": _W_IMPACT,
        "urgency_w": _W_URGENCY,
        "reachability_w": _W_REACHABILITY,
        "operational_feasibility_w": _W_FEASIBILITY,
        "strategic_w": _W_STRATEGIC,
    }

    for rank, r in enumerate(raw_items, start=1):
        action_type = r["_action_type"]
        rp = _RESOURCE_PROFILE_BY_ACTION.get(
            action_type, {"estimated_operational_load": "medium", "required_team_type": []}
        )
        portfolio_role = _PORTFOLIO_ROLE_BY_ACTION.get(action_type, "structural")

        # portfolio_balance_weight: 100 base, baja si rol saturado en cola
        same_role = sum(
            1
            for x in raw_items
            if _PORTFOLIO_ROLE_BY_ACTION.get(x["_action_type"], "structural")
            == portfolio_role
        )
        balance_penalty = max(0, same_role - 2) * 8.0
        portfolio_balance_weight = _clip(80.0 - balance_penalty + (10.0 if rank == 1 else 0.0))

        sat_text = "Saturación operativa: sin señales (V1)."
        if action_type in saturated_actions:
            sat_text = (
                f"Saturación V1: {action_counts[action_type]} entradas con la misma acción "
                f"`{action_type}` en cola; revisar capacidad de equipos antes de planear ejecución."
            )
        elif any(t in saturated_teams for t in (rp.get("required_team_type") or [])):
            ts = ", ".join(
                t for t in (rp.get("required_team_type") or []) if t in saturated_teams
            )
            sat_text = (
                f"Saturación V1 por equipo(s): {ts}; demasiadas recomendaciones requieren "
                "los mismos recursos."
            )

        breakdown = {
            "local_decision_strength": round(r["_local"], 2),
            "business_impact": round(r["_impact"], 2),
            "urgency": round(r["_urgency"], 2),
            "reachability": round(r["_reachability"], 2),
            "operational_feasibility": round(r["_feasibility"], 2),
            "strategic": round(r["_strategic"], 2),
            "strategic_multiplier": round(r["_strategic_mult"], 3),
            "composite_pre_confidence": round(
                r["_local"] * _W_LOCAL
                + r["_impact"] * _W_IMPACT
                + r["_urgency"] * _W_URGENCY
                + r["_reachability"] * _W_REACHABILITY
                + r["_feasibility"] * _W_FEASIBILITY
                + r["_strategic"] * _W_STRATEGIC,
                2,
            ),
            "confidence_applied": r["_conf"],
        }

        global_score = round(float(r["_composite"]), 2)
        global_policy_trace = {
            "policy_version": POLICY_VERSION,
            "policy_type": POLICY_TYPE,
            "inputs_used": inputs_used,
            "weights": weights,
            "score_breakdown": breakdown,
            "saturation_summary": {
                "action_counts": dict(action_counts),
                "team_counts": dict(team_counts),
                "saturated_actions": sorted(saturated_actions),
                "saturated_teams": sorted(saturated_teams),
            },
        }

        why = _why_prioritized(
            rank_hint=rank,
            entity=r["_entity"],
            action_name=r["_action_name"],
            impact=r["_impact"],
            urgency=r["_urgency"],
            reachability=r["_reachability"],
            feasibility=r["_feasibility"],
            strategic_mult=r["_strategic_mult"],
            alert=r["_alert"],
        )

        item: Dict[str, Any] = {
            "global_priority_rank": rank,
            "global_recommendation_id": _stable_rank_id(r["_entity_label"], action_type),
            "decision_recommendation_id": str(r["_reco"].get("recommendation_id") or ""),
            "entity": r["_entity"],
            "selected_decision": {
                "action_type": action_type,
                "action_name": r["_action_name"],
            },
            "global_decision_score": global_score,
            "global_decision_reasoning": {
                "why_prioritized_globally": why,
                "expected_business_impact": _expected_business_impact_text(
                    r["_ctx"], r["_alert"]
                ),
                "strategic_relevance": _strategic_relevance_text(
                    r["_entity"], r["_strategic_mult"]
                ),
                "urgency_reasoning": _urgency_text(r["_alert"], r["_urgency"]),
                "execution_feasibility": _execution_feasibility_text(
                    r["_reco"], r["_feasibility"]
                ),
            },
            "priority_dimensions": {
                "local_decision_strength": round(r["_local"], 2),
                "business_impact_weight": round(r["_impact"], 2),
                "reachability_impact_weight": round(r["_reachability"], 2),
                "operational_feasibility_weight": round(r["_feasibility"], 2),
                "urgency_weight": round(r["_urgency"], 2),
                "strategic_weight": round(r["_strategic"], 2),
            },
            "decision_risks": {
                "operational_saturation_risk": sat_text,
                "execution_complexity_risk": _risk_complexity(r["_reco"]),
                "confidence_risk": _risk_confidence(r["_conf"]),
            },
            "resource_profile": {
                "estimated_operational_load": rp.get("estimated_operational_load", "medium"),
                "required_team_type": list(rp.get("required_team_type") or []),
            },
            "portfolio_role": {
                "role_type": portfolio_role,
                "portfolio_balance_weight": round(portfolio_balance_weight, 2),
            },
            "global_policy_trace": global_policy_trace,
            "decision_constraints": {
                "requires_manual_validation": True,
                "execution_enabled": False,
                "data_confidence": r["_conf"],
            },
        }

        if not isinstance(item.get("global_policy_trace"), dict):
            return [], "missing"

        if not isinstance(item.get("global_decision_score"), (int, float)) or math.isnan(
            float(item["global_decision_score"])
        ):
            return [], "missing"

        queue_out.append(item)

    if not queue_out:
        return [], "missing"

    check = "ok"
    if any_partial:
        check = "partial"
    if low_conf_count > 0 and check == "ok":
        check = "partial"
    if str(integrity.get("status") or "") == "warning" and check == "ok":
        check = "partial"

    return queue_out, check


def safe_build_global_decision_queue(
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], str]:
    try:
        return build_global_decision_queue(**kwargs)
    except Exception as exc:
        logger.warning("safe_build_global_decision_queue: %s", exc, exc_info=True)
        return [], "missing"
