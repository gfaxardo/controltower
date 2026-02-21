"""
Real LOB Strategy: vistas agregadas país, forecast, LOB por país, ranking ciudades.
- ops.v_real_country_month (país + mes: trips, growth_mom, b2b_ratio)
- ops.v_real_country_month_forecast (forecast próximo mes, acceleration_index)
- ops.v_real_country_lob_month (país + lob_group + mes + forecast)
- ops.v_real_country_city_month (país + ciudad + mes + expansion_index)
Fuente: ops.mv_real_lob_month_v2. No toca Plan vs Real REALKEY.
"""
from alembic import op

revision = "045_real_lob_strategy"
down_revision = "044_real_lob_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── A) Vista base agregada mensual por país ─────────────────────────────
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_month_forecast CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_country_month AS
        WITH agg AS (
            SELECT
                country,
                (DATE_TRUNC('month', month_start)::DATE) AS month_start,
                SUM(trips) AS trips,
                SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
                MAX(max_trip_ts) AS max_trip_ts
            FROM ops.mv_real_lob_month_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
            GROUP BY country, (DATE_TRUNC('month', month_start)::DATE)
        ),
        with_prev AS (
            SELECT
                country,
                month_start,
                trips,
                b2b_trips,
                max_trip_ts,
                LAG(trips) OVER (PARTITION BY country ORDER BY month_start) AS trips_prev
            FROM agg
        )
        SELECT
            country,
            month_start,
            trips,
            trips_prev,
            CASE WHEN (trips_prev IS NOT NULL AND trips_prev > 0)
                 THEN (trips - trips_prev)::NUMERIC / NULLIF(trips_prev, 0)
                 ELSE NULL END AS growth_mom,
            b2b_trips,
            CASE WHEN trips > 0 THEN (b2b_trips::NUMERIC / trips) ELSE NULL END AS b2b_ratio,
            max_trip_ts
        FROM with_prev
    """)
    op.execute("COMMENT ON VIEW ops.v_real_country_month IS 'Real LOB Strategy: agregado mensual por país desde mv_real_lob_month_v2. Incluye growth_mom y b2b_ratio.'")

    # ─── B) Vista con forecast (momentum 0.5*M0 + 0.3*M-1 + 0.2*M-2) ─────────
    op.execute("""
        CREATE VIEW ops.v_real_country_month_forecast AS
        WITH base AS (
            SELECT * FROM ops.v_real_country_month
        ),
        with_lag AS (
            SELECT
                country,
                month_start,
                trips,
                trips_prev,
                growth_mom,
                b2b_trips,
                b2b_ratio,
                max_trip_ts,
                LAG(trips, 1) OVER (PARTITION BY country ORDER BY month_start) AS m_minus_1,
                LAG(trips, 2) OVER (PARTITION BY country ORDER BY month_start) AS m_minus_2
            FROM base
        ),
        forecast_calc AS (
            SELECT
                *,
                CASE
                    WHEN m_minus_1 IS NOT NULL AND m_minus_2 IS NOT NULL
                    THEN (0.5 * trips + 0.3 * m_minus_1 + 0.2 * m_minus_2)
                    WHEN m_minus_1 IS NOT NULL
                    THEN (trips + m_minus_1)::NUMERIC / 2
                    ELSE trips
                END AS forecast_next_month
            FROM with_lag
        ),
        growth_2m AS (
            SELECT
                country,
                month_start,
                AVG(growth_mom) OVER (
                    PARTITION BY country
                    ORDER BY month_start
                    ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
                ) AS avg_growth_last_2
            FROM base
            WHERE growth_mom IS NOT NULL
        ),
        growth_6m AS (
            SELECT
                country,
                month_start,
                AVG(growth_mom) OVER (
                    PARTITION BY country
                    ORDER BY month_start
                    ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
                ) AS avg_growth_last_6
            FROM base
            WHERE growth_mom IS NOT NULL
        )
        SELECT
            f.country,
            f.month_start,
            f.trips,
            f.trips_prev,
            f.growth_mom,
            f.b2b_trips,
            f.b2b_ratio,
            f.max_trip_ts,
            ROUND(f.forecast_next_month::NUMERIC, 0) AS forecast_next_month,
            CASE WHEN f.trips > 0 AND f.forecast_next_month IS NOT NULL
                 THEN (f.forecast_next_month - f.trips)::NUMERIC / NULLIF(f.trips, 0)
                 ELSE NULL END AS forecast_growth,
            ROUND((COALESCE(g2.avg_growth_last_2, 0) - COALESCE(g6.avg_growth_last_6, 0))::NUMERIC, 4) AS acceleration_index
        FROM forecast_calc f
        LEFT JOIN growth_2m g2 ON g2.country = f.country AND g2.month_start = f.month_start
        LEFT JOIN growth_6m g6 ON g6.country = f.country AND g6.month_start = f.month_start
    """)
    op.execute("COMMENT ON VIEW ops.v_real_country_month_forecast IS 'Real LOB Strategy: país + forecast próximo mes (momentum 3 meses) y acceleration_index.'")

    # ─── C) Vista agregada por LOB_GROUP dentro de país ───────────────────────
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_lob_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_country_lob_month AS
        WITH agg AS (
            SELECT
                country,
                lob_group,
                month_start,
                SUM(trips) AS trips,
                LAG(SUM(trips)) OVER (PARTITION BY country, lob_group ORDER BY month_start) AS trips_prev
            FROM ops.mv_real_lob_month_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
            GROUP BY country, lob_group, month_start
        ),
        with_growth AS (
            SELECT
                country,
                lob_group,
                month_start,
                trips,
                trips_prev,
                CASE WHEN (trips_prev IS NOT NULL AND trips_prev > 0)
                     THEN (trips - trips_prev)::NUMERIC / NULLIF(trips_prev, 0)
                     ELSE NULL END AS growth_mom
            FROM agg
        ),
        with_lag AS (
            SELECT
                *,
                LAG(trips, 1) OVER (PARTITION BY country, lob_group ORDER BY month_start) AS m_minus_1,
                LAG(trips, 2) OVER (PARTITION BY country, lob_group ORDER BY month_start) AS m_minus_2
            FROM with_growth
        )
        SELECT
            country,
            lob_group,
            month_start,
            trips,
            growth_mom,
            ROUND(
                CASE
                    WHEN m_minus_1 IS NOT NULL AND m_minus_2 IS NOT NULL
                    THEN (0.5 * trips + 0.3 * m_minus_1 + 0.2 * m_minus_2)
                    WHEN m_minus_1 IS NOT NULL THEN (trips + m_minus_1)::NUMERIC / 2
                    ELSE trips
                END::NUMERIC, 0
            ) AS forecast_next_month
        FROM with_lag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_country_lob_month IS 'Real LOB Strategy: país + LOB_GROUP + mes + forecast (momentum 3 meses).'")

    # ─── D) Vista ranking ciudades (expansion_index = growth_city / growth_country) ─
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_city_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_country_city_month AS
        WITH city_agg AS (
            SELECT
                country,
                city,
                month_start,
                SUM(trips) AS trips,
                LAG(SUM(trips)) OVER (PARTITION BY country, city ORDER BY month_start) AS trips_prev
            FROM ops.mv_real_lob_month_v2
            WHERE country IS NOT NULL AND TRIM(country) <> ''
              AND city IS NOT NULL AND TRIM(city) <> ''
            GROUP BY country, city, month_start
        ),
        city_growth AS (
            SELECT
                country,
                city,
                month_start,
                trips,
                CASE WHEN (trips_prev IS NOT NULL AND trips_prev > 0)
                     THEN (trips - trips_prev)::NUMERIC / NULLIF(trips_prev, 0)
                     ELSE NULL END AS growth_mom
            FROM city_agg
        ),
        country_growth AS (
            SELECT country, month_start, growth_mom AS country_growth_mom
            FROM ops.v_real_country_month
        )
        SELECT
            c.country,
            c.city,
            c.month_start,
            c.trips,
            c.growth_mom,
            CASE WHEN cg.country_growth_mom IS NOT NULL AND cg.country_growth_mom <> 0
                 THEN ROUND((c.growth_mom / NULLIF(cg.country_growth_mom, 0))::NUMERIC, 4)
                 ELSE NULL END AS expansion_index
        FROM city_growth c
        JOIN country_growth cg ON cg.country = c.country AND cg.month_start = c.month_start
    """)
    op.execute("COMMENT ON VIEW ops.v_real_country_city_month IS 'Real LOB Strategy: ranking ciudades por país con expansion_index (growth_city/growth_country).'")

    # ─── E) Índices sobre la MV para consultas por (country, month_start) ────
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_v2_country_month ON ops.mv_real_lob_month_v2 (country, month_start)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_lob_month_v2_country_city_month ON ops.mv_real_lob_month_v2 (country, city, month_start)")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_city_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_lob_month CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_month_forecast CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_country_month CASCADE")
    op.execute("DROP INDEX IF EXISTS ops.idx_mv_real_lob_month_v2_country_month")
    op.execute("DROP INDEX IF EXISTS ops.idx_mv_real_lob_month_v2_country_city_month")
