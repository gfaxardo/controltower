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
from datetime import date, datetime, timedelta
from typing import Any, List, Optional, Tuple

from app.db.connection import get_db

logger = logging.getLogger(__name__)

FACT_MONTH = "ops.real_business_slice_month_fact"
FACT_HOUR = "ops.real_business_slice_hour_fact"
FACT_DAY = "ops.real_business_slice_day_fact"
FACT_WEEK = "ops.real_business_slice_week_fact"
V_RESOLVED = "ops.v_real_trips_business_slice_resolved"

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
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')::bigint AS revenue_real_trips,
    sum(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    ) AS ticket_sum_completed,
    count(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    )::bigint AS ticket_count_completed,
    sum(r.total_fare) FILTER (
        WHERE r.completed_flag
          AND r.total_fare IS NOT NULL
          AND r.total_fare > 0
    ) AS total_fare_completed_positive_sum
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
            b.revenue_yego_real AS revenue_yego_net,
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
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')::bigint AS revenue_real_trips,
    sum(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    ) AS ticket_sum_completed,
    count(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    )::bigint AS ticket_count_completed,
    sum(r.total_fare) FILTER (
        WHERE r.completed_flag
          AND r.total_fare IS NOT NULL
          AND r.total_fare > 0
    ) AS total_fare_completed_positive_sum
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
            b.revenue_yego_real AS revenue_yego_net, b.ticket, b.km, b.duration_minutes,
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
        b.revenue_yego_real AS revenue_yego_net,
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
  AND r.trip_date IS NOT NULL
  AND r.business_slice_name IS NOT NULL
GROUP BY
    r.trip_date,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name
ON CONFLICT (trip_date, COALESCE(country, ''::text), COALESCE(city, ''::text), business_slice_name, COALESCE(fleet_display_name, ''::text), is_subfleet, COALESCE(subfleet_name, ''::text), COALESCE(parent_fleet_name, ''::text))
DO UPDATE SET
    trips_completed = EXCLUDED.trips_completed,
    trips_cancelled = EXCLUDED.trips_cancelled,
    active_drivers = EXCLUDED.active_drivers,
    avg_ticket = EXCLUDED.avg_ticket,
    commission_pct = EXCLUDED.commission_pct,
    trips_per_driver = EXCLUDED.trips_per_driver,
    revenue_yego_net = EXCLUDED.revenue_yego_net,
    cancel_rate_pct = EXCLUDED.cancel_rate_pct,
    refreshed_at = EXCLUDED.refreshed_at,
    loaded_at = EXCLUDED.loaded_at,
    revenue_yego_final = EXCLUDED.revenue_yego_final,
    revenue_real_coverage_pct = EXCLUDED.revenue_real_coverage_pct,
    revenue_proxy_trips = EXCLUDED.revenue_proxy_trips,
    revenue_real_trips = EXCLUDED.revenue_real_trips,
    ticket_sum_completed = EXCLUDED.ticket_sum_completed,
    ticket_count_completed = EXCLUDED.ticket_count_completed,
    total_fare_completed_positive_sum = EXCLUDED.total_fare_completed_positive_sum
"""

# ── CF-H1 WEEKLY DISTINCT HARDENING ──
# Agregación semanal directa desde _bs_enriched_month (misma fuente que day_fact y month_fact).
# Computa COUNT(DISTINCT driver_id) canónico, NO SUM(daily_counts).
_RESOLVE_AND_AGG_WEEK_FROM_TEMP = """
INSERT INTO {fact_week}
SELECT
    date_trunc('week', r.trip_date)::date AS week_start,
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
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_source = 'real')::bigint AS revenue_real_trips,
    sum(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    ) AS ticket_sum_completed,
    count(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    )::bigint AS ticket_count_completed,
    sum(r.total_fare) FILTER (
        WHERE r.completed_flag
          AND r.total_fare IS NOT NULL
          AND r.total_fare > 0
    ) AS total_fare_completed_positive_sum
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
            b.revenue_yego_real AS revenue_yego_net, b.revenue_yego_final, b.ticket, b.km, b.duration_minutes,
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
        b.revenue_yego_final,
        b.ticket,
        b.km,
        b.duration_minutes,
        b.gmv_passenger_paid,
        b.total_fare,
        b.condicion,
        b.source_table,
        CASE WHEN b.revenue_yego_net IS NULL THEN 'proxy' ELSE 'real' END AS revenue_source,
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
  AND r.trip_date IS NOT NULL
  AND r.business_slice_name IS NOT NULL
GROUP BY
    date_trunc('week', r.trip_date),
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name
"""

# ---------------------------------------------------------------------------
# SQL: week_fact — agregado canónico desde resolved (mantiene DISTINCT drivers)
# ---------------------------------------------------------------------------

_WEEK_AGG_FROM_RESOLVED = """
INSERT INTO {fact_week}
SELECT
    date_trunc('week', r.trip_date)::date AS week_start,
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
    CASE WHEN count(r.ticket) FILTER (WHERE r.completed_flag AND r.ticket IS NOT NULL) > 0
         THEN sum(r.ticket) FILTER (WHERE r.completed_flag AND r.ticket IS NOT NULL)
              / count(r.ticket) FILTER (WHERE r.completed_flag AND r.ticket IS NOT NULL)
         ELSE NULL
    END AS avg_ticket,
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
         ) / sum(r.total_fare) FILTER (
             WHERE r.completed_flag
               AND r.total_fare IS NOT NULL
               AND r.total_fare > 0
         )
         ELSE NULL
    END AS commission_pct,
    CASE WHEN count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag) > 0
         THEN count(*) FILTER (WHERE r.completed_flag)::numeric
              / count(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)
         ELSE NULL
    END AS trips_per_driver,
    sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_net,
    CASE WHEN (count(*) FILTER (WHERE r.completed_flag) + count(*) FILTER (WHERE r.cancelled_flag)) > 0
         THEN count(*) FILTER (WHERE r.cancelled_flag)::numeric
              / (count(*) FILTER (WHERE r.completed_flag) + count(*) FILTER (WHERE r.cancelled_flag))
         ELSE NULL
    END AS cancel_rate_pct,
    now() AS refreshed_at,
    now() AS loaded_at,
    sum(r.revenue_yego_net) FILTER (WHERE r.completed_flag) AS revenue_yego_final,
    NULL::numeric AS revenue_real_coverage_pct,
    0::bigint AS revenue_proxy_trips,
    count(*) FILTER (WHERE r.completed_flag AND r.revenue_yego_net IS NOT NULL)::bigint AS revenue_real_trips,
    sum(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    ) AS ticket_sum_completed,
    count(r.ticket) FILTER (
        WHERE r.completed_flag AND r.ticket IS NOT NULL
    )::bigint AS ticket_count_completed,
    sum(r.total_fare) FILTER (
        WHERE r.completed_flag
          AND r.total_fare IS NOT NULL
          AND r.total_fare > 0
    ) AS total_fare_completed_positive_sum
