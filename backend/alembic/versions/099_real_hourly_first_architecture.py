"""
CT-REAL-HOURLY-FIRST-ARCHITECTURE: Rediseño completo de la cadena analítica REAL.

Crea arquitectura desacoplada y escalable:
  fuente_raw → capa canónica por viaje (v_real_trip_fact_v2)
             → capa horaria (mv_real_lob_hour_v2)
             → capa diaria (mv_real_lob_day_v2)
             → capa semanal (mv_real_lob_week_v3)
             → capa mensual (mv_real_lob_month_v3)

Nuevas capacidades:
  - trip_outcome_norm: completed / cancelled / other
  - cancel_reason_norm: motivo de cancelación normalizado
  - cancel_reason_group: agrupación de negocio
  - trip_duration_minutes: derivado de inicio/fin con protección
  - trip_hour: hora del día (0-23)
  - Arquitectura source-agnostic

No elimina MVs v2 existentes (week/month) para no romper downstream inmediatamente.
"""
from alembic import op
from sqlalchemy import text

revision = "099_real_hourly_first_arch"
down_revision = "098_real_lob_root_cause_120d"
branch_labels = None
depends_on = None


# ── SQL: Función de normalización de motivo de cancelación ───────────────
SQL_CANCEL_REASON_NORM_FUNC = """
CREATE OR REPLACE FUNCTION canon.normalize_cancel_reason(raw_reason TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN raw_reason IS NULL OR TRIM(raw_reason) = '' THEN NULL
        ELSE LOWER(TRIM(
            regexp_replace(
                regexp_replace(raw_reason, '\\s+', ' ', 'g'),
                '[\\u00A0\\u200B\\uFEFF]', '', 'g'
            )
        ))
    END
$$;
"""

SQL_CANCEL_REASON_GROUP_FUNC = """
CREATE OR REPLACE FUNCTION canon.cancel_reason_group(norm_reason TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN norm_reason IS NULL THEN NULL
        WHEN norm_reason ILIKE '%usuario%' OR norm_reason ILIKE '%cliente%'
            OR norm_reason ILIKE '%pasajero%' OR norm_reason ILIKE '%user%'
            OR norm_reason ILIKE '%passenger%' THEN 'cliente'
        WHEN norm_reason ILIKE '%conductor%' OR norm_reason ILIKE '%driver%'
            OR norm_reason ILIKE '%chofer%' THEN 'conductor'
        WHEN norm_reason ILIKE '%timeout%' OR norm_reason ILIKE '%tiempo%'
            OR norm_reason ILIKE '%no asignado%' OR norm_reason ILIKE '%no encontr%'
            OR norm_reason ILIKE '%sin conductor%' OR norm_reason ILIKE '%no driver%'
            OR norm_reason ILIKE '%expirado%' OR norm_reason ILIKE '%expired%'
            THEN 'timeout_no_asignado'
        WHEN norm_reason ILIKE '%sistema%' OR norm_reason ILIKE '%system%'
            OR norm_reason ILIKE '%error%' OR norm_reason ILIKE '%fallo%'
            OR norm_reason ILIKE '%technical%' THEN 'sistema'
        WHEN norm_reason ILIKE '%duplica%' OR norm_reason ILIKE '%duplicate%'
            THEN 'duplicado'
        ELSE 'otro'
    END
$$;
"""

