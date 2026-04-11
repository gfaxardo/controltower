"""
Reglas canónicas de agregación para KPIs visibles en Omniview Matrix.

Objetivos:
- Evitar SUM/AVG inválidos al subir de daily -> weekly -> monthly.
- Documentar de forma explícita qué KPIs son aditivos, semi-aditivos o ratios.
- Centralizar guardrails para ETL, servicios y auditorías.
"""
from __future__ import annotations

from typing import Any, TypedDict


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


OMNIVIEW_MATRIX_KPI_RULES: dict[str, KpiAggregationRule] = {
    "trips_completed": {
        "label": "Trips",
        "aggregation_type": "additive",
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
    },
    "trips_cancelled": {
        "label": "Cancelled trips",
        "aggregation_type": "additive",
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
    },
    "revenue_yego_net": {
        "label": "Revenue net",
        "aggregation_type": "additive",
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
    },
    "active_drivers": {
        "label": "Active drivers",
        "aggregation_type": "semi_additive_distinct",
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
    },
    "avg_ticket": {
        "label": "Avg ticket",
        "aggregation_type": "non_additive_ratio",
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
    },
    "commission_pct": {
        "label": "Commission %",
        "aggregation_type": "non_additive_ratio",
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
    },
    "cancel_rate_pct": {
        "label": "Cancel rate %",
        "aggregation_type": "non_additive_ratio",
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
    },
    "trips_per_driver": {
        "label": "Trips per driver",
        "aggregation_type": "derived_ratio",
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
