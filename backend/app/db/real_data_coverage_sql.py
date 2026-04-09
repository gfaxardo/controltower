"""
Definición canónica de cobertura Real LOB por país (equivalente a ops.v_real_data_coverage).

- Dependencia canónica en BD: vista ops.v_real_data_coverage (Alembic 101 y 129).
- Fuente de filas: ops.real_rollup_day_fact (agregado por country IN ('pe','co')).
- Si la vista no existe tras migraciones pendientes, los servicios pueden usar la subconsulta
  inline como TEMPORARY_FALLBACK (log explícito; revertir aplicando `alembic upgrade head`).
"""
from __future__ import annotations

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

VIEW_V_REAL_DATA_COVERAGE = "ops.v_real_data_coverage"
FACT_TABLE_REAL_ROLLUP = "ops.real_rollup_day_fact"

TEMPORARY_FALLBACK_TAG = "[TEMPORARY_FALLBACK:v_real_data_coverage]"

# Subconsulta equivalente a la vista (misma semántica que migración 129).
SQL_COVERAGE_SUBQUERY_FROM_FACT = """
(
    SELECT
        country,
        MIN(trip_day) AS min_trip_date,
        MAX(trip_day) AS last_trip_date,
        MAX(last_trip_ts) AS last_trip_ts,
        date_trunc('month', MIN(trip_day))::date AS min_month,
        date_trunc('week', MIN(trip_day))::date AS min_week,
        date_trunc('month', MAX(trip_day))::date AS last_month_with_data,
        date_trunc('week', MAX(trip_day))::date AS last_week_with_data
    FROM ops.real_rollup_day_fact
    WHERE country IN ('pe', 'co')
    GROUP BY country
)
"""


def coverage_from_clause(cursor) -> Tuple[str, bool]:
    """
    Resuelve el origen para cobertura: vista canónica si existe; si no, subconsulta desde FACT.

    Returns:
        (fragment_sql, used_temporary_fallback)
    """
    cursor.execute("SELECT to_regclass(%s)", (VIEW_V_REAL_DATA_COVERAGE,))
    row = cursor.fetchone()
    reg = row[0] if row else None
    if reg:
        return VIEW_V_REAL_DATA_COVERAGE, False
    logger.warning(
        "%s Vista %s ausente; usando agregación inline desde %s. "
        "Aplicar migración 129 (o alembic upgrade head) y revertir fallback.",
        TEMPORARY_FALLBACK_TAG,
        VIEW_V_REAL_DATA_COVERAGE,
        FACT_TABLE_REAL_ROLLUP,
    )
    return SQL_COVERAGE_SUBQUERY_FROM_FACT.strip(), True