# ── SQL: Vista canónica por viaje (FACT) ─────────────────────────────────
# Lee de v_trips_real_canon_120d (ya filtrada por 120 días, index-friendly)
# INCLUYE TODOS los viajes (no solo completados) para análisis de cancelaciones
SQL_V_REAL_TRIP_FACT_V2 = """
CREATE VIEW ops.v_real_trip_fact_v2 AS
WITH canon_trips AS (
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
        t.source_table
    FROM ops.v_trips_real_canon_120d t
    WHERE t.fecha_inicio_viaje IS NOT NULL
),
with_park AS (
    SELECT
        ct.*,
        p.name AS park_name_raw,
        p.city AS park_city_raw
    FROM canon_trips ct
    LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(ct.park_id::text))
),
with_geo AS (
    SELECT
        wp.*,
        COALESCE(NULLIF(TRIM(wp.park_name_raw::text), ''), NULLIF(TRIM(wp.park_city_raw::text), ''), wp.park_id::text) AS park_name,
        LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(
                CASE
                    WHEN wp.park_name_raw::text ILIKE '%cali%' THEN 'cali'
                    WHEN wp.park_name_raw::text ILIKE '%bogot%' THEN 'bogota'
                    WHEN wp.park_name_raw::text ILIKE '%barranquilla%' THEN 'barranquilla'
                    WHEN wp.park_name_raw::text ILIKE '%medell%' THEN 'medellin'
                    WHEN wp.park_name_raw::text ILIKE '%cucut%' THEN 'cucuta'
                    WHEN wp.park_name_raw::text ILIKE '%bucaramanga%' THEN 'bucaramanga'
                    WHEN wp.park_name_raw::text ILIKE '%lima%' OR TRIM(wp.park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN wp.park_name_raw::text ILIKE '%arequip%' THEN 'arequipa'
                    WHEN wp.park_name_raw::text ILIKE '%trujill%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(wp.park_city_raw::text, '')))
                END,
            ''),
        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city,
        CASE
            WHEN wp.park_name_raw::text ILIKE '%cali%' OR wp.park_name_raw::text ILIKE '%bogot%'
                OR wp.park_name_raw::text ILIKE '%barranquilla%' OR wp.park_name_raw::text ILIKE '%medell%'
                OR wp.park_name_raw::text ILIKE '%cucut%' OR wp.park_name_raw::text ILIKE '%bucaramanga%'
                THEN 'co'
            WHEN wp.park_name_raw::text ILIKE '%lima%' OR TRIM(wp.park_name_raw::text) = 'Yego'
                OR wp.park_name_raw::text ILIKE '%arequip%' OR wp.park_name_raw::text ILIKE '%trujill%'
                THEN 'pe'
            ELSE ''
        END AS country
    FROM with_park wp
),
with_service AS (
    SELECT
        wg.*,
        canon.normalize_real_tipo_servicio(wg.tipo_servicio::text) AS tipo_servicio_norm
    FROM with_geo wg
    WHERE wg.tipo_servicio IS NOT NULL
      AND LENGTH(TRIM(wg.tipo_servicio::text)) < 100
      AND wg.tipo_servicio::text NOT LIKE '%->%'
),
with_lob AS (
    SELECT
        ws.*,
        COALESCE(g.lob_group_label, 'UNCLASSIFIED') AS lob_group,
        CASE WHEN ws.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
        (d.service_type_key IS NULL OR NOT d.is_active) AS is_unclassified
    FROM with_service ws
    LEFT JOIN canon.dim_service_type d ON d.service_type_key = ws.tipo_servicio_norm AND d.is_active = true
    LEFT JOIN canon.dim_lob_group g ON g.lob_group_key = d.lob_group_key AND g.is_active = true
)
SELECT
    wl.id AS trip_id,
    wl.fecha_inicio_viaje,
    wl.fecha_finalizacion,
    (wl.fecha_inicio_viaje)::date AS trip_date,
    EXTRACT(HOUR FROM wl.fecha_inicio_viaje)::int AS trip_hour,
    DATE_TRUNC('week', wl.fecha_inicio_viaje)::date AS trip_week_start,
    DATE_TRUNC('month', wl.fecha_inicio_viaje)::date AS trip_month_start,

    -- Outcome
    wl.condicion AS trip_condition_raw,
    CASE
        WHEN wl.condicion = 'Completado' THEN 'completed'
        WHEN wl.condicion = 'Cancelado' OR wl.condicion ILIKE '%cancel%' THEN 'cancelled'
        ELSE 'other'
    END AS trip_outcome_norm,
    (wl.condicion = 'Completado') AS is_completed,
    (wl.condicion = 'Cancelado' OR wl.condicion ILIKE '%cancel%') AS is_cancelled,

    -- Cancelación (solo se busca motivo_cancelacion en la fuente si está en condicion Cancelado)
    NULL::text AS motivo_cancelacion_raw,
    NULL::text AS cancel_reason_norm,
    NULL::text AS cancel_reason_group,

    -- Geo / Operación
    wl.country,
    wl.city,
    wl.park_id,
    wl.park_name,

    -- LOB / Servicio
    wl.tipo_servicio_norm AS real_tipo_servicio_norm,
    wl.lob_group,
    wl.segment_tag,

    -- Métricas base
    1 AS trips,
    GREATEST(0, COALESCE(wl.comision_empresa_asociada, 0)) AS gross_revenue,
    wl.comision_empresa_asociada AS margin_total,
    COALESCE(wl.distancia_km::numeric, 0) / 1000.0 AS distance_km,
    CASE
        WHEN wl.fecha_inicio_viaje IS NOT NULL
            AND wl.fecha_finalizacion IS NOT NULL
            AND wl.fecha_finalizacion > wl.fecha_inicio_viaje
            AND EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje)) BETWEEN 30 AND 36000
        THEN EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje))
        ELSE NULL
    END AS trip_duration_seconds,
    CASE
        WHEN wl.fecha_inicio_viaje IS NOT NULL
            AND wl.fecha_finalizacion IS NOT NULL
            AND wl.fecha_finalizacion > wl.fecha_inicio_viaje
            AND EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje)) BETWEEN 30 AND 36000
        THEN ROUND((EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje)) / 60.0)::numeric, 2)
        ELSE NULL
    END AS trip_duration_minutes,
    wl.conductor_id,
    wl.source_table
FROM with_lob wl
"""

