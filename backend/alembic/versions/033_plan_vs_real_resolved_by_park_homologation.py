"""
PASO 3D E2E — Vista v_plan_vs_real_lob_check_resolved por homologación (country, city, park_id, real_tipo_servicio).
Real desde v_real_universe_by_park_for_hunt; country heredado de lob_homologation.
"""
from alembic import op

revision = "033_plan_vs_real_resolved_park"
down_revision = "032_real_universe_join_parks_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check_resolved CASCADE")

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_lob_check_resolved AS
        WITH
        real_park AS (
            SELECT park_id, city, country, real_tipo_servicio, real_trips, first_seen_date, last_seen_date
            FROM ops.v_real_universe_by_park_for_hunt
        ),
        resolved AS (
            SELECT
                r.park_id,
                r.city,
                r.real_tipo_servicio,
                r.real_trips,
                r.first_seen_date,
                r.last_seen_date,
                LOWER(TRIM(h.plan_lob_name)) AS resolved_plan_lob_name,
                LOWER(TRIM(COALESCE(h.country, ''))) AS country
            FROM real_park r
            LEFT JOIN ops.lob_homologation h
              ON LOWER(TRIM(COALESCE(h.city, ''))) = LOWER(TRIM(r.city))
             AND LOWER(TRIM(COALESCE(h.park_id, ''))) = LOWER(TRIM(r.park_id))
             AND LOWER(TRIM(h.real_tipo_servicio)) = LOWER(TRIM(r.real_tipo_servicio))
        ),
        real_agg AS (
            SELECT
                country,
                city,
                resolved_plan_lob_name,
                SUM(real_trips) AS real_trips_total,
                MIN(first_seen_date) AS first_seen_date,
                MAX(last_seen_date) AS last_seen_date
            FROM resolved
            GROUP BY 1, 2, 3
        ),
        unmapped_agg AS (
            SELECT country, city, SUM(real_trips_total) AS unmapped_real_trips_total
            FROM real_agg
            WHERE resolved_plan_lob_name IS NULL
            GROUP BY 1, 2
        ),
        plan AS (
            SELECT country, city, plan_lob_name, trips_plan, revenue_plan
            FROM ops.v_plan_lob_universe_raw
        ),
        base AS (
            SELECT
                p.country,
                p.city,
                p.plan_lob_name,
                COALESCE(p.trips_plan, 0) AS plan_trips,
                COALESCE(p.revenue_plan, 0) AS plan_revenue,
                COALESCE(r.real_trips_total, 0) AS real_trips
            FROM plan p
            LEFT JOIN real_agg r
              ON LOWER(TRIM(COALESCE(r.country, ''))) = LOWER(TRIM(COALESCE(p.country, '')))
             AND LOWER(TRIM(COALESCE(r.city, ''))) = LOWER(TRIM(COALESCE(p.city, '')))
             AND r.resolved_plan_lob_name = p.plan_lob_name
        ),
        real_only AS (
            SELECT
                r.country,
                r.city,
                NULL::TEXT AS plan_lob_name,
                0::NUMERIC AS plan_trips,
                0::NUMERIC AS plan_revenue,
                r.real_trips_total AS real_trips
            FROM real_agg r
            WHERE r.resolved_plan_lob_name IS NULL
        ),
        combined AS (
            SELECT * FROM base
            UNION ALL
            SELECT * FROM real_only
        )
        SELECT
            c.country,
            c.city,
            c.plan_lob_name,
            c.plan_trips,
            c.plan_revenue,
            c.real_trips,
            (c.plan_trips > 0) AS exists_in_plan,
            (c.real_trips > 0) AS exists_in_real,
            CASE
                WHEN c.plan_trips > 0 AND c.real_trips > 0 AND COALESCE(u.unmapped_real_trips_total, 0) = 0 THEN 'OK'
                WHEN c.plan_trips > 0 AND c.real_trips = 0 THEN 'PLAN_ONLY'
                WHEN c.plan_trips = 0 AND c.real_trips > 0 THEN 'REAL_ONLY'
                WHEN c.plan_trips > 0 AND c.real_trips > 0 AND COALESCE(u.unmapped_real_trips_total, 0) > 0 THEN 'PARTIAL'
                ELSE 'UNKNOWN'
            END AS coverage_status,
            COALESCE(u.unmapped_real_trips_total, 0) AS unmapped_real_trips_total,
            CASE
                WHEN c.plan_trips > 0 AND c.real_trips > 0 AND COALESCE(u.unmapped_real_trips_total, 0) = 0 THEN 'Plan y real alineados'
                WHEN c.plan_trips > 0 AND c.real_trips = 0 THEN 'Solo en plan'
                WHEN c.plan_trips = 0 AND c.real_trips > 0 THEN 'Solo en real'
                WHEN c.plan_trips > 0 AND c.real_trips > 0 AND COALESCE(u.unmapped_real_trips_total, 0) > 0 THEN 'Hay real sin homologar en esta city'
                ELSE ''
            END AS comment
        FROM combined c
        LEFT JOIN unmapped_agg u
          ON LOWER(TRIM(COALESCE(u.country, ''))) = LOWER(TRIM(COALESCE(c.country, '')))
         AND LOWER(TRIM(COALESCE(u.city, ''))) = LOWER(TRIM(COALESCE(c.city, '')))
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_lob_check_resolved CASCADE")
    # Restore 024 version would require full 024 view definition; leave dropped for next upgrade
    pass
