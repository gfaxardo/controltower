"""
Fleet Leakage Monitor MVP — Vista ops.v_fleet_leakage_snapshot.
Una fila por conductor con semana de referencia (última disponible).
Fuentes: ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved.
Clasificación MVP: stable_retained, watchlist, progressive_leakage, lost_driver.
No usa vistas de Behavioral Alerts.
"""
from alembic import op

revision = "091_fleet_leakage_snapshot"
down_revision = "090_behavioral_alerts_sudden_stop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_fleet_leakage_snapshot AS
        WITH latest_week AS (
            SELECT MAX(week_start)::date AS ref_week FROM ops.mv_driver_segments_weekly
        ),
        driver_week AS (
            SELECT
                d.driver_key,
                d.week_start,
                d.park_id,
                d.trips_completed_week AS trips_current_week,
                d.baseline_trips_4w_avg,
                d.segment_week,
                CASE
                    WHEN d.baseline_trips_4w_avg IS NOT NULL AND d.baseline_trips_4w_avg > 0
                    THEN ROUND((d.trips_completed_week - d.baseline_trips_4w_avg)::numeric / d.baseline_trips_4w_avg, 4)
                    ELSE NULL
                END AS delta_pct
            FROM ops.mv_driver_segments_weekly d, latest_week lw
            WHERE d.week_start = lw.ref_week
        ),
        with_last_trip AS (
            SELECT
                dw.*,
                lt.last_trip_date,
                (CURRENT_DATE - lt.last_trip_date)::int AS days_since_last_trip
            FROM driver_week dw
            LEFT JOIN ops.v_driver_last_trip lt ON lt.driver_key = dw.driver_key
        ),
        with_geo AS (
            SELECT
                w.driver_key,
                w.week_start,
                w.park_id,
                w.trips_current_week,
                w.baseline_trips_4w_avg,
                w.segment_week,
                w.delta_pct,
                w.last_trip_date,
                w.days_since_last_trip,
                g.park_name,
                g.city AS city,
                g.country AS country
            FROM with_last_trip w
            LEFT JOIN dim.v_geo_park g ON g.park_id = w.park_id
        ),
        with_driver_name AS (
            SELECT
                w.driver_key,
                w.week_start,
                w.park_id,
                w.park_name,
                w.city,
                w.country,
                w.trips_current_week,
                w.baseline_trips_4w_avg,
                w.segment_week,
                w.delta_pct,
                w.last_trip_date,
                w.days_since_last_trip,
                COALESCE(NULLIF(TRIM(dr.driver_name), ''), w.driver_key::text) AS driver_name
            FROM with_geo w
            LEFT JOIN ops.v_dim_driver_resolved dr ON dr.driver_id = w.driver_key
        ),
        classified AS (
            SELECT
                *,
                CASE
                    WHEN days_since_last_trip > 45 OR (trips_current_week = 0 AND baseline_trips_4w_avg IS NOT NULL AND baseline_trips_4w_avg > 0) THEN 'lost_driver'
                    WHEN delta_pct IS NOT NULL AND delta_pct <= -0.20 THEN 'progressive_leakage'
                    WHEN (delta_pct IS NOT NULL AND delta_pct <= -0.10) OR (days_since_last_trip IS NOT NULL AND days_since_last_trip >= 14 AND days_since_last_trip <= 45) THEN 'watchlist'
                    ELSE 'stable_retained'
                END AS leakage_status,
                CASE
                    WHEN days_since_last_trip > 45 OR (trips_current_week = 0 AND baseline_trips_4w_avg IS NOT NULL AND baseline_trips_4w_avg > 0) THEN LEAST(100, 50 + COALESCE(days_since_last_trip, 0) / 2)
                    WHEN delta_pct IS NOT NULL AND delta_pct <= -0.20 THEN 70
                    WHEN (delta_pct IS NOT NULL AND delta_pct <= -0.10) OR (days_since_last_trip IS NOT NULL AND days_since_last_trip >= 14) THEN 40
                    ELSE 0
                END AS leakage_score,
                CASE
                    WHEN days_since_last_trip > 45 OR (trips_current_week = 0 AND baseline_trips_4w_avg IS NOT NULL AND baseline_trips_4w_avg > 0) THEN 'P1'
                    WHEN delta_pct IS NOT NULL AND delta_pct <= -0.20 THEN 'P2'
                    WHEN (delta_pct IS NOT NULL AND delta_pct <= -0.10) OR (days_since_last_trip IS NOT NULL AND days_since_last_trip >= 14) THEN 'P3'
                    ELSE 'P4'
                END AS recovery_priority,
                CASE
                    WHEN segment_week IN ('FT', 'ELITE', 'LEGEND') AND (
                        days_since_last_trip > 45 OR (trips_current_week = 0 AND baseline_trips_4w_avg > 0)
                        OR (delta_pct IS NOT NULL AND delta_pct <= -0.10)
                    ) THEN true
                    ELSE false
                END AS top_performer_at_risk
            FROM with_driver_name
        )
        SELECT
            driver_key,
            driver_name,
            week_start,
            park_id,
            park_name,
            city,
            country,
            trips_current_week,
            baseline_trips_4w_avg,
            delta_pct,
            last_trip_date,
            days_since_last_trip,
            segment_week,
            leakage_status,
            leakage_score,
            recovery_priority,
            top_performer_at_risk
        FROM classified
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_fleet_leakage_snapshot IS
        'Fleet Leakage MVP: one row per driver for latest week. Sources: mv_driver_segments_weekly, v_driver_last_trip, v_geo_park, v_dim_driver_resolved. Status: stable_retained, watchlist, progressive_leakage, lost_driver.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_fleet_leakage_snapshot CASCADE")
