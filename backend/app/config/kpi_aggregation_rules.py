"""
Reglas canónicas de agregación para KPIs visibles en Omniview Matrix.

Objetivos:
- Evitar SUM/AVG inválidos al subir de daily -> weekly -> monthly.
- Documentar de forma explícita qué KPIs son aditivos, semi-aditivos o ratios.
- Centralizar guardrails para ETL, servicios y auditorías.

Extensión FASE_KPI_CONSISTENCY:
- Se añaden campos de comparabilidad cross-grain (comparable_across_grains,
  comparison_rule, *_definition, diagnostic_note, recommended_ui_note) para
  formalizar el contrato exigido por la auditoría operativa.
- Alias `KPI_GRAIN_CONTRACT` apunta al mismo registry para alinear nomenclatura
  externa sin duplicar fuente de verdad.
"""
from __future__ import annotations

from typing import Any, TypedDict


# ─────────────────────────────────────────────────────────────────────────────
# Constantes de contrato (valores permitidos para los campos extendidos)
# ─────────────────────────────────────────────────────────────────────────────

# aggregation_type
AGG_ADDITIVE             = "additive"
AGG_SEMI_ADDITIVE        = "semi_additive_distinct"
AGG_NON_ADDITIVE_RATIO   = "non_additive_ratio"
AGG_DERIVED_RATIO        = "derived_ratio"

# comparison_rule
COMP_EXACT_SUM                       = "exact_sum"
COMP_SAME_FORMULA_DIFFERENT_SCOPE    = "same_formula_different_scope"
COMP_NOT_DIRECTLY_COMPARABLE         = "not_directly_comparable"


class KpiAggregationRule(TypedDict, total=False):
    label: str
    aggregation_type: str
    atomic_formula: str
    daily_formula: str
    weekly_formula: str
    monthly_formula: str
    numerator_component: str | None
    denominator_component: str | None
    rebuild_from_atomic: bool
    allowed_rollup_from_lower_grain: bool
    rollup_components_required: list[str]
    audit_notes: str
    # ── Extensión FASE_KPI_CONSISTENCY: contrato cross-grain ───────────────
    monthly_definition: str
    weekly_definition: str
    daily_definition: str
    comparable_across_grains: bool
    comparison_rule: str
    diagnostic_note: str
    recommended_ui_note: str
    # ── Extensión FASE_VALIDATION_FIX: decision readiness ─────────────────
    # allowed_for_cross_grain_decision: puede usarse para comparar valores
    #   entre granos distintos y tomar decisiones ejecutivas (ej: mensual vs semanal).
    #   Solo true para KPIs donde la comparación directa tiene sentido semántico.
    allowed_for_cross_grain_decision: bool
    # allowed_for_drift_alerts: puede gatillar alertas de derivación/brecha
    #   usando lógica aditiva (gap_abs, gap_pct, underperformance score).
    #   false para KPIs semi_additive o ratio que no se deben sumar.
    allowed_for_drift_alerts: bool
    # allowed_for_priority_scoring: puede entrar en el priority_score del
    #   alerting engine como KPI de base (no como componente auxiliar).
    allowed_for_priority_scoring: bool
    # decision_note: nota breve para el usuario sobre cómo usar el KPI.
    decision_note: str


