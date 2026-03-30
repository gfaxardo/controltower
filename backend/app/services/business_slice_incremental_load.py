"""
Carga incremental BUSINESS_SLICE: mes (DELETE+INSERT) y hora (bloque temporal).

Carga mensual: filtra primero en ops.v_real_trips_enriched_base vía
ops.fn_real_trips_business_slice_resolved_subset (misma lógica que la vista
resolved, sin materializar el universo completo). Fuente agregada mensual API:
ops.real_business_slice_month_fact.

Grano horario: ops.real_business_slice_hour_fact (sigue usando la vista resolved
acotada por rango de trip_hour_start; ver docs/BUSINESS_SLICE_HOURLY_FIRST.md).
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

FACT_MONTH = "ops.real_business_slice_month_fact"
FACT_HOUR = "ops.real_business_slice_hour_fact"

# Agregación mensual (mismas expresiones que antes) sobre filas ya resueltas.
_MONTH_AGG_FROM_RESOLVED_SOURCE = """
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
FROM {resolved_source} r
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

_MONTH_AGG_FROM_STAGING = """
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
FROM _bs_month_load_staging r
WHERE r.trip_month IS NOT NULL
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

_CREATE_STAGING_SQL = """
CREATE TEMP TABLE IF NOT EXISTS _bs_month_load_staging (
    trip_month date NOT NULL,
    country text,
    city text,
    business_slice_name text NOT NULL,
    fleet_display_name text,
    is_subfleet boolean NOT NULL,
    subfleet_name text,
    parent_fleet_name text,
    completed_flag boolean NOT NULL,
    cancelled_flag boolean NOT NULL,
    driver_id text,
    ticket numeric,
    total_fare numeric,
    revenue_yego_net numeric,
    km numeric,
    duration_minutes numeric
) ON COMMIT DELETE ROWS
"""

_INSERT_STAGING_FROM_FN = """
INSERT INTO _bs_month_load_staging (
    trip_month, country, city, business_slice_name, fleet_display_name,
    is_subfleet, subfleet_name, parent_fleet_name,
    completed_flag, cancelled_flag, driver_id, ticket, total_fare,
    revenue_yego_net, km, duration_minutes
)
SELECT
    r.trip_month,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    COALESCE(r.is_subfleet, false),
    r.subfleet_name,
    r.parent_fleet_name,
    r.completed_flag,
    r.cancelled_flag,
    r.driver_id::text,
    r.ticket,
    r.total_fare,
    r.revenue_yego_net,
    r.km,
    r.duration_minutes
FROM ops.fn_real_trips_business_slice_resolved_subset(
    %s::date, %s, %s, %s, %s, %s
) r
WHERE r.resolution_status = 'resolved'
  AND r.trip_month IS NOT NULL
  AND r.business_slice_name IS NOT NULL
