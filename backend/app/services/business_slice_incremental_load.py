"""
Carga incremental BUSINESS_SLICE: mes (DELETE+INSERT) y hora (bloque temporal).

Carga mensual — estrategia "materializar una vez, agregar N veces":
1. Pre-materializa ops.v_real_trips_enriched_base del mes en un TEMP TABLE indexado
   (UN solo scan de la vista pesada con UNION ALL + DISTINCT ON + JOINs).
2. Descubre chunks (country/city) desde el temp table (rápido, ya materializado).
3. Para cada chunk: resolución inline (mismas CTEs que fn 117) leyendo del temp table
   + agregación + INSERT en month_fact + COMMIT + print progreso.
4. DROP temp table.

Función SQL ops.fn_real_trips_business_slice_resolved_subset (migración 117) se
mantiene para auditorías y consultas ad-hoc; la carga mensual ya no la invoca.

Grano horario: ops.real_business_slice_hour_fact (sigue usando la vista resolved
acotada por rango de trip_hour_start; ver docs/BUSINESS_SLICE_HOURLY_FIRST.md).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime
from typing import Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

FACT_MONTH = "ops.real_business_slice_month_fact"
FACT_HOUR = "ops.real_business_slice_hour_fact"
FACT_DAY = "ops.real_business_slice_day_fact"
FACT_WEEK = "ops.real_business_slice_week_fact"

# ---------------------------------------------------------------------------
# SQL: resolución inline desde temp table + agregación mensual
# ---------------------------------------------------------------------------

_RESOLVE_AND_AGG_FROM_TEMP = """
INSERT INTO {fact_month}
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
    now() AS loaded_at,
    sum(r.revenue_yego_final) FILTER (WHERE r.completed_flag) AS revenue_yego_final,
    CASE
        WHEN count(*) FILTER (WHERE r.completed_flag) > 0
        THEN ROUND(
            100.0 * count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')
            / count(*) FILTER (WHERE r.completed_flag), 2
        )
        ELSE NULL
    END AS revenue_real_coverage_pct,
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'proxy')::bigint AS revenue_proxy_trips,
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')::bigint AS revenue_real_trips
FROM (
    WITH base AS (
        SELECT * FROM _bs_enriched_month
        WHERE country IS NOT DISTINCT FROM %s
          AND city IS NOT DISTINCT FROM %s
    ),
    rules AS (
        SELECT *
        FROM ops.business_slice_mapping_rules
        WHERE is_active
    ),
    m AS (
        SELECT
            b.trip_id,
            b.driver_id,
            b.park_id,
            b.park_name,
            b.country,
            b.city,
            b.tipo_servicio,
            b.works_terms,
            b.completed_flag,
            b.cancelled_flag,
            b.trip_date,
            b.trip_month,
            b.trip_week,
            b.hour_of_day,
            b.trip_hour_start,
            b.revenue_yego_net,
            b.ticket,
            b.km,
            b.duration_minutes,
            b.gmv_passenger_paid,
            b.total_fare,
            b.condicion,
            b.source_table,
            rl.id AS mapping_rule_id,
            rl.business_slice_name,
            rl.fleet_display_name,
            rl.is_subfleet,
            rl.subfleet_name,
            rl.parent_fleet_name,
            rl.rule_type,
            CASE rl.rule_type
                WHEN 'park_plus_works_terms' THEN 3
                WHEN 'park_plus_tipo_servicio' THEN 2
                WHEN 'park_only' THEN 1
                ELSE 0
            END AS spec_score
        FROM base b
        INNER JOIN rules rl
            ON lower(trim(b.park_id::text)) = lower(trim(rl.park_id::text))
        WHERE (
            rl.rule_type = 'park_only'
        )
        OR (
            rl.rule_type = 'park_plus_tipo_servicio'
            AND EXISTS (
                SELECT 1
                FROM unnest(rl.tipo_servicio_values) v
                WHERE nullif(trim(v::text), '') IS NOT NULL
                  AND ops.normalized_service_type(b.tipo_servicio::text)
                      = ops.normalized_service_type(v::text)
            )
        )
        OR (
            rl.rule_type = 'park_plus_works_terms'
            AND EXISTS (
                SELECT 1
                FROM unnest(rl.works_terms_values) w
                WHERE nullif(trim(w::text), '') IS NOT NULL
                  AND (
                    ops.normalized_works_terms(b.works_terms::text)
                        = ops.normalized_works_terms(w::text)
                    OR ops.normalized_works_terms(b.works_terms::text)
                        LIKE '%%' || ops.normalized_works_terms(w::text) || '%%'
                  )
            )
        )
    ),
    mx AS (
        SELECT trip_id, max(spec_score) AS max_spec
        FROM m
        GROUP BY trip_id
    ),
    best AS (
        SELECT m.*
        FROM m
        INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
    ),
    outcome AS (
        SELECT
            trip_id,
            count(DISTINCT business_slice_name) AS n_slices,
            array_agg(DISTINCT mapping_rule_id) AS rule_ids,
            array_agg(DISTINCT business_slice_name) AS slice_names
        FROM best
        GROUP BY trip_id
    ),
    winner AS (
        SELECT DISTINCT ON (trip_id)
            trip_id,
            mapping_rule_id,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            parent_fleet_name,
            rule_type,
            spec_score
        FROM best
        ORDER BY
            trip_id,
            is_subfleet ASC,
            parent_fleet_name NULLS FIRST,
            fleet_display_name ASC,
            mapping_rule_id ASC
    )
    SELECT
        b.trip_id,
        b.driver_id,
        b.park_id,
        b.park_name,
        b.country,
        b.city,
        b.tipo_servicio,
        b.works_terms,
        b.completed_flag,
        b.cancelled_flag,
        b.trip_date,
        b.trip_month,
        b.trip_week,
        b.hour_of_day,
        b.trip_hour_start,
        b.revenue_yego_net,
        b.ticket,
        b.km,
        b.duration_minutes,
        b.gmv_passenger_paid,
        b.total_fare,
        b.condicion,
        b.source_table,
        b.revenue_source,
        b.revenue_yego_final,
        CASE
            WHEN o.trip_id IS NULL THEN 'unmatched'
            WHEN o.n_slices > 1 THEN 'conflict'
            ELSE 'resolved'
        END AS resolution_status,
        w.mapping_rule_id,
        COALESCE(w.business_slice_name, '__UNMATCHED__') AS business_slice_name,
        w.fleet_display_name,
        COALESCE(w.is_subfleet, false) AS is_subfleet,
        w.subfleet_name,
        w.parent_fleet_name,
        w.rule_type AS matched_rule_type,
        o.n_slices AS conflict_slice_count,
        o.rule_ids AS conflict_rule_ids,
        o.slice_names AS conflict_slice_names
    FROM base b
    LEFT JOIN outcome o ON b.trip_id = o.trip_id
    LEFT JOIN winner w
        ON b.trip_id = w.trip_id
        AND o.trip_id IS NOT NULL
        AND o.n_slices = 1
) r
WHERE r.resolution_status = 'resolved'
  AND r.trip_month IS NOT NULL
  AND r.business_slice_name IS NOT NULL
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

