"""
Segmentación canónica de conductores REAL: activos, solo_cancelan, activity_drivers, % solo cancelan.
- Nace en v_trips_real_canon (conductor_id, condicion) + misma lógica country/lob/service_type que REAL.
- Grano: conductor + periodo + tajada (country, park, lob, service_type); sin doble conteo (dominante por dimensión).
- Métricas: active_drivers (completed_cnt > 0), cancel_only_drivers (completed=0 AND cancelled>0),
  activity_drivers (completed OR cancelled), cancel_only_pct = cancel_only_drivers / activity_drivers.
"""
from alembic import op
import logging

logger = logging.getLogger(__name__)

revision = "106_real_driver_segmentation_canonical"
down_revision = "105_recreate_mv_real_drill_dim_agg_cancelled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) Vista por viaje: conductor + condicion + dimensiones REAL (todos los viajes, no solo completados) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_driver_segment_trips CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_driver_segment_trips AS
        WITH base AS (
            SELECT
                t.conductor_id,
                t.condicion,
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.pago_corporativo,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.conductor_id IS NOT NULL
              AND t.fecha_inicio_viaje IS NOT NULL
              AND t.tipo_servicio IS NOT NULL
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                conductor_id, condicion, park_id, tipo_servicio, fecha_inicio_viaje, pago_corporativo,
                park_id_raw, park_name_raw, park_city_raw,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(COALESCE(park_name_raw::text,'')) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_country AS (
            SELECT
                conductor_id,
                condicion,
                pago_corporativo,
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                park_id_raw,
                park_name_raw,
                park_city_raw,
                city_norm,
                COALESCE(NULLIF(TRIM(city_norm), ''), '') AS city,
                CASE
                    WHEN city_norm IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_norm IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country,
                CASE
                    WHEN park_id IS NULL THEN 'SIN_PARK'
                    ELSE COALESCE(NULLIF(TRIM(park_name_raw::text), ''), 'UNKNOWN_PARK (' || park_id::text || ')')
                END AS park_name
            FROM with_city
        ),
        with_norm AS (
            SELECT
                conductor_id AS driver_key,
                condicion,
                pago_corporativo,
                fecha_inicio_viaje::date AS trip_date,
                date_trunc('week', fecha_inicio_viaje)::date AS week_start,
                date_trunc('month', fecha_inicio_viaje)::date AS month_start,
                country,
                city,
                park_id,
                park_name,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort+','confort plus','confort_plus','comfort+','comfort plus','comfort_plus') THEN 'confort_plus'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start','xl') THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'unknown'
                    ELSE COALESCE(LOWER(TRIM(tipo_servicio::text)), 'unknown')
                END AS service_type_norm
            FROM with_country
            WHERE NULLIF(TRIM(country), '') IS NOT NULL AND country IN ('co','pe')
        )
        SELECT
            v.driver_key,
            v.condicion,
            v.trip_date,
            v.week_start,
            v.month_start,
            v.country,
            v.city,
            v.park_id,
            v.park_name,
            v.service_type_norm,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
            CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag
        FROM with_norm v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.service_type_norm
    """)
    op.execute("COMMENT ON VIEW ops.v_real_driver_segment_trips IS 'Viajes con conductor_id y condicion para segmentación REAL. Fuente: v_trips_real_canon. Incluye completados y cancelados.'")

    # --- 2) Agregado por conductor + periodo + dimensiones; luego dimensión dominante por (driver, period, country, segment) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_driver_segment_driver_period CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_driver_segment_driver_period AS
        WITH agg AS (
            SELECT
                driver_key,
                'day'::text AS period_grain,
                trip_date AS period_start,
                country,
                segment_tag,
                park_id,
                park_name,
                city,
                lob_group,
                service_type_norm,
                COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed_cnt,
                COUNT(*) FILTER (WHERE condicion = 'Cancelado' OR condicion ILIKE '%%cancel%%') AS cancelled_cnt
            FROM ops.v_real_driver_segment_trips
            GROUP BY driver_key, trip_date, country, segment_tag, park_id, park_name, city, lob_group, service_type_norm
            UNION ALL
            SELECT
                driver_key,
                'week'::text,
                week_start,
                country,
                segment_tag,
                park_id,
                park_name,
                city,
                lob_group,
                service_type_norm,
                COUNT(*) FILTER (WHERE condicion = 'Completado'),
                COUNT(*) FILTER (WHERE condicion = 'Cancelado' OR condicion ILIKE '%%cancel%%')
            FROM ops.v_real_driver_segment_trips
            GROUP BY driver_key, week_start, country, segment_tag, park_id, park_name, city, lob_group, service_type_norm
            UNION ALL
            SELECT
                driver_key,
                'month'::text,
                month_start,
                country,
                segment_tag,
                park_id,
                park_name,
                city,
                lob_group,
                service_type_norm,
                COUNT(*) FILTER (WHERE condicion = 'Completado'),
                COUNT(*) FILTER (WHERE condicion = 'Cancelado' OR condicion ILIKE '%%cancel%%')
            FROM ops.v_real_driver_segment_trips
            GROUP BY driver_key, month_start, country, segment_tag, park_id, park_name, city, lob_group, service_type_norm
        ),
        tot AS (
            SELECT
                driver_key,
                period_grain,
                period_start,
                country,
                segment_tag,
                SUM(completed_cnt) AS completed_cnt,
                SUM(cancelled_cnt) AS cancelled_cnt
            FROM agg
            GROUP BY driver_key, period_grain, period_start, country, segment_tag
        ),
        park_rank AS (
            SELECT
                driver_key, period_grain, period_start, country, segment_tag,
                park_id, park_name, city,
                SUM(completed_cnt + cancelled_cnt) AS activity,
                ROW_NUMBER() OVER (PARTITION BY driver_key, period_grain, period_start, country, segment_tag ORDER BY SUM(completed_cnt + cancelled_cnt) DESC, park_id) AS rn
            FROM agg
            GROUP BY driver_key, period_grain, period_start, country, segment_tag, park_id, park_name, city
        ),
        lob_rank AS (
            SELECT
                driver_key, period_grain, period_start, country, segment_tag,
                lob_group,
                SUM(completed_cnt + cancelled_cnt) AS activity,
                ROW_NUMBER() OVER (PARTITION BY driver_key, period_grain, period_start, country, segment_tag ORDER BY SUM(completed_cnt + cancelled_cnt) DESC, lob_group) AS rn
            FROM agg
            GROUP BY driver_key, period_grain, period_start, country, segment_tag, lob_group
        ),
        svc_rank AS (
            SELECT
                driver_key, period_grain, period_start, country, segment_tag,
                service_type_norm,
                SUM(completed_cnt + cancelled_cnt) AS activity,
                ROW_NUMBER() OVER (PARTITION BY driver_key, period_grain, period_start, country, segment_tag ORDER BY SUM(completed_cnt + cancelled_cnt) DESC, service_type_norm) AS rn
            FROM agg
            GROUP BY driver_key, period_grain, period_start, country, segment_tag, service_type_norm
        )
        SELECT
            t.driver_key,
            t.period_grain,
            t.period_start,
            t.country,
            t.segment_tag,
            p.park_id AS park_id_dom,
            p.park_name AS park_name_dom,
            p.city AS city_dom,
            l.lob_group AS lob_dom,
            s.service_type_norm AS service_type_dom,
            t.completed_cnt,
            t.cancelled_cnt,
            (t.completed_cnt > 0) AS is_active,
            (t.completed_cnt = 0 AND t.cancelled_cnt > 0) AS is_cancel_only,
            (t.completed_cnt > 0 OR t.cancelled_cnt > 0) AS is_activity
        FROM tot t
        LEFT JOIN (SELECT * FROM park_rank WHERE rn = 1) p ON p.driver_key = t.driver_key AND p.period_grain = t.period_grain AND p.period_start = t.period_start AND p.country = t.country AND p.segment_tag = t.segment_tag
        LEFT JOIN (SELECT * FROM lob_rank WHERE rn = 1) l ON l.driver_key = t.driver_key AND l.period_grain = t.period_grain AND l.period_start = t.period_start AND l.country = t.country AND l.segment_tag = t.segment_tag
        LEFT JOIN (SELECT * FROM svc_rank WHERE rn = 1) s ON s.driver_key = t.driver_key AND s.period_grain = t.period_grain AND s.period_start = t.period_start AND s.country = t.country AND s.segment_tag = t.segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_driver_segment_driver_period IS 'Un conductor por periodo+país+segmento con dimensión dominante y conteos completed/cancelled. Segmentación: activo, solo_cancelan, activity.'")

    # --- 3) Agregado por tajada (country, period_grain, period_start, segment_tag, breakdown, dimension_key, dimension_id, city) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_driver_segment_agg CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_driver_segment_agg AS
        SELECT
            country,
            period_grain,
            period_start,
            segment_tag,
            'lob'::text AS breakdown,
            lob_dom AS dimension_key,
            NULL::text AS dimension_id,
            NULL::text AS city,
            COUNT(DISTINCT driver_key) FILTER (WHERE is_active) AS active_drivers,
            COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) AS cancel_only_drivers,
            COUNT(DISTINCT driver_key) FILTER (WHERE is_activity) AS activity_drivers,
            ROUND(100.0 * COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) / NULLIF(COUNT(DISTINCT driver_key) FILTER (WHERE is_activity), 0), 4) AS cancel_only_pct
        FROM ops.v_real_driver_segment_driver_period
        WHERE lob_dom IS NOT NULL
        GROUP BY country, period_grain, period_start, segment_tag, lob_dom
        UNION ALL
        SELECT
            country,
            period_grain,
            period_start,
            segment_tag,
            'park'::text,
            COALESCE(NULLIF(TRIM(park_name_dom::text), ''), park_id_dom::text),
            park_id_dom,
            city_dom,
            COUNT(DISTINCT driver_key) FILTER (WHERE is_active),
            COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only),
            COUNT(DISTINCT driver_key) FILTER (WHERE is_activity),
            ROUND(100.0 * COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) / NULLIF(COUNT(DISTINCT driver_key) FILTER (WHERE is_activity), 0), 4)
        FROM ops.v_real_driver_segment_driver_period
        WHERE park_id_dom IS NOT NULL
        GROUP BY country, period_grain, period_start, segment_tag, park_id_dom, park_name_dom, city_dom
        UNION ALL
        SELECT
            country,
            period_grain,
            period_start,
            segment_tag,
            'service_type'::text,
            COALESCE(service_type_dom, 'unknown'),
            NULL::text,
            NULL::text,
            COUNT(DISTINCT driver_key) FILTER (WHERE is_active),
            COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only),
            COUNT(DISTINCT driver_key) FILTER (WHERE is_activity),
            ROUND(100.0 * COUNT(DISTINCT driver_key) FILTER (WHERE is_cancel_only) / NULLIF(COUNT(DISTINCT driver_key) FILTER (WHERE is_activity), 0), 4)
        FROM ops.v_real_driver_segment_driver_period
        WHERE service_type_dom IS NOT NULL
        GROUP BY country, period_grain, period_start, segment_tag, service_type_dom
    """)
    op.execute("COMMENT ON VIEW ops.v_real_driver_segment_agg IS 'Métricas de segmentación por tajada REAL. Joinear con real_drill_dim_fact para active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct.'")

    # --- 4) Columnas en real_drill_dim_fact ---
    op.execute("""
        ALTER TABLE ops.real_drill_dim_fact
        ADD COLUMN IF NOT EXISTS active_drivers bigint,
        ADD COLUMN IF NOT EXISTS cancel_only_drivers bigint,
        ADD COLUMN IF NOT EXISTS activity_drivers bigint,
        ADD COLUMN IF NOT EXISTS cancel_only_pct numeric
    """)
    op.execute("COMMENT ON COLUMN ops.real_drill_dim_fact.active_drivers IS 'Conductores con al menos 1 viaje completado en el periodo (segmentación REAL)'")
    op.execute("COMMENT ON COLUMN ops.real_drill_dim_fact.cancel_only_drivers IS 'Conductores con 0 completados y al menos 1 cancelación en el periodo'")
    op.execute("COMMENT ON COLUMN ops.real_drill_dim_fact.activity_drivers IS 'Conductores con cualquier actividad (completado o cancelado)'")
    op.execute("COMMENT ON COLUMN ops.real_drill_dim_fact.cancel_only_pct IS 'Porcentaje solo cancelan = cancel_only_drivers / activity_drivers'")

    # --- 5) Recrear vista drill para que exponga las nuevas columnas (PostgreSQL fija columnas en CREATE VIEW) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_service_type CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_drill_dim_agg CASCADE")
    op.execute("CREATE VIEW ops.mv_real_drill_dim_agg AS SELECT * FROM ops.real_drill_dim_fact")
    op.execute("CREATE VIEW ops.v_real_drill_lob AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'lob'")
    op.execute("CREATE VIEW ops.v_real_drill_park AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'park'")
    op.execute("CREATE VIEW ops.v_real_drill_service_type AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'service_type'")

    logger.info("Real driver segmentation: v_real_driver_segment_trips, v_real_driver_segment_driver_period, v_real_driver_segment_agg creados; real_drill_dim_fact + 4 columnas; mv_real_drill_dim_agg recreada.")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_service_type CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_drill_dim_agg CASCADE")
    op.execute("CREATE VIEW ops.mv_real_drill_dim_agg AS SELECT * FROM ops.real_drill_dim_fact")
    op.execute("CREATE VIEW ops.v_real_drill_lob AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'lob'")
    op.execute("CREATE VIEW ops.v_real_drill_park AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'park'")
    op.execute("CREATE VIEW ops.v_real_drill_service_type AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'service_type'")
    op.execute("ALTER TABLE ops.real_drill_dim_fact DROP COLUMN IF EXISTS active_drivers")
    op.execute("ALTER TABLE ops.real_drill_dim_fact DROP COLUMN IF EXISTS cancel_only_drivers")
    op.execute("ALTER TABLE ops.real_drill_dim_fact DROP COLUMN IF EXISTS activity_drivers")
    op.execute("ALTER TABLE ops.real_drill_dim_fact DROP COLUMN IF EXISTS cancel_only_pct")
    op.execute("DROP VIEW IF EXISTS ops.v_real_driver_segment_agg CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_driver_segment_driver_period CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_driver_segment_trips CASCADE")