# ── SQL: Recrear v_trips_real_canon_120d con motivo_cancelacion ───────────
SQL_RECREATE_CANON_120D_WITH_CANCEL = """
CREATE OR REPLACE VIEW ops.v_trips_real_canon_120d AS
WITH union_all AS (
    SELECT
        t.id, t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.fecha_finalizacion,
        t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km, t.condicion, t.conductor_id,
        t.motivo_cancelacion,
        'trips_all'::text AS source_table, 1 AS source_priority
    FROM public.trips_all t
    WHERE t.fecha_inicio_viaje IS NOT NULL
      AND t.fecha_inicio_viaje < '2026-01-01'::date
      AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
    UNION ALL
    SELECT
        t.id, t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.fecha_finalizacion,
        t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km, t.condicion, t.conductor_id,
        t.motivo_cancelacion,
        'trips_2026'::text AS source_table, 2 AS source_priority
    FROM public.trips_2026 t
    WHERE t.fecha_inicio_viaje >= '2026-01-01'::date
      AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
)
SELECT DISTINCT ON (id)
    id, park_id, tipo_servicio, fecha_inicio_viaje, fecha_finalizacion,
    comision_empresa_asociada, pago_corporativo, distancia_km, condicion, conductor_id,
    motivo_cancelacion, source_table
FROM union_all
ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
"""