# ---------------------------------------------------------------------------
# SQL: day_fact — resolución inline desde temp table, grano diario
# ---------------------------------------------------------------------------

_RESOLVE_AND_AGG_DAY_FROM_TEMP = """
INSERT INTO {fact_day}
SELECT
    r.trip_date,
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
    avg(r.ticket) FILTER (WHERE r.completed_flag AND r.ticket IS NOT NULL) AS avg_ticket,
    CASE
        WHEN sum(r.total_fare) FILTER (WHERE r.completed_flag AND r.total_fare IS NOT NULL AND r.total_fare > 0) > 0
        THEN sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag AND r.total_fare IS NOT NULL AND r.total_fare > 0)
            / sum(r.total_fare) FILTER (WHERE r.completed_flag AND r.total_fare IS NOT NULL AND r.total_fare > 0)
        ELSE NULL
    END AS commission_pct,
    CASE
        WHEN count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) > 0
        THEN count(*) FILTER (WHERE r.completed_flag)::numeric
            / count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)
        ELSE NULL
    END AS trips_per_driver,
    sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_net,
    CASE
        WHEN (count(*) FILTER (WHERE r.completed_flag) + count(*) FILTER (WHERE r.cancelled_flag)) > 0
        THEN count(*) FILTER (WHERE r.cancelled_flag)::numeric
            / (count(*) FILTER (WHERE r.completed_flag) + count(*) FILTER (WHERE r.cancelled_flag))
        ELSE NULL
    END AS cancel_rate_pct,
    now() AS refreshed_at,
    now() AS loaded_at,
    sum(r.revenue_yego_final) FILTER (WHERE r.completed_flag) AS revenue_yego_final,
    CASE
        WHEN count(*) FILTER (WHERE r.completed_flag) > 0
        THEN ROUND(
            100.0 * count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')
            / count(*) FILTER (WHERE r.completed_flag), 2
        )
        ELSE NULL
    END AS revenue_real_coverage_pct,
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'proxy')::bigint AS revenue_proxy_trips,
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')::bigint AS revenue_real_trips
FROM (
    WITH base AS (
        SELECT * FROM _bs_enriched_month
        WHERE country IS NOT DISTINCT FROM %s
          AND city IS NOT DISTINCT FROM %s
    ),
    rules AS (
        SELECT * FROM ops.business_slice_mapping_rules WHERE is_active
    ),
    m AS (
        SELECT
            b.trip_id, b.driver_id, b.park_id, b.park_name,
            b.country, b.city, b.tipo_servicio, b.works_terms,
            b.completed_flag, b.cancelled_flag, b.trip_date, b.trip_month,
            b.trip_week, b.hour_of_day, b.trip_hour_start,
            b.revenue_yego_net, b.ticket, b.km, b.duration_minutes,
            b.gmv_passenger_paid, b.total_fare, b.condicion, b.source_table,
            rl.id AS mapping_rule_id, rl.business_slice_name, rl.fleet_display_name,
            rl.is_subfleet, rl.subfleet_name, rl.parent_fleet_name, rl.rule_type,
            CASE rl.rule_type
                WHEN 'park_plus_works_terms' THEN 3
                WHEN 'park_plus_tipo_servicio' THEN 2
                WHEN 'park_only' THEN 1 ELSE 0
            END AS spec_score
        FROM base b
        INNER JOIN rules rl ON lower(trim(b.park_id::text)) = lower(trim(rl.park_id::text))
        WHERE (rl.rule_type = 'park_only')
        OR (rl.rule_type = 'park_plus_tipo_servicio'
            AND EXISTS (SELECT 1 FROM unnest(rl.tipo_servicio_values) v
                WHERE nullif(trim(v::text), '') IS NOT NULL
                  AND ops.normalized_service_type(b.tipo_servicio::text) = ops.normalized_service_type(v::text)))
        OR (rl.rule_type = 'park_plus_works_terms'
            AND EXISTS (SELECT 1 FROM unnest(rl.works_terms_values) w
                WHERE nullif(trim(w::text), '') IS NOT NULL
                  AND (ops.normalized_works_terms(b.works_terms::text) = ops.normalized_works_terms(w::text)
                       OR ops.normalized_works_terms(b.works_terms::text) LIKE '%%' || ops.normalized_works_terms(w::text) || '%%')))
    ),
    mx AS (SELECT trip_id, max(spec_score) AS max_spec FROM m GROUP BY trip_id),
    best AS (SELECT m.* FROM m INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec),
    outcome AS (
        SELECT trip_id, count(DISTINCT business_slice_name) AS n_slices,
            array_agg(DISTINCT mapping_rule_id) AS rule_ids,
            array_agg(DISTINCT business_slice_name) AS slice_names
        FROM best GROUP BY trip_id
    ),
    winner AS (
        SELECT DISTINCT ON (trip_id)
            trip_id, mapping_rule_id, business_slice_name, fleet_display_name,
            is_subfleet, subfleet_name, parent_fleet_name, rule_type, spec_score
        FROM best
        ORDER BY trip_id, is_subfleet ASC, parent_fleet_name NULLS FIRST, fleet_display_name ASC, mapping_rule_id ASC
    )
    SELECT
        b.trip_id, b.driver_id, b.park_id, b.park_name,
        b.country, b.city, b.tipo_servicio, b.works_terms,
        b.completed_flag, b.cancelled_flag, b.trip_date, b.trip_month,
        b.trip_week, b.hour_of_day, b.trip_hour_start,
        b.revenue_yego_net, b.ticket, b.km, b.duration_minutes,
        b.gmv_passenger_paid, b.total_fare, b.condicion, b.source_table,
        b.revenue_source, b.revenue_yego_final,
        CASE WHEN o.trip_id IS NULL THEN 'unmatched' WHEN o.n_slices > 1 THEN 'conflict' ELSE 'resolved' END AS resolution_status,
        w.mapping_rule_id,
        COALESCE(w.business_slice_name, '__UNMATCHED__') AS business_slice_name,
        w.fleet_display_name,
        COALESCE(w.is_subfleet, false) AS is_subfleet,
        w.subfleet_name, w.parent_fleet_name,
        w.rule_type AS matched_rule_type,
        o.n_slices AS conflict_slice_count, o.rule_ids AS conflict_rule_ids, o.slice_names AS conflict_slice_names
    FROM base b
    LEFT JOIN outcome o ON b.trip_id = o.trip_id
    LEFT JOIN winner w ON b.trip_id = w.trip_id AND o.trip_id IS NOT NULL AND o.n_slices = 1
) r
WHERE r.resolution_status = 'resolved'
  AND r.trip_date IS NOT NULL
  AND r.business_slice_name IS NOT NULL
GROUP BY
    r.trip_date,
    r.country, r.city, r.business_slice_name, r.fleet_display_name,
    r.is_subfleet, r.subfleet_name, r.parent_fleet_name
"""

