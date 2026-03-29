"""
Carga incremental BUSINESS_SLICE: mes (DELETE+INSERT) y hora (bloque temporal).

Fuente de verdad agregada mensual: ops.real_business_slice_month_fact (API).
Grano horario: ops.real_business_slice_hour_fact (Fase 2; alimenta rollup vía
ops.v_real_business_slice_month_from_hour cuando esté poblado).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime
from typing import Any, Optional, Tuple

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

# Misma agregación pero acotada por viajes del mes+país en enriched (menos pico en pgsql_tmp).
_MONTH_AGG_SELECT_CHUNKED = """
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
INNER JOIN (
    SELECT trip_id
    FROM ops.v_real_trips_enriched_base
    WHERE trip_month = %s::date
      AND country IS NOT DISTINCT FROM %s
) lim ON lim.trip_id = r.trip_id
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

# Acotación mes + país + ciudad (menor pico en pgsql_tmp que solo país).
_MONTH_AGG_SELECT_CHUNKED_CITY = """
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
INNER JOIN (
    SELECT trip_id
    FROM ops.v_real_trips_enriched_base
    WHERE trip_month = %s::date
      AND country IS NOT DISTINCT FROM %s
      AND city IS NOT DISTINCT FROM %s
) lim ON lim.trip_id = r.trip_id
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


def apply_business_slice_load_session_settings(cur: Any) -> None:
    """
    Reduce derrames de ordenación/hash a pgsql_tmp (útil si el disco del servidor Postgres está justo).

    BUSINESS_SLICE_LOAD_WORK_MEM: valor PostgreSQL (ej. 256MB, 512MB). Por defecto 256MB.
    BUSINESS_SLICE_LOAD_WORK_MEM=0 — no modificar work_mem.

    BUSINESS_SLICE_MONTH_LOAD_CHUNK_BY_COUNTRY: si no es 0/off, la carga mensual hace INSERTs
    acotados vía join a enriched, para bajar el pico de temporales.

    BUSINESS_SLICE_MONTH_CHUNK_GRAIN: ``city`` (defecto) = un chunk por (país, ciudad); ``country`` = solo país.
    """
    raw = os.environ.get("BUSINESS_SLICE_LOAD_WORK_MEM", "256MB").strip()
    if raw in ("0", "", "off", "false"):
        return
    cur.execute("SET LOCAL work_mem = %s", (raw,))


def _month_load_use_country_chunks() -> bool:
    v = os.environ.get("BUSINESS_SLICE_MONTH_LOAD_CHUNK_BY_COUNTRY", "1").strip().lower()
    return v not in ("0", "", "off", "false", "no")


def _month_chunk_grain_country_only() -> bool:
    return os.environ.get("BUSINESS_SLICE_MONTH_CHUNK_GRAIN", "city").strip().lower() == "country"


def load_business_slice_month(
    cur: Any,
    target_month: date,
    conn: Optional[Any] = None,
) -> int:
    """
    Borra y recalcula un solo mes en ops.real_business_slice_month_fact.
    Retorna filas insertadas.

    Por defecto inserta por país (mismo mes) para reducir uso de pgsql_tmp. Desactivar con
    BUSINESS_SLICE_MONTH_LOAD_CHUNK_BY_COUNTRY=0.

    Si ``conn`` no es None y el modo va por países, hace COMMIT tras el DELETE y tras cada INSERT
    (transacciones cortas: menos riesgo de “connection already closed” en cargas largas). Pase la
    misma conexión que ``cur.connection`` desde scripts CLI.
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)
    apply_business_slice_load_session_settings(cur)
    cur.execute(f"DELETE FROM {FACT_MONTH} WHERE month = %s::date", (target_month,))
    deleted = cur.rowcount

    if _month_load_use_country_chunks():
        if _month_chunk_grain_country_only():
            cur.execute(
                """
                SELECT DISTINCT country
                FROM ops.v_real_trips_enriched_base
                WHERE trip_month = %s::date
                ORDER BY 1 NULLS FIRST
                """,
                (target_month,),
            )
            pairs = [(row[0], None) for row in cur.fetchall()]
            sql = f"INSERT INTO {FACT_MONTH} {_MONTH_AGG_SELECT_CHUNKED}"
            use_city = False
        else:
            cur.execute(
                """
                SELECT DISTINCT country, city
                FROM ops.v_real_trips_enriched_base
                WHERE trip_month = %s::date
                ORDER BY 1 NULLS FIRST, 2 NULLS FIRST
                """,
                (target_month,),
            )
            pairs = [(row[0], row[1]) for row in cur.fetchall()]
            sql = f"INSERT INTO {FACT_MONTH} {_MONTH_AGG_SELECT_CHUNKED_CITY}"
            use_city = True
        if conn is not None:
            conn.commit()
        inserted = 0
        n = len(pairs)
        grain = "país+ciudad" if use_city else "país"
        print(
            f"month_fact {target_month}: {n} chunk(s) ({grain}) — progreso (puede tardar mucho si hay muchas ciudades)",
            flush=True,
        )
        for i, (c_country, c_city) in enumerate(pairs):
            apply_business_slice_load_session_settings(cur)
            t_chunk = time.perf_counter()
            if use_city:
                cur.execute(sql, (target_month, c_country, c_city, target_month))
            else:
                cur.execute(sql, (target_month, c_country, target_month))
            rows = cur.rowcount
            inserted += rows
            if conn is not None:
                conn.commit()
            co = "∅" if c_country is None else str(c_country)
            ci = "∅" if c_city is None else str(c_city)
            dt = time.perf_counter() - t_chunk
            if use_city:
                print(f"  [{i + 1}/{n}] país={co!r} ciudad={ci!r} filas={rows} ({dt:.1f}s)", flush=True)
            else:
                print(f"  [{i + 1}/{n}] país={co!r} filas={rows} ({dt:.1f}s)", flush=True)
            logger.info(
                "business_slice month chunk: month=%s idx=%s/%s rows_batch=%s",
                target_month,
                i + 1,
                n,
                rows,
            )
        logger.info(
            "business_slice month load (chunked): month=%s deleted_rows=%s inserted_rows=%s chunks=%s",
            target_month,
            deleted,
            inserted,
            n,
        )
        return inserted

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
    apply_business_slice_load_session_settings(cur)
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
    cur: Any,
    start: date,
    end: date,
    conn: Optional[Any] = None,
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
        total_rows += load_business_slice_month(cur, d, conn)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return total_rows, months