"""


def month_first_day(year: int, month: int) -> date:
    return date(year, month, 1)


def apply_business_slice_load_session_settings(cur: Any) -> None:
    """
    Reduce derrames de ordenación/hash a pgsql_tmp (útil si el disco del servidor Postgres está justo).

    BUSINESS_SLICE_LOAD_WORK_MEM: valor PostgreSQL (ej. 256MB, 512MB). Por defecto 256MB.
    BUSINESS_SLICE_LOAD_WORK_MEM=0 — no modificar work_mem.

    BUSINESS_SLICE_MONTH_LOAD_CHUNK_BY_COUNTRY: si no es 0/off, la carga mensual va por chunks
    (país o país+ciudad o subchunks temporales según BUSINESS_SLICE_MONTH_CHUNK_GRAIN / --chunk-grain).
    """
    raw = os.environ.get("BUSINESS_SLICE_LOAD_WORK_MEM", "256MB").strip()
    if raw in ("0", "", "off", "false"):
        return
    cur.execute("SET LOCAL work_mem = %s", (raw,))


def _month_load_use_country_chunks() -> bool:
    v = os.environ.get("BUSINESS_SLICE_MONTH_LOAD_CHUNK_BY_COUNTRY", "1").strip().lower()
    return v not in ("0", "", "off", "false", "no")


def _effective_chunk_grain(cli_grain: Optional[str]) -> str:
    if cli_grain is not None and cli_grain.strip():
        return cli_grain.strip().lower()
    return os.environ.get("BUSINESS_SLICE_MONTH_CHUNK_GRAIN", "city").strip().lower()


def _require_resolved_subset_fn(cur: Any) -> None:
    cur.execute(
        """
        SELECT p.oid
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'ops'
          AND p.proname = 'fn_real_trips_business_slice_resolved_subset'
        """
    )
    if cur.fetchone() is None:
        raise RuntimeError(
            "Falta ops.fn_real_trips_business_slice_resolved_subset. "
            "Aplique la migración Alembic 117_business_slice_resolved_subset_fn: "
            "cd backend && alembic upgrade head"
        )


def _sql_month_insert_from_fn() -> str:
    src = _MONTH_AGG_FROM_RESOLVED_SOURCE.format(
        resolved_source="ops.fn_real_trips_business_slice_resolved_subset(%s::date, %s, %s, %s, %s, %s)"
    )
    return f"INSERT INTO {FACT_MONTH} {src}"


def _delete_month_slice(
    cur: Any, target_month: date, country: Any, city: Any, country_only: bool
) -> None:
    if country_only:
        cur.execute(
            f"""
            DELETE FROM {FACT_MONTH}
            WHERE month = %s::date
              AND country IS NOT DISTINCT FROM %s
            """,
            (target_month, country),
        )
    else:
        cur.execute(
            f"""
            DELETE FROM {FACT_MONTH}
            WHERE month = %s::date
              AND country IS NOT DISTINCT FROM %s
              AND city IS NOT DISTINCT FROM %s
            """,
            (target_month, country, city),
        )


def _ensure_staging(cur: Any) -> None:
    cur.execute(_CREATE_STAGING_SQL)


def _truncate_staging(cur: Any) -> None:
    cur.execute("TRUNCATE _bs_month_load_staging")


def load_business_slice_month(
    cur: Any,
    target_month: date,
    conn: Optional[Any] = None,
    chunk_grain: Optional[str] = None,
) -> int:
    """
    Borra y recalcula un solo mes en ops.real_business_slice_month_fact.
    Retorna filas insertadas (suma de filas reportadas por INSERT; puede ser > filas finales
    si hay varios INSERT por chunk).

    La resolución business_slice ocurre dentro de ops.fn_real_trips_business_slice_resolved_subset,
    que filtra primero en v_real_trips_enriched_base.

    chunk_grain (o env BUSINESS_SLICE_MONTH_CHUNK_GRAIN): ``country``, ``city`` (defecto),
    ``city_week``, ``city_day``. Los dos últimos agrupan por (país, ciudad) y fragmentan el tiempo
    para reducir picos de memoria/temporales; la agregación final por ciudad es correcta vía staging.

    Si ``conn`` no es None y el modo va por chunks, hace COMMIT tras la purga mensual y tras cada chunk.
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)
    _require_resolved_subset_fn(cur)
    apply_business_slice_load_session_settings(cur)

    grain = _effective_chunk_grain(chunk_grain)
    insert_sql_fn = _sql_month_insert_from_fn()

    if not _month_load_use_country_chunks():
        cur.execute(f"DELETE FROM {FACT_MONTH} WHERE month = %s::date", (target_month,))
        deleted = cur.rowcount
        apply_business_slice_load_session_settings(cur)
        cur.execute(
            insert_sql_fn,
            (target_month, None, None, None, None, None, target_month),
        )
        inserted = cur.rowcount
        logger.info(
            "business_slice month load (single fn): month=%s deleted_rows=%s inserted_rows=%s",
            target_month,
            deleted,
            inserted,
        )
        print(
            f"month_fact {target_month}: modo monolítico (solo mes en enriched→fn), inserted={inserted}",
            flush=True,
        )
        return inserted

    cur.execute(f"DELETE FROM {FACT_MONTH} WHERE month = %s::date", (target_month,))
    deleted = cur.rowcount
    if conn is not None:
        conn.commit()

    inserted_total = 0
    t0 = time.perf_counter()

    if grain == "country":
        cur.execute(
            """
            SELECT DISTINCT country
            FROM ops.v_real_trips_enriched_base
            WHERE trip_month = %s::date
            ORDER BY 1 NULLS FIRST
            """,
            (target_month,),
        )
        pairs: List[Tuple[Any, ...]] = [(r[0],) for r in cur.fetchall()]
        n = len(pairs)
        print(
            f"month_fact {target_month}: {n} chunk(s) (country) — enriched→fn→aggregate; progreso:",
            flush=True,
        )
        for i, (c_country,) in enumerate(pairs):
            apply_business_slice_load_session_settings(cur)
            t_chunk = time.perf_counter()
            try:
                _delete_month_slice(cur, target_month, c_country, None, country_only=True)
                cur.execute(
                    insert_sql_fn,
                    (target_month, c_country, None, None, None, None, target_month),
                )
                rows = cur.rowcount
            except Exception as e:
                co = "∅" if c_country is None else str(c_country)
                raise RuntimeError(
                    f"business_slice month load falló en chunk [{i + 1}/{n}] "
                    f"month={target_month} country={co!r} city=(todos) grain=country: {e}"
                ) from e
            inserted_total += rows
            if conn is not None:
                conn.commit()
            co = "∅" if c_country is None else str(c_country)
            dt = time.perf_counter() - t_chunk
            print(
                f"  [{i + 1}/{n}] month={target_month} country={co!r} city=∅ inserted={rows} duration={dt:.1f}s",
                flush=True,
            )
            logger.info(
                "business_slice month chunk: month=%s grain=country idx=%s/%s rows_batch=%s",
                target_month,
                i + 1,
                n,
                rows,
            )

    elif grain == "city":
        cur.execute(
            """
            SELECT DISTINCT country, city
            FROM ops.v_real_trips_enriched_base
            WHERE trip_month = %s::date
            ORDER BY 1 NULLS FIRST, 2 NULLS FIRST
            """,
            (target_month,),
        )
        pairs = list(cur.fetchall())
        n = len(pairs)
        print(
            f"month_fact {target_month}: {n} chunk(s) (city) — enriched→fn→aggregate; progreso:",
            flush=True,
        )
        for i, (c_country, c_city) in enumerate(pairs):
            apply_business_slice_load_session_settings(cur)
            t_chunk = time.perf_counter()
            try:
                _delete_month_slice(cur, target_month, c_country, c_city, country_only=False)
                cur.execute(
                    insert_sql_fn,
                    (target_month, c_country, c_city, None, None, None, target_month),
                )
                rows = cur.rowcount
            except Exception as e:
                co = "∅" if c_country is None else str(c_country)
                ci = "∅" if c_city is None else str(c_city)
                raise RuntimeError(
                    f"business_slice month load falló en chunk [{i + 1}/{n}] "
                    f"month={target_month} country={co!r} city={ci!r} grain=city: {e}"
                ) from e
            inserted_total += rows
            if conn is not None:
                conn.commit()
            co = "∅" if c_country is None else str(c_country)
            ci = "∅" if c_city is None else str(c_city)
            dt = time.perf_counter() - t_chunk
            print(
                f"  [{i + 1}/{n}] month={target_month} country={co!r} city={ci!r} inserted={rows} duration={dt:.1f}s",
                flush=True,
            )
            logger.info(
                "business_slice month chunk: month=%s grain=city idx=%s/%s rows_batch=%s",
                target_month,
                i + 1,
                n,
                rows,
            )

    elif grain in ("city_week", "city_day"):
        _ensure_staging(cur)
        insert_from_staging = f"INSERT INTO {FACT_MONTH} {_MONTH_AGG_FROM_STAGING}"

        if grain == "city_week":
            cur.execute(
                """
                SELECT DISTINCT country, city, trip_week
                FROM ops.v_real_trips_enriched_base
                WHERE trip_month = %s::date
                ORDER BY 1 NULLS FIRST, 2 NULLS FIRST, 3 NULLS FIRST
                """,
                (target_month,),
            )
            raw_rows = cur.fetchall()
        else:
            cur.execute(
                """
                SELECT DISTINCT country, city, trip_date
                FROM ops.v_real_trips_enriched_base
                WHERE trip_month = %s::date
                ORDER BY 1 NULLS FIRST, 2 NULLS FIRST, 3 NULLS FIRST
                """,
                (target_month,),
            )
            raw_rows = cur.fetchall()

        by_city: dict[Tuple[Any, Any], List[Any]] = defaultdict(list)
        for row in raw_rows:
            c_country, c_city, tkey = row[0], row[1], row[2]
            by_city[(c_country, c_city)].append(tkey)

        city_keys = sorted(by_city.keys(), key=lambda x: (x[0] is None, x[0], x[1] is None, x[1]))
        n_cities = len(city_keys)
        sub_label = "semana ISO (trip_week)" if grain == "city_week" else "día (trip_date)"
        print(
            f"month_fact {target_month}: {n_cities} ciudad(es), subchunk por {sub_label}; progreso:",
            flush=True,
        )
        city_idx = 0
        for c_country, c_city in city_keys:
            city_idx += 1
            subkeys = sorted(by_city[(c_country, c_city)])
            n_sub = len(subkeys)
            apply_business_slice_load_session_settings(cur)
            t_city = time.perf_counter()
            try:
                _delete_month_slice(cur, target_month, c_country, c_city, country_only=False)
                _truncate_staging(cur)
                for j, tk in enumerate(subkeys):
                    apply_business_slice_load_session_settings(cur)
                    if grain == "city_week":
                        cur.execute(
                            _INSERT_STAGING_FROM_FN,
                            (target_month, c_country, c_city, tk, None, None),
                        )
                    else:
                        d_end = tk + timedelta(days=1)
                        cur.execute(
                            _INSERT_STAGING_FROM_FN,
                            (target_month, c_country, c_city, None, tk, d_end),
                        )
                    logger.info(
                        "business_slice month subchunk: month=%s grain=%s city=%s/%s sub=%s/%s staging_rows=%s",
                        target_month,
                        grain,
                        city_idx,
                        n_cities,
                        j + 1,
                        n_sub,
                        cur.rowcount,
                    )
                cur.execute(insert_from_staging, (target_month,))
                rows = cur.rowcount
            except Exception as e:
                co = "∅" if c_country is None else str(c_country)
                ci = "∅" if c_city is None else str(c_city)
                raise RuntimeError(
                    f"business_slice month load falló en ciudad [{city_idx}/{n_cities}] "
                    f"month={target_month} country={co!r} city={ci!r} grain={grain}: {e}"
                ) from e
            inserted_total += rows
            if conn is not None:
                conn.commit()
            co = "∅" if c_country is None else str(c_country)
            ci = "∅" if c_city is None else str(c_city)
            dt = time.perf_counter() - t_city
            print(
                f"  [{city_idx}/{n_cities}] month={target_month} country={co!r} city={ci!r} "
                f"inserted={rows} subchunks={n_sub} duration={dt:.1f}s",
                flush=True,
            )

    else:
        raise ValueError(
            f"chunk_grain no soportado: {grain!r}. "
            "Use country | city | city_week | city_day (o variable BUSINESS_SLICE_MONTH_CHUNK_GRAIN)."
        )

    logger.info(
        "business_slice month load (chunked fn): month=%s deleted_rows=%s inserted_rows=%s grain=%s duration_s=%.1f",
        target_month,
        deleted,
        inserted_total,
        grain,
        time.perf_counter() - t0,
    )
    return inserted_total


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
    chunk_grain: Optional[str] = None,
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
        total_rows += load_business_slice_month(cur, d, conn, chunk_grain=chunk_grain)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return total_rows, months


def describe_month_load_sql_contract() -> dict[str, bool]:
    """
    Comprobaciones estáticas (sin BD) para validar que el camino mensual no escanea la vista resolved global.
    """
    month_sql = (
        _MONTH_AGG_FROM_RESOLVED_SOURCE
        + _MONTH_AGG_FROM_STAGING
        + _INSERT_STAGING_FROM_FN
        + _sql_month_insert_from_fn()
    )
    return {
        "month_path_uses_fn_subset": "fn_real_trips_business_slice_resolved_subset" in month_sql,
        "month_path_avoids_global_resolved_view": "v_real_trips_business_slice_resolved"
        not in month_sql,
        "hour_block_still_uses_resolved_view": "v_real_trips_business_slice_resolved"
        in _HOUR_AGG_SELECT,
    }