# ---------------------------------------------------------------------------
# SQL: week_fact — rollup desde day_fact (NO desde trips crudos)
# ---------------------------------------------------------------------------

_WEEK_ROLLUP_FROM_DAY_FACT = """
INSERT INTO {fact_week}
SELECT
    date_trunc('week', d.trip_date)::date AS week_start,
    d.country,
    d.city,
    d.business_slice_name,
    d.fleet_display_name,
    d.is_subfleet,
    d.subfleet_name,
    d.parent_fleet_name,
    sum(d.trips_completed)::bigint AS trips_completed,
    sum(d.trips_cancelled)::bigint AS trips_cancelled,
    sum(d.active_drivers)::bigint AS active_drivers,
    CASE WHEN sum(d.trips_completed) > 0
         THEN sum(d.avg_ticket * d.trips_completed) / sum(d.trips_completed)
         ELSE NULL
    END AS avg_ticket,
    CASE WHEN sum(d.revenue_yego_net) > 0
         THEN avg(d.commission_pct)
         ELSE NULL
    END AS commission_pct,
    CASE WHEN sum(d.active_drivers) > 0
         THEN sum(d.trips_completed)::numeric / sum(d.active_drivers)
         ELSE NULL
    END AS trips_per_driver,
    sum(d.revenue_yego_net) AS revenue_yego_net,
    CASE WHEN (sum(d.trips_completed) + sum(d.trips_cancelled)) > 0
         THEN sum(d.trips_cancelled)::numeric / (sum(d.trips_completed) + sum(d.trips_cancelled))
         ELSE NULL
    END AS cancel_rate_pct,
    now() AS refreshed_at,
    now() AS loaded_at,
    sum(d.revenue_yego_final) AS revenue_yego_final,
    CASE WHEN sum(d.trips_completed) > 0
         THEN ROUND(100.0 * sum(COALESCE(d.revenue_real_trips, 0)) / sum(d.trips_completed), 2)
         ELSE NULL
    END AS revenue_real_coverage_pct,
    sum(COALESCE(d.revenue_proxy_trips, 0))::bigint AS revenue_proxy_trips,
    sum(COALESCE(d.revenue_real_trips, 0))::bigint AS revenue_real_trips
FROM {fact_day} d
WHERE d.trip_date >= %s::date AND d.trip_date < %s::date
GROUP BY
    date_trunc('week', d.trip_date),
    d.country, d.city, d.business_slice_name, d.fleet_display_name,
    d.is_subfleet, d.subfleet_name, d.parent_fleet_name
"""