FROM {resolved} r
WHERE r.resolution_status = 'resolved'
  AND r.business_slice_name IS NOT NULL
  AND r.trip_date IS NOT NULL
  AND r.trip_date >= %s::date
  AND r.trip_date < %s::date
GROUP BY
    date_trunc('week', r.trip_date),
    r.country, r.city, r.business_slice_name, r.fleet_display_name,
    r.is_subfleet, r.subfleet_name, r.parent_fleet_name
"""

# Misma forma canónica que week desde resolved, pero agregando desde day_fact ya materializado
# (usado por backfill_runner tras cargar chunks diarios; evita V_RESOLVED).
# DEPRECATED para active_drivers: SUM(daily distinct) ≠ COUNT(DISTINCT driver_id) semanal.
# Usar _RESOLVE_AND_AGG_WEEK_FROM_TEMP en su lugar para definición canónica.
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
    SUM(d.trips_completed)::bigint AS trips_completed,
    SUM(d.trips_cancelled)::bigint AS trips_cancelled,
    SUM(COALESCE(d.active_drivers, 0))::bigint AS active_drivers,
    CASE WHEN SUM(COALESCE(d.ticket_count_completed, 0)) > 0
         THEN SUM(COALESCE(d.ticket_sum_completed, 0)) / SUM(d.ticket_count_completed)
         ELSE NULL
    END AS avg_ticket,
    CASE WHEN SUM(COALESCE(d.total_fare_completed_positive_sum, 0)) > 0
         THEN SUM(COALESCE(d.revenue_yego_net, 0)) / SUM(d.total_fare_completed_positive_sum)
         ELSE NULL
    END AS commission_pct,
    CASE WHEN SUM(COALESCE(d.active_drivers, 0)) > 0
         THEN SUM(d.trips_completed)::numeric / SUM(d.active_drivers)
         ELSE NULL
    END AS trips_per_driver,
    SUM(COALESCE(d.revenue_yego_net, 0)) AS revenue_yego_net,
    CASE WHEN SUM(d.trips_completed + d.trips_cancelled) > 0
         THEN SUM(d.trips_cancelled)::numeric / SUM(d.trips_completed + d.trips_cancelled)
         ELSE NULL
    END AS cancel_rate_pct,
    now() AS refreshed_at,
    now() AS loaded_at,
    SUM(COALESCE(d.revenue_yego_final, 0)) AS revenue_yego_final,
    CASE WHEN SUM(d.trips_completed) > 0
         THEN SUM(COALESCE(d.revenue_real_coverage_pct, 0) * d.trips_completed) / SUM(d.trips_completed)
         ELSE NULL
    END AS revenue_real_coverage_pct,
    SUM(COALESCE(d.revenue_proxy_trips, 0))::bigint AS revenue_proxy_trips,
    SUM(COALESCE(d.revenue_real_trips, 0))::bigint AS revenue_real_trips,
    SUM(COALESCE(d.ticket_sum_completed, 0)) AS ticket_sum_completed,
    SUM(COALESCE(d.ticket_count_completed, 0))::bigint AS ticket_count_completed,
    SUM(COALESCE(d.total_fare_completed_positive_sum, 0)) AS total_fare_completed_positive_sum
FROM {fact_day} d
WHERE d.trip_date >= %s::date
  AND d.trip_date < %s::date
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


# ══════════════════════════════════════════════════════════════════════════════
# CF-H1I — Incremental Refresh: bypass enriched view, direct RAW query
# ══════════════════════════════════════════════════════════════════════════════


def _materialize_enriched_direct(
    cur: Any, start_date: date, end_date: date, conn: Optional[Any]
) -> int:
    """
    Pre-materializa trips del rango [start_date, end_date) desde RAW directo
    con filtro nativo (usa indice btree), replicando la logica de
    ops.v_real_trips_enriched_base pero SIN el DISTINCT ON global.
    El DISTINCT ON solo opera sobre las filas del rango acotado.
    """
    t0 = time.perf_counter()
    apply_business_slice_load_session_settings(cur)
    cur.execute("DROP TABLE IF EXISTS _bs_enriched_month")

    need_2025 = start_date < date(2026, 1, 1)
    need_2026 = end_date > date(2025, 12, 31)

    print(
        f"  materializando enriched directo {start_date} -> {end_date} "
        f"(2025={'si' if need_2025 else 'no'}, 2026={'si' if need_2026 else 'no'}) ...",
        flush=True,
    )

    source_ctes = []
    for table_name, year_filter_start, year_filter_end in (
        [("trips_2025", date(2025, 1, 1), date(2026, 1, 1))]
        if need_2025
        else []
    ) + (
        [("trips_2026", date(2026, 1, 1), date(2027, 1, 1))]
        if need_2026
        else []
    ):
        tbl_start = max(start_date, year_filter_start)
        tbl_end = min(end_date, year_filter_end)
        source_ctes.append(
            f"""
            SELECT
                id, park_id, tipo_servicio, fecha_inicio_viaje, fecha_finalizacion,
                comision_empresa_asociada, pago_corporativo, distancia_km,
                condicion, conductor_id, precio_yango_pro, efectivo, tarjeta,
                motivo_cancelacion,
                '{table_name}' AS source_table,
                {2 if table_name == 'trips_2026' else 1} AS source_priority
            FROM public.{table_name}
            WHERE fecha_inicio_viaje IS NOT NULL
              AND fecha_inicio_viaje >= '{tbl_start.isoformat()} 00:00:00'::timestamptz
              AND fecha_inicio_viaje <  '{tbl_end.isoformat()} 00:00:00'::timestamptz
            """
        )

    raw_union = " UNION ALL ".join(source_ctes)

    # Deduplicate within the filtered range only (not 65M rows)
    sql = f"""
        CREATE TEMP TABLE _bs_enriched_month AS
        WITH raw_filtered AS (
            {raw_union}
        ),
        canon AS (
            SELECT DISTINCT ON (id) *
            FROM raw_filtered
            ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
        )
        SELECT
            c.id::varchar(255) AS trip_id,
            c.conductor_id AS driver_id,
            c.park_id,
            NULLIF(btrim(COALESCE(dp.park_name, '')), '') AS park_name,
            NULLIF(btrim(COALESCE(dp.country, '')), '') AS country,
            NULLIF(btrim(COALESCE(dp.city, '')), '') AS city,
            c.tipo_servicio,
            d.works_terms,
            c.condicion::text = 'Completado' AS completed_flag,
            c.condicion::text = 'Cancelado' AS cancelled_flag,
            c.fecha_inicio_viaje::date AS trip_date,
            date_trunc('month', c.fecha_inicio_viaje)::date AS trip_month,
            date_trunc('week', c.fecha_inicio_viaje)::date AS trip_week,
            EXTRACT(HOUR FROM c.fecha_inicio_viaje)::int AS hour_of_day,
            date_trunc('hour', c.fecha_inicio_viaje) AS trip_hour_start,
            NULLIF(c.comision_empresa_asociada, 0) AS revenue_yego_net,
            c.precio_yango_pro AS ticket,
            CASE
                WHEN c.distancia_km IS NOT NULL THEN ABS(c.distancia_km) / 1000.0
                ELSE NULL
            END AS km,
            CASE
                WHEN c.fecha_finalizacion IS NOT NULL
                 AND c.fecha_inicio_viaje IS NOT NULL
                 AND c.fecha_finalizacion > c.fecha_inicio_viaje
                THEN EXTRACT(EPOCH FROM c.fecha_finalizacion - c.fecha_inicio_viaje) / 60.0
                ELSE NULL
            END AS duration_minutes,
            COALESCE(c.efectivo, 0) + COALESCE(c.tarjeta, 0) + COALESCE(c.pago_corporativo, 0) AS gmv_passenger_paid,
            COALESCE(c.efectivo, 0) + COALESCE(c.tarjeta, 0) + COALESCE(c.pago_corporativo, 0) AS total_fare,
            c.condicion,
            c.source_table,
            c.motivo_cancelacion,
            -- Derived columns
            CASE
                WHEN c.condicion::text = 'Completado'
                 AND NULLIF(c.comision_empresa_asociada, 0) IS NOT NULL
                THEN ABS(NULLIF(c.comision_empresa_asociada, 0))
                ELSE NULL
            END AS revenue_yego_real,
            CASE
                WHEN c.condicion::text = 'Completado'
                 AND c.precio_yango_pro IS NOT NULL AND c.precio_yango_pro > 0
                THEN c.precio_yango_pro * COALESCE(
                    ops.resolve_commission_pct(
                        NULLIF(btrim(COALESCE(dp.country, '')), ''),
                        NULLIF(btrim(COALESCE(dp.city, '')), ''),
                        c.park_id, c.tipo_servicio, c.fecha_inicio_viaje::date
                    ), 0.03)
                ELSE NULL
            END AS revenue_yego_proxy,
            CASE
                WHEN c.condicion::text = 'Completado'
                 AND NULLIF(c.comision_empresa_asociada, 0) IS NOT NULL
                THEN ABS(NULLIF(c.comision_empresa_asociada, 0))
                WHEN c.condicion::text = 'Completado'
                 AND c.precio_yango_pro IS NOT NULL AND c.precio_yango_pro > 0
                THEN c.precio_yango_pro * COALESCE(
                    ops.resolve_commission_pct(
                        NULLIF(btrim(COALESCE(dp.country, '')), ''),
                        NULLIF(btrim(COALESCE(dp.city, '')), ''),
                        c.park_id, c.tipo_servicio, c.fecha_inicio_viaje::date
                    ), 0.03)
                ELSE NULL
            END AS revenue_yego_final,
            CASE
                WHEN c.condicion::text != 'Completado' THEN NULL
                WHEN NULLIF(c.comision_empresa_asociada, 0) IS NOT NULL THEN 'real'
                WHEN c.precio_yango_pro IS NOT NULL AND c.precio_yango_pro > 0 THEN 'proxy'
                ELSE 'missing'
            END AS revenue_source
        FROM canon c
        LEFT JOIN dim.dim_park dp
            ON lower(btrim(dp.park_id::text)) = lower(btrim(c.park_id::text))
        LEFT JOIN public.drivers d
            ON lower(btrim(c.conductor_id::text)) = lower(btrim(d.driver_id::text))
        WHERE c.fecha_inicio_viaje::date IS NOT NULL
    """

    cur.execute(sql)
    mat_rows = cur.rowcount
    cur.execute("CREATE INDEX _bsem_geo ON _bs_enriched_month (country, city)")
    cur.execute("CREATE INDEX _bsem_park ON _bs_enriched_month (park_id)")
    cur.execute("ANALYZE _bs_enriched_month")
    dt = time.perf_counter() - t0
    print(
        f"  enriched directo materializado: {mat_rows} viajes en {dt:.1f}s",
        flush=True,
    )
    if conn is not None:
        conn.commit()
    return mat_rows


def refresh_business_slice_day_range(
    cur: Any, start_date: date, end_date: date, conn: Optional[Any] = None
) -> dict:
    """
    Refresca day_fact solo para el rango [start_date, end_date).
    Materializa enriched desde RAW directo (sin vista pesada), luego usa
    la misma resolución + agregación que el loader mensual (chunk por ciudad).
    Retorna dict con ok, rows_inserted, duration_seconds, errors.
    """
    t0 = time.perf_counter()
    errors = []

    print(f"CF-H1I day_fact incremental: {start_date} -> {end_date}", flush=True)
    mat_rows = _materialize_enriched_direct(cur, start_date, end_date, conn)
    if mat_rows == 0:
        _drop_enriched_temp(cur)
        return {"ok": True, "skipped": True, "reason": "no_raw_data", "duration_seconds": round(time.perf_counter() - t0, 2)}

    # Delete existing facts in range
    cur.execute(
        f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s AND trip_date < %s",
        (start_date, end_date),
    )
    deleted = cur.rowcount
    print(f"  day_fact: {deleted} rows deleted", flush=True)
    if conn is not None:
        conn.commit()

    # Discover chunks from temp table
    cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
    chunks = cur.fetchall()
    total_inserted = 0

    for country, city in chunks:
        cur.execute(
            _RESOLVE_AND_AGG_DAY_FROM_TEMP.format(fact_day=FACT_DAY),
            (country, city),
        )
        n = cur.rowcount
        total_inserted += n
        if conn is not None:
            conn.commit()
        print(f"  day_fact chunk ({country}, {city}): {n} rows", flush=True)

    _drop_enriched_temp(cur)
    if conn is not None:
        conn.commit()

    dt = round(time.perf_counter() - t0, 2)
    return {
        "ok": len(errors) == 0,
        "deleted": deleted,
        "rows_inserted": total_inserted,
        "raw_rows": mat_rows,
        "duration_seconds": dt,
        "errors": errors,
    }


def refresh_business_slice_week_range(
    cur: Any, start_date: date, end_date: date, conn: Optional[Any] = None
) -> dict:
    """
    Refresca week_fact para las semanas afectadas por el rango [start_date, end_date).
    Usa enriched directo (bypass vista) + resolución/agregación estándar.
    Retorna dict con ok, rows_inserted, duration_seconds, errors.
    """
    t0 = time.perf_counter()
    errors = []

    print(f"CF-H1I week_fact incremental: {start_date} -> {end_date}", flush=True)
    mat_rows = _materialize_enriched_direct(cur, start_date, end_date, conn)
    if mat_rows == 0:
        _drop_enriched_temp(cur)
        return {"ok": True, "skipped": True, "reason": "no_raw_data", "duration_seconds": round(time.perf_counter() - t0, 2)}

    # Delete affected weeks — find ALL ISO weeks intersecting [start_date, end_date)
    affected_weeks = set()
    from datetime import timedelta
    first_monday = start_date - timedelta(days=start_date.weekday())
    last_date = end_date - timedelta(days=1)
    last_monday = last_date - timedelta(days=last_date.weekday())
    w = first_monday
    while w <= last_monday:
        affected_weeks.add(w)
        w += timedelta(days=7)
    for w_ in sorted(affected_weeks):
        we = w_ + timedelta(days=7)
        cur.execute(
            f"DELETE FROM {FACT_WEEK} WHERE week_start >= %s AND week_start < %s",
            (w_, we),
        )
    deleted = cur.rowcount
    print(f"  week_fact: {deleted} rows deleted", flush=True)
    if conn is not None:
        conn.commit()

    # Discover chunks and insert
    cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
    chunks = cur.fetchall()
    total_inserted = 0

    for country, city in chunks:
        cur.execute(
            _RESOLVE_AND_AGG_WEEK_FROM_TEMP.format(fact_week=FACT_WEEK),
            (country, city),
        )
        n = cur.rowcount
        total_inserted += n
        if conn is not None:
            conn.commit()
        print(f"  week_fact chunk ({country}, {city}): {n} rows", flush=True)

    _drop_enriched_temp(cur)
    if conn is not None:
        conn.commit()

    dt = round(time.perf_counter() - t0, 2)
    return {
        "ok": len(errors) == 0,
        "rows_inserted": total_inserted,
        "raw_rows": mat_rows,
        "duration_seconds": dt,
        "errors": errors,
    }


def refresh_business_slice_month_range(
    cur: Any, start_date: date, end_date: date, conn: Optional[Any] = None
) -> dict:
    """
    Refresca month_fact para los meses afectados por el rango [start_date, end_date).
    Usa enriched directo (bypass vista) + resolución/agregación estándar.
    Retorna dict con ok, rows_inserted, duration_seconds, errors.
    """
    t0 = time.perf_counter()
    errors = []

    print(f"CF-H1I month_fact incremental: {start_date} -> {end_date}", flush=True)
    mat_rows = _materialize_enriched_direct(cur, start_date, end_date, conn)
    if mat_rows == 0:
        _drop_enriched_temp(cur)
        return {"ok": True, "skipped": True, "reason": "no_raw_data", "duration_seconds": round(time.perf_counter() - t0, 2)}

    # Delete affected months
    affected_months = set()
    d = date(start_date.year, start_date.month, 1)
    end_month = date(end_date.year, end_date.month, 1)
    while d <= end_month:
        affected_months.add(d)
        if d.month == 12:
            d = date(d.year + 1, 1, 1)
        else:
            d = date(d.year, d.month + 1, 1)

    for m in sorted(affected_months):
        cur.execute(
            f"DELETE FROM {FACT_MONTH} WHERE month = %s::date",
            (m,),
        )
    deleted = cur.rowcount
    print(f"  month_fact: {deleted} rows deleted", flush=True)
    if conn is not None:
        conn.commit()

    # Discover chunks and insert
    cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
    chunks = cur.fetchall()
    total_inserted = 0

    for country, city in chunks:
        cur.execute(
            _RESOLVE_AND_AGG_FROM_TEMP.format(fact_month=FACT_MONTH),
            (country, city),
        )
        n = cur.rowcount
        total_inserted += n
        if conn is not None:
            conn.commit()
        print(f"  month_fact chunk ({country}, {city}): {n} rows", flush=True)

    _drop_enriched_temp(cur)
    if conn is not None:
        conn.commit()

    dt = round(time.perf_counter() - t0, 2)
    return {
        "ok": len(errors) == 0,
        "rows_inserted": total_inserted,
        "raw_rows": mat_rows,
        "duration_seconds": dt,
        "errors": errors,
    }


def refresh_omniview_incremental(
    start_date: date, end_date: date, cur: Any, conn: Any, grains: list = None
) -> dict:
    """
    Refresco incremental completo: day_fact + week_fact + month_fact
    para el rango [start_date, end_date).

    Args:
        start_date: fecha inicio (inclusive)
        end_date: fecha fin (exclusive)
        cur: cursor de base de datos
        conn: conexion (para commit)
        grains: lista de grains a refrescar ['day','week','month'] o None para todos

    Safety: si el rango > 45 dias, requiere confirmacion explicita.
    """
    if grains is None:
        grains = ["day", "week", "month"]

    days = (end_date - start_date).days
    if days > 45:
        return {
            "ok": False,
            "error": f"Rango de {days} dias excede el limite de seguridad (45). "
                      "Use rangos menores o pase force=True al script CLI.",
        }

    if days <= 0:
        return {"ok": False, "error": "start_date debe ser anterior a end_date"}

    print(f"CF-H1I incremental refresh: {start_date} -> {end_date} ({days} dias)", flush=True)

    results = {"start_date": str(start_date), "end_date": str(end_date), "days": days}

    if "day" in grains:
        results["day"] = refresh_business_slice_day_range(cur, start_date, end_date, conn)

    if "week" in grains:
        results["week"] = refresh_business_slice_week_range(cur, start_date, end_date, conn)

    if "month" in grains:
        results["month"] = refresh_business_slice_month_range(cur, start_date, end_date, conn)

    return results
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
    4. Para cada chunk: resolución inline desde temp table -> agregación -> INSERT + COMMIT
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
            f"  enriched vacío para {target_month}: no hay viajes -> 0 filas insertadas.",
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
    keep_enriched: bool = False,
) -> int:
    """
    Calcula day_fact para un mes completo. Reutiliza la misma estrategia
    de materialización enriched del loader mensual.

    Hace DELETE del rango mensual antes de INSERTAR para permitir re-ejecuciones
    sin errores de UniqueViolation.

    Si keep_enriched=True, no droppea _bs_enriched_month al final (para que
    week_fact pueda usarla con COUNT(DISTINCT driver_id) canónico).
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)

    grain = _effective_chunk_grain(chunk_grain)
    resolve_sql = _RESOLVE_AND_AGG_DAY_FROM_TEMP.format(fact_day=FACT_DAY)

    apply_business_slice_load_session_settings(cur)

    import calendar
    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    end_date = date(target_month.year, target_month.month, last_day)

    mat_rows = _materialize_enriched_for_month(cur, target_month, conn)
    if mat_rows == 0:
        print(f"  enriched vacío para {target_month}: 0 filas -> day_fact.", flush=True)
        _drop_enriched_temp(cur)
        logger.warning(
            "day_fact SAFETY: enriched vacío para month=%s. day_fact existente PRESERVADO.",
            target_month,
        )
        return 0

    cur.execute(
        f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s::date AND trip_date <= %s::date",
        (target_month, end_date),
    )
    deleted_day = cur.rowcount
    if conn is not None:
        conn.commit()

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
    print(
        f"  {n} chunk(s) — day_fact resolución inline desde temp table (deleted={deleted_day})",
        flush=True,
    )

    for i, chunk in enumerate(chunks):
        c_country, c_city = chunk[0], chunk[1] if len(chunk) > 1 else None
        apply_business_slice_load_session_settings(cur)
        t_chunk = time.perf_counter()
        try:
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

    if inserted_total == 0:
        logger.warning(
            "day_fact SAFETY: 0 filas insertadas para month=%s. "
            "DELETE ya ejecutado (deleted_day=%s). Verificar enriched y mapping rules.",
            target_month, deleted_day,
        )

    if not keep_enriched:
        _drop_enriched_temp(cur)
    total_dt = time.perf_counter() - t0
    print(f"  TOTAL day_fact {target_month}: inserted={inserted_total} {total_dt:.1f}s", flush=True)
    return inserted_total