OMNIVIEW_MATRIX_KPI_RULES: dict[str, KpiAggregationRule] = {
    "trips_completed": {
        "label": "Trips",
        "aggregation_type": AGG_ADDITIVE,
        "atomic_formula": "COUNT(*) FILTER (WHERE completed_flag)",
        "daily_formula": "SUM(trips_completed)",
        "weekly_formula": "SUM(trips_completed)",
        "monthly_formula": "SUM(trips_completed)",
        "numerator_component": "trips_completed",
        "denominator_component": None,
        "rebuild_from_atomic": False,
        "allowed_rollup_from_lower_grain": True,
        "rollup_components_required": ["trips_completed"],
        "audit_notes": "Aditivo puro; puede sumarse entre periodos si la fuente base es canónica.",
        "monthly_definition": "Conteo de viajes completados durante el mes calendario.",
        "weekly_definition": "Conteo de viajes completados durante la semana ISO.",
        "daily_definition": "Conteo de viajes completados en el día.",
        "comparable_across_grains": True,
        "comparison_rule": COMP_EXACT_SUM,
        "diagnostic_note": "SUM(daily_in_month) debe coincidir con monthly (tolerancia <=1% o <=1 viaje). weekly_sum_full_iso es solo informativo.",
        "recommended_ui_note": "Aditivo: la suma de días del mes equivale al mes.",
        "allowed_for_cross_grain_decision": True,
        "allowed_for_drift_alerts": True,
        "allowed_for_priority_scoring": True,
        "decision_note": "DECISION READY. Usar daily_in_month como base de comparación; NOT weekly ISO full sum.",
    },
    "trips_cancelled": {
        "label": "Cancelled trips",
        "aggregation_type": AGG_ADDITIVE,
        "atomic_formula": "COUNT(*) FILTER (WHERE cancelled_flag)",
        "daily_formula": "SUM(trips_cancelled)",
        "weekly_formula": "SUM(trips_cancelled)",
        "monthly_formula": "SUM(trips_cancelled)",
        "numerator_component": "trips_cancelled",
        "denominator_component": None,
        "rebuild_from_atomic": False,
        "allowed_rollup_from_lower_grain": True,
        "rollup_components_required": ["trips_cancelled"],
        "audit_notes": "Aditivo puro; se usa también como numerador de cancel_rate_pct.",
        "monthly_definition": "Conteo de viajes cancelados durante el mes.",
        "weekly_definition": "Conteo de viajes cancelados durante la semana.",
        "daily_definition": "Conteo de viajes cancelados en el día.",
        "comparable_across_grains": True,
        "comparison_rule": COMP_EXACT_SUM,
        "diagnostic_note": "SUM(daily_in_month) debe coincidir con monthly. weekly_sum_full_iso solo informativo.",
        "recommended_ui_note": "Aditivo: la suma de días del mes equivale al mes.",
        "allowed_for_cross_grain_decision": True,
        "allowed_for_drift_alerts": True,
        "allowed_for_priority_scoring": False,
        "decision_note": "DECISION READY (componente de cancel_rate). No es KPI principal de scoring.",
    },
    "revenue_yego_net": {
        "label": "Revenue net",
        "aggregation_type": AGG_ADDITIVE,
        "atomic_formula": "SUM(revenue_yego_net) FILTER (WHERE completed_flag)",
        "daily_formula": "SUM(revenue_yego_net)",
        "weekly_formula": "SUM(revenue_yego_net)",
        "monthly_formula": "SUM(revenue_yego_net)",
        "numerator_component": "revenue_yego_net",
        "denominator_component": None,
        "rebuild_from_atomic": False,
        "allowed_rollup_from_lower_grain": True,
        "rollup_components_required": ["revenue_yego_net"],
        "audit_notes": "Aditivo si proviene de la fuente real/proxy canónica ya conciliada.",
        "monthly_definition": "Suma de revenue neto Yego de viajes completados en el mes.",
        "weekly_definition": "Suma de revenue neto Yego en la semana.",
        "daily_definition": "Suma de revenue neto Yego en el día.",
        "comparable_across_grains": True,
        "comparison_rule": COMP_EXACT_SUM,
        "diagnostic_note": "SUM(daily_in_month) debe coincidir con monthly (tolerancia 1% o eps absoluto). weekly_sum_full_iso solo informativo.",
        "recommended_ui_note": "Aditivo: la suma de días del mes equivale al mes.",
        "allowed_for_cross_grain_decision": True,
        "allowed_for_drift_alerts": True,
        "allowed_for_priority_scoring": True,
        "decision_note": "DECISION READY. KPI de revenue aditivo; comparar siempre vs plan mensual o daily acumulado.",
    },
    "active_drivers": {
        "label": "Active drivers",
        "aggregation_type": AGG_SEMI_ADDITIVE,
        "atomic_formula": "COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)",
        "daily_formula": "COUNT(DISTINCT driver_id) en el dia",
        "weekly_formula": "COUNT(DISTINCT driver_id) en la semana",
        "monthly_formula": "COUNT(DISTINCT driver_id) en el mes",
        "numerator_component": None,
        "denominator_component": None,
        "rebuild_from_atomic": True,
        "allowed_rollup_from_lower_grain": False,
        "rollup_components_required": [],
        "audit_notes": "Nunca sumar; la unicidad se rompe al encadenar daily -> weekly/monthly o al sumar filas dimensionadas.",
        "monthly_definition": "Drivers únicos que completaron al menos un viaje en el mes.",
        "weekly_definition": "Drivers únicos que completaron al menos un viaje en la semana.",
        "daily_definition": "Drivers únicos que completaron al menos un viaje en el día.",
        "comparable_across_grains": False,
        "comparison_rule": COMP_NOT_DIRECTLY_COMPARABLE,
        "diagnostic_note": (
            "Distinct count por scope. monthly NO equivale a SUM(weekly) ni SUM(daily). "
            "Comparar solo contra el valor del mismo scope (mensual vs plan mensual, "
            "no contra suma de semanales). Usar daily_max como referencia de sanity."
        ),
        "recommended_ui_note": "Drivers únicos del periodo. No sumar entre granos. Leer por scope.",
        "allowed_for_cross_grain_decision": False,
        "allowed_for_drift_alerts": True,
        "allowed_for_priority_scoring": True,
        "decision_note": (
            "SCOPE_ONLY. Drift permitido SOLO contra plan del mismo scope "
            "(mensual vs plan mensual). NO usar suma weekly/daily como base de alerta. "
            "La brecha de drivers debe leerse como: '¿cuántos drivers únicos del mes "
            "vs los esperados para el mes?'."
        ),
    },
    "avg_ticket": {
        "label": "Avg ticket",
        "aggregation_type": AGG_NON_ADDITIVE_RATIO,
        "atomic_formula": "SUM(ticket) / COUNT(ticket) sobre completed_flag y ticket no nulo",
        "daily_formula": "ticket_sum_completed / ticket_count_completed",
        "weekly_formula": "SUM(ticket_sum_completed) / SUM(ticket_count_completed)",
        "monthly_formula": "SUM(ticket_sum_completed) / SUM(ticket_count_completed)",
        "numerator_component": "ticket_sum_completed",
        "denominator_component": "ticket_count_completed",
        "rebuild_from_atomic": True,
        "allowed_rollup_from_lower_grain": True,
        "rollup_components_required": ["ticket_sum_completed", "ticket_count_completed"],
        "audit_notes": "Nunca usar promedio simple de promedios; requiere numerador y denominador canónicos.",
        "monthly_definition": "Ticket promedio de viajes completados con ticket no nulo en el mes.",
        "weekly_definition": "Ticket promedio en la semana, recomputado desde componentes.",
        "daily_definition": "Ticket promedio en el día, recomputado desde componentes.",
        "comparable_across_grains": True,
        "comparison_rule": COMP_SAME_FORMULA_DIFFERENT_SCOPE,
        "diagnostic_note": "Ratios no se suman. Validar fórmula consistente por scope; no esperar exact_sum.",
        "recommended_ui_note": "Ratio: misma fórmula aplicada a distinto periodo. Comparar por scope, no por suma.",
        "allowed_for_cross_grain_decision": True,
        "allowed_for_drift_alerts": False,
        "allowed_for_priority_scoring": False,
        "decision_note": (
            "FORMULA_ONLY. Comparable si se recomputa la fórmula (ticket_sum/ticket_count) "
            "para cada scope. NO gatillar alertas aditivas (gap_abs/gap_pct) entre granos distintos."
        ),
    },
    "commission_pct": {
        "label": "Commission %",
        "aggregation_type": AGG_NON_ADDITIVE_RATIO,
        "atomic_formula": "SUM(revenue_yego_net) / SUM(total_fare_completed_positive_sum)",
        "daily_formula": "revenue_yego_net / total_fare_completed_positive_sum",
        "weekly_formula": "SUM(revenue_yego_net) / SUM(total_fare_completed_positive_sum)",
        "monthly_formula": "SUM(revenue_yego_net) / SUM(total_fare_completed_positive_sum)",
        "numerator_component": "revenue_yego_net",
        "denominator_component": "total_fare_completed_positive_sum",
        "rebuild_from_atomic": True,
        "allowed_rollup_from_lower_grain": True,
        "rollup_components_required": ["revenue_yego_net", "total_fare_completed_positive_sum"],
        "audit_notes": "Nunca promediar porcentajes entre dias o slices con distinto denominador.",
        "monthly_definition": "% de comisión: revenue_yego_net / total_fare_completed_positive en el mes.",
        "weekly_definition": "% de comisión recomputado desde componentes en la semana.",
        "daily_definition": "% de comisión recomputado desde componentes en el día.",
        "comparable_across_grains": True,
        "comparison_rule": COMP_SAME_FORMULA_DIFFERENT_SCOPE,
        "diagnostic_note": "No promediar %. Validar fórmula recomputada por scope.",
        "recommended_ui_note": "Ratio: misma fórmula aplicada a distinto periodo. Comparar por scope, no por suma.",
        "allowed_for_cross_grain_decision": True,
        "allowed_for_drift_alerts": False,
        "allowed_for_priority_scoring": False,
        "decision_note": (
            "FORMULA_ONLY. Comparable si se recomputa rev/fare para cada scope. "
            "NO gatillar alertas aditivas entre granos distintos."
        ),
    },
    "cancel_rate_pct": {
        "label": "Cancel rate %",
        "aggregation_type": AGG_NON_ADDITIVE_RATIO,
        "atomic_formula": "trips_cancelled / (trips_completed + trips_cancelled)",
        "daily_formula": "trips_cancelled / (trips_completed + trips_cancelled)",
        "weekly_formula": "SUM(trips_cancelled) / SUM(trips_completed + trips_cancelled)",
        "monthly_formula": "SUM(trips_cancelled) / SUM(trips_completed + trips_cancelled)",
        "numerator_component": "trips_cancelled",
        "denominator_component": "requested_or_relevant_trips",
        "rebuild_from_atomic": True,
        "allowed_rollup_from_lower_grain": True,
        "rollup_components_required": ["trips_completed", "trips_cancelled"],
        "audit_notes": "Se recalcula desde la base de viajes relevantes; no promediar porcentajes.",
        "monthly_definition": "% de cancelación recomputado desde trips_cancelled / (completed + cancelled) en el mes.",
        "weekly_definition": "% de cancelación recomputado en la semana.",
        "daily_definition": "% de cancelación recomputado en el día.",
        "comparable_across_grains": True,
        "comparison_rule": COMP_SAME_FORMULA_DIFFERENT_SCOPE,
        "diagnostic_note": "Recomputar desde componentes; nunca promediar % directamente.",
        "recommended_ui_note": "Ratio: misma fórmula aplicada a distinto periodo. Comparar por scope, no por suma.",
        "allowed_for_cross_grain_decision": True,
        "allowed_for_drift_alerts": False,
        "allowed_for_priority_scoring": False,
        "decision_note": (
            "FORMULA_ONLY. Usar solo para comparar la tasa de cancelación del periodo "
            "contra plan del mismo scope. NO alertar con lógica aditiva."
        ),
    },
    "trips_per_driver": {
        "label": "Trips per driver",
        "aggregation_type": AGG_DERIVED_RATIO,
        "atomic_formula": "trips_completed / active_drivers",
        "daily_formula": "trips_completed / active_drivers",
        "weekly_formula": "SUM(trips_completed) / COUNT(DISTINCT driver_id)",
        "monthly_formula": "SUM(trips_completed) / COUNT(DISTINCT driver_id)",
        "numerator_component": "trips_completed",
        "denominator_component": "active_drivers",
        "rebuild_from_atomic": True,
        "allowed_rollup_from_lower_grain": False,
        "rollup_components_required": ["trips_completed", "active_drivers"],
        "audit_notes": "Derivado; nunca sumar ni promediar ciegamente. Debe recalcularse desde sus componentes canónicos.",
        "monthly_definition": "trips_completed_mes / active_drivers_mes (ambos por scope mensual).",
        "weekly_definition": "trips_completed_semana / active_drivers_semana (distinct semanal).",
        "daily_definition": "trips_completed_día / active_drivers_día.",
        "comparable_across_grains": False,
        "comparison_rule": COMP_NOT_DIRECTLY_COMPARABLE,
        "diagnostic_note": (
            "Derivado de active_drivers (semi-aditivo). monthly no equivale a SUM(weekly_trips)/SUM(weekly_drivers). "
            "Validar consistencia de fórmula por scope, no por suma."
        ),
        "recommended_ui_note": "Derivado de drivers únicos. No comparable por suma entre granos. Leer por scope.",
        "allowed_for_cross_grain_decision": False,
        "allowed_for_drift_alerts": False,
        "allowed_for_priority_scoring": False,
        "decision_note": (
            "RESTRICTED. No usar para decisiones cross-grain ni para alertas de brecha aditiva. "
            "Interpretar solo dentro del mismo scope (mes vs plan_mes, semana vs plan_semana)."
        ),
    },
}