# ---------------------------------------------------------------------------
# SQL: hour_fact (sin cambios, sigue usando vista resolved acotada por rango)
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def month_first_day(year: int, month: int) -> date:
    return date(year, month, 1)


def apply_business_slice_load_session_settings(cur: Any) -> None:
    """
    Ajustes de sesión para cargas BUSINESS_SLICE (sorts/hashes y temporales).

    BUSINESS_SLICE_LOAD_WORK_MEM: ej. 256MB, 512MB. Por defecto 256MB.
    BUSINESS_SLICE_LOAD_WORK_MEM=0 / off / false — no modificar work_mem.

    BUSINESS_SLICE_LOAD_TEMP_TABLESPACES: tablespaces separados por coma (p. ej. ``pg_big_tmp``).
    Requiere haber creado antes el TABLESPACE en el servidor (directorio en disco grande, propietario postgres).

    BUSINESS_SLICE_LOAD_JIT_OFF: 1/true/on — ``SET LOCAL jit = off``.
    """
    raw_wm = os.environ.get("BUSINESS_SLICE_LOAD_WORK_MEM", "256MB").strip()
    if raw_wm not in ("0", "", "off", "false"):
        cur.execute("SET LOCAL work_mem = %s", (raw_wm,))

    ts = os.environ.get("BUSINESS_SLICE_LOAD_TEMP_TABLESPACES", "").strip()
    if ts:
        cur.execute("SET LOCAL temp_tablespaces = %s", (ts,))

    jit_off = os.environ.get("BUSINESS_SLICE_LOAD_JIT_OFF", "").strip().lower()
    if jit_off in ("1", "true", "on", "yes"):
        cur.execute("SET LOCAL jit = off")

    # Evita cortes por statement_timeout del rol/pool durante chunks largos (carga completa del mes).
    if os.environ.get("BUSINESS_SLICE_LOAD_RESPECT_STMT_TIMEOUT", "").strip().lower() not in (
        "1",
        "true",
        "on",
        "yes",
    ):
        cur.execute("SET LOCAL statement_timeout = 0")


