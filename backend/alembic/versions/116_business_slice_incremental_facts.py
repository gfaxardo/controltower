"""
BUSINESS_SLICE: tablas fact mensual/horario; trip_hour_start; vista mensual de compat sobre month_fact.

- ops.v_real_trips_enriched_base: único punto raw→joins (canon + dim.dim_park + drivers).
- ops.v_real_trips_business_slice_base: alias estable SELECT * FROM enriched (contrato legacy).
- ops.real_business_slice_month_fact: agregado mensual incremental (DELETE+INSERT por mes).
- ops.mv_real_business_slice_monthly: vista de compatibilidad (mismas columnas que la MV antigua).
- total_fare = efectivo+tarjeta+pago_corporativo (NULL si no aplica).
- connected_only_drivers_status = 'NOT_IMPLEMENTED' (explícito).
"""
from alembic import op
from sqlalchemy import text

revision = "116_business_slice_incremental_facts"
down_revision = "115_business_slice_mv_feed_resolved_12m"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.real_business_slice_month_fact (
            month date NOT NULL,
            country text,
            city text,
            business_slice_name text NOT NULL,
            fleet_display_name text,
            is_subfleet boolean NOT NULL DEFAULT false,
            subfleet_name text,
            parent_fleet_name text,
            trips_completed bigint NOT NULL DEFAULT 0,
            trips_cancelled bigint NOT NULL DEFAULT 0,
            active_drivers bigint,
            connected_only_drivers bigint,
            connected_only_drivers_status text,
            avg_ticket numeric,
            commission_pct numeric,
            trips_per_driver numeric,
            revenue_yego_net numeric,
            precio_km numeric,
            tiempo_km numeric,
            completados_por_hora numeric,
            cancelados_por_hora numeric,
            refreshed_at timestamptz NOT NULL DEFAULT now(),
            loaded_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.real_business_slice_hour_fact (
            hour_start timestamp NOT NULL,
            country text,
            city text,
            business_slice_name text NOT NULL,
            fleet_display_name text,
            is_subfleet boolean NOT NULL DEFAULT false,
            subfleet_name text,
            parent_fleet_name text,
            trips_completed bigint NOT NULL DEFAULT 0,
            trips_cancelled bigint NOT NULL DEFAULT 0,
            active_drivers bigint,
            connected_only_drivers bigint,
            connected_only_drivers_status text,
            avg_ticket numeric,
            commission_pct numeric,
            trips_per_driver numeric,
            revenue_yego_net numeric,
            total_fare_completed_positive_sum numeric,
            precio_km numeric,
            tiempo_km numeric,
            completados_por_hora numeric,
            cancelados_por_hora numeric,
            refreshed_at timestamptz NOT NULL DEFAULT now(),
            loaded_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_real_business_slice_month_fact_grain
        ON ops.real_business_slice_month_fact (
            month,
            COALESCE(country, ''),
            COALESCE(city, ''),
            business_slice_name,
            COALESCE(fleet_display_name, ''),
            is_subfleet,
            COALESCE(subfleet_name, ''),
            COALESCE(parent_fleet_name, '')
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_real_business_slice_hour_fact_grain
        ON ops.real_business_slice_hour_fact (
            hour_start,
            COALESCE(country, ''),
            COALESCE(city, ''),
            business_slice_name,
            COALESCE(fleet_display_name, ''),
            is_subfleet,
            COALESCE(subfleet_name, ''),
            COALESCE(parent_fleet_name, '')
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rbs_month_fact_month ON ops.real_business_slice_month_fact (month)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rbs_hour_fact_hour ON ops.real_business_slice_hour_fact (hour_start)")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_business_slice_month_from_hour AS
        SELECT
            date_trunc('month', hour_start)::date AS month,
            country,
            city,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            parent_fleet_name,
            sum(trips_completed)::bigint AS trips_completed,
            sum(trips_cancelled)::bigint AS trips_cancelled,
            NULL::bigint AS active_drivers,
            NULL::bigint AS connected_only_drivers,
            'DERIVED_FROM_HOUR'::text AS connected_only_drivers_status,
            CASE
                WHEN sum(trips_completed) FILTER (WHERE avg_ticket IS NOT NULL) > 0
                THEN sum(avg_ticket * trips_completed) FILTER (WHERE avg_ticket IS NOT NULL)
                    / sum(trips_completed) FILTER (WHERE avg_ticket IS NOT NULL)
                ELSE NULL
            END AS avg_ticket,
            CASE
                WHEN coalesce(sum(total_fare_completed_positive_sum), 0) > 0
                THEN sum(revenue_yego_net) / sum(total_fare_completed_positive_sum)
                ELSE NULL
            END AS commission_pct,
            NULL::numeric AS trips_per_driver,
            sum(revenue_yego_net) AS revenue_yego_net,
            NULL::numeric AS precio_km,
            NULL::numeric AS tiempo_km,
            NULL::numeric AS completados_por_hora,
            NULL::numeric AS cancelados_por_hora,
            max(refreshed_at) AS refreshed_at,
            max(loaded_at) AS loaded_at
        FROM ops.real_business_slice_hour_fact
        GROUP BY
            date_trunc('month', hour_start)::date,
            country,
            city,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            parent_fleet_name
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_business_slice_month_from_hour IS
        'Rollup mensual desde hour_fact. active_drivers y métricas km/tiempo no son agregación fiel; commission_pct coherente vía sumas de fare.'
    """)
    conn = op.get_bind()
    has_2026 = conn.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'trips_2026'
        """)
    ).fetchone()

    op.execute("DROP VIEW IF EXISTS ops.v_plan_business_slice_join_stub CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_resolved_mv12 CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_coverage_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_conflict_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_unmatched_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_base CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_enriched_base CASCADE")

    if has_2026:
        base_union = """
            WITH union_all AS (
                SELECT
                    t.id,
                    t.park_id,
                    t.tipo_servicio,
                    t.fecha_inicio_viaje,
                    t.fecha_finalizacion,
                    t.comision_empresa_asociada,
                    t.pago_corporativo,
                    t.distancia_km,
                    t.condicion,
                    t.conductor_id,
                    t.precio_yango_pro,
                    t.efectivo,
                    t.tarjeta,
                    'trips_all'::text AS source_table,
                    1 AS source_priority
                FROM public.trips_all t
                WHERE t.fecha_inicio_viaje IS NULL OR t.fecha_inicio_viaje < '2026-01-01'::date
                UNION ALL
                SELECT
                    t.id,
                    t.park_id,
                    t.tipo_servicio,
                    t.fecha_inicio_viaje,
                    t.fecha_finalizacion,
                    t.comision_empresa_asociada,
                    t.pago_corporativo,
                    t.distancia_km,
                    t.condicion,
                    t.conductor_id,
                    t.precio_yango_pro,
                    t.efectivo,
                    t.tarjeta,
                    'trips_2026'::text AS source_table,
                    2 AS source_priority
                FROM public.trips_2026 t
                WHERE t.fecha_inicio_viaje >= '2026-01-01'::date
            ),
            canon AS (
                SELECT DISTINCT ON (id)
                    id,
                    park_id,
                    tipo_servicio,
                    fecha_inicio_viaje,
                    fecha_finalizacion,
                    comision_empresa_asociada,
                    pago_corporativo,
                    distancia_km,
                    condicion,
                    conductor_id,
                    precio_yango_pro,
                    efectivo,
                    tarjeta,
                    source_table
                FROM union_all
                ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
            )
        """
    else:
        base_union = """
            WITH canon AS (
                SELECT
                    t.id,
                    t.park_id,
                    t.tipo_servicio,
                    t.fecha_inicio_viaje,
                    t.fecha_finalizacion,
                    t.comision_empresa_asociada,
                    t.pago_corporativo,
                    t.distancia_km,
                    t.condicion,
                    t.conductor_id,
                    t.precio_yango_pro,
                    t.efectivo,
                    t.tarjeta,
                    'trips_all'::text AS source_table
                FROM public.trips_all t
            )
        """

    op.execute(f"""
        CREATE VIEW ops.v_real_trips_enriched_base AS
        {base_union}
        SELECT
            c.id AS trip_id,
            c.conductor_id AS driver_id,
            c.park_id,
            NULLIF(TRIM(COALESCE(dp.park_name::text, '')), '') AS park_name,
            NULLIF(TRIM(COALESCE(dp.country::text, '')), '') AS country,
            NULLIF(TRIM(COALESCE(dp.city::text, '')), '') AS city,
            c.tipo_servicio,
            d.works_terms AS works_terms,
            (c.condicion = 'Completado') AS completed_flag,
            (
                c.condicion = 'Cancelado'
                OR lower(COALESCE(c.condicion::text, '')) LIKE '%cancel%'
            ) AS cancelled_flag,
            c.fecha_inicio_viaje::date AS trip_date,
            date_trunc('month', c.fecha_inicio_viaje)::date AS trip_month,
            date_trunc('week', c.fecha_inicio_viaje)::date AS trip_week,
            EXTRACT(HOUR FROM c.fecha_inicio_viaje)::int AS hour_of_day,
            date_trunc('hour', c.fecha_inicio_viaje)::timestamp AS trip_hour_start,
            NULLIF(c.comision_empresa_asociada, 0)::numeric AS revenue_yego_net,
            c.precio_yango_pro::numeric AS ticket,
            CASE
                WHEN c.distancia_km IS NOT NULL
                THEN abs(c.distancia_km::numeric) / 1000.0
                ELSE NULL
            END AS km,
            CASE
                WHEN c.fecha_finalizacion IS NOT NULL
                     AND c.fecha_inicio_viaje IS NOT NULL
                     AND c.fecha_finalizacion > c.fecha_inicio_viaje
                     AND EXTRACT(
                         EPOCH FROM (c.fecha_finalizacion - c.fecha_inicio_viaje)
                     ) BETWEEN 30 AND 36000
                THEN EXTRACT(
                    EPOCH FROM (c.fecha_finalizacion - c.fecha_inicio_viaje)
                ) / 60.0
                ELSE NULL
            END AS duration_minutes,
            (
                COALESCE(c.efectivo, 0)::numeric
                + COALESCE(c.tarjeta, 0)::numeric
                + COALESCE(c.pago_corporativo, 0)::numeric
            ) AS gmv_passenger_paid,
            (
                COALESCE(c.efectivo, 0)::numeric
                + COALESCE(c.tarjeta, 0)::numeric
                + COALESCE(c.pago_corporativo, 0)::numeric
            ) AS total_fare,
            c.condicion,
            c.source_table
        FROM canon c
        LEFT JOIN dim.dim_park dp
            ON lower(trim(dp.park_id::text)) = lower(trim(c.park_id::text))
        LEFT JOIN public.drivers d
            ON lower(trim(c.conductor_id::text)) = lower(trim(d.driver_id::text))
        WHERE c.fecha_inicio_viaje IS NOT NULL
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_enriched_base IS
        'Capa enriquecida REAL: canon trips_all∪trips_2026 + dim.dim_park + drivers. Pipeline: enriched → resolved → facts (mensual incremental) / hour_fact (bloques).'
    """)
    op.execute("""
        COMMENT ON COLUMN ops.v_real_trips_enriched_base.total_fare IS
        'Tarifa total lado pasajero (efectivo+tarjeta+pago_corporativo). commission_pct mensual = SUM(revenue_yego_net)/SUM(total_fare) sobre viajes completados.'
    """)

    op.execute("""
        COMMENT ON COLUMN ops.v_real_trips_enriched_base.trip_hour_start IS
        'Inicio de hora del viaje (date_trunc sobre fecha_inicio_viaje). Grano hourly-first business_slice.'
    """)

    op.execute("""
        CREATE VIEW ops.v_real_trips_business_slice_base AS
        SELECT * FROM ops.v_real_trips_enriched_base
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_business_slice_base IS
        'Alias de ops.v_real_trips_enriched_base para compatibilidad. No duplica lógica.'
    """)

    op.execute("""
        CREATE VIEW ops.v_real_trips_business_slice_resolved AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_enriched_base
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
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_business_slice_resolved IS
        'Clasificación sobre v_real_trips_enriched_base. Jerarquía subflota: tie-break por parent_fleet_name, fleet_display_name.'
    """)

    op.execute("""
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
""")

    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_business_slice_resolved_mv12 IS
        'Feed 12m para auditoría; API mensual canónica en ops.real_business_slice_month_fact (carga incremental).'
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.mv_real_business_slice_monthly AS
        SELECT
            month,
            country,
            city,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            parent_fleet_name,
            trips_completed,
            trips_cancelled,
            active_drivers,
            connected_only_drivers,
            connected_only_drivers_status,
            avg_ticket,
            commission_pct,
            trips_per_driver,
            revenue_yego_net,
            precio_km,
            tiempo_km,
            completados_por_hora,
            cancelados_por_hora,
            refreshed_at
        FROM ops.real_business_slice_month_fact
    """)
    op.execute("""
        COMMENT ON VIEW ops.mv_real_business_slice_monthly IS
        'Compatibilidad de nombre/columnas; datos en ops.real_business_slice_month_fact.'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_mv_bs_monthly_dims_compat ON ops.real_business_slice_month_fact (month, country, city, business_slice_name)")
    op.execute("""
        CREATE VIEW ops.v_plan_business_slice_join_stub AS
        SELECT DISTINCT
            m.country,
            m.city,
            m.business_slice_name,
            m.month,
            'pending_plan_key_country_city_business_slice_month'::text AS join_contract,
            NULL::numeric AS plan_value_placeholder
        FROM ops.real_business_slice_month_fact m
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_plan_business_slice_join_stub IS
        'Contrato futuro Plan vs Real por BUSINESS_SLICE: clave country + city + business_slice_name + month.'
    """)
    op.execute("""
        CREATE VIEW ops.v_business_slice_unmatched_trips AS
        SELECT *
        FROM ops.v_real_trips_business_slice_resolved
        WHERE resolution_status = 'unmatched'
    """)
    op.execute("""
        CREATE VIEW ops.v_business_slice_conflict_trips AS
        SELECT *
        FROM ops.v_real_trips_business_slice_resolved
        WHERE resolution_status = 'conflict'
    """)

    op.execute("""
        CREATE VIEW ops.v_business_slice_coverage_month AS
        WITH base AS (
            SELECT trip_month AS month, country, city
            FROM ops.v_real_trips_business_slice_base
            WHERE trip_month IS NOT NULL
        ),
        tot AS (
            SELECT month, country, city, count(*)::bigint AS trips_total
            FROM base
            GROUP BY month, country, city
        ),
        matched AS (
            SELECT trip_month AS month, country, city, count(*)::bigint AS trips_matched
            FROM ops.v_real_trips_business_slice_resolved
            WHERE resolution_status = 'resolved'
            GROUP BY trip_month, country, city
        )
        SELECT
            t.month,
            t.country,
            t.city,
            t.trips_total,
            coalesce(m.trips_matched, 0) AS trips_matched,
            CASE
                WHEN t.trips_total > 0
                THEN round(
                    (coalesce(m.trips_matched, 0)::numeric / t.trips_total) * 100,
                    2
                )
                ELSE NULL
            END AS coverage_pct
        FROM tot t
        LEFT JOIN matched m
            ON t.month = m.month
            AND coalesce(t.country, '') = coalesce(m.country, '')
            AND coalesce(t.city, '') = coalesce(m.city, '')
    """)

def downgrade() -> None:
    raise NotImplementedError("Downgrade 116 no automatizado.")