OMNIVIEW_MATRIX_VISIBLE_KPIS: tuple[str, ...] = (
    "commission_pct",
    "trips_completed",
    "avg_ticket",
    "active_drivers",
    "revenue_yego_net",
    "cancel_rate_pct",
    "trips_per_driver",
)


OMNIVIEW_SUPPORTING_COMPONENTS: tuple[str, ...] = (
    "trips_completed",
    "trips_cancelled",
    "revenue_yego_net",
    "ticket_sum_completed",
    "ticket_count_completed",
    "total_fare_completed_positive_sum",
    "active_drivers",
)


# ─────────────────────────────────────────────────────────────────────────────
# Alias FASE_KPI_CONSISTENCY: misma fuente de verdad, nombre alineado al plan
# ─────────────────────────────────────────────────────────────────────────────
KPI_GRAIN_CONTRACT: dict[str, KpiAggregationRule] = OMNIVIEW_MATRIX_KPI_RULES


# ─────────────────────────────────────────────────────────────────────────────
# Helpers existentes
# ─────────────────────────────────────────────────────────────────────────────

def get_omniview_kpi_rule(kpi_key: str) -> KpiAggregationRule:
    try:
        return OMNIVIEW_MATRIX_KPI_RULES[kpi_key]
    except KeyError as exc:
        raise KeyError(f"KPI sin regla de agregacion registrada: {kpi_key}") from exc