def _effective_chunk_grain(cli_grain: Optional[str]) -> str:
    if cli_grain is not None and cli_grain.strip():
        return cli_grain.strip().lower()
    return os.environ.get("BUSINESS_SLICE_MONTH_CHUNK_GRAIN", "city").strip().lower()


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


# ---------------------------------------------------------------------------
# Materialización enriched (UN solo scan de la vista pesada)
# ---------------------------------------------------------------------------


def _materialize_enriched_for_month(
    cur: Any, target_month: date, conn: Optional[Any]
) -> int:
    """
    Pre-materializa ops.v_real_trips_enriched_base del mes objetivo
    en un TEMP TABLE ``_bs_enriched_month``, con índices.
    Retorna filas materializadas.

    Incluye filtro explícito por trip_date (rango del mes) para que
    PostgreSQL pueda descartar particiones/filas antes del DISTINCT ON
    del view subyacente.
    """
    import calendar

    print(
        f"  materializando enriched base para {target_month} ...",
        flush=True,
    )
    t0 = time.perf_counter()
    apply_business_slice_load_session_settings(cur)
    cur.execute("DROP TABLE IF EXISTS _bs_enriched_month")

    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    month_end_exclusive = date(
        target_month.year + (1 if target_month.month == 12 else 0),
        1 if target_month.month == 12 else target_month.month + 1,
        1,
    )
    cur.execute(
        """
        CREATE TEMP TABLE _bs_enriched_month AS
        SELECT e.*,
            CASE
                WHEN e.completed_flag AND e.revenue_yego_net IS NOT NULL
                THEN ABS(e.revenue_yego_net)
                ELSE NULL
            END AS revenue_yego_real,
            CASE
                WHEN e.completed_flag AND e.ticket IS NOT NULL AND e.ticket > 0
                THEN e.ticket * COALESCE(
                    ops.resolve_commission_pct(e.country, e.city, e.park_id, e.tipo_servicio, e.trip_date),
                    0.03
                )
                ELSE NULL
            END AS revenue_yego_proxy,
            CASE
                WHEN e.completed_flag AND e.revenue_yego_net IS NOT NULL
                THEN ABS(e.revenue_yego_net)
                WHEN e.completed_flag AND e.ticket IS NOT NULL AND e.ticket > 0
                THEN e.ticket * COALESCE(
                    ops.resolve_commission_pct(e.country, e.city, e.park_id, e.tipo_servicio, e.trip_date),
                    0.03
                )
                ELSE NULL
            END AS revenue_yego_final,
            CASE
                WHEN NOT e.completed_flag THEN NULL
                WHEN e.revenue_yego_net IS NOT NULL THEN 'real'
                WHEN e.ticket IS NOT NULL AND e.ticket > 0 THEN 'proxy'
                ELSE 'missing'
            END AS revenue_source
        FROM ops.v_real_trips_enriched_base e
        WHERE e.trip_month = %s::date
          AND e.trip_date >= %s::date
          AND e.trip_date < %s::date
        """,
        (target_month, target_month, month_end_exclusive),
    )
    mat_rows = cur.rowcount
    cur.execute(
        "CREATE INDEX _bsem_geo ON _bs_enriched_month (country, city)"
    )
    cur.execute(
        "CREATE INDEX _bsem_park ON _bs_enriched_month (park_id)"
    )
    cur.execute("ANALYZE _bs_enriched_month")
    dt = time.perf_counter() - t0
    print(
        f"  enriched materializado: {mat_rows} viajes en {dt:.1f}s",
        flush=True,
    )
    if conn is not None:
        conn.commit()
    return mat_rows