# ---------------------------------------------------------------------------
# week_fact loader (agregado canónico desde resolved)
# ---------------------------------------------------------------------------


def load_business_slice_week_for_month(
    cur: Any,
    target_month: date,
    conn: Optional[Any] = None,
    chunk_grain: Optional[str] = None,
) -> int:
    """
    CF-H1J.8A SAFE STAGING: Agrega week_fact desde _bs_enriched_month con
    staging seguro. Primero INSERTA en tabla temporal _week_fact_stage,
    luego cuenta filas. Si staged_count == 0 NO borra datos existentes.
    Si staged_count > 0 hace DELETE + INSERT desde staging.

    Previene pérdida de datos canónicos cuando el enriched no produce filas.
    """
    if target_month.day != 1:
        target_month = target_month.replace(day=1)

    import calendar
    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    end_date = date(target_month.year, target_month.month, last_day)

    first_monday = target_month - __import__('datetime').timedelta(days=target_month.weekday())
    next_monday_after_end = end_date + __import__('datetime').timedelta(days=(7 - end_date.weekday()) % 7 or 7)

    apply_business_slice_load_session_settings(cur)

    stage_table = "_week_fact_stage"
    cur.execute(f"DROP TABLE IF EXISTS {stage_table}")
    cur.execute(f"CREATE TEMP TABLE {stage_table} (LIKE {FACT_WEEK} INCLUDING DEFAULTS)")
    stage_sql = _RESOLVE_AND_AGG_WEEK_FROM_TEMP.format(fact_week=stage_table)

    grain = _effective_chunk_grain(chunk_grain)

    t0 = __import__('time').perf_counter()
    staged_total = 0
    use_country_only = grain == "country"

    if use_country_only:
        cur.execute("SELECT DISTINCT country FROM _bs_enriched_month ORDER BY 1 NULLS FIRST")
        chunks = [(r[0], None) for r in cur.fetchall()]
    else:
        cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
        chunks = list(cur.fetchall())

    n = len(chunks)
    print(
        f"  {n} chunk(s) — week_fact staging desde _bs_enriched_month",
        flush=True,
    )

    for i, chunk in enumerate(chunks):
        c_country, c_city = chunk[0], chunk[1] if len(chunk) > 1 else None
        apply_business_slice_load_session_settings(cur)
        try:
            cur.execute(stage_sql, (c_country, c_city))
            rows = cur.rowcount
        except Exception as e:
            cur.execute(f"DROP TABLE IF EXISTS {stage_table}")
            raise RuntimeError(f"week_fact stage falló chunk [{i+1}/{n}] month={target_month}: {e}") from e
        staged_total += rows
        if conn is not None:
            conn.commit()

    stage_dt = __import__('time').perf_counter() - t0

    if staged_total == 0:
        cur.execute(f"DROP TABLE IF EXISTS {stage_table}")
        logger.warning(
            "week_fact SAFETY: 0 filas staged para month=%s range=[%s..%s). "
            "week_fact existente PRESERVADO. Remediation: verificar enriched table y mapping rules.",
            target_month, first_monday, next_monday_after_end,
        )
        return 0

    cur.execute(
        f"DELETE FROM {FACT_WEEK} WHERE week_start >= %s::date AND week_start < %s::date",
        (first_monday, next_monday_after_end),
    )
    deleted = cur.rowcount
    if conn is not None:
        conn.commit()

    cur.execute(f"INSERT INTO {FACT_WEEK} SELECT * FROM {stage_table}")
    inserted = cur.rowcount
    if conn is not None:
        conn.commit()

    cur.execute(f"DROP TABLE IF EXISTS {stage_table}")

    total_dt = __import__('time').perf_counter() - t0
    print(
        f"  week_fact [{first_monday}..{next_monday_after_end}): "
        f"staged={staged_total} deleted={deleted} inserted={inserted} ({stage_dt:.1f}s stage + {total_dt-stage_dt:.1f}s swap)",
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
            nd = load_business_slice_day_for_month(cur, d, conn, chunk_grain=chunk_grain, keep_enriched=True)
            nw = load_business_slice_week_for_month(cur, d, conn)
            _drop_enriched_temp(cur)
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


# ═══════════════════════════════════════════════════════════════════════════════
# CF-H1L.9 — REFRESH FAMILY ATOMICITY
# ═══════════════════════════════════════════════════════════════════════════════

_STG_DAY = "_stg_real_business_slice_day_fact"
_STG_WEEK = "_stg_real_business_slice_week_fact"
_STG_MONTH = "_stg_real_business_slice_month_fact"
_AUDIT_TABLE = "ops.omniview_real_slice_refresh_audit"

_STG_GRAIN_MAP = {
    "day": (_STG_DAY, FACT_DAY),
    "week": (_STG_WEEK, FACT_WEEK),
    "month": (_STG_MONTH, FACT_MONTH),
}


def _ensure_staging_tables(cur: Any) -> None:
    """Crea tablas de staging si no existen (estructura igual a las productivas)."""
    for stg, prod in _STG_GRAIN_MAP.values():
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {stg} (LIKE {prod} INCLUDING ALL);
            TRUNCATE {stg};
        """)


def _ensure_audit_table(cur: Any) -> None:
    """Crea tabla de auditoria de refresh si no existe."""
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {_AUDIT_TABLE} (
            run_id        TEXT PRIMARY KEY,
            started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at   TIMESTAMPTZ,
            status        TEXT NOT NULL DEFAULT 'running',
            start_date    DATE NOT NULL,
            end_date      DATE NOT NULL,
            grains        TEXT[] NOT NULL,
            day_rows      INT,
            week_rows     INT,
            month_rows    INT,
            day_trips     BIGINT,
            week_trips    BIGINT,
            month_trips   BIGINT,
            raw_rows      INT,
            error_message TEXT,
            created_by    TEXT DEFAULT 'atomic_refresh'
        );
    """)


