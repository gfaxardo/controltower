"""
Consolidación de revenue en cadena hourly-first:
1. Migra v_trips_real_canon_120d de trips_all a trips_2025+trips_2026
2. Inyecta revenue proxy en v_real_trip_fact_v2 (gross_revenue y margin_total
   usan COALESCE(comision_real, proxy) para completados sin comisión)
3. Agrega revenue_source y commission_pct_applied al fact para trazabilidad
4. Las MVs (hour_v2, day_v2) no se recrean — solo requieren REFRESH

NO sobreescribe comision_empresa_asociada.
NO toca las MVs directamente.
NO modifica v_real_trips_enriched_base (Business Slice).

Revision ID: 121_consolidate_hourly_first_revenue
Revises: 120_revenue_proxy_config_and_layer
"""
from alembic import op

revision = "121_consolidate_hourly_first_revenue"
down_revision = "120_revenue_proxy_config_and_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================================
    # 1. Recrear v_trips_real_canon_120d con trips_2025 + trips_2026
    #    (elimina dependencia de trips_all + agrega precio_yango_pro)
    # =====================================================================
    op.execute("DROP VIEW IF EXISTS ops.v_real_trip_fact_v2 CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon_120d CASCADE")

    op.execute("""
        CREATE VIEW ops.v_trips_real_canon_120d AS
        WITH union_all AS (
            SELECT
                t.id, t.park_id, t.tipo_servicio,
                t.fecha_inicio_viaje, t.fecha_finalizacion,
                t.comision_empresa_asociada,
                t.precio_yango_pro,
                t.pago_corporativo, t.distancia_km,
                t.condicion, t.conductor_id,
                t.motivo_cancelacion,
                'trips_2025'::text AS source_table,
                1 AS source_priority
            FROM public.trips_2025 t
            WHERE t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_inicio_viaje >= '2025-01-01'::date
              AND t.fecha_inicio_viaje < '2026-01-01'::date
              AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
            UNION ALL
            SELECT
                t.id, t.park_id, t.tipo_servicio,
                t.fecha_inicio_viaje, t.fecha_finalizacion,
                t.comision_empresa_asociada,
                t.precio_yango_pro,
                t.pago_corporativo, t.distancia_km,
                t.condicion, t.conductor_id,
                t.motivo_cancelacion,
                'trips_2026'::text AS source_table,
                2 AS source_priority
            FROM public.trips_2026 t
            WHERE t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_inicio_viaje >= '2026-01-01'::date
              AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
        )
        SELECT DISTINCT ON (id)
            id, park_id, tipo_servicio,
            fecha_inicio_viaje, fecha_finalizacion,
            comision_empresa_asociada,
            precio_yango_pro,
            pago_corporativo, distancia_km,
            condicion, conductor_id,
            motivo_cancelacion, source_table
        FROM union_all
        ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_trips_real_canon_120d IS
        'Canon 120d: trips_2025 + trips_2026 (sin trips_all). '
        'Incluye precio_yango_pro para cálculo de revenue proxy. '
        'Migración 121.'
    """)

    # =====================================================================
    # 2. Recrear v_real_trip_fact_v2 con revenue proxy integrado
    #    gross_revenue y margin_total usan COALESCE(real, proxy)
    #    para completados; revenue_source indica procedencia
    # =====================================================================
    op.execute("""
        CREATE VIEW ops.v_real_trip_fact_v2 AS
        WITH canon_trips AS (
            SELECT
                t.id, t.park_id, t.tipo_servicio,
                t.fecha_inicio_viaje, t.fecha_finalizacion,
                t.comision_empresa_asociada,
                t.precio_yango_pro,
                t.pago_corporativo, t.distancia_km,
                t.condicion, t.conductor_id,
                t.motivo_cancelacion, t.source_table
            FROM ops.v_trips_real_canon_120d t
            WHERE t.fecha_inicio_viaje IS NOT NULL
        ),
        with_park AS (
            SELECT ct.*,
                p.name AS park_name_raw, p.city AS park_city_raw
            FROM canon_trips ct
            LEFT JOIN public.parks p
                ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(ct.park_id::text))
        ),
        with_geo AS (
            SELECT wp.*,
                COALESCE(
                    NULLIF(TRIM(wp.park_name_raw::text), ''),
                    NULLIF(TRIM(wp.park_city_raw::text), ''),
                    wp.park_id::text
                ) AS park_name,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(
                        CASE
                            WHEN wp.park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                            WHEN wp.park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                            WHEN wp.park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                            WHEN wp.park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                            WHEN wp.park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                            WHEN wp.park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                            WHEN wp.park_name_raw::text ILIKE '%%lima%%'
                                OR TRIM(wp.park_name_raw::text) = 'Yego' THEN 'lima'
                            WHEN wp.park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                            WHEN wp.park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                            ELSE LOWER(TRIM(COALESCE(wp.park_city_raw::text, '')))
                        END,
                    ''),
                'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n'))
                AS city,
                CASE
                    WHEN wp.park_name_raw::text ILIKE '%%cali%%'
                        OR wp.park_name_raw::text ILIKE '%%bogot%%'
                        OR wp.park_name_raw::text ILIKE '%%barranquilla%%'
                        OR wp.park_name_raw::text ILIKE '%%medell%%'
                        OR wp.park_name_raw::text ILIKE '%%cucut%%'
                        OR wp.park_name_raw::text ILIKE '%%bucaramanga%%'
                        THEN 'co'
                    WHEN wp.park_name_raw::text ILIKE '%%lima%%'
                        OR TRIM(wp.park_name_raw::text) = 'Yego'
                        OR wp.park_name_raw::text ILIKE '%%arequip%%'
                        OR wp.park_name_raw::text ILIKE '%%trujill%%'
                        THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_park wp
        ),
        with_service AS (
            SELECT wg.*,
                canon.normalize_real_tipo_servicio(wg.tipo_servicio::text)
                    AS tipo_servicio_norm
            FROM with_geo wg
            WHERE wg.tipo_servicio IS NOT NULL
              AND LENGTH(TRIM(wg.tipo_servicio::text)) < 100
              AND wg.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_lob AS (
            SELECT ws.*,
                COALESCE(g.lob_group_label, 'UNCLASSIFIED') AS lob_group,
                CASE WHEN ws.pago_corporativo IS NOT NULL
                     THEN 'B2B' ELSE 'B2C'
                END AS segment_tag
            FROM with_service ws
            LEFT JOIN canon.dim_service_type d
                ON d.service_type_key = ws.tipo_servicio_norm
                AND d.is_active = true
            LEFT JOIN canon.dim_lob_group g
                ON g.lob_group_key = d.lob_group_key
                AND g.is_active = true
        ),
        with_revenue AS (
            SELECT wl.*,
                -- Revenue real (comision_empresa_asociada usable)
                CASE
                    WHEN wl.condicion = 'Completado'
                         AND wl.comision_empresa_asociada IS NOT NULL
                         AND wl.comision_empresa_asociada != 0
                    THEN wl.comision_empresa_asociada
                    ELSE NULL
                END AS _revenue_real,
                -- Revenue proxy (ticket * config pct)
                CASE
                    WHEN wl.condicion = 'Completado'
                         AND (wl.comision_empresa_asociada IS NULL
                              OR wl.comision_empresa_asociada = 0)
                         AND wl.precio_yango_pro IS NOT NULL
                         AND wl.precio_yango_pro > 0
                    THEN wl.precio_yango_pro * COALESCE(
                        ops.resolve_commission_pct(
                            wl.country, wl.city,
                            wl.park_id, wl.tipo_servicio,
                            wl.fecha_inicio_viaje::date
                        ), 0.03)
                    ELSE NULL
                END AS _revenue_proxy
            FROM with_lob wl
        )
        SELECT
            wr.id AS trip_id,
            wr.fecha_inicio_viaje,
            wr.fecha_finalizacion,
            (wr.fecha_inicio_viaje)::date AS trip_date,
            EXTRACT(HOUR FROM wr.fecha_inicio_viaje)::int AS trip_hour,
            DATE_TRUNC('week', wr.fecha_inicio_viaje)::date AS trip_week_start,
            DATE_TRUNC('month', wr.fecha_inicio_viaje)::date AS trip_month_start,

            wr.condicion AS trip_condition_raw,
            CASE
                WHEN wr.condicion = 'Completado' THEN 'completed'
                WHEN wr.condicion = 'Cancelado'
                    OR wr.condicion ILIKE '%%cancel%%' THEN 'cancelled'
                ELSE 'other'
            END AS trip_outcome_norm,
            (wr.condicion = 'Completado') AS is_completed,
            (wr.condicion = 'Cancelado'
                OR wr.condicion ILIKE '%%cancel%%') AS is_cancelled,

            wr.motivo_cancelacion AS motivo_cancelacion_raw,
            canon.normalize_cancel_reason(wr.motivo_cancelacion)
                AS cancel_reason_norm,
            canon.cancel_reason_group(
                canon.normalize_cancel_reason(wr.motivo_cancelacion)
            ) AS cancel_reason_group,

            wr.country, wr.city, wr.park_id, wr.park_name,
            wr.tipo_servicio_norm AS real_tipo_servicio_norm,
            wr.lob_group, wr.segment_tag,

            1 AS trips,

            -- gross_revenue: usa revenue final (real > proxy > 0)
            GREATEST(0, COALESCE(wr._revenue_real, wr._revenue_proxy, 0))
                AS gross_revenue,

            -- margin_total: usa revenue final (real > proxy)
            COALESCE(wr._revenue_real, wr._revenue_proxy)
                AS margin_total,

            -- Preservar campo original para auditoría
            wr.comision_empresa_asociada AS comision_empresa_asociada_raw,

            -- Revenue source trazabilidad
            CASE
                WHEN wr.condicion != 'Completado' THEN NULL
                WHEN wr._revenue_real IS NOT NULL THEN 'real'
                WHEN wr._revenue_proxy IS NOT NULL THEN 'proxy'
                ELSE 'missing'
            END AS revenue_source,

            COALESCE(wr.distancia_km::numeric, 0) / 1000.0 AS distance_km,
            CASE
                WHEN wr.fecha_inicio_viaje IS NOT NULL
                    AND wr.fecha_finalizacion IS NOT NULL
                    AND wr.fecha_finalizacion > wr.fecha_inicio_viaje
                    AND EXTRACT(EPOCH FROM (
                        wr.fecha_finalizacion - wr.fecha_inicio_viaje
                    )) BETWEEN 30 AND 36000
                THEN EXTRACT(EPOCH FROM (
                    wr.fecha_finalizacion - wr.fecha_inicio_viaje
                ))
                ELSE NULL
            END AS trip_duration_seconds,
            CASE
                WHEN wr.fecha_inicio_viaje IS NOT NULL
                    AND wr.fecha_finalizacion IS NOT NULL
                    AND wr.fecha_finalizacion > wr.fecha_inicio_viaje
                    AND EXTRACT(EPOCH FROM (
                        wr.fecha_finalizacion - wr.fecha_inicio_viaje
                    )) BETWEEN 30 AND 36000
                THEN ROUND((EXTRACT(EPOCH FROM (
                    wr.fecha_finalizacion - wr.fecha_inicio_viaje
                )) / 60.0)::numeric, 2)
                ELSE NULL
            END AS trip_duration_minutes,
            wr.conductor_id,
            wr.source_table
        FROM with_revenue wr
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_trip_fact_v2 IS
        'Fact por viaje: revenue consolidado (real > proxy > 0). '
        'gross_revenue y margin_total alimentados por COALESCE(comision_real, proxy). '
        'revenue_source = real|proxy|missing para trazabilidad. '
        'comision_empresa_asociada_raw preserva valor original. '
        'Canon 120d desde trips_2025+trips_2026. Migración 121.'
    """)

    # =====================================================================
    # 3. Recrear real_rollup_day_fact y vista intermedia
    #    (dependen de v_real_trip_fact_v2 vía day_v2, pero real_rollup es
    #    vista sobre day_v2, no sobre fact_v2 directamente. Si se borraron
    #    por CASCADE, hay que recrearlas)
    # =====================================================================
    op.execute("DROP VIEW IF EXISTS ops.real_rollup_day_fact CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_rollup_day_from_day_v2 CASCADE")

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_rollup_day_from_day_v2 AS
        SELECT
            trip_date AS trip_day,
            country,
            city,
            park_id,
            COALESCE(
                NULLIF(TRIM(park_name::text), ''),
                park_id::text, ''
            ) AS park_name_resolved,
            CASE
                WHEN park_id IS NOT NULL
                    AND TRIM(COALESCE(park_id,'')) <> ''
                THEN 'OK' ELSE 'SIN_PARK'
            END AS park_bucket,
            lob_group,
            segment_tag,
            SUM(completed_trips)::bigint AS trips,
            SUM(CASE WHEN segment_tag = 'B2B'
                THEN completed_trips ELSE 0 END)::bigint AS b2b_trips,
            SUM(margin_total) AS margin_total_raw,
            ABS(SUM(margin_total)) AS margin_total_pos,
            CASE WHEN SUM(completed_trips) > 0
                THEN ABS(SUM(margin_total)) / SUM(completed_trips)
                ELSE NULL
            END AS margin_unit_pos,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(completed_trips) > 0
                AND SUM(distance_total_km) IS NOT NULL
                THEN SUM(distance_total_km) / SUM(completed_trips)
                ELSE NULL
            END AS km_prom,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_day_v2
        GROUP BY trip_date, country, city, park_id, park_name,
                 lob_group, segment_tag
    """)
    op.execute("""
        CREATE VIEW ops.real_rollup_day_fact AS
        SELECT * FROM ops.v_real_rollup_day_from_day_v2
    """)


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade 121 no automatizado. "
        "Restaurar canon_120d y fact_v2 desde backup o reaplicar 099."
    )
