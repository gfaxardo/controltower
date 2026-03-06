"""
Real LOB Drill: MV desglose tipo_servicio por park para filtro rápido.
- ops.mv_real_drill_service_by_park: (country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips, margin_total, ...).
- Misma lógica y ventana (90 días) que real_drill_dim_fact. REFRESH con el backfill o cron.
"""
import logging

from alembic import op

revision = "068_real_drill_service_by_park_mv"
down_revision = "067_mv_driver_segments_weekly_join_config"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.068")

# Ventana reciente (igual que 064)
CUTOFF_INTERVAL = "90 days"


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_service_by_park CASCADE")
    # Misma cadena base/with_city/with_country/with_lob/enriched que 064; agregado por (country, period, segment, park_id, city, tipo_servicio_norm)
    op.execute(f"""
        CREATE MATERIALIZED VIEW ops.mv_real_drill_service_by_park AS
        WITH base AS (
            SELECT
                t.fecha_inicio_viaje,
                NULLIF(TRIM(t.park_id::text), '') AS park_key,
                t.tipo_servicio,
                t.comision_empresa_asociada,
                t.distancia_km,
                t.pago_corporativo,
                p.id AS park_catalog_id,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
            WHERE t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_inicio_viaje::date >= (CURRENT_DATE - INTERVAL '{CUTOFF_INTERVAL}')::date
              AND t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                b.*,
                CASE
                    WHEN b.park_city_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN b.park_city_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN b.park_city_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN b.park_city_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN b.park_city_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN b.park_city_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN b.park_city_raw::text ILIKE '%%lima%%' OR TRIM(COALESCE(b.park_name_raw::text,'')) = 'Yego' THEN 'lima'
                    WHEN b.park_city_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN b.park_city_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(b.park_city_raw::text, '')))
                END AS city_norm_raw
            FROM base b
        ),
        with_country AS (
            SELECT
                w.*,
                COALESCE(NULLIF(TRIM(w.city_norm_raw), ''), 'sin_city') AS city_norm,
                COALESCE(d.country, f.country, 'unk') AS country,
                CASE
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(w.tipo_servicio::text))
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(w.tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(w.tipo_servicio::text))
                END AS tipo_servicio_norm,
                CASE WHEN w.pago_corporativo IS NOT NULL AND (w.pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END AS segment
            FROM with_city w
            LEFT JOIN ops.dim_city_country d ON d.city_norm = NULLIF(TRIM(w.city_norm_raw), '')
            LEFT JOIN ops.park_country_fallback f ON f.park_id = w.park_key
        ),
        enriched AS (
            SELECT park_key, city_norm, country, tipo_servicio_norm, segment, fecha_inicio_viaje, comision_empresa_asociada, distancia_km, pago_corporativo
            FROM with_country
            WHERE country IN ('co','pe')
        ),
        agg_month AS (
            SELECT
                country,
                'month'::text AS period_grain,
                DATE_TRUNC('month', fecha_inicio_viaje)::date AS period_start,
                segment,
                park_key AS park_id,
                city_norm AS city,
                tipo_servicio_norm,
                COUNT(*)::bigint AS trips,
                (-1) * SUM(comision_empresa_asociada)::numeric AS margin_total,
                (-1) * AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
                (AVG(distancia_km)::numeric) / 1000.0 AS km_avg,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::bigint AS b2b_trips,
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)) AS b2b_share,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM enriched
            GROUP BY country, segment, park_key, city_norm, tipo_servicio_norm, DATE_TRUNC('month', fecha_inicio_viaje)::date
        ),
        agg_week AS (
            SELECT
                country,
                'week'::text AS period_grain,
                DATE_TRUNC('week', fecha_inicio_viaje)::date AS period_start,
                segment,
                park_key AS park_id,
                city_norm AS city,
                tipo_servicio_norm,
                COUNT(*)::bigint AS trips,
                (-1) * SUM(comision_empresa_asociada)::numeric AS margin_total,
                (-1) * AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
                (AVG(distancia_km)::numeric) / 1000.0 AS km_avg,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::bigint AS b2b_trips,
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)) AS b2b_share,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM enriched
            GROUP BY country, segment, park_key, city_norm, tipo_servicio_norm, DATE_TRUNC('week', fecha_inicio_viaje)::date
        )
        SELECT * FROM agg_month
        UNION ALL
        SELECT * FROM agg_week
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_drill_service_by_park
        ON ops.mv_real_drill_service_by_park (country, period_grain, period_start, segment, COALESCE(park_id,''), COALESCE(city,''), COALESCE(tipo_servicio_norm,''))
    """)
    op.execute("CREATE INDEX idx_mv_real_drill_svc_by_park_lookup ON ops.mv_real_drill_service_by_park (country, period_grain, period_start, park_id)")
    logger.info("Created ops.mv_real_drill_service_by_park (REFRESH con backfill o cron)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_service_by_park CASCADE")
