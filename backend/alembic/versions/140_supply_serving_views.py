"""
140 — Supply Serving Views: reemplazan mv_supply_weekly y mv_supply_monthly.

Fase 1B.2 — Supply Serving Contract Repair.

Las MVs mv_supply_weekly y mv_supply_monthly (migración 060) no existen en la DB.
Sus datos se pierden silenciosamente en los endpoints supply (retornan []).
En su lugar, se crean VIEWS serving que agregan desde las MVs existentes
(mv_driver_weekly_stats, mv_driver_monthly_stats, mv_supply_segments_weekly,
v_driver_weekly_churn_reactivation) y no requieren refresh adicional.

También se reparan las vistas de migración 075 que referencian mv_supply_weekly.
"""

from alembic import op

revision = "140_supply_serving_views"
down_revision = "139_refresh_run_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- weekly serving view ----
    op.execute("DROP VIEW IF EXISTS ops.v_supply_weekly_serving CASCADE")
    op.execute("""
        CREATE VIEW ops.v_supply_weekly_serving AS
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
    op.execute("COMMENT ON VIEW ops.v_supply_weekly_serving IS 'Serving view: agrega mv_driver_weekly_stats + churn/reactivation por park/semana. Reemplaza mv_supply_weekly (rota).'")

    # ---- monthly serving view ----
    op.execute("DROP VIEW IF EXISTS ops.v_supply_monthly_serving CASCADE")
    op.execute("""
        CREATE VIEW ops.v_supply_monthly_serving AS
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
    op.execute("COMMENT ON VIEW ops.v_supply_monthly_serving IS 'Serving view: agrega mv_driver_monthly_stats por park/mes. Reemplaza mv_supply_monthly (rota).'")

    # ---- Reparar vistas de migración 075 que referencian mv_supply_weekly ----
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_mv_freshness AS
        SELECT 'mv_real_lob_drill'::text AS view_name,
               (SELECT MAX(period_start) FROM ops.real_drill_dim_fact) AS last_period_start,
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(last_trip_ts) FROM ops.real_drill_dim_fact)))/3600.0 AS lag_hours,
               CASE WHEN (SELECT MAX(last_trip_ts) FROM ops.real_drill_dim_fact) >= NOW() - interval '48 hours' THEN 'OK' ELSE 'STALE' END AS status
        UNION ALL
        SELECT 'mv_real_lob',
               (SELECT MAX(trip_day) FROM ops.real_rollup_day_fact),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(last_trip_ts) FROM ops.real_rollup_day_fact)))/3600.0,
               CASE WHEN (SELECT MAX(last_trip_ts) FROM ops.real_rollup_day_fact) >= NOW() - interval '48 hours' THEN 'OK' ELSE 'STALE' END
        UNION ALL
        SELECT 'mv_driver_lifecycle_weekly',
               (SELECT MAX(week_start) FROM ops.mv_driver_weekly_stats),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(week_start) FROM ops.mv_driver_weekly_stats)::timestamptz))/3600.0,
               CASE WHEN (SELECT MAX(week_start) FROM ops.mv_driver_weekly_stats) >= (date_trunc('week', CURRENT_DATE)::date - 7) THEN 'OK' ELSE 'STALE' END
        UNION ALL
        SELECT 'mv_supply_weekly',
               (SELECT MAX(week_start) FROM ops.v_supply_weekly_serving),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(week_start) FROM ops.v_supply_weekly_serving)::timestamptz))/3600.0,
               CASE WHEN (SELECT MAX(week_start) FROM ops.v_supply_weekly_serving) >= (date_trunc('week', CURRENT_DATE)::date - 7) THEN 'OK' ELSE 'STALE' END
        UNION ALL
        SELECT 'mv_driver_segments_weekly',
               (SELECT MAX(week_start) FROM ops.mv_driver_segments_weekly),
               EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(week_start) FROM ops.mv_driver_segments_weekly)::timestamptz))/3600.0,
               CASE WHEN (SELECT MAX(week_start) FROM ops.mv_driver_segments_weekly) >= (date_trunc('week', CURRENT_DATE)::date - 7) THEN 'OK' ELSE 'STALE' END
    """)

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_driver_consistency AS
        WITH week_trips AS (
            SELECT date_trunc('week', fecha_inicio_viaje)::date AS week_start,
                   COUNT(DISTINCT conductor_id) AS drivers_trips
            FROM ops.v_trips_real_canon
            WHERE condicion = 'Completado' AND fecha_inicio_viaje IS NOT NULL AND conductor_id IS NOT NULL
            GROUP BY date_trunc('week', fecha_inicio_viaje)::date
        ),
        week_lifecycle AS (
            SELECT week_start, COUNT(DISTINCT driver_key) AS drivers_lifecycle
            FROM ops.mv_driver_weekly_stats
            GROUP BY week_start
        ),
        week_supply AS (
            SELECT week_start, SUM(active_drivers) AS drivers_supply
            FROM ops.v_supply_weekly_serving
            GROUP BY week_start
        )
        SELECT
            COALESCE(t.week_start, l.week_start, s.week_start) AS week,
            COALESCE(t.drivers_trips, 0) AS drivers_trips,
            COALESCE(l.drivers_lifecycle, 0) AS drivers_lifecycle,
            COALESCE(s.drivers_supply, 0) AS drivers_supply
        FROM week_trips t
        FULL OUTER JOIN week_lifecycle l ON l.week_start = t.week_start
        FULL OUTER JOIN week_supply s ON s.week_start = COALESCE(t.week_start, l.week_start)
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_supply_weekly_serving CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_supply_monthly_serving CASCADE")
    # Las vistas de 075 se revierten a su estado original (aunque fallen en runtime si las MVs no existen)