# ── SQL: Fact view que lee motivo_cancelacion directamente de canon_120d ─
SQL_V_REAL_TRIP_FACT_V2_WITH_CANCEL = """
CREATE VIEW ops.v_real_trip_fact_v2 AS
WITH canon_trips AS (
    SELECT
        t.id, t.park_id, t.tipo_servicio,
        t.fecha_inicio_viaje, t.fecha_finalizacion,
        t.comision_empresa_asociada, t.pago_corporativo,
        t.distancia_km, t.condicion, t.conductor_id,
        t.motivo_cancelacion, t.source_table
    FROM ops.v_trips_real_canon_120d t
    WHERE t.fecha_inicio_viaje IS NOT NULL
),
with_park AS (
    SELECT ct.*,
        p.name AS park_name_raw, p.city AS park_city_raw
    FROM canon_trips ct
    LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(ct.park_id::text))
),
with_geo AS (
    SELECT wp.*,
        COALESCE(NULLIF(TRIM(wp.park_name_raw::text), ''), NULLIF(TRIM(wp.park_city_raw::text), ''), wp.park_id::text) AS park_name,
        LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
            COALESCE(
                CASE
                    WHEN wp.park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN wp.park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN wp.park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN wp.park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN wp.park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN wp.park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN wp.park_name_raw::text ILIKE '%%lima%%' OR TRIM(wp.park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN wp.park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN wp.park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(wp.park_city_raw::text, '')))
                END,
            ''),
        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city,
        CASE
            WHEN wp.park_name_raw::text ILIKE '%%cali%%' OR wp.park_name_raw::text ILIKE '%%bogot%%'
                OR wp.park_name_raw::text ILIKE '%%barranquilla%%' OR wp.park_name_raw::text ILIKE '%%medell%%'
                OR wp.park_name_raw::text ILIKE '%%cucut%%' OR wp.park_name_raw::text ILIKE '%%bucaramanga%%'
                THEN 'co'
            WHEN wp.park_name_raw::text ILIKE '%%lima%%' OR TRIM(wp.park_name_raw::text) = 'Yego'
                OR wp.park_name_raw::text ILIKE '%%arequip%%' OR wp.park_name_raw::text ILIKE '%%trujill%%'
                THEN 'pe'
            ELSE ''
        END AS country
    FROM with_park wp
),
with_service AS (
    SELECT wg.*,
        canon.normalize_real_tipo_servicio(wg.tipo_servicio::text) AS tipo_servicio_norm
    FROM with_geo wg
    WHERE wg.tipo_servicio IS NOT NULL
      AND LENGTH(TRIM(wg.tipo_servicio::text)) < 100
      AND wg.tipo_servicio::text NOT LIKE '%%->%%'
),
with_lob AS (
    SELECT ws.*,
        COALESCE(g.lob_group_label, 'UNCLASSIFIED') AS lob_group,
        CASE WHEN ws.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag
    FROM with_service ws
    LEFT JOIN canon.dim_service_type d ON d.service_type_key = ws.tipo_servicio_norm AND d.is_active = true
    LEFT JOIN canon.dim_lob_group g ON g.lob_group_key = d.lob_group_key AND g.is_active = true
)
SELECT
    wl.id AS trip_id,
    wl.fecha_inicio_viaje,
    wl.fecha_finalizacion,
    (wl.fecha_inicio_viaje)::date AS trip_date,
    EXTRACT(HOUR FROM wl.fecha_inicio_viaje)::int AS trip_hour,
    DATE_TRUNC('week', wl.fecha_inicio_viaje)::date AS trip_week_start,
    DATE_TRUNC('month', wl.fecha_inicio_viaje)::date AS trip_month_start,

    wl.condicion AS trip_condition_raw,
    CASE
        WHEN wl.condicion = 'Completado' THEN 'completed'
        WHEN wl.condicion = 'Cancelado' OR wl.condicion ILIKE '%%cancel%%' THEN 'cancelled'
        ELSE 'other'
    END AS trip_outcome_norm,
    (wl.condicion = 'Completado') AS is_completed,
    (wl.condicion = 'Cancelado' OR wl.condicion ILIKE '%%cancel%%') AS is_cancelled,

    wl.motivo_cancelacion AS motivo_cancelacion_raw,
    canon.normalize_cancel_reason(wl.motivo_cancelacion) AS cancel_reason_norm,
    canon.cancel_reason_group(canon.normalize_cancel_reason(wl.motivo_cancelacion)) AS cancel_reason_group,

    wl.country, wl.city, wl.park_id, wl.park_name,
    wl.tipo_servicio_norm AS real_tipo_servicio_norm,
    wl.lob_group, wl.segment_tag,

    1 AS trips,
    GREATEST(0, COALESCE(wl.comision_empresa_asociada, 0)) AS gross_revenue,
    wl.comision_empresa_asociada AS margin_total,
    COALESCE(wl.distancia_km::numeric, 0) / 1000.0 AS distance_km,
    CASE
        WHEN wl.fecha_inicio_viaje IS NOT NULL AND wl.fecha_finalizacion IS NOT NULL
            AND wl.fecha_finalizacion > wl.fecha_inicio_viaje
            AND EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje)) BETWEEN 30 AND 36000
        THEN EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje))
        ELSE NULL
    END AS trip_duration_seconds,
    CASE
        WHEN wl.fecha_inicio_viaje IS NOT NULL AND wl.fecha_finalizacion IS NOT NULL
            AND wl.fecha_finalizacion > wl.fecha_inicio_viaje
            AND EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje)) BETWEEN 30 AND 36000
        THEN ROUND((EXTRACT(EPOCH FROM (wl.fecha_finalizacion - wl.fecha_inicio_viaje)) / 60.0)::numeric, 2)
        ELSE NULL
    END AS trip_duration_minutes,
    wl.conductor_id, wl.source_table
FROM with_lob wl
"""

