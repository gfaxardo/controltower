"""lob_homologation_add_park_id

Revision ID: 024_lob_homologation_park
Revises: 023_lob_hunt_by_park
Create Date: 2026-01-23 05:00:00.000000

E2E: Extender homologación para soportar park_id. Ranking: park_id match > country+city > country > global.
"""

from alembic import op

revision = "024_lob_homologation_park"
down_revision = "023_lob_hunt_by_park"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Add park_id (TEXT: mismo tipo que dim_park.park_id)
    op.execute("""
        ALTER TABLE ops.lob_homologation
        ADD COLUMN IF NOT EXISTS park_id TEXT NULL
    """)

    # Drop old unique constraint (nombre generado por PostgreSQL)
    op.execute("""
        DO $$
        DECLARE
            cname TEXT;
        BEGIN
            SELECT con.conname INTO cname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'ops' AND rel.relname = 'lob_homologation'
              AND con.contype = 'u'
            LIMIT 1;
            IF cname IS NOT NULL THEN
                EXECUTE format('ALTER TABLE ops.lob_homologation DROP CONSTRAINT %I', cname);
            END IF;
        END $$;
    """)

    # Índice único (PG < 15: NULLs no se consideran iguales; con park_id no NULL evita duplicados)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lob_homologation_country_city_park_real_plan
        ON ops.lob_homologation (country, city, park_id, real_tipo_servicio, plan_lob_name)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_lob_homologation_park_id
        ON ops.lob_homologation(park_id) WHERE park_id IS NOT NULL
    """)

    # 2) v_real_lob_base: añadir park_id para ranking en resolución
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_base CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_base AS
        SELECT
            t.id AS trip_id,
            t.park_id,
            t.fecha_inicio_viaje AS trip_date,
            vc.country,
            vc.city_resolved AS city,
            vc.city_raw,
            COALESCE(t.tipo_servicio, '') AS lob_base,
            CASE WHEN COALESCE(t.pago_corporativo, 0)::numeric > 0 THEN 'B2B' ELSE 'B2C' END AS market_type,
            CASE WHEN COALESCE(t.pago_corporativo, 0)::numeric > 0 THEN 'B2B_' || COALESCE(t.tipo_servicio, '') ELSE COALESCE(t.tipo_servicio, '') END AS lob_effective,
            t.pago_corporativo AS pago_corporativo_raw
        FROM public.trips_all t
        JOIN ops.v_city_resolved vc ON vc.trip_id = t.id
        WHERE t.condicion = 'Completado'
    """)

    # v_real_lob_resolution: ranking 1) park_id exact, 2) country+city, 3) country, 4) global
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolution AS
        SELECT
            rb.trip_id,
            rb.park_id,
            rb.country,
            rb.city,
            rb.city_raw,
            rb.trip_date,
            rb.lob_base,
            rb.market_type,
            rb.lob_effective,
            h.plan_lob_name AS homologated_plan_lob,
            h.homologation_id,
            h.confidence AS homologation_confidence,
            l.lob_id,
            lc.lob_name,
            l.mapping_id,
            CASE
                WHEN l.lob_id IS NOT NULL THEN 'OK'
                WHEN h.homologation_id IS NOT NULL THEN 'HOMOLOGATED_NO_MAPPING'
                ELSE 'UNMATCHED'
            END AS resolution_status,
            l.confidence,
            l.priority AS mapping_priority
        FROM ops.v_real_lob_base rb
        LEFT JOIN LATERAL (
            SELECT h.*
            FROM ops.lob_homologation h
            WHERE TRIM(LOWER(h.real_tipo_servicio)) = TRIM(LOWER(rb.lob_base))
              AND (h.country IS NULL OR h.country = '' OR h.country = rb.country)
              AND (h.city IS NULL OR h.city = '' OR h.city = rb.city)
              AND (h.park_id IS NULL OR h.park_id = rb.park_id)
            ORDER BY
                CASE WHEN h.park_id IS NOT NULL AND h.park_id = rb.park_id THEN 0
                     WHEN h.park_id IS NULL AND h.country IS NOT NULL AND h.city IS NOT NULL THEN 1
                     WHEN h.country IS NOT NULL AND (h.city IS NULL OR h.city = '') THEN 2
                     WHEN h.country IS NULL OR h.country = '' THEN 3
                     ELSE 4 END,
                h.created_at DESC NULLS LAST
            LIMIT 1
        ) h ON TRUE
        LEFT JOIN LATERAL (
            SELECT m.*
            FROM ops.lob_plan_real_mapping m
            WHERE (m.country IS NULL OR m.country = rb.country)
              AND (m.city IS NULL OR m.city = rb.city)
              AND (m.service_type IS NULL OR LOWER(TRIM(m.service_type)) = LOWER(TRIM(rb.lob_base)))
              AND (m.market_type IS NULL OR m.market_type = rb.market_type)
              AND (m.valid_to IS NULL OR rb.trip_date::date <= m.valid_to)
              AND (m.valid_from IS NULL OR rb.trip_date::date >= m.valid_from)
            ORDER BY m.priority ASC, m.confidence DESC
            LIMIT 1
        ) l ON TRUE
        LEFT JOIN ops.lob_catalog lc ON (
            lc.lob_id = l.lob_id
            OR (h.plan_lob_name IS NOT NULL AND l.lob_id IS NULL
                AND TRIM(LOWER(lc.lob_name)) = TRIM(LOWER(h.plan_lob_name))
                AND (lc.country IS NULL OR lc.country = '' OR lc.country = rb.country)
                AND (lc.city IS NULL OR lc.city = '' OR lc.city = rb.city)
                AND lc.status = 'active')
        )
    """)

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_without_plan_lob AS
        SELECT country, city, city_raw, lob_base, market_type,
               COUNT(*) AS trips_count,
               MIN(trip_date) AS first_seen_date,
               MAX(trip_date) AS last_seen_date,
               COUNT(DISTINCT CASE WHEN homologation_id IS NOT NULL THEN homologation_id END) AS has_homologation_count,
               COUNT(DISTINCT CASE WHEN homologation_id IS NULL THEN trip_id END) AS no_homologation_count
        FROM ops.v_real_lob_resolution
        WHERE resolution_status IN ('UNMATCHED', 'HOMOLOGATED_NO_MAPPING')
        GROUP BY country, city, city_raw, lob_base, market_type
        ORDER BY trips_count DESC
    """)

    # 3) v_real_to_plan_lob_resolved: prioridad 1) park_id+country+city, 2) country+city, 3) country, 4) global
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_to_plan_lob_resolved CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_to_plan_lob_resolved AS
        WITH real AS (
            SELECT country, city, real_tipo_servicio, trips_count
            FROM ops.mv_real_tipo_servicio_universe_fast
        ),
        h_ranked AS (
            SELECT h.*,
                CASE
                    WHEN h.park_id IS NOT NULL AND h.country IS NOT NULL AND h.city IS NOT NULL THEN 1
                    WHEN h.park_id IS NULL AND h.country IS NOT NULL AND h.city IS NOT NULL THEN 2
                    WHEN h.country IS NOT NULL AND (h.city IS NULL OR h.city = '') THEN 3
                    WHEN h.country IS NULL OR h.country = '' THEN 4
                    ELSE 5
                END AS specificity_rank
            FROM ops.lob_homologation h
        ),
        real_join AS (
            SELECT r.country, r.city, r.real_tipo_servicio, r.trips_count,
                   hh.plan_lob_name, hh.confidence, hh.specificity_rank,
                   ROW_NUMBER() OVER (
                       PARTITION BY r.country, r.city, r.real_tipo_servicio
                       ORDER BY hh.specificity_rank ASC, hh.created_at DESC NULLS LAST
                   ) AS rn
            FROM real r
            LEFT JOIN h_ranked hh
                ON (hh.country IS NULL OR LOWER(TRIM(COALESCE(hh.country,''))) = LOWER(TRIM(COALESCE(r.country,''))))
               AND (hh.city IS NULL OR LOWER(TRIM(COALESCE(hh.city,''))) = LOWER(TRIM(COALESCE(r.city,''))))
               AND TRIM(LOWER(hh.real_tipo_servicio)) = TRIM(LOWER(r.real_tipo_servicio))
               AND hh.park_id IS NULL
        )
        SELECT country, city, real_tipo_servicio, trips_count,
               CASE WHEN rn = 1 THEN TRIM(LOWER(plan_lob_name)) END AS plan_lob_name_norm,
               CASE WHEN rn = 1 THEN confidence END AS homologation_confidence
        FROM real_join
        WHERE rn = 1
    """)

    # Recrear v_plan_vs_real_lob_check_resolved (depende de v_real_to_plan_lob_resolved)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_lob_check_resolved AS
        WITH plan AS (
            SELECT country, city, plan_lob_name_norm, plan_trips, plan_revenue FROM ops.v_plan_lob_agg
        ),
        real_raw AS (
            SELECT country, city, real_tipo_servicio, trips_count FROM ops.mv_real_tipo_servicio_universe_fast
        ),
        norm_plan AS (
            SELECT LOWER(TRIM(COALESCE(country,''))) AS country_norm, LOWER(TRIM(COALESCE(city,''))) AS city_norm,
                   country, city, plan_lob_name_norm, plan_trips, plan_revenue FROM plan
        ),
        norm_real AS (
            SELECT LOWER(TRIM(COALESCE(country,''))) AS country_norm, LOWER(TRIM(COALESCE(city,''))) AS city_norm,
                   country, city, real_tipo_servicio, trips_count FROM real_raw
        ),
        direct_match AS (
            SELECT p.country, p.city, p.plan_lob_name_norm, p.plan_trips, p.plan_revenue,
                   r.real_tipo_servicio, r.trips_count AS real_trips, 'DIRECT' AS resolution_method
            FROM norm_plan p
            JOIN norm_real r ON r.country_norm = p.country_norm AND r.city_norm = p.city_norm
             AND TRIM(LOWER(r.real_tipo_servicio)) = p.plan_lob_name_norm
        ),
        plan_direct_miss AS (
            SELECT p.country, p.city, p.plan_lob_name_norm, p.plan_trips, p.plan_revenue
            FROM norm_plan p
            LEFT JOIN direct_match d ON d.country = p.country AND (d.city IS NOT DISTINCT FROM p.city) AND d.plan_lob_name_norm = p.plan_lob_name_norm
            WHERE d.plan_lob_name_norm IS NULL
        ),
        real_to_plan AS (
            SELECT country, city, real_tipo_servicio, trips_count, plan_lob_name_norm
            FROM ops.v_real_to_plan_lob_resolved WHERE plan_lob_name_norm IS NOT NULL
        ),
        homologation_match AS (
            SELECT p.country, p.city, p.plan_lob_name_norm, p.plan_trips, p.plan_revenue,
                   rtp.real_tipo_servicio, rtp.trips_count AS real_trips, 'HOMOLOGATION' AS resolution_method
            FROM plan_direct_miss p
            JOIN real_to_plan rtp ON LOWER(TRIM(COALESCE(rtp.country,''))) = LOWER(TRIM(COALESCE(p.country,'')))
             AND LOWER(TRIM(COALESCE(rtp.city,''))) = LOWER(TRIM(COALESCE(p.city,'')))
             AND rtp.plan_lob_name_norm = p.plan_lob_name_norm
        ),
        plan_side AS (
            SELECT * FROM direct_match UNION ALL SELECT * FROM homologation_match
        ),
        real_mapped AS (SELECT country, city, real_tipo_servicio FROM plan_side),
        real_only AS (
            SELECT r.country, r.city, NULL::TEXT AS plan_lob_name_norm, 0::NUMERIC AS plan_trips, 0::NUMERIC AS plan_revenue,
                   r.real_tipo_servicio, r.trips_count AS real_trips, 'NONE' AS resolution_method
            FROM real_raw r
            LEFT JOIN real_mapped m ON LOWER(TRIM(COALESCE(m.country,''))) = LOWER(TRIM(COALESCE(r.country,'')))
             AND LOWER(TRIM(COALESCE(m.city,''))) = LOWER(TRIM(COALESCE(r.city,''))) AND m.real_tipo_servicio = r.real_tipo_servicio
            WHERE m.real_tipo_servicio IS NULL
        ),
        plan_mapped AS (SELECT country, city, plan_lob_name_norm FROM plan_side),
        plan_only AS (
            SELECT p.country, p.city, p.plan_lob_name_norm, p.plan_trips, p.plan_revenue,
                   NULL::TEXT AS real_tipo_servicio, 0::NUMERIC AS real_trips, 'NONE' AS resolution_method
            FROM plan p
            LEFT JOIN plan_mapped pm ON LOWER(TRIM(COALESCE(pm.country,''))) = LOWER(TRIM(COALESCE(p.country,'')))
             AND LOWER(TRIM(COALESCE(pm.city,''))) = LOWER(TRIM(COALESCE(p.city,''))) AND pm.plan_lob_name_norm = p.plan_lob_name_norm
            WHERE pm.plan_lob_name_norm IS NULL
        ),
        combined AS (
            SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips, resolution_method FROM plan_side
            UNION ALL SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips, resolution_method FROM real_only
            UNION ALL SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips, resolution_method FROM plan_only
        )
        SELECT country, city, plan_lob_name_norm, real_tipo_servicio, plan_trips, plan_revenue, real_trips,
               CASE WHEN plan_lob_name_norm IS NOT NULL AND real_tipo_servicio IS NOT NULL THEN 'OK'
                    WHEN plan_lob_name_norm IS NOT NULL AND real_tipo_servicio IS NULL THEN 'PLAN_ONLY'
                    WHEN plan_lob_name_norm IS NULL AND real_tipo_servicio IS NOT NULL THEN 'REAL_ONLY' ELSE 'UNKNOWN' END AS coverage_status,
               resolution_method
        FROM combined
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_to_plan_lob_resolved CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_without_plan_lob CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_resolution CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_base CASCADE")

    op.execute("DROP INDEX IF EXISTS ops.uq_lob_homologation_country_city_park_real_plan")
    op.execute("ALTER TABLE ops.lob_homologation DROP COLUMN IF EXISTS park_id")
    op.execute("DROP INDEX IF EXISTS ops.idx_lob_homologation_park_id")

    op.execute("""
        ALTER TABLE ops.lob_homologation
        ADD CONSTRAINT lob_homologation_country_city_real_tipo_servicio_plan_lob_name_key
        UNIQUE (country, city, real_tipo_servicio, plan_lob_name)
    """)

    # Recrear vistas sin park_id (definiciones mínimas; 022/020 tenían la lógica completa)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_base AS
        SELECT t.id AS trip_id, t.fecha_inicio_viaje AS trip_date, vc.country, vc.city_resolved AS city, vc.city_raw,
               COALESCE(t.tipo_servicio, '') AS lob_base,
               CASE WHEN COALESCE(t.pago_corporativo, 0)::numeric > 0 THEN 'B2B' ELSE 'B2C' END AS market_type,
               CASE WHEN COALESCE(t.pago_corporativo, 0)::numeric > 0 THEN 'B2B_' || COALESCE(t.tipo_servicio, '') ELSE COALESCE(t.tipo_servicio, '') END AS lob_effective,
               t.pago_corporativo AS pago_corporativo_raw
        FROM public.trips_all t
        JOIN ops.v_city_resolved vc ON vc.trip_id = t.id
        WHERE t.condicion = 'Completado'
    """)
    # v_real_lob_resolution y v_real_without_plan_lob se restauran con upgrade de 022 al bajar 024 (no re-aplicamos 022 aquí)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_lob_resolution AS
        SELECT rb.trip_id, rb.country, rb.city, rb.city_raw, rb.trip_date, rb.lob_base, rb.market_type, rb.lob_effective,
               h.plan_lob_name AS homologated_plan_lob, h.homologation_id, h.confidence AS homologation_confidence,
               l.lob_id, lc.lob_name, l.mapping_id,
               CASE WHEN l.lob_id IS NOT NULL THEN 'OK' WHEN h.homologation_id IS NOT NULL THEN 'HOMOLOGATED_NO_MAPPING' ELSE 'UNMATCHED' END AS resolution_status,
               l.confidence, l.priority AS mapping_priority
        FROM ops.v_real_lob_base rb
        LEFT JOIN ops.lob_homologation h ON (h.country IS NULL OR h.country = '' OR h.country = rb.country) AND (h.city IS NULL OR h.city = '' OR h.city = rb.city)
         AND TRIM(LOWER(h.real_tipo_servicio)) = TRIM(LOWER(rb.lob_base))
        LEFT JOIN LATERAL (SELECT m.* FROM ops.lob_plan_real_mapping m WHERE (m.country IS NULL OR m.country = rb.country) AND (m.city IS NULL OR m.city = rb.city)
         AND (m.service_type IS NULL OR LOWER(TRIM(m.service_type)) = LOWER(TRIM(rb.lob_base))) AND (m.market_type IS NULL OR m.market_type = rb.market_type)
         AND (m.valid_to IS NULL OR rb.trip_date::date <= m.valid_to) AND (m.valid_from IS NULL OR rb.trip_date::date >= m.valid_from)
         ORDER BY m.priority ASC, m.confidence DESC LIMIT 1) l ON TRUE
        LEFT JOIN ops.lob_catalog lc ON lc.lob_id = l.lob_id OR (h.plan_lob_name IS NOT NULL AND l.lob_id IS NULL AND TRIM(LOWER(lc.lob_name)) = TRIM(LOWER(h.plan_lob_name)) AND (lc.country IS NULL OR lc.country = '' OR lc.country = rb.country) AND (lc.city IS NULL OR lc.city = '' OR lc.city = rb.city) AND lc.status = 'active')
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_without_plan_lob AS
        SELECT country, city, city_raw, lob_base, market_type, COUNT(*) AS trips_count, MIN(trip_date) AS first_seen_date, MAX(trip_date) AS last_seen_date
        FROM ops.v_real_lob_resolution WHERE resolution_status IN ('UNMATCHED', 'HOMOLOGATED_NO_MAPPING')
        GROUP BY country, city, city_raw, lob_base, market_type ORDER BY trips_count DESC
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_to_plan_lob_resolved AS
        WITH real AS (SELECT country, city, real_tipo_servicio, trips_count FROM ops.mv_real_tipo_servicio_universe_fast),
        h_ranked AS (SELECT h.*, CASE WHEN h.country IS NOT NULL AND h.city IS NOT NULL THEN 1 WHEN h.country IS NOT NULL AND h.city IS NULL THEN 2 WHEN h.country IS NULL AND h.city IS NULL THEN 3 ELSE 4 END AS specificity_rank FROM ops.lob_homologation h),
        real_join AS (SELECT r.country, r.city, r.real_tipo_servicio, r.trips_count, hh.plan_lob_name, hh.confidence, hh.specificity_rank,
            ROW_NUMBER() OVER (PARTITION BY r.country, r.city, r.real_tipo_servicio ORDER BY hh.specificity_rank ASC, hh.created_at DESC NULLS LAST) AS rn
            FROM real r LEFT JOIN h_ranked hh ON (hh.country IS NULL OR LOWER(TRIM(COALESCE(hh.country,''))) = LOWER(TRIM(COALESCE(r.country,'')))) AND (hh.city IS NULL OR LOWER(TRIM(COALESCE(hh.city,''))) = LOWER(TRIM(COALESCE(r.city,'')))) AND TRIM(LOWER(hh.real_tipo_servicio)) = TRIM(LOWER(r.real_tipo_servicio)))
        SELECT country, city, real_tipo_servicio, trips_count, CASE WHEN rn = 1 THEN TRIM(LOWER(plan_lob_name)) END AS plan_lob_name_norm, CASE WHEN rn = 1 THEN confidence END AS homologation_confidence FROM real_join WHERE rn = 1
    """)
