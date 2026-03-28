"""
Carga incremental BUSINESS_SLICE: mes (DELETE+INSERT) y hora (bloque temporal).

Fuente de verdad agregada mensual: ops.real_business_slice_month_fact (API).
Grano horario: ops.real_business_slice_hour_fact (Fase 2; alimenta rollup vía
ops.v_real_business_slice_month_from_hour cuando esté poblado).
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Tuple

logger = logging.getLogger(__name__)

FACT_MONTH = "ops.real_business_slice_month_fact"
FACT_HOUR = "ops.real_business_slice_hour_fact"

# Mismas expresiones que la MV histórica (115), sobre v_real_trips_business_slice_resolved completo.
_MONTH_AGG_SELECT = """
SELECT
    r.trip_month AS month,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name,
    count(*) FILTER (WHERE r.completed_flag) AS trips_completed,
    count(*) FILTER (WHERE r.cancelled_flag) AS trips_cancelled,
    count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers,
    NULL::bigint AS connected_only_drivers,
    'NOT_IMPLEMENTED'::text AS connected_only_drivers_status,
    avg(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    ) AS avg_ticket,
    CASE
        WHEN sum(r.total_fare) FILTER (
            WHERE r.completed_flag
              AND r.total_fare IS NOT NULL
              AND r.total_fare > 0
        ) > 0
        THEN sum(r.revenue_yego_net) FILTER (
            WHERE r.completed_flag
              AND r.total_fare IS NOT NULL
              AND r.total_fare > 0
        )
            / sum(r.total_fare) FILTER (
                WHERE r.completed_flag
                  AND r.total_fare IS NOT NULL
                  AND r.total_fare > 0
            )
        ELSE NULL
    END AS commission_pct,
    CASE
        WHEN count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) > 0
        THEN (
            count(*) FILTER (WHERE r.completed_flag)::numeric
            / count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)
        )
        ELSE NULL
    END AS trips_per_driver,
    sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_net,
    CASE
        WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
        THEN sum(r.ticket) FILTER (WHERE r.completed_flag AND r.km > 0)
            / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
        ELSE NULL
    END AS precio_km,
    CASE
        WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
        THEN sum(r.duration_minutes) FILTER (WHERE r.completed_flag AND r.km > 0)
            / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
        ELSE NULL
    END AS tiempo_km,
    CASE
        WHEN sum(r.duration_minutes) FILTER (
            WHERE r.completed_flag AND r.duration_minutes > 0
        ) > 0
        THEN count(*) FILTER (WHERE r.completed_flag)::numeric
            / (
                sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) / 60.0
            )
        ELSE NULL
    END AS completados_por_hora,
    CASE
        WHEN sum(r.duration_minutes) FILTER (
            WHERE r.completed_flag AND r.duration_minutes > 0
        ) > 0
        THEN count(*) FILTER (WHERE r.cancelled_flag)::numeric
            / (
                sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) / 60.0
            )
        ELSE NULL
    END AS cancelados_por_hora,
    now() AS refreshed_at,
    now() AS loaded_at
FROM ops.v_real_trips_business_slice_resolved r
WHERE r.resolution_status = 'resolved'
  AND r.trip_month IS NOT NULL
  AND r.business_slice_name IS NOT NULL
  AND r.trip_month = %s::date
GROUP BY
    r.trip_month,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name