# ── SQL: MV horaria ──────────────────────────────────────────────────────
SQL_MV_HOUR = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_hour_v2 AS
SELECT
    trip_date,
    trip_hour,
    country,
    city,
    park_id,
    park_name,
    lob_group,
    real_tipo_servicio_norm,
    segment_tag,
    trip_outcome_norm,
    cancel_reason_norm,
    cancel_reason_group,

    COUNT(*) AS requested_trips,
    COUNT(*) FILTER (WHERE is_completed) AS completed_trips,
    COUNT(*) FILTER (WHERE is_cancelled) AS cancelled_trips,
    COUNT(*) FILTER (WHERE NOT is_completed AND NOT is_cancelled) AS unknown_outcome_trips,

    SUM(gross_revenue) AS gross_revenue,
    SUM(margin_total) AS margin_total,
    SUM(distance_km) AS distance_total_km,
    SUM(trip_duration_minutes) AS duration_total_minutes,
    AVG(trip_duration_minutes) AS duration_avg_minutes,

    CASE WHEN COUNT(*) > 0
        THEN ROUND((COUNT(*) FILTER (WHERE is_cancelled))::numeric / COUNT(*)::numeric, 4)
        ELSE 0 END AS cancellation_rate,
    CASE WHEN COUNT(*) > 0
        THEN ROUND((COUNT(*) FILTER (WHERE is_completed))::numeric / COUNT(*)::numeric, 4)
        ELSE 0 END AS completion_rate,

    MAX(fecha_inicio_viaje) AS max_trip_ts
FROM ops.v_real_trip_fact_v2
GROUP BY
    trip_date, trip_hour, country, city, park_id, park_name,
    lob_group, real_tipo_servicio_norm, segment_tag,
    trip_outcome_norm, cancel_reason_norm, cancel_reason_group