def _populate_staging_day(cur: Any, start_date: date, end_date: date) -> dict:
    """Puebla staging day_fact sin tocar la tabla productiva."""
    t0 = time.perf_counter()
    mat_rows = _materialize_enriched_direct(cur, start_date, end_date, None)
    if mat_rows == 0:
        return {"ok": False, "error": "no_raw_data", "rows": 0, "trips": 0}
    cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
    chunks = cur.fetchall()
    total_rows = 0
    total_trips = 0
    for country, city in chunks:
        insert_sql = _RESOLVE_AND_AGG_DAY_FROM_TEMP.format(fact_day=_STG_DAY)
        cur.execute(insert_sql, (country, city))
        total_rows += cur.rowcount
    cur.execute(f"SELECT COALESCE(SUM(trips_completed),0)::bigint FROM {_STG_DAY}")
    total_trips = int((cur.fetchone() or (0,))[0])
    return {"ok": True, "rows": total_rows, "trips": total_trips, "raw_rows": mat_rows,
            "duration_seconds": round(time.perf_counter() - t0, 2)}


def _populate_staging_week(cur: Any, start_date: date, end_date: date) -> dict:
    """Puebla staging week_fact sin tocar la tabla productiva."""
    t0 = time.perf_counter()
    mat_rows = _materialize_enriched_direct(cur, start_date, end_date, None)
    if mat_rows == 0:
        return {"ok": False, "error": "no_raw_data", "rows": 0, "trips": 0}
    cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
    chunks = cur.fetchall()
    total_rows = 0
    total_trips = 0
    for country, city in chunks:
        insert_sql = _RESOLVE_AND_AGG_WEEK_FROM_TEMP.format(fact_week=_STG_WEEK)
        cur.execute(insert_sql, (country, city))
        total_rows += cur.rowcount
    cur.execute(f"SELECT COALESCE(SUM(trips_completed),0)::bigint FROM {_STG_WEEK}")
    total_trips = int((cur.fetchone() or (0,))[0])
    return {"ok": True, "rows": total_rows, "trips": total_trips, "raw_rows": mat_rows,
            "duration_seconds": round(time.perf_counter() - t0, 2)}


