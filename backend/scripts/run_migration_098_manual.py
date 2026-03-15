#!/usr/bin/env python3
"""
Aplica la migración 098 (índices + vistas _120d + MVs) usando la conexión del proyecto.
Usar cuando 'alembic upgrade head' no esté disponible en el entorno.

Uso: cd backend && python scripts/run_migration_098_manual.py
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass


def main():
    from app.db.connection import get_db, init_db_pool

    init_db_pool()
    with get_db() as conn:
        conn.autocommit = True
        cur = conn.cursor()

        # --- FASE B: Índices ---
        print("Creando índices en trips_all y trips_2026...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_trips_all_fecha_inicio_viaje
            ON public.trips_all (fecha_inicio_viaje)
            WHERE fecha_inicio_viaje IS NOT NULL
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_trips_2026_fecha_inicio_viaje
            ON public.trips_2026 (fecha_inicio_viaje)
        """)

        # --- Comprobar trips_2026 ---
        cur.execute("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'trips_2026'
        """)
        has_2026 = cur.fetchone() is not None

        # --- FASE C: Drop vistas _120d si existen ---
        print("Eliminando vistas _120d anteriores si existen...")
        cur.execute("DROP VIEW IF EXISTS ops.v_real_trips_with_lob_v2_120d CASCADE")
        cur.execute("DROP VIEW IF EXISTS ops.v_real_trips_service_lob_resolved_120d CASCADE")
        cur.execute("DROP VIEW IF EXISTS ops.v_trips_real_canon_120d CASCADE")

        if has_2026:
            print("Creando ops.v_trips_real_canon_120d (con trips_2026)...")
            cur.execute("""
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
            print("Creando ops.v_trips_real_canon_120d (solo trips_all)...")
            cur.execute("""
                CREATE VIEW ops.v_trips_real_canon_120d AS
                SELECT
                    t.id, t.park_id, t.tipo_servicio, t.fecha_inicio_viaje, t.fecha_finalizacion,
                    t.comision_empresa_asociada, t.pago_corporativo, t.distancia_km, t.condicion, t.conductor_id,
                    'trips_all'::text AS source_table
                FROM public.trips_all t
                WHERE t.fecha_inicio_viaje IS NOT NULL
                  AND t.fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days'
            """)

        cur.execute("""
            COMMENT ON VIEW ops.v_trips_real_canon_120d IS
            'Ventana 120 días para Real LOB: mismo contrato que v_trips_real_canon con filtro por fecha en cada rama (index-friendly).'
        """)

        print("Creando ops.v_real_trips_service_lob_resolved_120d...")
        cur.execute("""
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
        """.replace("%%", "%"))

        print("Creando ops.v_real_trips_with_lob_v2_120d...")
        cur.execute("""
            CREATE VIEW ops.v_real_trips_with_lob_v2_120d AS
            SELECT
                country, city, park_id, park_name, fecha_inicio_viaje,
                tipo_servicio_norm AS real_tipo_servicio_norm,
                lob_group_resolved AS lob_group,
                segment_tag, revenue, comision_empresa_asociada, distancia_km
            FROM ops.v_real_trips_service_lob_resolved_120d
        """)

        # --- Recrear MVs ---
        print("Eliminando MVs antiguas y creando MVs con capa 120d...")
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_week_v2")
        cur.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_lob_month_v2")

        cur.execute("""
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
        cur.execute("CREATE UNIQUE INDEX uq_mv_real_lob_month_v2 ON ops.mv_real_lob_month_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, month_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_month_v2_ccpm ON ops.mv_real_lob_month_v2 (country, city, park_id, month_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_month_v2_ls ON ops.mv_real_lob_month_v2 (lob_group, segment_tag)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_lookup ON ops.mv_real_lob_month_v2 (real_tipo_servicio_norm)")

        cur.execute("""
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
        cur.execute("CREATE UNIQUE INDEX uq_mv_real_lob_week_v2 ON ops.mv_real_lob_week_v2 (country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag, week_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_week_v2_ccpw ON ops.mv_real_lob_week_v2 (country, city, park_id, week_start)")
        cur.execute("CREATE INDEX idx_mv_real_lob_week_v2_ls ON ops.mv_real_lob_week_v2 (lob_group, segment_tag)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_week_lookup ON ops.mv_real_lob_week_v2 (real_tipo_servicio_norm)")

        # Marcar revisión en alembic_version si existe la tabla
        cur.execute("""
            UPDATE alembic_version SET version_num = '098_real_lob_root_cause_120d'
            WHERE version_num = '097_real_vs_projection'
        """)
        if cur.rowcount:
            print("Actualizada alembic_version a 098_real_lob_root_cause_120d.")
        else:
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'alembic_version'")
            if cur.fetchone():
                print("Aviso: alembic_version no tenía 097; no se actualizó. Comprueba con: SELECT * FROM alembic_version")
            else:
                print("Tabla alembic_version no existe; migración aplicada igualmente.")

        print("Migración 098 aplicada correctamente.")


if __name__ == "__main__":
    main()
