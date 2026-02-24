"""
Real LOB v2: agregar margin_total y distance_total_km a las MVs para Unit Economics y Uso.
- Vista base v_real_trips_with_lob_v2: exponer comision_empresa_asociada y distancia_km (trips_all).
- MVs: agregar margin_total = SUM(comision_empresa_asociada), distance_total_km = SUM(distancia_km::numeric)/1000.0.
  distancia_km en trips_all viene en metros; se convierte a km.
- Nulls: excluir de AVG (COUNT); para totales usar SUM(comision_empresa_asociada) y SUM(COALESCE(distancia_km,0))/1000.
"""
from alembic import op

revision = "047_real_lob_v2_margin_distance"
down_revision = "046_real_drill_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Recrear vista base añadiendo comision_empresa_asociada y distancia_km en el output
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_trips_with_lob_v2 AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                t.distancia_km,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM public.trips_all t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                distancia_km,
                revenue,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM with_country
        )
        SELECT
            v.country,
            v.city,
            v.park_id,
            v.park_name,
            v.fecha_inicio_viaje,
            v.real_tipo_servicio_norm,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            v.revenue,
            v.comision_empresa_asociada,
            v.distancia_km
        FROM with_norm v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm
    """)

    # 2) Recrear MV mensual con margin_total y distance_total_km
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
        ),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                lob_group,
                real_tipo_servicio_norm,
                segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        )
        SELECT
            a.country,
            a.city,
            a.park_id,
            a.park_name,
            a.lob_group,
            a.real_tipo_servicio_norm,
            a.segment_tag,
            a.month_start,
            a.trips,
            a.revenue,
            a.margin_total,
            a.distance_total_km,
            a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
        FROM agg a
        CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")

    # 3) Recrear MV semanal
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
        ),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                lob_group,
                real_tipo_servicio_norm,
                segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*) AS trips,
                SUM(revenue) AS revenue,
                SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        )
        SELECT
            a.country,
            a.city,
            a.park_id,
            a.park_name,
            a.lob_group,
            a.real_tipo_servicio_norm,
            a.segment_tag,
            a.week_start,
            a.trips,
            a.revenue,
            a.margin_total,
            a.distance_total_km,
            a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
        FROM agg a
        CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")


def downgrade() -> None:
    # Restore MVs and view to state without margin/distance (re-run 044 logic for MVs and 046 for drill views would be needed; here we only revert 047)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")
    # Restore view without comision_empresa_asociada/distancia_km in output (original 044)
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_trips_with_lob_v2 AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM public.trips_all t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                pago_corporativo,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                revenue,
                pago_corporativo,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT
                country,
                city,
                park_id,
                park_name,
                fecha_inicio_viaje,
                revenue,
                pago_corporativo,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM with_country
        )
        SELECT
            v.country,
            v.city,
            v.park_id,
            v.park_name,
            v.fecha_inicio_viaje,
            v.real_tipo_servicio_norm,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
            v.revenue
        FROM with_norm v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm
    """)
    # Recreate MVs without margin/distance (044 style)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue, MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        )
        SELECT a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.month_start, a.trips, a.revenue, a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
        FROM agg a CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue, MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        )
        SELECT a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.week_start, a.trips, a.revenue, a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
        FROM agg a CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