def _populate_staging_month(cur: Any, start_date: date, end_date: date) -> dict:
    """Puebla staging month_fact sin tocar la tabla productiva.
    CF-H1L.9: extiende a meses completos para evitar month_fact parcial."""
    # Extender a meses completos: first_day del primer mes al first_day del mes siguiente al ultimo
    mo_start = start_date.replace(day=1)
    if end_date.day > 1:
        mo_end = (end_date.replace(day=1) + timedelta(days=32)).replace(day=1)
    else:
        mo_end = end_date
    t0 = time.perf_counter()
    mat_rows = _materialize_enriched_direct(cur, mo_start, mo_end, None)
    if mat_rows == 0:
        return {"ok": False, "error": "no_raw_data", "rows": 0, "trips": 0}
    cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
    chunks = cur.fetchall()
    total_rows = 0
    total_trips = 0
    for country, city in chunks:
        insert_sql = _RESOLVE_AND_AGG_FROM_TEMP.format(fact_month=_STG_MONTH)
        cur.execute(insert_sql, (country, city))
        total_rows += cur.rowcount
    cur.execute(f"SELECT COALESCE(SUM(trips_completed),0)::bigint FROM {_STG_MONTH}")
    total_trips = int((cur.fetchone() or (0,))[0])
    return {"ok": True, "rows": total_rows, "trips": total_trips, "raw_rows": mat_rows,
            "duration_seconds": round(time.perf_counter() - t0, 2)}


