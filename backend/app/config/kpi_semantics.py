"""
KPI Semantics — FASE DECISION READINESS

Archivo canónico de clasificación por naturaleza y rol de decisión.

Dos dimensiones por KPI:
  type            : naturaleza matemática del KPI
                    "additive"  → se puede sumar entre periodos (trips, revenue)
                    "distinct"  → conteo único (no sumar entre granos)
                    "ratio"     → fórmula (no sumar directamente)

  decision_role   : qué papel puede jugar en decisiones ejecutivas
                    "decision_ready" → válido para alertas y scoring aditivo
                    "context_only"   → leer solo dentro del mismo scope
                    "formula_only"   → comparable si se recomputa la fórmula

Regla de alertas:
  Solo KPIs con decision_role == "decision_ready" pueden gatillar alertas
  de brecha aditiva (gap_abs, gap_pct, underperformance scoring).

Alineación con kpi_aggregation_rules.py:
  "additive"  ↔  aggregation_type: "additive"
  "distinct"  ↔  aggregation_type: "semi_additive_distinct"
  "ratio"     ↔  aggregation_type: "non_additive_ratio" | "derived_ratio"

  "decision_ready" ↔  allowed_for_drift_alerts: True
  "context_only"   ↔  decision_status: "scope_only"
  "formula_only"   ↔  decision_status: "formula_only"
"""
from __future__ import annotations

from typing import Literal, TypedDict

KpiType         = Literal["additive", "distinct", "ratio"]
DecisionRole    = Literal["decision_ready", "context_only", "formula_only"]


class KpiSemantics(TypedDict, total=False):
    type: KpiType
    decision_role: DecisionRole
    # Columna real en las fact tables (None = KPI no disponible aún en BD).
    db_column: str | None
    # Nota operativa breve.
    note: str


KPI_SEMANTICS: dict[str, KpiSemantics] = {
    # ── Aditivos puros — DECISION READY ──────────────────────────────────────
    "trips_completed": {
        "type": "additive",
        "decision_role": "decision_ready",
        "db_column": "trips_completed",
        "note": "Conteo de viajes completados. SUM(daily_in_month) == monthly.",
    },
    "revenue": {
        "type": "additive",
        "decision_role": "decision_ready",
        "db_column": "revenue_yego_net",       # alias canónico en las fact tables
        "note": "Revenue neto Yego. Aditivo: SUM(daily_in_month) == monthly.",
    },
    "cancellations": {
        "type": "additive",
        "decision_role": "decision_ready",
        "db_column": "trips_cancelled",
        "note": "Cancelaciones. Aditivo: SUM(daily_in_month) == monthly.",
    },
    "gmv": {
        "type": "additive",
        "decision_role": "decision_ready",
        "db_column": "total_fare_completed_positive_sum",   # proxy de GMV
        "note": (
            "GMV (facturación bruta). Proxy en BD: total_fare_completed_positive_sum. "
            "Aditivo: SUM(daily_in_month) == monthly."
        ),
    },
    # ── Distinct count — CONTEXT ONLY ────────────────────────────────────────
    "active_drivers": {
        "type": "distinct",
        "decision_role": "context_only",
        "db_column": "active_drivers",
        "note": (
            "Drivers únicos que operaron en el periodo. "
            "NO sumar entre granos. Leer solo vs plan del mismo scope."
        ),
    },
    # ── Ratios — FORMULA ONLY ────────────────────────────────────────────────
    "avg_ticket": {
        "type": "ratio",
        "decision_role": "formula_only",
        "db_column": "avg_ticket",
        "note": (
            "Ticket promedio = ticket_sum / ticket_count. "
            "Comparable solo recomputando la fórmula por scope. No sumar."
        ),
    },
    "take_rate": {
        "type": "ratio",
        "decision_role": "formula_only",
        "db_column": "commission_pct",          # take_rate ≡ commission_pct
        "note": (
            "Take rate = revenue_yego_net / total_fare. "
            "Comparable recomputando por scope. No promediar directamente."
        ),
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def is_decision_ready(kpi_key: str) -> bool:
    """True si el KPI puede gatillar alertas de brecha aditiva."""
    return KPI_SEMANTICS.get(kpi_key, {}).get("decision_role") == "decision_ready"


def is_additive(kpi_key: str) -> bool:
    """True si el KPI es aditivo (puede sumarse entre periodos del mismo scope)."""
    return KPI_SEMANTICS.get(kpi_key, {}).get("type") == "additive"


def get_db_column(kpi_key: str) -> str | None:
    """Columna real en fact tables, o None si no está disponible."""
    return KPI_SEMANTICS.get(kpi_key, {}).get("db_column")


def additive_kpis() -> list[str]:
    """Lista de KPIs aditivos con columna en BD disponible."""
    return [
        k for k, v in KPI_SEMANTICS.items()
        if v.get("type") == "additive" and v.get("db_column")
    ]


def decision_ready_kpis() -> list[str]:
    """Lista de KPIs válidos para alertas de brecha aditiva."""
    return [
        k for k, v in KPI_SEMANTICS.items()
        if v.get("decision_role") == "decision_ready"
    ]
