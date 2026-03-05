"""
Real LOB: fuente canónica de trips (trips_all + trips_2026) y freshness.
- ops.v_trips_real_canon: unión trips_all (<2026) + trips_2026 (>=2026) con columnas necesarias para Real LOB y freshness; source_table para auditoría.
- ops.v_real_freshness_trips: MAX(trip_datetime) por country desde canon con condicion='Completado'.
- v_real_trips_with_lob_v2, mv_real_rollup_day: leer de ops.v_trips_real_canon.
- ops.mv_real_drill_dim_agg: MV dimensional única con breakdown (lob|park|service_type); 1 fila por dimensión por periodo.
  Fix LOB duplicado: drill por LOB agrupa SOLO por lob_group. Nuevo desglose: Tipo de servicio (economico, confort, confort_plus, xl, premier, unknown).
- v_real_drill_lob, v_real_drill_park, v_real_drill_service_type: vistas legacy filtradas por breakdown.
"""
import logging

from alembic import op
from sqlalchemy import text

revision = "064_real_lob_trips_canon"
down_revision = "063_supply_segments_alerts"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.064")


def _log_temp_usage(conn, step: str) -> None:
    """Registra temp_files y temp_bytes de pg_stat_database para observabilidad."""
    try:
        r = conn.execute(text(
            "SELECT datname, temp_files, pg_size_pretty(temp_bytes) AS temp_bytes "
            "FROM pg_stat_database WHERE datname = current_database()"
        )).fetchone()
        if r:
            logger.info("TEMP [%s]: datname=%s temp_files=%s temp_bytes=%s", step, r[0], r[1], r[2])
    except Exception as e:
        logger.warning("No se pudo obtener temp usage en %s: %s", step, e)


def _set_local_resources(conn) -> None:
    """Blinda sesión: work_mem, maintenance_work_mem, timeouts. Solo para esta transacción."""
    conn.execute(text("SET LOCAL statement_timeout = '1h'"))
    conn.execute(text("SET LOCAL lock_timeout = '5min'"))
    conn.execute(text("SET LOCAL work_mem = '256MB'"))
    conn.execute(text("SET LOCAL maintenance_work_mem = '512MB'"))
    try:
        conn.execute(text("SET LOCAL temp_file_limit = '-1'"))
    except Exception as e:
        logger.info("temp_file_limit no seteado (puede requerir superuser): %s", e)