def _validate_staging_family(cur: Any, staging_results: dict, start_date: date, end_date: date, grains: list[str] = None) -> list[str]:
    """Valida que el staging tenga datos minimos antes del swap atomico."""
    if grains is None:
        grains = ["day", "week", "month"]
    errors = []
    for grain in grains:
        r = staging_results.get(grain, {})
        if not r.get("ok"):
            errors.append(f"staging {grain} failed: {r.get('error', 'unknown')}")
            continue
        if r.get("rows", 0) == 0:
            errors.append(f"staging {grain} has 0 rows")
        if r.get("trips", 0) == 0:
            errors.append(f"staging {grain} has 0 trips")

    if errors:
        return errors

    if "day" in grains:
        cur.execute(
            f"SELECT COUNT(*) FROM {_STG_DAY} "
            f"WHERE trip_date >= %s AND trip_date < %s",
            (start_date, end_date),
        )
        if int((cur.fetchone() or (0,))[0]) == 0:
            errors.append("staging day has 0 rows in target range")

    if "week" in grains:
        cur.execute(
            f"SELECT COUNT(*) FROM {_STG_WEEK} "
            f"WHERE week_start >= %s AND week_start < %s",
            (start_date, end_date),
        )
        if int((cur.fetchone() or (0,))[0]) == 0:
            errors.append("staging week has 0 rows in target range")

    return errors