def _drop_enriched_temp(cur: Any) -> None:
    cur.execute("DROP TABLE IF EXISTS _bs_enriched_month")


# ---------------------------------------------------------------------------
# Loader mensual principal
# ---------------------------------------------------------------------------


def load_business_slice_month(
    cur: Any,
    target_month: date,
    conn: Optional[Any] = None,
    chunk_grain: Optional[str] = None,
) -> int:
    """
    Borra y recalcula un solo mes en ops.real_business_slice_month_fact.

    Estrategia "materializar una vez, agregar N veces":
    1. DELETE del mes + COMMIT
    2. Pre-materializar enriched del mes en temp table + COMMIT
    3. Descubrir chunks (country o country+city) desde el temp table
    4. Para cada chunk: resolución inline desde temp table → agregación → INSERT + COMMIT
    5. DROP temp table

    chunk_grain: ``country``, ``city`` (defecto), ``city_week``, ``city_day``.
    Los granos city_week / city_day se comportan igual que city (la materialización
    ya eliminó el cuello de botella de re-evaluar la vista por subchunk).
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)

    grain = _effective_chunk_grain(chunk_grain)
    if grain not in ("country", "city", "city_week", "city_day"):
        raise ValueError(
            f"chunk_grain no soportado: {grain!r}. "
            "Use country | city | city_week | city_day."
        )

    resolve_sql = _RESOLVE_AND_AGG_FROM_TEMP.format(fact_month=FACT_MONTH)

    apply_business_slice_load_session_settings(cur)

    # --- Paso 1: purga del mes ---
    cur.execute(f"DELETE FROM {FACT_MONTH} WHERE month = %s::date", (target_month,))
    deleted = cur.rowcount
    if conn is not None:
        conn.commit()
    print(
        f"month_fact {target_month}: deleted={deleted}; grain={grain}",
        flush=True,
    )

    # --- Paso 2: materializar enriched ---
    mat_rows = _materialize_enriched_for_month(cur, target_month, conn)
    if mat_rows == 0:
        print(
            f"  enriched vacío para {target_month}: no hay viajes → 0 filas insertadas.",
            flush=True,
        )
        _drop_enriched_temp(cur)
        return 0

    t0 = time.perf_counter()
    inserted_total = 0

    # --- Paso 3: descubrir chunks desde temp table ---
    use_country_only = grain == "country"

    if use_country_only:
        cur.execute(
            """
            SELECT DISTINCT country
            FROM _bs_enriched_month
            ORDER BY 1 NULLS FIRST
            """
        )
        chunks: List[Tuple[Any, ...]] = [(r[0], None) for r in cur.fetchall()]
    else:
        cur.execute(
            """
            SELECT DISTINCT country, city
            FROM _bs_enriched_month
            ORDER BY 1 NULLS FIRST, 2 NULLS FIRST
            """
        )
        chunks = list(cur.fetchall())

    n = len(chunks)
    chunk_label = "country" if use_country_only else "city"
    print(
        f"  {n} chunk(s) ({chunk_label}) — resolución inline desde temp table; progreso:",
        flush=True,
    )

    # --- Paso 4: resolver + agregar por chunk ---
    for i, chunk in enumerate(chunks):
        c_country = chunk[0]
        c_city = chunk[1] if len(chunk) > 1 else None

        apply_business_slice_load_session_settings(cur)
        t_chunk = time.perf_counter()
        try:
            _delete_month_slice(
                cur, target_month, c_country, c_city, country_only=use_country_only
            )
            cur.execute(resolve_sql, (c_country, c_city))
            rows = cur.rowcount
        except Exception as e:
            co = "∅" if c_country is None else str(c_country)
            ci = "∅" if c_city is None else str(c_city)
            _drop_enriched_temp(cur)
            raise RuntimeError(
                f"business_slice month load falló en chunk [{i + 1}/{n}] "
                f"month={target_month} country={co!r} city={ci!r} grain={grain}: {e}"
            ) from e
        inserted_total += rows
        if conn is not None:
            conn.commit()
        co = "∅" if c_country is None else str(c_country)
        ci = "∅" if c_city is None else str(c_city)
        dt = time.perf_counter() - t_chunk
        print(
            f"  [{i + 1}/{n}] month={target_month} country={co!r} city={ci!r} "
            f"inserted={rows} duration={dt:.1f}s",
            flush=True,
        )
        logger.info(
            "business_slice month chunk: month=%s grain=%s idx=%s/%s rows=%s",
            target_month, grain, i + 1, n, rows,
        )

    # --- Paso 5: limpiar ---
    _drop_enriched_temp(cur)

    total_dt = time.perf_counter() - t0
    logger.info(
        "business_slice month load: month=%s deleted=%s inserted=%s grain=%s mat_rows=%s duration_s=%.1f",
        target_month, deleted, inserted_total, grain, mat_rows, total_dt,
    )
    print(
        f"  TOTAL month_fact {target_month}: inserted={inserted_total} duration={total_dt:.1f}s",
        flush=True,
    )
    return inserted_total


# ---------------------------------------------------------------------------
# day_fact loader
# ---------------------------------------------------------------------------


def load_business_slice_day_for_month(
    cur: Any,
    target_month: date,
    conn: Optional[Any] = None,
    chunk_grain: Optional[str] = None,
) -> int:
    """
    Calcula day_fact para un mes completo. Reutiliza la misma estrategia
    de materialización enriched del loader mensual.
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)

    grain = _effective_chunk_grain(chunk_grain)
    resolve_sql = _RESOLVE_AND_AGG_DAY_FROM_TEMP.format(fact_day=FACT_DAY)

    apply_business_slice_load_session_settings(cur)

    import calendar
    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    end_date = date(target_month.year, target_month.month, last_day)

    cur.execute(
        f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s::date AND trip_date <= %s::date",
        (target_month, end_date),
    )
    deleted = cur.rowcount
    if conn is not None:
        conn.commit()
    print(f"day_fact {target_month}: deleted={deleted}; grain={grain}", flush=True)

    mat_rows = _materialize_enriched_for_month(cur, target_month, conn)
    if mat_rows == 0:
        print(f"  enriched vacío para {target_month}: 0 filas → day_fact.", flush=True)
        _drop_enriched_temp(cur)
        return 0

    t0 = time.perf_counter()
    inserted_total = 0
    use_country_only = grain == "country"

    if use_country_only:
        cur.execute("SELECT DISTINCT country FROM _bs_enriched_month ORDER BY 1 NULLS FIRST")
        chunks: List[Tuple[Any, ...]] = [(r[0], None) for r in cur.fetchall()]
    else:
        cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
        chunks = list(cur.fetchall())

    n = len(chunks)
    print(f"  {n} chunk(s) — day_fact resolución inline desde temp table", flush=True)

    for i, chunk in enumerate(chunks):
        c_country, c_city = chunk[0], chunk[1] if len(chunk) > 1 else None
        apply_business_slice_load_session_settings(cur)
        t_chunk = time.perf_counter()
        try:
            if use_country_only:
                cur.execute(
                    f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s AND trip_date <= %s AND country IS NOT DISTINCT FROM %s",
                    (target_month, end_date, c_country),
                )
            else:
                cur.execute(
                    f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s AND trip_date <= %s AND country IS NOT DISTINCT FROM %s AND city IS NOT DISTINCT FROM %s",
                    (target_month, end_date, c_country, c_city),
                )
            cur.execute(resolve_sql, (c_country, c_city))
            rows = cur.rowcount
        except Exception as e:
            _drop_enriched_temp(cur)
            raise RuntimeError(f"day_fact load falló chunk [{i+1}/{n}] month={target_month}: {e}") from e
        inserted_total += rows
        if conn is not None:
            conn.commit()
        dt = time.perf_counter() - t_chunk
        print(f"  [{i+1}/{n}] day_fact country={c_country!r} city={c_city!r} inserted={rows} {dt:.1f}s", flush=True)

    _drop_enriched_temp(cur)
    total_dt = time.perf_counter() - t0
    print(f"  TOTAL day_fact {target_month}: inserted={inserted_total} {total_dt:.1f}s", flush=True)
    return inserted_total


