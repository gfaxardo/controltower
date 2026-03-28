"""
BUSINESS_SLICE: vista de alimentación MV con filtro 12m en la CTE base.

Evita que REFRESH evalúe toda la historia al construir la clasificación:
misma lógica que v_real_trips_business_slice_resolved pero base acotada a trip_month >= inicio mes (hoy-12m).
"""
from alembic import op

revision = "115_business_slice_mv_feed_resolved_12m"
down_revision = "114_business_slice_mv_12m_window"
branch_labels = None
depends_on = None

RESOLVED_MV12 = """
CREATE VIEW ops.v_real_trips_business_slice_resolved_mv12 AS
WITH base AS (
    SELECT * FROM ops.v_real_trips_enriched_base
    WHERE trip_month >= date_trunc('month', (CURRENT_DATE - INTERVAL '12 months')::date)::date
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
"""

MV_SQL = """
CREATE MATERIALIZED VIEW ops.mv_real_business_slice_monthly AS
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
    now() AS refreshed_at
FROM ops.v_real_trips_business_slice_resolved_mv12 r
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
WITH NO DATA
"""


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_business_slice_join_stub CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_resolved_mv12 CASCADE")
    op.execute(RESOLVED_MV12)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_business_slice_resolved_mv12 IS
        'Solo para alimentar MV mensual: clasificación idéntica a v_real_trips_business_slice_resolved con base limitada a 12 meses (menos temp en REFRESH).'
    """)
    op.execute(MV_SQL)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_bs_monthly_dims
        ON ops.mv_real_business_slice_monthly (month, country, city, business_slice_name)
    """)
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_business_slice_monthly IS
        'Fuente: v_real_trips_business_slice_resolved_mv12 (12m). commission_pct = SUM(revenue)/SUM(total_fare).'
    """)
    op.execute("""
        CREATE VIEW ops.v_plan_business_slice_join_stub AS
        SELECT DISTINCT
            m.country,
            m.city,
            m.business_slice_name,
            m.month,
            'pending_plan_key_country_city_business_slice_month'::text AS join_contract,
            NULL::numeric AS plan_value_placeholder
        FROM ops.mv_real_business_slice_monthly m
    """)


def downgrade() -> None:
    raise NotImplementedError("Downgrade 115: restaurar 114 manualmente si aplica.")