def _swap_staging_to_production(cur: Any, grains: list[str], start_date: date, end_date: date) -> dict:
    """Atomico: DELETE + INSERT desde staging a productivo en una sola funcion.
    El caller debe manejar el COMMIT/ROLLBACK de la transaccion."""
    results = {}

    if "day" in grains:
        # Delete via staging composite key para evitar gaps entre rangos
        cur.execute(f"""
            DELETE FROM {FACT_DAY} d
            USING {_STG_DAY} s
            WHERE d.trip_date = s.trip_date
              AND COALESCE(d.country, '') = COALESCE(s.country, '')
              AND COALESCE(d.city, '') = COALESCE(s.city, '')
              AND COALESCE(d.business_slice_name, '') = COALESCE(s.business_slice_name, '')
              AND COALESCE(d.fleet_display_name, '') = COALESCE(s.fleet_display_name, '')
              AND COALESCE(d.is_subfleet, false) = COALESCE(s.is_subfleet, false)
              AND COALESCE(d.subfleet_name, '') = COALESCE(s.subfleet_name, '')
        """)
        day_del = cur.rowcount
        cur.execute(f"INSERT INTO {FACT_DAY} SELECT * FROM {_STG_DAY}")
        day_ins = cur.rowcount
        cur.execute(f"SELECT COALESCE(SUM(trips_completed),0)::bigint FROM {FACT_DAY}")
        day_trips = int((cur.fetchone() or (0,))[0])
        results["day"] = {"deleted": day_del, "inserted": day_ins, "trips": day_trips}

    if "week" in grains:
        # Delete solo las filas que existen en staging (evita conflictos de clave)
        cur.execute(f"""
            DELETE FROM {FACT_WEEK} w
            USING {_STG_WEEK} s
            WHERE w.week_start = s.week_start
              AND COALESCE(w.country, '') = COALESCE(s.country, '')
              AND COALESCE(w.city, '') = COALESCE(s.city, '')
              AND COALESCE(w.business_slice_name, '') = COALESCE(s.business_slice_name, '')
              AND COALESCE(w.fleet_display_name, '') = COALESCE(s.fleet_display_name, '')
              AND COALESCE(w.is_subfleet, false) = COALESCE(s.is_subfleet, false)
              AND COALESCE(w.subfleet_name, '') = COALESCE(s.subfleet_name, '')
        """)
        wk_del = cur.rowcount
        cur.execute(f"INSERT INTO {FACT_WEEK} SELECT * FROM {_STG_WEEK}")
        wk_ins = cur.rowcount
        cur.execute(f"SELECT COALESCE(SUM(trips_completed),0)::bigint FROM {FACT_WEEK}")
        wk_trips = int((cur.fetchone() or (0,))[0])
        results["week"] = {"deleted": wk_del, "inserted": wk_ins, "trips": wk_trips}

    if "month" in grains:
        # Delete solo las filas que existen en staging (mismo month + composite key)
        # Esto preserva slices de otros meses no afectados por el rango
        cur.execute(f"""
            DELETE FROM {FACT_MONTH} m
            USING {_STG_MONTH} s
            WHERE m.month = s.month
              AND COALESCE(m.country, '') = COALESCE(s.country, '')
              AND COALESCE(m.city, '') = COALESCE(s.city, '')
              AND COALESCE(m.business_slice_name, '') = COALESCE(s.business_slice_name, '')
              AND COALESCE(m.fleet_display_name, '') = COALESCE(s.fleet_display_name, '')
              AND COALESCE(m.is_subfleet, false) = COALESCE(s.is_subfleet, false)
              AND COALESCE(m.subfleet_name, '') = COALESCE(s.subfleet_name, '')
        """)
        total_mo_del = cur.rowcount
        cur.execute(f"INSERT INTO {FACT_MONTH} SELECT * FROM {_STG_MONTH}")
        mo_ins = cur.rowcount
        cur.execute(f"SELECT COALESCE(SUM(trips_completed),0)::bigint FROM {FACT_MONTH}")
        mo_trips = int((cur.fetchone() or (0,))[0])
        results["month"] = {"deleted": total_mo_del, "inserted": mo_ins, "trips": mo_trips}

    return results


def _cleanup_staging(cur: Any) -> None:
    """Limpia tablas de staging."""
    for stg in (_STG_DAY, _STG_WEEK, _STG_MONTH):
        try:
            cur.execute(f"TRUNCATE {stg}")
        except Exception:
            pass