WITH NO DATA
"""

# ── SQL: MV diaria (desde hourly) ────────────────────────────────────────
SQL_MV_DAY = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_day_v2 AS
SELECT
    trip_date,
    country,
    city,
    park_id,
    park_name,
    lob_group,
    real_tipo_servicio_norm,
    segment_tag,
    trip_outcome_norm,
    cancel_reason_norm,
    cancel_reason_group,

    SUM(requested_trips) AS requested_trips,
    SUM(completed_trips) AS completed_trips,
    SUM(cancelled_trips) AS cancelled_trips,
    SUM(unknown_outcome_trips) AS unknown_outcome_trips,

    SUM(gross_revenue) AS gross_revenue,
    SUM(margin_total) AS margin_total,
    SUM(distance_total_km) AS distance_total_km,
    SUM(duration_total_minutes) AS duration_total_minutes,
    CASE WHEN SUM(completed_trips) > 0
        THEN ROUND(SUM(duration_total_minutes) / SUM(completed_trips)::numeric, 2)
        ELSE NULL END AS duration_avg_minutes,

    CASE WHEN SUM(requested_trips) > 0
        THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips)::numeric, 4)
        ELSE 0 END AS cancellation_rate,
    CASE WHEN SUM(requested_trips) > 0
        THEN ROUND(SUM(completed_trips)::numeric / SUM(requested_trips)::numeric, 4)
        ELSE 0 END AS completion_rate,

    MAX(max_trip_ts) AS max_trip_ts
FROM ops.mv_real_lob_hour_v2
GROUP BY
    trip_date, country, city, park_id, park_name,
    lob_group, real_tipo_servicio_norm, segment_tag,
    trip_outcome_norm, cancel_reason_norm, cancel_reason_group
WITH NO DATA
"""

# ── SQL: MV semanal (desde hourly) ───────────────────────────────────────
SQL_MV_WEEK = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v3 AS
WITH hourly AS (SELECT * FROM ops.mv_real_lob_hour_v2),
global_max AS (SELECT MAX(max_trip_ts) AS m FROM hourly)
SELECT
    DATE_TRUNC('week', h.trip_date)::date AS week_start,
    h.country,
    h.city,
    h.park_id,
    h.park_name,
    h.lob_group,
    h.real_tipo_servicio_norm,
    h.segment_tag,

    SUM(h.requested_trips) AS trips,
    SUM(h.completed_trips) AS completed_trips,
    SUM(h.cancelled_trips) AS cancelled_trips,
    SUM(h.gross_revenue) AS revenue,
    SUM(h.margin_total) AS margin_total,
    SUM(h.distance_total_km) AS distance_total_km,
    SUM(h.duration_total_minutes) AS duration_total_minutes,
    MAX(h.max_trip_ts) AS max_trip_ts,
    (DATE_TRUNC('week', h.trip_date)::date = DATE_TRUNC('week', g.m)::date) AS is_open
FROM hourly h
CROSS JOIN global_max g
GROUP BY
    DATE_TRUNC('week', h.trip_date)::date,
    h.country, h.city, h.park_id, h.park_name,
    h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
    (DATE_TRUNC('week', h.trip_date)::date = DATE_TRUNC('week', g.m)::date)
WITH NO DATA
"""

# ── SQL: MV mensual (desde hourly) ───────────────────────────────────────
SQL_MV_MONTH = """
CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v3 AS
WITH hourly AS (SELECT * FROM ops.mv_real_lob_hour_v2),
global_max AS (SELECT MAX(max_trip_ts) AS m FROM hourly)
SELECT
    DATE_TRUNC('month', h.trip_date)::date AS month_start,
    h.country,
    h.city,
    h.park_id,
    h.park_name,
    h.lob_group,
    h.real_tipo_servicio_norm,
    h.segment_tag,

    SUM(h.requested_trips) AS trips,
    SUM(h.completed_trips) AS completed_trips,
    SUM(h.cancelled_trips) AS cancelled_trips,
    SUM(h.gross_revenue) AS revenue,
    SUM(h.margin_total) AS margin_total,
    SUM(h.distance_total_km) AS distance_total_km,
    SUM(h.duration_total_minutes) AS duration_total_minutes,
    MAX(h.max_trip_ts) AS max_trip_ts,
    (DATE_TRUNC('month', h.trip_date)::date = DATE_TRUNC('month', g.m)::date) AS is_open