def is_rollup_allowed(kpi_key: str) -> bool:
    return bool(get_omniview_kpi_rule(kpi_key).get("allowed_rollup_from_lower_grain"))


def rule_summary_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kpi_key in OMNIVIEW_MATRIX_VISIBLE_KPIS:
        rule = get_omniview_kpi_rule(kpi_key)
        rows.append(
            {
                "kpi": kpi_key,
                "label": rule.get("label"),
                "aggregation_type": rule.get("aggregation_type"),
                "rebuild_from_atomic": bool(rule.get("rebuild_from_atomic")),
                "allowed_rollup_from_lower_grain": bool(rule.get("allowed_rollup_from_lower_grain")),
                "daily_formula": rule.get("daily_formula"),
                "weekly_formula": rule.get("weekly_formula"),
                "monthly_formula": rule.get("monthly_formula"),
                "audit_notes": rule.get("audit_notes"),
            }
        )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Helpers FASE_KPI_CONSISTENCY: contrato cross-grain
# ─────────────────────────────────────────────────────────────────────────────

def get_kpi_grain_contract(kpi_key: str) -> KpiAggregationRule:
    """Alias semántico de get_omniview_kpi_rule para usar bajo nomenclatura del plan."""
    return get_omniview_kpi_rule(kpi_key)


