"""
BUSINESS_SLICE Fase 1 — mapeo negocio, base REAL enriquecida, resolución, agregado mensual.

- ops.normalized_works_terms(text): normalización para matchear drivers.works_terms.
- ops.business_slice_mapping_rules: reglas importadas desde Excel (no datos seed en migración).
- ops.v_real_trips_business_slice_base: trips_all ∪ trips_2026 (misma deduplicación que v_trips_real_canon) + dim_park + drivers.works_terms.
- ops.v_real_trips_business_slice_resolved: clasificación por prioridad works_terms > tipo_servicio > park_only; conflict / unmatched explícitos.
- ops.v_business_slice_unmatched_trips / ops.v_business_slice_conflict_trips: auditoría.
- ops.v_business_slice_coverage_month: cobertura agregada.
- ops.mv_real_business_slice_monthly: agregado mensual REAL (REFRESH manual).
- ops.v_plan_business_slice_join_stub: contrato futuro Plan ↔ slice (sin mezclar datos Plan).
"""
from alembic import op
from sqlalchemy import text

revision = "111_business_slice_phase1"
down_revision = "110_plan_vs_real_parity_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    has_2026 = conn.execute(
        text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'trips_2026'
        """)
    ).fetchone()

    op.execute("""
        CREATE OR REPLACE FUNCTION ops.normalized_works_terms(raw text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT NULLIF(
                regexp_replace(
                    lower(trim(unaccent(COALESCE(raw, '')))),
                    '[^a-z0-9]', '', 'g'
                ),
                ''
            )
        $$
    """)
    op.execute("""
        COMMENT ON FUNCTION ops.normalized_works_terms(text) IS
        'Normalización para comparar works_terms de drivers con valores del Excel de mapeo BUSINESS_SLICE.'
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.business_slice_mapping_rules (
            id SERIAL PRIMARY KEY,
            country TEXT NOT NULL,
            city TEXT NOT NULL,
            business_slice_name TEXT NOT NULL,
            fleet_display_name TEXT NOT NULL,
            is_subfleet BOOLEAN NOT NULL DEFAULT false,
            subfleet_name TEXT,
            parent_fleet_name TEXT,
            park_id TEXT NOT NULL,
            rule_type TEXT NOT NULL
                CHECK (rule_type IN (
                    'park_only',
                    'park_plus_tipo_servicio',
                    'park_plus_works_terms'
                )),
            tipo_servicio_values TEXT[] NOT NULL DEFAULT '{}',
            works_terms_values TEXT[] NOT NULL DEFAULT '{}',
            notes TEXT,
            source_file_name TEXT,
            source_row_number INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_business_slice_mapping_rules_active_park
        ON ops.business_slice_mapping_rules (is_active, lower(trim(park_id)))
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_business_slice_mapping_rules_slice_city
        ON ops.business_slice_mapping_rules (country, city, business_slice_name)
        WHERE is_active
    """)
    op.execute("""
        COMMENT ON TABLE ops.business_slice_mapping_rules IS
        'Mapeo negocio BUSINESS_SLICE (Excel Plantillas_Control_Tower_Simplificadas_final). Una fila por parque (tras explosión de IDs) y variante de flota/subflota. is_active=false excluye del agregado REAL.'
    """)

    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_business_slice_join_stub CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_coverage_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_conflict_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_unmatched_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_base CASCADE")

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
        CREATE VIEW ops.v_real_trips_business_slice_base AS
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
        COMMENT ON VIEW ops.v_real_trips_business_slice_base IS
        'Base REAL por viaje para BUSINESS_SLICE: canon trips_all∪trips_2026 + dim.dim_park + drivers.works_terms. revenue_yego_net = comision_empresa_asociada canónica (sin ajuste IGV/IVA en esta capa).'
    """)

    op.execute("""
        CREATE VIEW ops.v_real_trips_business_slice_resolved AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_business_slice_base
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
            ORDER BY trip_id, is_subfleet ASC, mapping_rule_id ASC
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
        'Clasificación BUSINESS_SLICE con prioridad especificidad: works_terms > tipo_servicio > park_only. unmatched / conflict explícitos.'
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

    op.execute("""
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
            avg(r.ticket) FILTER (
                WHERE r.completed_flag AND r.ticket IS NOT NULL
            ) AS avg_ticket,
            avg(
                CASE
                    WHEN r.completed_flag
                         AND r.gmv_passenger_paid IS NOT NULL
                         AND r.gmv_passenger_paid > 0
                         AND r.revenue_yego_net IS NOT NULL
                    THEN r.revenue_yego_net / r.gmv_passenger_paid
                END
            ) AS commission_pct,
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
        FROM ops.v_real_trips_business_slice_resolved r
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
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_bs_monthly_dims
        ON ops.mv_real_business_slice_monthly (month, country, city, business_slice_name)
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
    op.execute("""
        COMMENT ON VIEW ops.v_plan_business_slice_join_stub IS
        'Contrato futuro Plan vs Real por BUSINESS_SLICE: clave country + city + business_slice_name + month. Sin homologación Plan en Fase 1.'
    """)

    op.execute("""
        INSERT INTO ops.observability_artifact_registry
            (artifact_name, artifact_type, module_name, schema_name, refresh_owner, source_kind, active_flag, notes)
        VALUES
            (
                'ops.mv_real_business_slice_monthly',
                'materialized_view',
                'Business Slice',
                'ops',
                'scripts/refresh_business_slice_mvs.py',
                'postgres',
                true,
                'Agregado mensual REAL por business_slice. REFRESH MATERIALIZED VIEW manual.'
            ),
            (
                'ops.business_slice_mapping_rules',
                'table',
                'Business Slice',
                'ops',
                'scripts/import_business_slice_mapping_from_xlsx.py',
                'excel',
                true,
                'Reglas de mapeo; trazabilidad source_file_name + source_row_number.'
            )
        ON CONFLICT (artifact_name) DO UPDATE SET
            notes = EXCLUDED.notes,
            refresh_owner = EXCLUDED.refresh_owner,
            updated_at = now()
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM ops.observability_artifact_registry
        WHERE artifact_name IN (
            'ops.mv_real_business_slice_monthly',
            'ops.business_slice_mapping_rules'
        )
    """)
    op.execute("DROP VIEW IF EXISTS ops.v_plan_business_slice_join_stub CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_business_slice_monthly CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_coverage_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_conflict_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_unmatched_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_business_slice_base CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.business_slice_mapping_rules CASCADE")
    op.execute("DROP FUNCTION IF EXISTS ops.normalized_works_terms(text)")
