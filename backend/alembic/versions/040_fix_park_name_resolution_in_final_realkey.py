"""
E2E PASO A.5 — Resolver park_name siempre por park_id (incl. filas PLAN_ONLY).

La vista final tomaba park_name solo del lado REAL; en filas solo plan park_name quedaba NULL.
Ahora: base = full outer join plan/real; luego LEFT JOIN public.parks por park_id y
park_name = COALESCE(base.park_name, p.name, p.city, park_id::text).
No se toca join_key (sigue siendo id). Country/city se mantienen del base (plan/real).
"""
from alembic import op

revision = "040_park_name_final_realkey"  # <=32 chars for alembic_version.version_num
# Si tienes 039 (generado por pasoA4), cambia a: down_revision = "039_fix_parks_join_key_realkey"
down_revision = "038_plan_realkey_no_homologation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_city_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_final CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_realkey_final AS
        WITH base AS (
            SELECT
                COALESCE(p.country, r.country) AS country,
                COALESCE(p.city, r.city) AS city,
                COALESCE(p.park_id, r.park_id) AS park_id,
                r.park_name AS base_park_name,
                COALESCE(p.real_tipo_servicio, r.real_tipo_servicio) AS real_tipo_servicio,
                COALESCE(p.period_date, r.period_date) AS period_date,
                p.trips_plan,
                r.real_trips AS trips_real,
                p.revenue_plan,
                r.revenue_real AS revenue_real,
                (COALESCE(r.real_trips, 0) - COALESCE(p.trips_plan, 0)) AS variance_trips,
                (COALESCE(r.revenue_real, 0) - COALESCE(p.revenue_plan, 0)) AS variance_revenue
            FROM ops.v_plan_universe_by_park_realkey p
            FULL OUTER JOIN ops.v_real_universe_by_park_realkey r
                ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
               AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
               AND TRIM(COALESCE(p.park_id, '')) = TRIM(COALESCE(r.park_id, ''))
               AND LOWER(TRIM(COALESCE(p.real_tipo_servicio, ''))) = LOWER(TRIM(COALESCE(r.real_tipo_servicio, '')))
               AND p.period_date = r.period_date
        )
        SELECT
            base.country,
            base.city,
            base.park_id,
            COALESCE(
                NULLIF(TRIM(base.base_park_name), ''),
                NULLIF(TRIM(p.name::text), ''),
                NULLIF(TRIM(p.city::text), ''),
                base.park_id::text
            ) AS park_name,
            base.real_tipo_servicio,
            base.period_date,
            base.trips_plan,
            base.trips_real,
            base.revenue_plan,
            base.revenue_real,
            base.variance_trips,
            base.variance_revenue
        FROM base
        LEFT JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(base.park_id::text))
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_city_month AS
        SELECT
            country,
            city,
            period_date,
            SUM(trips_plan) AS trips_plan,
            SUM(trips_real) AS trips_real,
            SUM(revenue_plan) AS revenue_plan,
            SUM(revenue_real) AS revenue_real,
            SUM(variance_trips) AS variance_trips,
            SUM(variance_revenue) AS variance_revenue
        FROM ops.v_plan_vs_real_realkey_final
        GROUP BY country, city, period_date
        ORDER BY country, city, period_date
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_city_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_realkey_final CASCADE")
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_realkey_final AS
        SELECT
            COALESCE(p.country, r.country) AS country,
            COALESCE(p.city, r.city) AS city,
            COALESCE(p.park_id, r.park_id) AS park_id,
            r.park_name,
            COALESCE(p.real_tipo_servicio, r.real_tipo_servicio) AS real_tipo_servicio,
            COALESCE(p.period_date, r.period_date) AS period_date,
            p.trips_plan,
            r.real_trips AS trips_real,
            p.revenue_plan,
            r.revenue_real AS revenue_real,
            (COALESCE(r.real_trips, 0) - COALESCE(p.trips_plan, 0)) AS variance_trips,
            (COALESCE(r.revenue_real, 0) - COALESCE(p.revenue_plan, 0)) AS variance_revenue
        FROM ops.v_plan_universe_by_park_realkey p
        FULL OUTER JOIN ops.v_real_universe_by_park_realkey r
            ON LOWER(TRIM(COALESCE(p.country, ''))) = LOWER(TRIM(COALESCE(r.country, '')))
           AND LOWER(TRIM(COALESCE(p.city, ''))) = LOWER(TRIM(COALESCE(r.city, '')))
           AND TRIM(COALESCE(p.park_id, '')) = TRIM(COALESCE(r.park_id, ''))
           AND LOWER(TRIM(COALESCE(p.real_tipo_servicio, ''))) = LOWER(TRIM(COALESCE(r.real_tipo_servicio, '')))
           AND p.period_date = r.period_date
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_city_month AS
        SELECT
            country,
            city,
            period_date,
            SUM(trips_plan) AS trips_plan,
            SUM(trips_real) AS trips_real,
            SUM(revenue_plan) AS revenue_plan,
            SUM(revenue_real) AS revenue_real,
            SUM(variance_trips) AS variance_trips,
            SUM(variance_revenue) AS variance_revenue
        FROM ops.v_plan_vs_real_realkey_final
        GROUP BY country, city, period_date
        ORDER BY country, city, period_date
    """)