def _write_refresh_audit(cur: Any, run_id: str, status: str, start_date: date,
                         end_date: date, grains: list[str], staging: dict,
                         swap: dict, raw_rows: int, error: str = None) -> None:
    """Escribe registro de auditoria del refresh atomico."""
    try:
        cur.execute(f"""
            UPDATE {_AUDIT_TABLE} SET
                finished_at = now(),
                status = %s,
                day_rows = %s, week_rows = %s, month_rows = %s,
                day_trips = %s, week_trips = %s, month_trips = %s,
                raw_rows = %s, error_message = %s
            WHERE run_id = %s
        """, (
            status,
            staging.get("day", {}).get("rows") if swap else (staging.get("day", {}).get("rows")),
            staging.get("week", {}).get("rows") if swap else (staging.get("week", {}).get("rows")),
            staging.get("month", {}).get("rows") if swap else (staging.get("month", {}).get("rows")),
            staging.get("day", {}).get("trips") if swap else (staging.get("day", {}).get("trips")),
            staging.get("week", {}).get("trips") if swap else (staging.get("week", {}).get("trips")),
            staging.get("month", {}).get("trips") if swap else (staging.get("month", {}).get("trips")),
            raw_rows, error, run_id,
        ))
    except Exception:
        pass


def refresh_omniview_real_slice_family_atomic(
    conn: Any, start_date: date, end_date: date,
    grains: Optional[list[str]] = None,
) -> dict:
    """
    CF-H1L.9: Refresco atomico de la familia de facts (day + week + month).

    Principio: NUNCA borrar facts productivos hasta que el staging este completo y validado.

    Flujo:
    1. Crear staging tables (si no existen)
    2. Poblar staging para cada grain
    3. Validar staging (rows > 0, trips > 0, rango cubierto)
    4. Si validacion falla → abortar, productivo intacto
    5. Si validacion OK → DELETE + INSERT atomico en UNA transaccion
    6. Si swap falla → ROLLBACK completo, productivo intacto
    7. Registrar audit log

    Returns dict with ok, staging, swap, audit_run_id, error.
    """
    import uuid

    if grains is None:
        grains = ["day", "week", "month"]

    run_id = uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    staging_results = {}
    swap_results = {}
    raw_rows = 0
    error_msg = None

    cur = conn.cursor()

    try:
        _ensure_staging_tables(cur)
        _ensure_audit_table(cur)
        conn.commit()

        cur.execute(f"""
            INSERT INTO {_AUDIT_TABLE} (run_id, start_date, end_date, grains, status)
            VALUES (%s, %s, %s, %s, 'running')
        """, (run_id, start_date, end_date, grains))
        conn.commit()

        # ── Fase 1: Poblar staging ──
        print(f"CF-H1L.9 atomic staging: {start_date} -> {end_date} grains={grains} run={run_id}", flush=True)

        if "day" in grains:
            print("  staging day_fact...", flush=True)
            staging_results["day"] = _populate_staging_day(cur, start_date, end_date)
            raw_rows = max(raw_rows, staging_results["day"].get("raw_rows", 0))
            print(f"    day staging: {staging_results['day'].get('rows', 0)} rows, {staging_results['day'].get('trips', 0)} trips", flush=True)

        if "week" in grains:
            print("  staging week_fact...", flush=True)
            staging_results["week"] = _populate_staging_week(cur, start_date, end_date)
            raw_rows = max(raw_rows, staging_results["week"].get("raw_rows", 0))
            print(f"    week staging: {staging_results['week'].get('rows', 0)} rows, {staging_results['week'].get('trips', 0)} trips", flush=True)

        if "month" in grains:
            print("  staging month_fact...", flush=True)
            staging_results["month"] = _populate_staging_month(cur, start_date, end_date)
            raw_rows = max(raw_rows, staging_results["month"].get("raw_rows", 0))
            print(f"    month staging: {staging_results['month'].get('rows', 0)} rows, {staging_results['month'].get('trips', 0)} trips", flush=True)

        # ── Fase 2: Validar staging ──
        print("  validating staging...", flush=True)
        val_errors = _validate_staging_family(cur, staging_results, start_date, end_date, grains)
        if val_errors:
            error_msg = "staging validation failed: " + "; ".join(val_errors)
            print(f"  FAIL: {error_msg}", flush=True)
            _write_refresh_audit(cur, run_id, "staging_failed", start_date, end_date, grains,
                                 staging_results, {}, raw_rows, error_msg)
            conn.commit()
            _cleanup_staging(cur)
            conn.commit()
            return {
                "ok": False, "error": error_msg, "run_id": run_id,
                "staging": staging_results, "duration_seconds": round(time.perf_counter() - t0, 2),
            }

        # ── Fase 3: Swap atomico ──
        print("  atomic swap staging -> production...", flush=True)
        try:
            swap_results = _swap_staging_to_production(cur, grains, start_date, end_date)
            conn.commit()
            print(f"  swap OK: day={swap_results.get('day',{}).get('inserted',0)} "
                  f"week={swap_results.get('week',{}).get('inserted',0)} "
                  f"month={swap_results.get('month',{}).get('inserted',0)}", flush=True)

            _write_refresh_audit(cur, run_id, "success", start_date, end_date, grains,
                                 staging_results, swap_results, raw_rows)
            conn.commit()
        except Exception as swap_err:
            conn.rollback()
            error_msg = f"swap failed, rolled back: {swap_err}"
            print(f"  ROLLBACK: {error_msg}", flush=True)
            _write_refresh_audit(cur, run_id, "swap_failed", start_date, end_date, grains,
                                 staging_results, {}, raw_rows, str(swap_err)[:500])
            conn.commit()
            _cleanup_staging(cur)
            conn.commit()
            return {
                "ok": False, "error": error_msg, "run_id": run_id,
                "staging": staging_results, "duration_seconds": round(time.perf_counter() - t0, 2),
            }

        _cleanup_staging(cur)
        conn.commit()

        dt = round(time.perf_counter() - t0, 2)
        return {
            "ok": True, "run_id": run_id, "mode": "atomic",
            "start_date": str(start_date), "end_date": str(end_date),
            "days": (end_date - start_date).days,
            "staging": staging_results, "swap": swap_results,
            "raw_rows": raw_rows, "duration_seconds": dt,
        }

    except Exception as e:
        conn.rollback()
        error_msg = str(e)[:500]
        print(f"  FATAL: {error_msg}", flush=True)
        try:
            _write_refresh_audit(cur, run_id, "fatal_error", start_date, end_date, grains,
                                 staging_results, {}, raw_rows, error_msg)
            conn.commit()
        except Exception:
            pass
        return {
            "ok": False, "error": error_msg, "run_id": run_id,
            "staging": staging_results, "duration_seconds": round(time.perf_counter() - t0, 2),
        }
    finally:
        try:
            cur.close()
        except Exception:
            pass