def is_kpi_comparable_across_grains(kpi_key: str) -> bool:
    """True si SUM(weekly) o SUM(daily) puede compararse contra monthly."""
    try:
        return bool(get_omniview_kpi_rule(kpi_key).get("comparable_across_grains"))
    except KeyError:
        return False


def get_kpi_comparison_rule(kpi_key: str) -> str:
    """exact_sum | same_formula_different_scope | not_directly_comparable."""
    try:
        return get_omniview_kpi_rule(kpi_key).get("comparison_rule") or COMP_NOT_DIRECTLY_COMPARABLE
    except KeyError:
        return COMP_NOT_DIRECTLY_COMPARABLE


def get_kpi_diagnostic_note(kpi_key: str) -> str:
    try:
        return get_omniview_kpi_rule(kpi_key).get("diagnostic_note") or ""
    except KeyError:
        return ""


def get_kpi_recommended_ui_note(kpi_key: str) -> str:
    try:
        return get_omniview_kpi_rule(kpi_key).get("recommended_ui_note") or ""
    except KeyError:
        return ""


def is_kpi_additive(kpi_key: str) -> bool:
    """True solo para KPIs cuyo aggregation_type es 'additive' (trips, revenue)."""
    try:
        return get_omniview_kpi_rule(kpi_key).get("aggregation_type") == AGG_ADDITIVE
    except KeyError:
        return False


