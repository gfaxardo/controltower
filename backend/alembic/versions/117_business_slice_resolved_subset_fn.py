"""
BUSINESS_SLICE: función SQL de resolución sobre subconjunto filtrado de enriched.

Misma lógica que ops.v_real_trips_business_slice_resolved pero la CTE `base` se acota
antes de unir reglas (evita materializar el universo completo en cargas incrementales).
"""
from alembic import op

revision = "117_business_slice_resolved_subset_fn"
down_revision = "116_business_slice_incremental_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
CREATE OR REPLACE FUNCTION ops.fn_real_trips_business_slice_resolved_subset(
    p_trip_month date,
    p_country text DEFAULT NULL,
    p_city text DEFAULT NULL,
    p_trip_week date DEFAULT NULL,
    p_day_start date DEFAULT NULL,
    p_day_end_exclusive date DEFAULT NULL
)
RETURNS SETOF ops.v_real_trips_business_slice_resolved
LANGUAGE sql
STABLE
AS $fn$
WITH base AS (
    SELECT e.*
    FROM ops.v_real_trips_enriched_base e
    WHERE e.trip_month = p_trip_month
      AND (p_country IS NULL OR e.country IS NOT DISTINCT FROM p_country)
      AND (p_city IS NULL OR e.city IS NOT DISTINCT FROM p_city)
      AND (p_trip_week IS NULL OR e.trip_week IS NOT DISTINCT FROM p_trip_week)
      AND (
          p_day_start IS NULL
          OR (
              e.trip_date >= p_day_start
              AND e.trip_date < p_day_end_exclusive
          )
      )
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
        r.id AS mapping_rule_id,
        r.business_slice_name,
        r.fleet_display_name,
        r.is_subfleet,
        r.subfleet_name,
        r.parent_fleet_name,
        r.rule_type,
        CASE r.rule_type
            WHEN 'park_plus_works_terms' THEN 3
            WHEN 'park_plus_tipo_servicio' THEN 2
            WHEN 'park_only' THEN 1
            ELSE 0
        END AS spec_score
    FROM base b
    INNER JOIN rules r
        ON lower(trim(b.park_id::text)) = lower(trim(r.park_id::text))
    WHERE (
        r.rule_type = 'park_only'
    )
    OR (
        r.rule_type = 'park_plus_tipo_servicio'
        AND EXISTS (
            SELECT 1
            FROM unnest(r.tipo_servicio_values) v
            WHERE nullif(trim(v::text), '') IS NOT NULL
              AND ops.normalized_service_type(b.tipo_servicio::text)
                  = ops.normalized_service_type(v::text)
        )
    )
    OR (
        r.rule_type = 'park_plus_works_terms'
        AND EXISTS (
            SELECT 1
            FROM unnest(r.works_terms_values) w
            WHERE nullif(trim(w::text), '') IS NOT NULL
              AND (
                ops.normalized_works_terms(b.works_terms::text)
                    = ops.normalized_works_terms(w::text)
                OR ops.normalized_works_terms(b.works_terms::text)
                    LIKE '%' || ops.normalized_works_terms(w::text) || '%'
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
    CASE
        WHEN o.trip_id IS NULL THEN 'unmatched'
        WHEN o.n_slices > 1 THEN 'conflict'
        ELSE 'resolved'
    END AS resolution_status,
    w.mapping_rule_id,
    w.business_slice_name,
    w.fleet_display_name,
    w.is_subfleet,
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
$fn$;
""")
    op.execute("""
        COMMENT ON FUNCTION ops.fn_real_trips_business_slice_resolved_subset(date, text, text, date, date, date) IS
        'Resolución BUSINESS_SLICE sobre filas de v_real_trips_enriched_base ya acotadas (mes + filtros opcionales país/ciudad/semana/rango de día). Misma prioridad works_terms > tipo_servicio > park_only y tie-break subflota que la vista ops.v_real_trips_business_slice_resolved. Uso: cargas incrementales sin evaluar el universo completo en la vista global.'
    """)


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS ops.fn_real_trips_business_slice_resolved_subset(date, text, text, date, date, date)"
    )
