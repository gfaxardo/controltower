"""
CT-REAL-LOB-ROOT-CAUSE-FIX: índices en tablas fuente y capa 120d index-friendly.

FASE B: Índices sobre fecha_inicio_viaje para range scan de la ventana de 120 días.
FASE C: Vistas _120d que aplican el filtro de fecha en cada rama del UNION (no después),
        para que el planner use Index Scan y evite Seq Scan + Sort masivo.

- public.trips_all: índice (fecha_inicio_viaje) WHERE fecha_inicio_viaje IS NOT NULL
- public.trips_2026: índice (fecha_inicio_viaje)
- ops.v_trips_real_canon_120d: misma estructura que v_trips_real_canon con filtro 120d en cada rama
- ops.v_real_trips_service_lob_resolved_120d: igual que v_real_trips_service_lob_resolved leyendo de _120d
- ops.v_real_trips_with_lob_v2_120d: wrapper para contrato LOB sobre _120d
- MVs month_v2 y week_v2: recreadas para usar v_real_trips_with_lob_v2_120d (sin WHERE en base)
"""
from alembic import op
from sqlalchemy import text

revision = "098_real_lob_root_cause_120d"
down_revision = "097_real_vs_projection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- FASE B: Índices en tablas fuente (justificados por diagnóstico) ---
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_trips_all_fecha_inicio_viaje
        ON public.trips_all (fecha_inicio_viaje)
        WHERE fecha_inicio_viaje IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_trips_2026_fecha_inicio_viaje
        ON public.trips_2026 (fecha_inicio_viaje)
    """)

    # --- FASE C: Vista canónica con ventana 120d (filtro en cada rama del UNION) ---
    has_2026 = conn.execute(text("""
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'trips_2026'
    """)).fetchone()

    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2_120d CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved_120d CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon_120d CASCADE")

    if has_2026:
        op.execute("""
            CREATE VIEW ops.v_trips_real_canon_120d AS
            WITH union_all AS (
                SELECT
                    t.id, t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.fecha_finalizacion,
                    t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km, t.condicion, t.conductor_id,
                    'trips_all'::text AS source_table, 1 AS source_priority
                FROM public.trips_all t
                WHERE t.fecha_inicio_viaje IS NOT NULL
                  AND t.fecha_inicio_viaje < '2026-01-01'::date
                  AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
                UNION ALL
                SELECT
                    t.id, t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.fecha_finalizacion,
                    t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km, t.condicion, t.conductor_id,
                    'trips_2026'::text AS source_table, 2 AS source_priority
                FROM public.trips_2026 t
                WHERE t.fecha_inicio_viaje >= '2026-01-01'::date
                  AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
            )
            SELECT DISTINCT ON (id)
                id, park_id, tipo_servicio, fecha_inicio_viaje, fecha_finalizacion,
                comision_empresa_asociada, pago_corporativo, distancia_km, condicion, conductor_id, source_table
            FROM union_all
            ORDER BY id, source_priority DESC, fecha_inicio_viaje DESC NULLS LAST
        """)
    else:
        op.execute("""
            CREATE VIEW ops.v_trips_real_canon_120d AS
            SELECT
                t.id, t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.fecha_finalizacion,
                t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km, t.condicion, t.conductor_id,
                'trips_all'::text AS source_table
            FROM public.trips_all t
            WHERE t.fecha_inicio_viaje IS NOT NULL
              AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
        """)

    op.execute("""
        COMMENT ON VIEW ops.v_trips_real_canon_120d IS
        'Ventana 120 días para Real LOB: mismo contrato que v_trips_real_canon con filtro por fecha en cada rama (index-friendly).'
    """)

    # v_real_trips_service_lob_resolved_120d (misma definición que en 090 pero desde v_trips_real_canon_120d)
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

    # --- Recrear MVs para usar la capa 120d (sin WHERE en base; el filtro está en la vista) ---
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2_120d),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
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
            a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.month_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
        FROM agg a
        CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")

    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (SELECT * FROM ops.v_real_trips_with_lob_v2_120d),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT
                country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
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
            a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag,
            a.week_start, a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
        FROM agg a
        CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")
    # Restaurar MVs como en 096 (con WHERE en base sobre v_real_trips_with_lob_v2)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_month_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
        ),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue, SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km, MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('month', fecha_inicio_viaje)::DATE)
        )
        SELECT a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag, a.month_start,
            a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.month_start = (DATE_TRUNC('month', g.m)::DATE)) AS is_open
        FROM agg a CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_lob_week_v2 AS
        WITH base AS (
            SELECT * FROM ops.v_real_trips_with_lob_v2
            WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
        ),
        global_max AS (SELECT MAX(fecha_inicio_viaje) AS m FROM base),
        agg AS (
            SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                (DATE_TRUNC('week', fecha_inicio_viaje)::DATE) AS week_start,
                COUNT(*) AS trips, SUM(revenue) AS revenue, SUM(comision_empresa_asociada) AS margin_total,
                SUM(COALESCE(distancia_km::numeric, 0)) / 1000.0 AS distance_total_km, MAX(fecha_inicio_viaje) AS max_trip_ts
            FROM base
            GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, (DATE_TRUNC('week', fecha_inicio_viaje)::DATE)
        )
        SELECT a.country, a.city, a.park_id, a.park_name, a.lob_group, a.real_tipo_servicio_norm, a.segment_tag, a.week_start,
            a.trips, a.revenue, a.margin_total, a.distance_total_km, a.max_trip_ts,
            (a.week_start = (DATE_TRUNC('week', g.m)::DATE)) AS is_open
        FROM agg a CROSS JOIN global_max g
        WITH NO DATA
    """)
    op.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
    op.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")

    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2_120d CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved_120d CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon_120d CASCADE")

    op.execute("DROP INDEX IF EXISTS public.ix_trips_all_fecha_inicio_viaje")
    op.execute("DROP INDEX IF EXISTS public.ix_trips_2026_fecha_inicio_viaje")
