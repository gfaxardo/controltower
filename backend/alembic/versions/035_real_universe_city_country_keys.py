"""
PASO 4 FIX UNMAPPED — Vista real con city/country normalizados (city_key, country_key)
para que REAL matchee con PLAN. Join parks.id = trips_all.park_id.
"""
from alembic import op

revision = "035_real_city_country_keys"
down_revision = "034_lob_homologation_final"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")

    # city_norm desde nombre de park (ILIKE) + fallback p.city; city/country de salida = keys (sin tildes)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        WITH base AS (
            SELECT
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM public.trips_all t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio)) < 100
              AND t.tipo_servicio NOT LIKE '%%->%%'
        ),
        with_city AS (
            SELECT
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                park_id_raw,
                COALESCE(
                    NULLIF(TRIM(park_name_raw::text), ''),
                    NULLIF(TRIM(park_city_raw::text), ''),
                    park_id_raw::text
                ) AS park_name,
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
                LOWER(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                        'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')
                ) AS city_key
            FROM with_city
        )
        SELECT
            park_id::text AS park_id,
            park_name AS park_name,
            COALESCE(NULLIF(city_key, ''), '') AS city,
            CASE
                WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                ELSE ''
            END AS country,
            LOWER(TRIM(tipo_servicio::text)) AS real_tipo_servicio,
            COUNT(*) AS real_trips,
            MIN((fecha_inicio_viaje)::date) AS first_seen_date,
            MAX((fecha_inicio_viaje)::date) AS last_seen_date
        FROM with_key
        GROUP BY park_id, park_name, city_key, LOWER(TRIM(tipo_servicio::text))
    """)

    # Recrear vistas que dependen de v_real_universe_by_park_for_hunt (CASCADE las borró)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolved_final AS
        SELECT
            r.country,
            r.city,
            r.park_id,
            r.park_name,
            r.real_tipo_servicio,
            COALESCE(h.plan_lob_name, 'UNMAPPED') AS resolved_lob,
            r.real_trips,
            r.first_seen_date,
            r.last_seen_date
        FROM ops.v_real_universe_by_park_for_hunt r
        LEFT JOIN ops.lob_homologation_final h
            ON LOWER(TRIM(COALESCE(r.country, ''))) = LOWER(TRIM(COALESCE(h.country, '')))
           AND LOWER(TRIM(r.city)) = LOWER(TRIM(COALESCE(h.city, '')))
           AND LOWER(TRIM(r.park_id)) = LOWER(TRIM(COALESCE(h.park_id, '')))
           AND LOWER(TRIM(r.real_tipo_servicio)) = LOWER(TRIM(h.real_tipo_servicio))
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_final AS
        SELECT
            COALESCE(p.country, r.country) AS country,
            COALESCE(p.city, r.city) AS city,
            COALESCE(p.plan_lob_name, r.resolved_lob) AS lob,
            COALESCE(SUM(p.trips_plan), 0) AS plan_trips,
            COALESCE(SUM(r.real_trips), 0) AS real_trips,
            COALESCE(SUM(r.real_trips), 0) - COALESCE(SUM(p.trips_plan), 0) AS variance_trips
        FROM ops.v_plan_lob_universe_raw p
        FULL OUTER JOIN ops.v_real_lob_resolved_final r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND LOWER(TRIM(p.plan_lob_name)) = LOWER(TRIM(r.resolved_lob))
        GROUP BY 1, 2, 3
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_universe_by_park_for_hunt CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_universe_by_park_for_hunt AS
        SELECT
          p.id::text AS park_id,
          COALESCE(NULLIF(TRIM(p.name::text), ''), NULLIF(TRIM(p.created_at::text), ''), p.id::text) AS park_name,
          LOWER(TRIM(COALESCE(p.city::text, ''))) AS city,
          ''::text AS country,
          LOWER(TRIM(t.tipo_servicio::text)) AS real_tipo_servicio,
          COUNT(*) AS real_trips,
          MIN((t.fecha_inicio_viaje)::date) AS first_seen_date,
          MAX((t.fecha_inicio_viaje)::date) AS last_seen_date
        FROM public.trips_all t
        JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
        WHERE t.tipo_servicio IS NOT NULL AND t.condicion = 'Completado'
        GROUP BY 1, 2, 3, 4, 5
    """)