"""

_HOUR_AGG_SELECT = """
SELECT
    r.trip_hour_start AS hour_start,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name,
    count(*) FILTER (WHERE r.completed_flag) AS trips_completed,
    count(*) FILTER (WHERE r.cancelled_flag) AS trips_cancelled,
    count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) AS active_drivers,
    NULL::bigint AS connected_only_drivers,
    'NOT_IMPLEMENTED'::text AS connected_only_drivers_status,
    avg(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    ) AS avg_ticket,
    CASE
        WHEN sum(r.total_fare) FILTER (
            WHERE r.completed_flag
              AND r.total_fare IS NOT NULL
              AND r.total_fare > 0
        ) > 0
        THEN sum(r.revenue_yego_net) FILTER (
            WHERE r.completed_flag
              AND r.total_fare IS NOT NULL
              AND r.total_fare > 0
        )
            / sum(r.total_fare) FILTER (
                WHERE r.completed_flag
                  AND r.total_fare IS NOT NULL
                  AND r.total_fare > 0
            )
        ELSE NULL
    END AS commission_pct,
    CASE
        WHEN count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) > 0
        THEN (
            count(*) FILTER (WHERE r.completed_flag)::numeric
            / count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)
        )
        ELSE NULL
    END AS trips_per_driver,
    sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_net,
    sum(r.total_fare) FILTER (
        WHERE r.completed_flag
          AND r.total_fare IS NOT NULL
          AND r.total_fare > 0
    ) AS total_fare_completed_positive_sum,
    CASE
        WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
        THEN sum(r.ticket) FILTER (WHERE r.completed_flag AND r.km > 0)
            / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
        ELSE NULL
    END AS precio_km,
    CASE
        WHEN sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0) > 0
        THEN sum(r.duration_minutes) FILTER (WHERE r.completed_flag AND r.km > 0)
            / sum(r.km) FILTER (WHERE r.completed_flag AND r.km > 0)
        ELSE NULL
    END AS tiempo_km,
    CASE
        WHEN sum(r.duration_minutes) FILTER (
            WHERE r.completed_flag AND r.duration_minutes > 0
        ) > 0
        THEN count(*) FILTER (WHERE r.completed_flag)::numeric
            / (
                sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) / 60.0
            )
        ELSE NULL
    END AS completados_por_hora,
    CASE
        WHEN sum(r.duration_minutes) FILTER (
            WHERE r.completed_flag AND r.duration_minutes > 0
        ) > 0
        THEN count(*) FILTER (WHERE r.cancelled_flag)::numeric
            / (
                sum(r.duration_minutes) FILTER (
                    WHERE r.completed_flag AND r.duration_minutes > 0
                ) / 60.0
            )
        ELSE NULL
    END AS cancelados_por_hora,
    now() AS refreshed_at,
    now() AS loaded_at
FROM ops.v_real_trips_business_slice_resolved r
WHERE r.resolution_status = 'resolved'
  AND r.business_slice_name IS NOT NULL
  AND r.trip_hour_start IS NOT NULL
  AND r.trip_hour_start >= %s::timestamp
  AND r.trip_hour_start < %s::timestamp
GROUP BY
    r.trip_hour_start,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name
"""


def month_first_day(year: int, month: int) -> date:
    return date(year, month, 1)


def load_business_slice_month(cur: Any, target_month: date) -> int:
    """
    Borra y recalcula un solo mes en ops.real_business_slice_month_fact.
    Retorna filas insertadas.
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)
    cur.execute(f"DELETE FROM {FACT_MONTH} WHERE month = %s::date", (target_month,))
    deleted = cur.rowcount
    sql = f"INSERT INTO {FACT_MONTH} {_MONTH_AGG_SELECT}"
    cur.execute(sql, (target_month,))
    inserted = cur.rowcount
    logger.info(
        "business_slice month load: month=%s deleted_rows=%s inserted_rows=%s",
        target_month,
        deleted,
        inserted,
    )
    return inserted


def load_business_slice_hour_block(
    cur: Any, range_start: datetime, range_end: datetime
) -> int:
    """
    Borra e inserta agregados horarios en [range_start, range_end).
    """
    cur.execute(
        f"""
        DELETE FROM {FACT_HOUR}
        WHERE hour_start >= %s::timestamp AND hour_start < %s::timestamp
        """,
        (range_start, range_end),
    )
    sql = f"INSERT INTO {FACT_HOUR} {_HOUR_AGG_SELECT}"
    cur.execute(sql, (range_start, range_end))
    inserted = cur.rowcount
    logger.info(
        "business_slice hour block: [%s, %s) inserted_rows=%s",
        range_start,
        range_end,
        inserted,
    )
    return inserted


def backfill_business_slice_months(
    cur: Any, start: date, end: date
) -> Tuple[int, list[date]]:
    """
    Recorre meses civiles [start, end] (inclusive en mes de inicio y fin).
    Normaliza a primer día de cada mes.
    Retorna (total_filas_insertadas, lista_meses_procesados).
    """
    if start > end:
        start, end = end, start
    y, m = start.year, start.month
    end_y, end_m = end.year, end.month
    months: list[date] = []
    total_rows = 0
    while (y, m) <= (end_y, end_m):
        d = month_first_day(y, m)
        months.append(d)
        total_rows += load_business_slice_month(cur, d)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return total_rows, months


