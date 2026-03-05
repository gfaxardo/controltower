"""
Control Tower Supply: ops.mv_supply_weekly, ops.mv_supply_monthly, ops.refresh_supply_mvs().
Fuente: ops.mv_driver_weekly_stats, ops.mv_driver_monthly_stats, vistas churn/reactivation, dim.v_geo_park.
"""
from alembic import op

revision = "060_supply_mvs"
down_revision = "059_dim_geo_park"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Depende de que existan mv_driver_weekly_stats y mv_driver_monthly_stats (driver lifecycle build)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_weekly CASCADE")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_weekly AS
        WITH geo AS (
            SELECT park_id, park_name, city, country FROM dim.v_geo_park
        ),
        first_week AS (
            SELECT driver_key, MIN(week_start) AS first_week
            FROM ops.mv_driver_weekly_stats
            GROUP BY driver_key
        ),
        activations_week AS (
            SELECT w.week_start, w.park_id, COUNT(*) AS activations
            FROM ops.mv_driver_weekly_stats w
            JOIN first_week f ON f.driver_key = w.driver_key AND f.first_week = w.week_start
            WHERE w.park_id IS NOT NULL
            GROUP BY w.week_start, w.park_id
        ),
        active_drivers_week AS (
            SELECT week_start, park_id, COUNT(DISTINCT driver_key) AS active_drivers
            FROM ops.mv_driver_weekly_stats
            WHERE park_id IS NOT NULL
            GROUP BY week_start, park_id
        ),
        churn_week AS (
            SELECT c.week_start, w.park_id, COUNT(DISTINCT c.driver_key) AS churned
            FROM ops.v_driver_weekly_churn_reactivation c
            JOIN ops.mv_driver_weekly_stats w ON w.driver_key = c.driver_key AND w.week_start = (c.week_start - 7)
            WHERE c.churn_flow_week AND w.park_id IS NOT NULL
            GROUP BY c.week_start, w.park_id
        ),
        reactivated_week AS (
            SELECT c.week_start, w.park_id, COUNT(DISTINCT c.driver_key) AS reactivated
            FROM ops.v_driver_weekly_churn_reactivation c
            JOIN ops.mv_driver_weekly_stats w ON w.driver_key = c.driver_key AND w.week_start = c.week_start
            WHERE c.reactivated_week AND w.park_id IS NOT NULL
            GROUP BY c.week_start, w.park_id
        ),
        calendar AS (
            SELECT DISTINCT w.week_start, w.park_id
            FROM ops.mv_driver_weekly_stats w
            WHERE w.park_id IS NOT NULL
        )
        SELECT
            c.week_start,
            c.park_id,
            g.park_name,
            g.city,
            g.country,
            COALESCE(ax.activations, 0)::bigint AS activations,
            COALESCE(ad.active_drivers, 0)::bigint AS active_drivers,
            COALESCE(cf.churned, 0)::bigint AS churned,
            COALESCE(rx.reactivated, 0)::bigint AS reactivated,
            CASE WHEN COALESCE(ad.active_drivers, 0) > 0
                THEN ROUND(100.0 * COALESCE(cf.churned, 0) / ad.active_drivers, 4) ELSE NULL END AS churn_rate,
            CASE WHEN (COALESCE(ad.active_drivers, 0) - COALESCE(cf.churned, 0) + COALESCE(rx.reactivated, 0)) > 0
                THEN ROUND(100.0 * COALESCE(rx.reactivated, 0) / (ad.active_drivers - COALESCE(cf.churned, 0) + COALESCE(rx.reactivated, 0)), 4) ELSE NULL END AS reactivation_rate,
            (COALESCE(ax.activations, 0) + COALESCE(rx.reactivated, 0) - COALESCE(cf.churned, 0))::bigint AS net_growth
        FROM calendar c
        LEFT JOIN geo g ON g.park_id = c.park_id
        LEFT JOIN activations_week ax ON ax.week_start = c.week_start AND ax.park_id = c.park_id
        LEFT JOIN active_drivers_week ad ON ad.week_start = c.week_start AND ad.park_id = c.park_id
        LEFT JOIN churn_week cf ON cf.week_start = c.week_start AND cf.park_id = c.park_id
        LEFT JOIN reactivated_week rx ON rx.week_start = c.week_start AND rx.park_id = c.park_id
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_supply_weekly_week_park
        ON ops.mv_supply_weekly (week_start, park_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_supply_weekly_country_city_week
        ON ops.mv_supply_weekly (country, city, week_start)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_supply_weekly_park_week
        ON ops.mv_supply_weekly (park_id, week_start)
    """)

    # Monthly: análogo desde mv_driver_monthly_stats (sin vista churn mensual, simplificado)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_monthly CASCADE")
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_supply_monthly AS
        WITH geo AS (
            SELECT park_id, park_name, city, country FROM dim.v_geo_park
        ),
        first_month AS (
            SELECT driver_key, MIN(month_start) AS first_month
            FROM ops.mv_driver_monthly_stats
            GROUP BY driver_key
        ),
        activations_month AS (
            SELECT m.month_start, m.park_id, COUNT(*) AS activations
            FROM ops.mv_driver_monthly_stats m
            JOIN first_month f ON f.driver_key = m.driver_key AND f.first_month = m.month_start
            WHERE m.park_id IS NOT NULL
            GROUP BY m.month_start, m.park_id
        ),
        active_drivers_month AS (
            SELECT month_start, park_id, COUNT(DISTINCT driver_key) AS active_drivers
            FROM ops.mv_driver_monthly_stats
            WHERE park_id IS NOT NULL
            GROUP BY month_start, park_id
        ),
        calendar AS (
            SELECT DISTINCT m.month_start, m.park_id
            FROM ops.mv_driver_monthly_stats m
            WHERE m.park_id IS NOT NULL
        )
        SELECT
            c.month_start,
            c.park_id,
            g.park_name,
            g.city,
            g.country,
            COALESCE(ax.activations, 0)::bigint AS activations,
            COALESCE(ad.active_drivers, 0)::bigint AS active_drivers,
            0::bigint AS churned,
            0::bigint AS reactivated,
            NULL::numeric AS churn_rate,
            NULL::numeric AS reactivation_rate,
            (COALESCE(ax.activations, 0))::bigint AS net_growth
        FROM calendar c
        LEFT JOIN geo g ON g.park_id = c.park_id
        LEFT JOIN activations_month ax ON ax.month_start = c.month_start AND ax.park_id = c.park_id
        LEFT JOIN active_drivers_month ad ON ad.month_start = c.month_start AND ad.park_id = c.park_id
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_supply_monthly_month_park
        ON ops.mv_supply_monthly (month_start, park_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_supply_monthly_country_city_month
        ON ops.mv_supply_monthly (country, city, month_start)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_mv_supply_monthly_park_month
        ON ops.mv_supply_monthly (park_id, month_start)
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_supply_mvs()
        RETURNS void
        LANGUAGE plpgsql
        AS $$
        BEGIN
            PERFORM set_config('statement_timeout', '60min', true);
            PERFORM set_config('lock_timeout', '60s', true);
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_supply_weekly;
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_supply_monthly;
        END;
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_supply_mvs() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_supply_weekly CASCADE")