# ---------------------------------------------------------------------------
# week_fact loader (rollup from day_fact — NO desde trips crudos)
# ---------------------------------------------------------------------------


def load_business_slice_week_for_month(
    cur: Any,
    target_month: date,
    conn: Optional[Any] = None,
) -> int:
    """
    Calcula week_fact para todas las semanas que tocan el mes objetivo.
    Rollup directo desde day_fact (no escanea vista resolved).
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)

    import calendar
    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    end_date = date(target_month.year, target_month.month, last_day)

    first_monday = target_month - __import__('datetime').timedelta(days=target_month.weekday())
    next_monday_after_end = end_date + __import__('datetime').timedelta(days=(7 - end_date.weekday()) % 7 or 7)

    apply_business_slice_load_session_settings(cur)

    cur.execute(
        f"DELETE FROM {FACT_WEEK} WHERE week_start >= %s::date AND week_start < %s::date",
        (first_monday, next_monday_after_end),
    )
    deleted = cur.rowcount

    rollup_sql = _WEEK_ROLLUP_FROM_DAY_FACT.format(fact_week=FACT_WEEK, fact_day=FACT_DAY)
    cur.execute(rollup_sql, (first_monday, next_monday_after_end))
    inserted = cur.rowcount

    if conn is not None:
        conn.commit()
    print(
        f"  week_fact [{first_monday}..{next_monday_after_end}): deleted={deleted} inserted={inserted}",
        flush=True,
    )
    return inserted


# ---------------------------------------------------------------------------
# hour_fact (sin cambios en esta iteración)
# ---------------------------------------------------------------------------


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
        range_start, range_end, inserted,
    )
    return inserted


# ---------------------------------------------------------------------------
# backfill
# ---------------------------------------------------------------------------


def backfill_business_slice_months(
    cur: Any,
    start: date,
    end: date,
    conn: Optional[Any] = None,
    chunk_grain: Optional[str] = None,
    with_daily: bool = True,
) -> Tuple[int, list[date]]:
    """
    Recorre meses civiles [start, end] (inclusive en mes de inicio y fin).
    Normaliza a primer día de cada mes.
    Con with_daily=True (default) también genera day_fact y week_fact.
    Retorna (total_filas_insertadas_month, lista_meses_procesados).
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
        if with_daily:
            nd = load_business_slice_day_for_month(cur, d, conn, chunk_grain=chunk_grain)
            nw = load_business_slice_week_for_month(cur, d, conn)
            logger.info(
                "backfill day/week: month=%s day_rows=%s week_rows=%s",
                d, nd, nw,
            )
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1
    return total_rows, months


# ---------------------------------------------------------------------------
# Contrato estático (validación sin BD)
# ---------------------------------------------------------------------------


def describe_month_load_sql_contract() -> dict[str, bool]:
    """
    Comprobaciones estáticas para validar que el camino mensual no escanea
    la vista resolved global ni la función subset en el tramo de agregación.
    """
    return {
        "month_path_uses_temp_table": "_bs_enriched_month" in _RESOLVE_AND_AGG_FROM_TEMP,
        "month_path_avoids_global_resolved_view": "v_real_trips_business_slice_resolved"
        not in _RESOLVE_AND_AGG_FROM_TEMP,
        "month_path_avoids_fn_subset": "fn_real_trips_business_slice_resolved_subset"
        not in _RESOLVE_AND_AGG_FROM_TEMP,
        "hour_block_still_uses_resolved_view": "v_real_trips_business_slice_resolved"
        in _HOUR_AGG_SELECT,
    }
