"""
Business Slice trust hardening: fuente unificada public.trips_unified.

Revision ID: 126_business_slice_trips_unified_trust
Revises: 125_learning_engine_phase9
"""
from alembic import op

revision = "126_business_slice_trips_unified_trust"
down_revision = "125_learning_engine_phase9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public.trips_unified AS
        SELECT
            t.id::varchar,
            t.condicion::varchar(100),
            t.codigo_pedido::varchar(100),
            t.conductor_id::varchar(100),
            t.conductor_nombre::varchar(255),
            t.vehiculo_placa::varchar,
            t.vehiculo_modelo::varchar(255),
            t.fecha_inicio_viaje::timestamp,
            t.fecha_finalizacion::timestamp,
            t.motivo_cancelacion::text,
            t.direccion::text,
            t.tipo_servicio::varchar(100),
            t.distancia_km::numeric(10, 2),
            t.precio_yango_pro::numeric,
            t.efectivo::numeric,
            t.tarjeta::numeric,
            t.pago_corporativo::numeric,
            t.propina::numeric,
            t.promocion::numeric,
            t.bonificaciones::numeric,
            t.comision_servicio::numeric,
            t.comision_empresa_asociada::numeric,
            t.otros_pagos::numeric,
            t.pagos_viajes_flota::numeric,
            t.park_id::varchar(100)
        FROM public.trips_2025 t
        WHERE t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_inicio_viaje >= '2025-01-01'::date
          AND t.fecha_inicio_viaje < '2026-01-01'::date
        UNION ALL
        SELECT
            t.id::varchar,
            t.condicion::varchar(100),
            t.codigo_pedido::varchar(100),
            t.conductor_id::varchar(100),
            t.conductor_nombre::varchar(255),
            t.vehiculo_placa::varchar,
            t.vehiculo_modelo::varchar(255),
            t.fecha_inicio_viaje::timestamp,
            t.fecha_finalizacion::timestamp,
            t.motivo_cancelacion::text,
            t.direccion::text,
            t.tipo_servicio::varchar(100),
            t.distancia_km::numeric(10, 2),
            t.precio_yango_pro::numeric,
            t.efectivo::numeric,
            t.tarjeta::numeric,
            t.pago_corporativo::numeric,
            t.propina::numeric,
            t.promocion::numeric,
            t.bonificaciones::numeric,
            t.comision_servicio::numeric,
            t.comision_empresa_asociada::numeric,
            t.otros_pagos::numeric,
            t.pagos_viajes_flota::numeric,
            t.park_id::varchar(100)
        FROM public.trips_2026 t
        WHERE t.fecha_inicio_viaje IS NOT NULL
          AND t.fecha_inicio_viaje >= '2026-01-01'::date
    """)
    op.execute("""
        COMMENT ON VIEW public.trips_unified IS
        'Fuente REAL unificada para Business Slice: trips_2025 + trips_2026 con source_table/source_priority. Excluye trips_all legacy.'
    """)

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_trips_enriched_base AS
        WITH canon AS (
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
                motivo_cancelacion,
                CASE
                    WHEN fecha_inicio_viaje >= '2026-01-01'::date THEN 'trips_2026'::text
                    ELSE 'trips_2025'::text
                END AS source_table,
                CASE
                    WHEN fecha_inicio_viaje >= '2026-01-01'::date THEN 2
                    ELSE 1
                END AS source_priority
            FROM public.trips_unified
            ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
        )
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
                OR lower(COALESCE(c.condicion::text, '')) LIKE '%%cancel%%'
                OR length(trim(COALESCE(c.motivo_cancelacion::text, ''))) > 0
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
                THEN EXTRACT(EPOCH FROM (c.fecha_finalizacion - c.fecha_inicio_viaje)) / 60.0
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
            c.motivo_cancelacion,
            c.source_table
        FROM canon c
        LEFT JOIN dim.dim_park dp
            ON lower(trim(dp.park_id::text)) = lower(trim(c.park_id::text))
        LEFT JOIN public.drivers d
            ON lower(trim(c.conductor_id::text)) = lower(trim(d.driver_id::text))
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trips_enriched_base IS
        'Capa enriquecida REAL: public.trips_unified + dim.dim_park + drivers. Pipeline: enriched → resolved → facts.'
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW public.trips_unified AS
        SELECT
            t.id::varchar,
            t.condicion::varchar(100),
            t.codigo_pedido::varchar(100),
            t.conductor_id::varchar(100),
            t.conductor_nombre::varchar(255),
            t.vehiculo_placa::varchar,
            t.vehiculo_modelo::varchar(255),
            t.fecha_inicio_viaje::timestamp,
            t.fecha_finalizacion::timestamp,
            t.motivo_cancelacion::text,
            t.direccion::text,
            t.tipo_servicio::varchar(100),
            t.distancia_km::numeric(10, 2),
            t.precio_yango_pro::numeric,
            t.efectivo::numeric,
            t.tarjeta::numeric,
            t.pago_corporativo::numeric,
            t.propina::numeric,
            t.promocion::numeric,
            t.bonificaciones::numeric,
            t.comision_servicio::numeric,
            t.comision_empresa_asociada::numeric,
            t.otros_pagos::numeric,
            t.pagos_viajes_flota::numeric,
            t.park_id::varchar(100)
        FROM public.trips_all t
        WHERE t.fecha_inicio_viaje IS NULL OR t.fecha_inicio_viaje < '2026-01-01'::date
        UNION ALL
        SELECT
            t.id::varchar,
            t.condicion::varchar(100),
            t.codigo_pedido::varchar(100),
            t.conductor_id::varchar(100),
            t.conductor_nombre::varchar(255),
            t.vehiculo_placa::varchar,
            t.vehiculo_modelo::varchar(255),
            t.fecha_inicio_viaje::timestamp,
            t.fecha_finalizacion::timestamp,
            t.motivo_cancelacion::text,
            t.direccion::text,
            t.tipo_servicio::varchar(100),
            t.distancia_km::numeric(10, 2),
            t.precio_yango_pro::numeric,
            t.efectivo::numeric,
            t.tarjeta::numeric,
            t.pago_corporativo::numeric,
            t.propina::numeric,
            t.promocion::numeric,
            t.bonificaciones::numeric,
            t.comision_servicio::numeric,
            t.comision_empresa_asociada::numeric,
            t.otros_pagos::numeric,
            t.pagos_viajes_flota::numeric,
            t.park_id::varchar(100)
        FROM public.trips_2026 t
        WHERE t.fecha_inicio_viaje >= '2026-01-01'::date
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_trips_enriched_base AS
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
                t.motivo_cancelacion,
                'trips_2025'::text AS source_table,
                1 AS source_priority
            FROM public.trips_2025 t
            WHERE t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_inicio_viaje >= '2025-01-01'::date
              AND t.fecha_inicio_viaje < '2026-01-01'::date
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
                t.motivo_cancelacion,
                'trips_2026'::text AS source_table,
                2 AS source_priority
            FROM public.trips_2026 t
            WHERE t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_inicio_viaje >= '2026-01-01'::date
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
                motivo_cancelacion,
                source_table
            FROM union_all
            ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
        )
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
                OR lower(COALESCE(c.condicion::text, '')) LIKE '%%cancel%%'
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
                THEN EXTRACT(EPOCH FROM (c.fecha_finalizacion - c.fecha_inicio_viaje)) / 60.0
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
            c.motivo_cancelacion,
            c.source_table
        FROM canon c
        LEFT JOIN dim.dim_park dp
            ON lower(trim(dp.park_id::text)) = lower(trim(c.park_id::text))
        LEFT JOIN public.drivers d
            ON lower(trim(c.conductor_id::text)) = lower(trim(d.driver_id::text))
    """)
    op.execute("DROP VIEW IF EXISTS public.trips_unified")