def kpi_contract_for_meta(kpi_keys: tuple[str, ...] | list[str] | None = None) -> dict[str, dict[str, Any]]:
    """
    Subset compacto del contrato pensado para enviar en `meta.kpi_contract` de
    respuestas Omniview/projection. Incluye campos de decision readiness.
    """
    keys = tuple(kpi_keys) if kpi_keys else OMNIVIEW_MATRIX_VISIBLE_KPIS
    out: dict[str, dict[str, Any]] = {}
    for k in keys:
        try:
            r = get_omniview_kpi_rule(k)
        except KeyError:
            continue
        out[k] = {
            "label": r.get("label"),
            "aggregation_type": r.get("aggregation_type"),
            "comparable_across_grains": bool(r.get("comparable_across_grains")),
            "comparison_rule": r.get("comparison_rule"),
            "diagnostic_note": r.get("diagnostic_note"),
            "recommended_ui_note": r.get("recommended_ui_note"),
            # FASE_VALIDATION_FIX: decision readiness
            "allowed_for_cross_grain_decision": bool(r.get("allowed_for_cross_grain_decision")),
            "allowed_for_drift_alerts": bool(r.get("allowed_for_drift_alerts")),
            "allowed_for_priority_scoring": bool(r.get("allowed_for_priority_scoring")),
            "decision_note": r.get("decision_note") or "",
        }
    return out


# ─── Helpers FASE_VALIDATION_FIX: decision readiness ─────────────────────────

def is_kpi_allowed_for_cross_grain_decision(kpi_key: str) -> bool:
    """True si el KPI puede usarse para comparar valores entre granos distintos."""
    try:
        return bool(get_omniview_kpi_rule(kpi_key).get("allowed_for_cross_grain_decision"))
    except KeyError:
        return False


def is_kpi_allowed_for_drift_alerts(kpi_key: str) -> bool:
    """True si el KPI puede gatillar alertas de brecha/derivación aditiva."""
    try:
        return bool(get_omniview_kpi_rule(kpi_key).get("allowed_for_drift_alerts"))
    except KeyError:
        return False


def is_kpi_allowed_for_priority_scoring(kpi_key: str) -> bool:
    """True si el KPI puede entrar como base en el priority_score del alerting engine."""
    try:
        return bool(get_omniview_kpi_rule(kpi_key).get("allowed_for_priority_scoring"))
    except KeyError:
        return False


def get_kpi_decision_status(kpi_key: str) -> str:
    """
    Clasifica el KPI en una de las 4 categorías de decision readiness:
      - decision_ready  : additive, allowed en las 3 dimensiones.
      - scope_only      : semi_additive/distinct; permitido solo dentro del mismo scope.
      - formula_only    : ratio/derived; comparable por fórmula, no por suma.
      - restricted      : no usar en ningún cálculo cross-grain.
    """
    try:
        r = get_omniview_kpi_rule(kpi_key)
    except KeyError:
        return "restricted"
    agg = r.get("aggregation_type")
    cross = bool(r.get("allowed_for_cross_grain_decision"))
    drift = bool(r.get("allowed_for_drift_alerts"))
    prio = bool(r.get("allowed_for_priority_scoring"))
    if agg == AGG_ADDITIVE and cross and drift and prio:
        return "decision_ready"
    if agg == AGG_ADDITIVE and cross and drift:
        return "decision_ready"
    if agg == AGG_SEMI_ADDITIVE:
        return "scope_only"
    if agg in (AGG_NON_ADDITIVE_RATIO, AGG_DERIVED_RATIO):
        return "formula_only" if cross else "restricted"
    return "restricted"
