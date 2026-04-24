"""
KPI Consistency Service — FASE DECISION READINESS

Valida la consistencia entre valores mensuales y la suma de valores diarios
dentro del mes calendario, SOLO para KPIs aditivos.

Regla canónica:
  monthly_value ≈ SUM(daily_value WHERE trip_date IN [primer_dia..ultimo_dia_del_mes])

Esta es la comparación correcta.
  ❌ NO comparar contra SUM(weekly_ISO_completas) — incluye días de meses adyacentes.
  ✅ SÍ comparar contra SUM(daily dentro del mes calendario).

KPIs no aditivos (distinct, ratio) se omiten automáticamente.
"""
from __future__ import annotations

from typing import Any

from app.config.kpi_semantics import KPI_SEMANTICS, get_db_column

# Tolerancias por defecto
_DEFAULT_REL_TOL = 0.01     # 1% relativo
_DEFAULT_ABS_TOL = 1.0      # 1 unidad absoluta


def validate_kpi_consistency(
    monthly_df: "Any",
    daily_df: "Any",
    rel_tol: float = _DEFAULT_REL_TOL,
    abs_tol: float = _DEFAULT_ABS_TOL,
) -> list[dict[str, Any]]:
    """
    Valida que monthly ≈ SUM(daily_in_month) para cada KPI aditivo.

    Args:
        monthly_df  : DataFrame (o dict-like) con columnas = columnas BD de las fact tables.
                      Se espera que ya esté filtrado al mes deseado.
        daily_df    : DataFrame con valores diarios SOLO del mes calendario (ya filtrado).
        rel_tol     : Tolerancia relativa (por defecto 1%).
        abs_tol     : Tolerancia absoluta (por defecto 1 unidad).

    Returns:
        Lista de dicts por KPI con:
          kpi, db_column, monthly, daily_sum, diff, diff_pct, status
          status: "ok" | "mismatch" | "no_data"
    """
    results: list[dict[str, Any]] = []

    for kpi, meta in KPI_SEMANTICS.items():
        if meta.get("type") != "additive":
            # KPIs distinct y ratio se omiten — no tienen sentido comparar por suma.
            continue

        db_col = get_db_column(kpi)
        if db_col is None:
            continue

        monthly_value = _extract_sum(monthly_df, db_col)
        daily_value   = _extract_sum(daily_df, db_col)

        if monthly_value is None and daily_value is None:
            results.append({
                "kpi": kpi,
                "db_column": db_col,
                "monthly": None,
                "daily_sum": None,
                "diff": None,
                "diff_pct": None,
                "status": "no_data",
            })
            continue

        m = monthly_value or 0.0
        d = daily_value or 0.0
        diff = abs(m - d)
        base = max(abs(m), abs(d))
        diff_pct = (diff / base * 100.0) if base > 0 else 0.0

        if diff <= abs_tol or (base > 0 and diff / base <= rel_tol):
            status = "ok"
        else:
            status = "mismatch"

        results.append({
            "kpi": kpi,
            "db_column": db_col,
            "monthly": m,
            "daily_sum": d,
            "diff": round(diff, 4),
            "diff_pct": round(diff_pct, 4),
            "status": status,
        })

    return results


def _extract_sum(df: Any, column: str) -> float | None:
    """
    Extrae la suma de una columna de un DataFrame (pandas) o de una lista de dicts.
    Devuelve None si la columna no existe.
    """
    if df is None:
        return None

    # pandas DataFrame
    try:
        import pandas as pd  # type: ignore
        if isinstance(df, pd.DataFrame):
            if column not in df.columns:
                return None
            s = df[column].sum()
            return float(s) if s == s else None   # NaN check
    except ImportError:
        pass

    # Lista de dicts (output directo de psycopg2)
    if isinstance(df, list):
        total = 0.0
        found = False
        for row in df:
            v = row.get(column)
            if v is not None:
                try:
                    total += float(v)
                    found = True
                except (TypeError, ValueError):
                    pass
        return total if found else None

    # Dict simple (fila única)
    if isinstance(df, dict):
        v = df.get(column)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return None


def consistency_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    """Resumen de resultados: conteo por status."""
    counts: dict[str, int] = {"ok": 0, "mismatch": 0, "no_data": 0}
    for r in results:
        s = r.get("status") or "no_data"
        counts[s] = counts.get(s, 0) + 1
    return counts
