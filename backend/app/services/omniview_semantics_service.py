"""
Semántica canónica para métricas comparativas de Omniview Matrix.

FASE 3.5 — Canonical Omniview Semantics

Define y centraliza las reglas de cálculo para avance %, gap absoluto y
gap % en todos los granos temporales (monthly, weekly, daily) y todos
los KPIs comparables.

Reglas canónicas:
  avance_pct  = actual / expected_base × 100   — NUNCA negativo
  gap_abs     = actual − expected_base          — puede ser negativo
  gap_pct     = (actual − expected_base)
                / expected_base × 100           — puede ser negativo

Base esperada por arco temporal:
  monthly  → full_month           (período cerrado)
             expected_to_date_month (mes en curso)
  weekly   → full_week            (semana cerrada)
             expected_to_date_week  (semana en curso)
  daily    → full_day             (plan del día)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# ─── Etiquetas legibles de comparison_basis ──────────────────────────────────
COMPARISON_BASIS_LABELS: Dict[str, str] = {
    "full_month":              "Plan mes completo (período cerrado)",
    "expected_to_date_month":  "Expected al corte (mes en curso)",
    "full_week":               "Plan semana completa (semana cerrada)",
    "expected_to_date_week":   "Expected al corte (semana en curso)",
    "full_day":                "Plan diario",
    "unknown":                 "Base no determinada",
}


def resolve_comparison_basis(is_full_period: bool, grain: str) -> str:
    """
    Determina la base de comparación para un período dado.

    Args:
        is_full_period: True si el período ya cerró completamente
                        (mes pasado, semana pasada, día completo).
        grain:          'monthly' | 'weekly' | 'daily'

    Returns:
        String identificador de comparison_basis.
    """
    if grain == "monthly":
        return "full_month" if is_full_period else "expected_to_date_month"
    if grain == "weekly":
        return "full_week" if is_full_period else "expected_to_date_week"
    return "full_day"


def compute_canonical_metrics(
    actual: Optional[float],
    expected_base: Optional[float],
    plan_full: Optional[float],
    comparison_basis: str,
) -> Dict[str, Any]:
    """
    Computa las métricas canónicas de Omniview para una celda.

    Regla crítica: avance_pct NUNCA es negativo.
      - Si actual < 0 (ej: revenue negativo) → avance_pct = None.
      - gap_pct SÍ puede ser negativo.

    Casos especiales:
      - expected_base None/0 → avance_pct = None, gap_pct = None,
        comparison_status = "not_comparable"
      - actual None y plan_full > 0 → comparison_status = "no_execution_yet"
      - actual ≥ 0 y plan_full None → comparison_status = "missing_plan"

    Args:
        actual:           Valor real acumulado al corte.
        expected_base:    Base esperada (expected_to_date o plan_full).
        plan_full:        Plan total del período completo (referencia).
        comparison_basis: Identificador del tipo de base usada.

    Returns:
        Dict con avance_pct, gap_abs, gap_pct, comparison_status.
    """
    # ── comparison_status ────────────────────────────────────────────────────
    if actual is None and (plan_full is None or plan_full == 0):
        comparison_status = "no_data"
    elif actual is None:
        comparison_status = "no_execution_yet"
    elif plan_full is None and expected_base is None:
        comparison_status = "missing_plan"
    elif expected_base is None or expected_base == 0:
        comparison_status = "not_comparable"
    else:
        comparison_status = "comparable"

    # ── avance_pct ──────────────────────────────────────────────────────────
    # NUNCA negativo: solo se computa cuando actual >= 0 y expected_base > 0.
    avance_pct: Optional[float] = None
    if (
        actual is not None
        and actual >= 0
        and expected_base is not None
        and expected_base > 0
    ):
        avance_pct = round((actual / expected_base) * 100.0, 2)

    # ── gap_abs ─────────────────────────────────────────────────────────────
    gap_abs: Optional[float] = None
    if actual is not None and expected_base is not None:
        gap_abs = round(actual - expected_base, 2)

    # ── gap_pct ─────────────────────────────────────────────────────────────
    # Puede ser negativo. Solo cuando expected_base != 0.
    gap_pct: Optional[float] = None
    if actual is not None and expected_base is not None and expected_base != 0:
        gap_pct = round(((actual - expected_base) / expected_base) * 100.0, 2)

    return {
        "avance_pct":        avance_pct,
        "gap_abs":           gap_abs,
        "gap_pct":           gap_pct,
        "comparison_status": comparison_status,
    }


def resolve_signal(avance_pct: Optional[float], actual: Optional[float]) -> str:
    """
    Semáforo basado en avance %.

    Si avance_pct es None pero actual < 0 (ej: revenue negativo),
    la señal es 'danger' para mantener visibilidad del problema.

    Returns:
        'green' | 'warning' | 'danger' | 'no_data'
    """
    if avance_pct is not None:
        if avance_pct >= 100.0:
            return "green"
        if avance_pct >= 90.0:
            return "warning"
        return "danger"
    # avance_pct es None: puede ser porque actual < 0 o no hay datos
    if actual is not None and actual < 0:
        return "danger"
    return "no_data"


def edge_case_row_for_no_plan(
    actual: Optional[float],
    kpi: str,
    period_field: str,
    period_value: str,
    grain: str,
) -> Dict[str, Any]:
    """
    Genera los campos canónicos de métricas para una fila sin plan (missing_plan).

    Para filas donde solo existe real pero no hay plan matcheado:
    - projected_total = None
    - expected_base = None → avance_pct = None, gap = None
    - comparison_status = "missing_plan"
    """
    return {
        kpi: actual,
        f"{kpi}_projected_total":    None,
        f"{kpi}_projected_expected": None,
        f"{kpi}_attainment_pct":     None,
        f"{kpi}_gap_to_expected":    None,
        f"{kpi}_gap_pct":            None,
        f"{kpi}_gap_to_full":        None,
        f"{kpi}_completion_pct":     None,
        f"{kpi}_signal":             "no_data",
        f"{kpi}_curve_method":       None,
        f"{kpi}_curve_confidence":   None,
        f"{kpi}_fallback_level":     None,
        f"{kpi}_expected_ratio":     None,
        f"{kpi}_comparison_basis":   "unknown",
    }