def upgrade() -> None:
    conn = op.get_bind()
    _set_local_resources(conn)
    _log_temp_usage(conn, "inicio")

    # --- 1) Vista canónica: solo columnas necesarias, mismo corte por fecha que trips_unified ---
    op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon CASCADE")
    has_2026 = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'trips_2026'
    """)).fetchone()
    if has_2026:
        op.execute("""
            CREATE VIEW ops.v_trips_real_canon AS
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
                    'trips_2026'::text AS source_table,
                    2 AS source_priority
                FROM public.trips_2026 t
                WHERE t.fecha_inicio_viaje >= '2026-01-01'::date
            )
            SELECT DISTINCT ON (id)
                id, park_id, tipo_servicio, fecha_inicio_viaje, fecha_finalizacion,
                comision_empresa_asociada, pago_corporativo, distancia_km, condicion, conductor_id, source_table
            FROM union_all
            ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
        """)
    else:
        op.execute("""
            CREATE VIEW ops.v_trips_real_canon AS
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
                'trips_all'::text AS source_table
            FROM public.trips_all t
        """)
    op.execute("""
        COMMENT ON VIEW ops.v_trips_real_canon IS
        'Fuente real canónica para Real LOB y freshness: trips_all (histórico <2026) + trips_2026 (>=2026). Columnas mínimas + source_table.'
    """)

    # --- 2) Freshness por país desde canon (condicion = Completado, country vía parks) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_freshness_trips CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_freshness_trips AS
        WITH with_park AS (
            SELECT
                t.fecha_inicio_viaje,
                t.condicion,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
        ),
        with_country AS (
            SELECT
                fecha_inicio_viaje,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' OR park_city_raw::text ILIKE '%%cali%%' THEN 'co'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' OR park_city_raw::text ILIKE '%%bogot%%' THEN 'co'
                    WHEN park_name_raw::text ILIKE '%%medell%%' OR park_city_raw::text ILIKE '%%medell%%' THEN 'co'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' OR park_city_raw::text ILIKE '%%barranquilla%%' THEN 'co'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' OR park_city_raw::text ILIKE '%%cucut%%' THEN 'co'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' OR park_city_raw::text ILIKE '%%bucaramanga%%' THEN 'co'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR park_city_raw::text ILIKE '%%lima%%' OR TRIM(COALESCE(park_name_raw::text,'')) = 'Yego' THEN 'pe'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' OR park_city_raw::text ILIKE '%%arequip%%' THEN 'pe'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' OR park_city_raw::text ILIKE '%%trujill%%' THEN 'pe'
                    ELSE NULL
                END AS country
            FROM with_park
            WHERE condicion = 'Completado'
              AND fecha_inicio_viaje IS NOT NULL
        )
        SELECT
            country,
            MAX(fecha_inicio_viaje)::date AS last_trip_date,
            MAX(fecha_inicio_viaje) AS max_trip_ts
        FROM with_country
        WHERE country IS NOT NULL AND country IN ('co','pe')
        GROUP BY country
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_freshness_trips IS
        'Freshness Real LOB: último viaje completado por país. Fuente: ops.v_trips_real_canon.'
    """)

    # --- 2b) Índices base opcionales en trips_all/trips_2026 para reducir temp spill en refresh ---
    # Mínimos: fecha + condicion (filtro drill). Si fallan por permisos, ejecutar manualmente CONCURRENTLY.
    try:
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_trips_all_real_lob_refresh
            ON public.trips_all (condicion, fecha_inicio_viaje)
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_trips_all_park_fecha
            ON public.trips_all (park_id, fecha_inicio_viaje)
            WHERE condicion = 'Completado'
        """)
        if has_2026:
            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_trips_2026_real_lob_refresh
                ON public.trips_2026 (condicion, fecha_inicio_viaje)
                WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL
            """)
            op.execute("""
                CREATE INDEX IF NOT EXISTS ix_trips_2026_park_fecha
                ON public.trips_2026 (park_id, fecha_inicio_viaje)
                WHERE condicion = 'Completado'
            """)
        logger.info("Índices base trips_all/trips_2026 creados.")
    except Exception as e:
        logger.warning("Índices base no creados (ejecutar manualmente si trips es grande): %s", e)

    # --- 3) v_real_trips_with_lob_v2: leer de canon ---
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
            FROM ops.v_trips_real_canon t
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

    # --- 4) mv_real_drill_dim_agg: MV dimensional única (breakdown lob|park|service_type); 1 fila por dimensión ---
    # Estrategia en 2 fases para reducir pico de uso de temp (DiskFull): primero MV intermedia, luego agregados.
    # Fase 4a: ops.mv_real_drill_enriched (1 fila por trip enriquecido) — usa temp para joins.
    # Fase 4b: ops.mv_real_drill_dim_agg lee de enriched — menos temp (solo GROUP BY sobre tabla materializada).
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_dim_agg CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_enriched CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_drill_agg CASCADE")

    _log_temp_usage(conn, "pre-mv_real_drill_enriched")
    # --- 4a) MV intermedia: 1 fila por trip enriquecido (country co/pe) ---
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_drill_enriched AS
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
                    WHEN w.park_key IS NULL THEN 'SIN_PARK'
                    ELSE COALESCE(NULLIF(TRIM(w.park_name_raw::text), ''), 'UNKNOWN_PARK (' || w.park_key::text || ')')
                END AS park_name,
                CASE
                    WHEN w.park_catalog_id IS NOT NULL THEN
                        COALESCE(NULLIF(TRIM(w.park_name_raw::text), ''), 'Sin nombre') || ' — ' || COALESCE(NULLIF(TRIM(w.park_city_raw::text), ''), 'Sin ciudad')
                    ELSE COALESCE(NULLIF(TRIM(w.park_name_raw::text), ''), 'UNKNOWN_PARK (' || w.park_key::text || ')')
                END AS park_display_key,
                CASE
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('económico','economico') THEN 'economico'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('confort','comfort') THEN 'confort'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('confort+','confort plus','confort_plus','comfort+','comfort plus','comfort_plus') THEN 'confort_plus'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) = 'xl' THEN 'xl'
                    WHEN LOWER(TRIM(w.tipo_servicio::text)) IN ('premier','premiere') THEN 'premier'
                    ELSE 'unknown'
                END AS service_type_norm,
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
                END AS tipo_servicio_norm
            FROM with_city w
            LEFT JOIN ops.dim_city_country d ON d.city_norm = NULLIF(TRIM(w.city_norm_raw), '')
            LEFT JOIN ops.park_country_fallback f ON f.park_id = w.park_key
        ),
        with_lob AS (
            SELECT
                v.fecha_inicio_viaje,
                v.park_key,
                v.city_norm,
                v.park_display_key,
                v.service_type_norm,
                v.comision_empresa_asociada,
                v.distancia_km,
                v.pago_corporativo,
                COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
                CASE WHEN v.pago_corporativo IS NOT NULL AND (v.pago_corporativo::numeric) <> 0 THEN 'B2B' ELSE 'B2C' END AS segment,
                v.country
            FROM with_country v
            LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.tipo_servicio_norm
        )
        SELECT * FROM with_lob WHERE country IN ('co','pe')
    """)
    _log_temp_usage(conn, "post-mv_real_drill_enriched")

    # --- 4b) MV dimensional: agregados desde enriched (menos temp: solo GROUP BY sobre tabla) ---
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_drill_dim_agg AS
        WITH lob_agg AS (
            SELECT
                country,
                'month' AS period_grain,
                DATE_TRUNC('month', fecha_inicio_viaje)::date AS period_start,
                segment,
                'lob'::text AS breakdown,
                lob_group AS dimension_key,
                NULL::text AS dimension_id,
                NULL::text AS city,
                COUNT(*) AS trips,
                (-1) * SUM(comision_empresa_asociada)::numeric AS margin_total,
                (-1) * AVG(comision_empresa_asociada)::numeric AS margin_per_trip,
                (AVG(distancia_km)::numeric) / 1000.0 AS km_avg,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END) AS b2b_trips,
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric) <> 0 THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)) AS b2b_share,
                MAX(fecha_inicio_viaje) AS last_trip_ts
            FROM ops.mv_real_drill_enriched
            GROUP BY country, segment, lob_group, DATE_TRUNC('month', fecha_inicio_viaje)::date
            UNION ALL
            SELECT
                country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date, segment,
                'lob', lob_group, NULL, NULL,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM ops.mv_real_drill_enriched
            GROUP BY country, segment, lob_group, DATE_TRUNC('week', fecha_inicio_viaje)::date
        ),
        park_agg AS (
            SELECT
                country, 'month', DATE_TRUNC('month', fecha_inicio_viaje)::date, segment,
                'park', park_display_key, park_key, city_norm,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM ops.mv_real_drill_enriched
            GROUP BY country, segment, city_norm, park_key, park_display_key, DATE_TRUNC('month', fecha_inicio_viaje)::date
            UNION ALL
            SELECT
                country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date, segment,
                'park', park_display_key, park_key, city_norm,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM ops.mv_real_drill_enriched
            GROUP BY country, segment, city_norm, park_key, park_display_key, DATE_TRUNC('week', fecha_inicio_viaje)::date
        ),
        service_agg AS (
            SELECT
                country, 'month', DATE_TRUNC('month', fecha_inicio_viaje)::date, segment,
                'service_type', service_type_norm, NULL, NULL,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM ops.mv_real_drill_enriched
            GROUP BY country, segment, service_type_norm, DATE_TRUNC('month', fecha_inicio_viaje)::date
            UNION ALL
            SELECT
                country, 'week', DATE_TRUNC('week', fecha_inicio_viaje)::date, segment,
                'service_type', service_type_norm, NULL, NULL,
                COUNT(*), (-1)*SUM(comision_empresa_asociada)::numeric, (-1)*AVG(comision_empresa_asociada)::numeric,
                (AVG(distancia_km)::numeric)/1000.0,
                SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END),
                (SUM(CASE WHEN pago_corporativo IS NOT NULL AND (pago_corporativo::numeric)<>0 THEN 1 ELSE 0 END)::numeric/NULLIF(COUNT(*),0)),
                MAX(fecha_inicio_viaje)
            FROM ops.mv_real_drill_enriched
            GROUP BY country, segment, service_type_norm, DATE_TRUNC('week', fecha_inicio_viaje)::date
        )
        SELECT * FROM lob_agg
        UNION ALL SELECT * FROM park_agg
        UNION ALL SELECT * FROM service_agg
    """)
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_drill_dim_agg IS
        'Drill dimensional: 1 fila por (country, period, segment, breakdown, dimension_key). breakdown: lob|park|service_type. service_type_norm: economico, confort, confort_plus, xl, premier, unknown.'
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_drill_dim_agg
        ON ops.mv_real_drill_dim_agg (country, period_grain, period_start, segment, breakdown, COALESCE(dimension_key,''), COALESCE(dimension_id,''), COALESCE(city,''))
    """)
    op.execute("CREATE INDEX idx_mv_real_drill_dim_country_period ON ops.mv_real_drill_dim_agg (country, period_grain, period_start DESC)")
    op.execute("CREATE INDEX idx_mv_real_drill_dim_breakdown ON ops.mv_real_drill_dim_agg (breakdown, country, period_start)")
    _log_temp_usage(conn, "post-mv_real_drill_dim_agg")

    # --- 4c) Vistas legacy por breakdown ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob CASCADE")
    op.execute("CREATE VIEW ops.v_real_drill_lob AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'lob'")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park CASCADE")
    op.execute("CREATE VIEW ops.v_real_drill_park AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'park'")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_service_type CASCADE")
    op.execute("CREATE VIEW ops.v_real_drill_service_type AS SELECT * FROM ops.mv_real_drill_dim_agg WHERE breakdown = 'service_type'")

    # --- 5) mv_real_rollup_day: base desde canon ---
    _log_temp_usage(conn, "pre-mv_real_rollup_day")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_rollup_day AS
        WITH base AS (
            SELECT
                (t.fecha_inicio_viaje)::date AS trip_day,
                t.fecha_inicio_viaje AS trip_ts,
                NULLIF(TRIM(t.park_id::text), '') AS park_id_norm,
                t.tipo_servicio,
                t.pago_corporativo,
                t.comision_empresa_asociada,
                t.distancia_km,
                p.id AS park_catalog_id,
                p.name AS park_name,
                p.city AS park_city,
                LOWER(TRIM(COALESCE(p.city,'')::text)) AS city_norm
            FROM ops.v_trips_real_canon t
            LEFT JOIN public.parks p ON p.id::text = NULLIF(TRIM(t.park_id::text), '')
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
        ),
        with_country AS (
            SELECT
                b.*,
                COALESCE(d.country, f.country, 'unk') AS country,
                COALESCE(NULLIF(TRIM(b.park_city::text), ''), 'SIN_CITY') AS city,
                CASE
                    WHEN b.park_id_norm IS NULL THEN 'SIN_PARK'
                    ELSE COALESCE(NULLIF(TRIM(b.park_name::text), ''), 'UNKNOWN_PARK (' || b.park_id_norm::text || ')')
                END AS park_name_resolved,
                CASE
                    WHEN b.park_id_norm IS NULL THEN 'SIN_PARK_ID'
                    WHEN b.park_catalog_id IS NULL THEN 'PARK_NO_CATALOG'
                    ELSE 'OK'
                END AS park_bucket,
                CASE
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start') THEN LOWER(TRIM(b.tipo_servicio::text))
                    WHEN LOWER(TRIM(b.tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(b.tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(b.tipo_servicio::text))
                END AS real_tipo_norm
            FROM base b
            LEFT JOIN ops.dim_city_country d ON d.city_norm = b.city_norm
            LEFT JOIN ops.park_country_fallback f ON f.park_id = b.park_id_norm
        ),
        agg AS (
            SELECT
                v.trip_day,
                v.country,
                v.city,
                v.park_id_norm AS park_id,
                v.park_name_resolved,
                v.park_bucket,
                COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group,
                CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END AS segment_tag,
                COUNT(*) AS trips,
                SUM(CASE WHEN v.pago_corporativo IS NOT NULL THEN 1 ELSE 0 END) AS b2b_trips,
                SUM(v.comision_empresa_asociada) AS margin_total_raw,
                ABS(SUM(v.comision_empresa_asociada)) AS margin_total_pos,
                SUM(COALESCE(v.distancia_km::numeric, 0)) / 1000.0 AS distance_total_km,
                MAX(v.trip_ts) AS last_trip_ts
            FROM with_country v
            LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_norm
            GROUP BY v.trip_day, v.country, v.city, v.park_id_norm, v.park_name_resolved, v.park_bucket,
                     COALESCE(m.lob_group, 'UNCLASSIFIED'),
                     CASE WHEN v.pago_corporativo IS NOT NULL THEN 'B2B' ELSE 'B2C' END
        )
        SELECT
            a.trip_day,
            a.country,
            a.city,
            a.park_id,
            a.park_name_resolved,
            a.park_bucket,
            a.lob_group,
            a.segment_tag,
            a.trips,
            a.b2b_trips,
            a.margin_total_raw,
            a.margin_total_pos,
            CASE WHEN a.trips > 0 THEN a.margin_total_pos / a.trips ELSE NULL END AS margin_unit_pos,
            a.distance_total_km,
            CASE WHEN a.trips > 0 AND a.distance_total_km IS NOT NULL THEN a.distance_total_km / a.trips ELSE NULL END AS km_prom,
            a.last_trip_ts
        FROM agg a
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_mv_real_rollup_day
        ON ops.mv_real_rollup_day (trip_day, country, COALESCE(city,''), COALESCE(park_id::text,''), lob_group, segment_tag)
    """)
    op.execute("CREATE INDEX idx_mv_real_rollup_country_day ON ops.mv_real_rollup_day (country, trip_day)")
    op.execute("CREATE INDEX idx_mv_real_rollup_country_city_day ON ops.mv_real_rollup_day (country, city, trip_day)")
    op.execute("CREATE INDEX idx_mv_real_rollup_country_park_day ON ops.mv_real_rollup_day (country, park_id, trip_day)")

    # --- 6) Recrear v_real_data_coverage (depende de mv_real_rollup_day) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_data_coverage AS
        SELECT
            country,
            MIN(trip_day) AS min_trip_date,
            MAX(trip_day) AS last_trip_date,
            MAX(last_trip_ts) AS last_trip_ts,
            date_trunc('month', MIN(trip_day))::date AS min_month,
            date_trunc('week', MIN(trip_day))::date AS min_week,
            date_trunc('month', MAX(trip_day))::date AS last_month_with_data,
            date_trunc('week', MAX(trip_day))::date AS last_week_with_data
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country
    """)

    # --- 7) Recrear vistas de drill que dependen de mv_real_rollup_day / v_real_data_coverage (mismo contenido que 053) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_month AS
        WITH
        countries AS (SELECT unnest(ARRAY['co','pe']) AS country),
        cov AS (
            SELECT MIN(min_month) AS min_month, MAX(last_month_with_data) AS max_month
            FROM ops.v_real_data_coverage
        ),
        bounds AS (
            SELECT
                COALESCE((SELECT min_month FROM cov), date_trunc('month', CURRENT_DATE)::date) AS min_month,
                date_trunc('month', CURRENT_DATE)::date AS current_month
        ),
        month_cal AS (
            SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
            FROM bounds b
        ),
        country_months AS (
            SELECT c.country, m.period_start
            FROM countries c
            CROSS JOIN month_cal m
        ),
        agg AS (
            SELECT
                country,
                date_trunc('month', trip_day)::date AS period_start,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total_raw) AS margin_total_raw,
                SUM(margin_total_pos) AS margin_total_pos,
                SUM(distance_total_km) AS distance_total_km,
                MAX(last_trip_ts) AS last_trip_ts
            FROM ops.mv_real_rollup_day
            WHERE country IN ('co','pe')
            GROUP BY country, date_trunc('month', trip_day)::date
        ),
        combined AS (
            SELECT
                cm.country,
                cm.period_start,
                COALESCE(a.trips, 0) AS trips,
                COALESCE(a.b2b_trips, 0) AS b2b_trips,
                a.margin_total_raw,
                a.margin_total_pos,
                a.distance_total_km,
                a.last_trip_ts,
                (cm.period_start = (SELECT current_month FROM bounds)) AS period_is_current,
                (cm.period_start < (SELECT current_month FROM bounds)) AS period_closed,
                LEAST(CURRENT_DATE - 1, (cm.period_start + interval '1 month' - interval '1 day')::date) AS expected_last_date
            FROM country_months cm
            LEFT JOIN agg a ON a.country = cm.country AND a.period_start = cm.period_start
        )
        SELECT
            c.country,
            c.period_start,
            c.trips,
            c.b2b_trips,
            c.margin_total_raw,
            c.margin_total_pos,
            CASE WHEN c.trips > 0 AND c.margin_total_pos IS NOT NULL THEN c.margin_total_pos / c.trips ELSE NULL END AS margin_unit_pos,
            c.distance_total_km,
            CASE WHEN c.trips > 0 AND c.distance_total_km IS NOT NULL THEN c.distance_total_km / c.trips ELSE NULL END AS km_prom,
            CASE WHEN c.trips > 0 THEN c.b2b_trips::numeric / c.trips ELSE 0 END AS b2b_pct,
            c.last_trip_ts,
            c.expected_last_date,
            (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
            CASE
                WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
                WHEN c.period_is_current THEN 'ABIERTO'
                WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM combined c
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_week AS
        WITH
        countries AS (SELECT unnest(ARRAY['co','pe']) AS country),
        bounds AS (
            SELECT
                COALESCE((SELECT MIN(date_trunc('week', trip_day)::date) FROM ops.mv_real_rollup_day WHERE country IN ('co','pe')), date_trunc('week', CURRENT_DATE)::date) AS min_week,
                date_trunc('week', CURRENT_DATE)::date AS current_week
        ),
        week_cal AS (
            SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
            FROM bounds b
        ),
        country_weeks AS (
            SELECT c.country, w.period_start
            FROM countries c
            CROSS JOIN week_cal w
        ),
        agg AS (
            SELECT
                country,
                date_trunc('week', trip_day)::date AS period_start,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total_raw) AS margin_total_raw,
                SUM(margin_total_pos) AS margin_total_pos,
                SUM(distance_total_km) AS distance_total_km,
                MAX(last_trip_ts) AS last_trip_ts
            FROM ops.mv_real_rollup_day
            WHERE country IN ('co','pe')
            GROUP BY country, date_trunc('week', trip_day)::date
        ),
        combined AS (
            SELECT
                cw.country,
                cw.period_start,
                COALESCE(a.trips, 0) AS trips,
                COALESCE(a.b2b_trips, 0) AS b2b_trips,
                a.margin_total_raw,
                a.margin_total_pos,
                a.distance_total_km,
                a.last_trip_ts,
                (cw.period_start = (SELECT current_week FROM bounds)) AS period_is_current,
                (cw.period_start < (SELECT current_week FROM bounds)) AS period_closed,
                LEAST(CURRENT_DATE - 1, cw.period_start + 6) AS expected_last_date
            FROM country_weeks cw
            LEFT JOIN agg a ON a.country = cw.country AND a.period_start = cw.period_start
        )
        SELECT
            c.country,
            c.period_start,
            c.trips,
            c.b2b_trips,
            c.margin_total_raw,
            c.margin_total_pos,
            CASE WHEN c.trips > 0 AND c.margin_total_pos IS NOT NULL THEN c.margin_total_pos / c.trips ELSE NULL END AS margin_unit_pos,
            c.distance_total_km,
            CASE WHEN c.trips > 0 AND c.distance_total_km IS NOT NULL THEN c.distance_total_km / c.trips ELSE NULL END AS km_prom,
            CASE WHEN c.trips > 0 THEN c.b2b_trips::numeric / c.trips ELSE 0 END AS b2b_pct,
            c.last_trip_ts,
            c.expected_last_date,
            (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) AS falta_data,
            CASE
                WHEN c.period_is_current AND (c.expected_last_date IS NOT NULL AND (c.last_trip_ts IS NULL OR c.last_trip_ts::date < c.expected_last_date)) THEN 'FALTA_DATA'
                WHEN c.period_is_current THEN 'ABIERTO'
                WHEN c.period_closed AND c.trips = 0 THEN 'VACIO'
                ELSE 'CERRADO'
            END AS estado
        FROM combined c
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_month AS
        SELECT
            country,
            lob_group,
            date_trunc('month', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total_raw) AS margin_total_raw,
            SUM(margin_total_pos) AS margin_total_pos,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total_pos) IS NOT NULL THEN SUM(margin_total_pos) / SUM(trips) ELSE NULL END AS margin_unit_pos,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS km_prom,
            MAX(last_trip_ts) AS last_trip_ts,
            'Todos'::text AS segment_tag
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe') AND lob_group IS NOT NULL
        GROUP BY country, lob_group, date_trunc('month', trip_day)::date
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_week AS
        SELECT
            country,
            lob_group,
            date_trunc('week', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total_raw) AS margin_total_raw,
            SUM(margin_total_pos) AS margin_total_pos,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total_pos) IS NOT NULL THEN SUM(margin_total_pos) / SUM(trips) ELSE NULL END AS margin_unit_pos,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS km_prom,
            MAX(last_trip_ts) AS last_trip_ts,
            'Todos'::text AS segment_tag
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe') AND lob_group IS NOT NULL
        GROUP BY country, lob_group, date_trunc('week', trip_day)::date
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_month AS
        SELECT
            country,
            city,
            park_id,
            park_name_resolved,
            park_bucket,
            date_trunc('month', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total_raw) AS margin_total_raw,
            SUM(margin_total_pos) AS margin_total_pos,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total_pos) IS NOT NULL THEN SUM(margin_total_pos) / SUM(trips) ELSE NULL END AS margin_unit_pos,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS km_prom,
            MAX(last_trip_ts) AS last_trip_ts
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('month', trip_day)::date
    """)

    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_week AS
        SELECT
            country,
            city,
            park_id,
            park_name_resolved,
            park_bucket,
            date_trunc('week', trip_day)::date AS period_start,
            SUM(trips) AS trips,
            SUM(b2b_trips) AS b2b_trips,
            SUM(margin_total_raw) AS margin_total_raw,
            SUM(margin_total_pos) AS margin_total_pos,
            CASE WHEN SUM(trips) > 0 AND SUM(margin_total_pos) IS NOT NULL THEN SUM(margin_total_pos) / SUM(trips) ELSE NULL END AS margin_unit_pos,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS km_prom,
            MAX(last_trip_ts) AS last_trip_ts
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country, city, park_id, park_name_resolved, park_bucket, date_trunc('week', trip_day)::date
    """)

    # --- 8) Refrescar MVs: NO ejecutado en migración ---
    # CREATE MATERIALIZED VIEW ... AS SELECT ya popula las MVs. Para actualizar datos tras carga:
    #   python -m scripts.safe_refresh_real_lob
    _log_temp_usage(conn, "fin-migracion-064")


def downgrade() -> None:
    # Revertir: vistas/MVs que leen de trips_all otra vez (definiciones abreviadas; en producción usar backup de 053).
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_service_type CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_dim_agg CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_drill_enriched CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2 CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_freshness_trips CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon CASCADE")
    # Recrear v_real_trips_with_lob_v2, mv_real_lob_drill_agg, mv_real_rollup_day, v_real_data_coverage desde public.trips_all
    # requiere re-ejecutar lógica de 047/053; no se reimplementa aquí. Ejecutar downgrade de 064 y luego upgrade de 053/047.
    raise NotImplementedError(
        "Downgrade 064: recrear vistas/MVs desde trips_all manualmente o volver a aplicar migraciones 047/053."
    )