FROM hourly h
CROSS JOIN global_max g
GROUP BY
    DATE_TRUNC('month', h.trip_date)::date,
    h.country, h.city, h.park_id, h.park_name,
    h.lob_group, h.real_tipo_servicio_norm, h.segment_tag,
    (DATE_TRUNC('month', h.trip_date)::date = DATE_TRUNC('month', g.m)::date)
WITH NO DATA
"""


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1) Funciones de normalización de cancelación ─────────────────────
    op.execute(SQL_CANCEL_REASON_NORM_FUNC)
    op.execute(SQL_CANCEL_REASON_GROUP_FUNC)

    # ── 2) Recrear v_trips_real_canon_120d con motivo_cancelacion ────────
    has_cancel_col = conn.execute(text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'trips_all'
        AND column_name = 'motivo_cancelacion'
    """)).fetchone()

    if has_cancel_col:
        op.execute("DROP VIEW IF EXISTS ops.v_real_trip_fact_v2 CASCADE")
        op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2_120d CASCADE")
        op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved_120d CASCADE")
        op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon_120d CASCADE")
        op.execute(SQL_RECREATE_CANON_120D_WITH_CANCEL)
        # Recrear dependent views from 098
        op.execute("""
            CREATE VIEW ops.v_real_trips_service_lob_resolved_120d AS
            WITH base AS (
                SELECT
                    t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km,
                    p.id AS park_id_raw, p.name AS park_name_raw, p.city AS park_city_raw
                FROM ops.v_trips_real_canon_120d t
                JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
                WHERE t.tipo_servicio IS NOT NULL
                  AND t.condicion = 'Completado'
                  AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
                  AND t.tipo_servicio::text NOT LIKE '%%->%%'
            ),
            with_city AS (
                SELECT park_id, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km, park_id_raw,
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
                SELECT park_id, park_name, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km,
                    GREATEST(0, COALESCE(comision_empresa_asociada, 0)) AS revenue,
                    LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        COALESCE(NULLIF(TRIM(city_norm), ''), ''), 'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
                FROM with_city
            ),
            with_country AS (
                SELECT park_id, park_name, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km, revenue,
                    COALESCE(NULLIF(city_key, ''), '') AS city,
                    CASE
                        WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                        WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                        ELSE ''
                    END AS country
                FROM with_key
            ),
            with_norm AS (
                SELECT country, city, park_id, park_name, tipo_servicio, fecha_inicio_viaje, comision_empresa_asociada, pago_corporativo, distancia_km, revenue,
                    canon.normalize_real_tipo_servicio(tipo_servicio::text) AS tipo_servicio_norm
                FROM with_country
            )
            SELECT
                r.country, r.city, r.park_id, r.park_name, r.fecha_inicio_viaje, r.tipo_servicio AS tipo_servicio_raw, r.tipo_servicio_norm,
                COALESCE(g.lob_group_label, 'UNCLASSIFIED') AS lob_group_resolved,
                (d.service_type_key IS NULL OR NOT d.is_active) AS is_unclassified,
                CASE WHEN r.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
                r.revenue, r.comision_empresa_asociada, r.distancia_km
            FROM with_norm r
            LEFT JOIN canon.dim_service_type d ON d.service_type_key = r.tipo_servicio_norm AND d.is_active = true
            LEFT JOIN canon.dim_lob_group g ON g.lob_group_key = d.lob_group_key AND g.is_active = true
        """)
        op.execute("""
            CREATE VIEW ops.v_real_trips_with_lob_v2_120d AS
            SELECT
                country, city, park_id, park_name, fecha_inicio_viaje,
                tipo_servicio_norm AS real_tipo_servicio_norm,
                lob_group_resolved AS lob_group,
                segment_tag, revenue, comision_empresa_asociada, distancia_km
            FROM ops.v_real_trips_service_lob_resolved_120d
        """)
        op.execute(SQL_V_REAL_TRIP_FACT_V2_WITH_CANCEL)
    else:
        op.execute("DROP VIEW IF EXISTS ops.v_real_trip_fact_v2 CASCADE")
        op.execute(SQL_V_REAL_TRIP_FACT_V2)

    op.execute("""
        COMMENT ON VIEW ops.v_real_trip_fact_v2 IS
        'Capa canónica por viaje (FACT). 1 fila por trip. Source-agnostic wrapper. '
        'Incluye outcome, cancelación, duración, hora. Lee de v_trips_real_canon_120d.'
    """)

    # ── 3) MV horaria ───────────────────────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_hour_v2 CASCADE")
    op.execute(SQL_MV_HOUR)

    op.execute("""CREATE UNIQUE INDEX uq_mv_real_lob_hour_v2
        ON ops.mv_real_lob_hour_v2 (
            trip_date, trip_hour, country, city, park_id,
            lob_group, real_tipo_servicio_norm, segment_tag,
            trip_outcome_norm,
            COALESCE(cancel_reason_norm, ''),
            COALESCE(cancel_reason_group, '')
        )""")
    op.execute("CREATE INDEX idx_mv_hour_v2_date ON ops.mv_real_lob_hour_v2 (trip_date)")
    op.execute("CREATE INDEX idx_mv_hour_v2_country_date ON ops.mv_real_lob_hour_v2 (country, trip_date)")
    op.execute("CREATE INDEX idx_mv_hour_v2_hour ON ops.mv_real_lob_hour_v2 (trip_hour)")
    op.execute("CREATE INDEX idx_mv_hour_v2_lob ON ops.mv_real_lob_hour_v2 (lob_group, segment_tag)")

    # ── 4) MV diaria ────────────────────────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_day_v2 CASCADE")
    op.execute(SQL_MV_DAY)

    op.execute("""CREATE UNIQUE INDEX uq_mv_real_lob_day_v2
        ON ops.mv_real_lob_day_v2 (
            trip_date, country, city, park_id,
            lob_group, real_tipo_servicio_norm, segment_tag,
            trip_outcome_norm,
            COALESCE(cancel_reason_norm, ''),
            COALESCE(cancel_reason_group, '')
        )""")
    op.execute("CREATE INDEX idx_mv_day_v2_country_date ON ops.mv_real_lob_day_v2 (country, trip_date)")
    op.execute("CREATE INDEX idx_mv_day_v2_lob ON ops.mv_real_lob_day_v2 (lob_group, segment_tag)")

    # ── 5) MV semanal (v3, desde hourly) ─────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v3 CASCADE")
    op.execute(SQL_MV_WEEK)

    op.execute("""CREATE UNIQUE INDEX uq_mv_real_lob_week_v3
        ON ops.mv_real_lob_week_v3 (
            country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start
        )""")
    op.execute("CREATE INDEX idx_mv_week_v3_ccpw ON ops.mv_real_lob_week_v3 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_week_v3_ls ON ops.mv_real_lob_week_v3 (lob_group, segment_tag)")

    # ── 6) MV mensual (v3, desde hourly) ─────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v3 CASCADE")
    op.execute(SQL_MV_MONTH)

    op.execute("""CREATE UNIQUE INDEX uq_mv_real_lob_month_v3
        ON ops.mv_real_lob_month_v3 (
            country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start
        )""")
    op.execute("CREATE INDEX idx_mv_month_v3_ccpm ON ops.mv_real_lob_month_v3 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_month_v3_ls ON ops.mv_real_lob_month_v3 (lob_group, segment_tag)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v3 CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v3 CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_day_v2 CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_hour_v2 CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trip_fact_v2 CASCADE")
    op.execute("DROP FUNCTION IF EXISTS canon.cancel_reason_group(TEXT)")
    op.execute("DROP FUNCTION IF EXISTS canon.normalize_cancel_reason(TEXT)")
    # Restore original v_trips_real_canon_120d from 098 (without motivo_cancelacion)
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2_120d CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved_120d CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon_120d CASCADE")
    # The 098 downgrade will recreate these, so we just drop them here
