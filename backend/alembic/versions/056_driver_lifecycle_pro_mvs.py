"""
FASE 5: Driver Lifecycle PRO — MVs para analítica semanal.
- ops.mv_driver_weekly_behavior: driver_key, week_start, park_id_dominante, trips_completed_week, active_days_week, work_mode_week.
- ops.mv_driver_churn_segments_weekly: power/mid/light/newbie por actividad previa 4 semanas.
- ops.mv_driver_behavior_shifts_weekly: drop/spike vs baseline 4w.
- ops.mv_driver_park_shock_weekly: shock últimas 8 semanas vs baseline 12-5 (cambio de park dominante).
Fuente: ops.mv_driver_weekly_stats (ya usa trips_unified vía v_driver_lifecycle_trips_completed).
"""
from alembic import op

revision = "056_driver_lifecycle_pro_mvs"
down_revision = "055_driver_lifecycle_unified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Evitar timeout en tablas grandes (trips_unified / v_driver_lifecycle_trips_completed)
    op.execute("SET statement_timeout = '1h'")
    # 1) mv_driver_weekly_behavior: añade active_days_week desde viajes (mismo grano que weekly_stats)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_weekly_behavior AS
        WITH days_per_week AS (
            SELECT
                conductor_id AS driver_key,
                DATE_TRUNC('week', completion_ts)::date AS week_start,
                COUNT(*) AS trips_completed_week,
                COUNT(DISTINCT completion_ts::date) AS active_days_week
            FROM ops.v_driver_lifecycle_trips_completed
            GROUP BY 1, 2
        ),
        park_dominant AS (
            SELECT driver_key, week_start, park_id,
                   ROW_NUMBER() OVER (PARTITION BY driver_key, week_start ORDER BY cnt DESC, park_id ASC) AS rn
            FROM (
                SELECT conductor_id AS driver_key,
                       DATE_TRUNC('week', completion_ts)::date AS week_start,
                       park_id,
                       COUNT(*) AS cnt
                FROM ops.v_driver_lifecycle_trips_completed
                WHERE park_id IS NOT NULL AND TRIM(COALESCE(park_id::text, '')) != ''
                GROUP BY 1, 2, 3
            ) t
        )
        SELECT
            d.driver_key,
            d.week_start,
            p.park_id AS park_id_dominante,
            d.trips_completed_week,
            d.active_days_week,
            CASE WHEN d.trips_completed_week >= 20 THEN 'FT' WHEN d.trips_completed_week >= 5 THEN 'PT' ELSE 'casual' END AS work_mode_week
        FROM days_per_week d
        LEFT JOIN (SELECT driver_key, week_start, park_id FROM park_dominant WHERE rn = 1) p
          ON p.driver_key = d.driver_key AND p.week_start = d.week_start
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_weekly_behavior_driver_week
        ON ops.mv_driver_weekly_behavior (driver_key, week_start)
    """)

    # 2) mv_driver_churn_segments_weekly: segmento por actividad en 4 semanas previas (power/mid/light/newbie)
    # Fuente: ops.mv_driver_weekly_behavior (creada en paso 1) para no depender de mv_driver_weekly_stats
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_churn_segments_weekly AS
        WITH baseline_4w AS (
            SELECT
                w.driver_key,
                w.week_start,
                SUM(prev.trips_completed_week) AS trips_prev_4w
            FROM ops.mv_driver_weekly_behavior w
            JOIN ops.mv_driver_weekly_behavior prev
              ON prev.driver_key = w.driver_key
              AND prev.week_start >= w.week_start - INTERVAL '4 weeks'
              AND prev.week_start < w.week_start
            GROUP BY w.driver_key, w.week_start
        ),
        current_week AS (
            SELECT driver_key, week_start, park_id_dominante AS park_id, trips_completed_week, work_mode_week
            FROM ops.mv_driver_weekly_behavior
        )
        SELECT
            c.driver_key,
            c.week_start,
            c.park_id,
            c.trips_completed_week,
            c.work_mode_week,
            COALESCE(b.trips_prev_4w, 0) AS trips_prev_4w,
            CASE
                WHEN COALESCE(b.trips_prev_4w, 0) = 0 THEN 'newbie'
                WHEN b.trips_prev_4w >= 60 THEN 'power'
                WHEN b.trips_prev_4w >= 20 THEN 'mid'
                ELSE 'light'
            END AS churn_segment
        FROM current_week c
        LEFT JOIN baseline_4w b ON b.driver_key = c.driver_key AND b.week_start = c.week_start
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_churn_segments_driver_week
        ON ops.mv_driver_churn_segments_weekly (driver_key, week_start)
    """)

    # 3) mv_driver_behavior_shifts_weekly: drop/spike vs media 4w previas (fuente: mv_driver_weekly_behavior)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_behavior_shifts_weekly AS
        WITH baseline_4w AS (
            SELECT
                w.driver_key,
                w.week_start,
                AVG(prev.trips_completed_week) AS avg_trips_prev_4w,
                SUM(prev.trips_completed_week) AS sum_trips_prev_4w
            FROM ops.mv_driver_weekly_behavior w
            JOIN ops.mv_driver_weekly_behavior prev
              ON prev.driver_key = w.driver_key
              AND prev.week_start >= w.week_start - INTERVAL '4 weeks'
              AND prev.week_start < w.week_start
            GROUP BY w.driver_key, w.week_start
        ),
        c AS (
            SELECT driver_key, week_start, park_id_dominante AS park_id, trips_completed_week
            FROM ops.mv_driver_weekly_behavior
        )
        SELECT
            c.driver_key,
            c.week_start,
            c.park_id,
            c.trips_completed_week AS trips_current_week,
            b.avg_trips_prev_4w,
            CASE
                WHEN b.avg_trips_prev_4w IS NULL OR b.avg_trips_prev_4w = 0 THEN NULL
                WHEN c.trips_completed_week <= 0.5 * b.avg_trips_prev_4w THEN 'drop'
                WHEN c.trips_completed_week >= 1.5 * b.avg_trips_prev_4w THEN 'spike'
                ELSE 'stable'
            END AS behavior_shift
        FROM c
        LEFT JOIN baseline_4w b ON b.driver_key = c.driver_key AND b.week_start = c.week_start
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_behavior_shifts_driver_week
        ON ops.mv_driver_behavior_shifts_weekly (driver_key, week_start)
    """)

    # 4) mv_driver_park_shock_weekly: park dominante en últimas 8 semanas vs baseline 12-5 (fuente: mv_driver_weekly_behavior)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_driver_park_shock_weekly AS
        WITH src AS (
            SELECT driver_key, week_start, park_id_dominante AS park_id, trips_completed_week
            FROM ops.mv_driver_weekly_behavior
        ),
        baseline_park AS (
            SELECT driver_key, week_start, park_id,
                   ROW_NUMBER() OVER (PARTITION BY driver_key, week_start ORDER BY cnt DESC, park_id) AS rn
            FROM (
                SELECT w.driver_key, ref.week_start, w.park_id, SUM(w.trips_completed_week) AS cnt
                FROM src w
                CROSS JOIN (SELECT DISTINCT week_start FROM src) ref
                WHERE w.week_start >= ref.week_start - INTERVAL '12 weeks'
                  AND w.week_start < ref.week_start - INTERVAL '5 weeks'
                  AND w.park_id IS NOT NULL
                GROUP BY w.driver_key, ref.week_start, w.park_id
            ) t
        ),
        recent_park AS (
            SELECT driver_key, week_start, park_id,
                   ROW_NUMBER() OVER (PARTITION BY driver_key, week_start ORDER BY cnt DESC, park_id) AS rn
            FROM (
                SELECT w.driver_key, ref.week_start, w.park_id, SUM(w.trips_completed_week) AS cnt
                FROM src w
                CROSS JOIN (SELECT DISTINCT week_start FROM src) ref
                WHERE w.week_start >= ref.week_start - INTERVAL '8 weeks'
                  AND w.week_start < ref.week_start
                  AND w.park_id IS NOT NULL
                GROUP BY w.driver_key, ref.week_start, w.park_id
            ) t
        )
        SELECT
            r.driver_key,
            r.week_start,
            bp.park_id AS baseline_park_id,
            r.park_id AS recent_park_id,
            (bp.park_id IS DISTINCT FROM r.park_id) AS park_shock
        FROM (SELECT driver_key, week_start, park_id FROM recent_park WHERE rn = 1) r
        LEFT JOIN (SELECT driver_key, week_start, park_id FROM baseline_park WHERE rn = 1) bp
          ON bp.driver_key = r.driver_key AND bp.week_start = r.week_start
    """)
    op.execute("""
        CREATE UNIQUE INDEX ux_mv_driver_park_shock_driver_week
        ON ops.mv_driver_park_shock_weekly (driver_key, week_start)
    """)

    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_driver_weekly_behavior IS 'Driver-week con active_days_week y work_mode_week (FT/PT/casual). Fuente: trips_unified.'")
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_driver_churn_segments_weekly IS 'Segmento churn por actividad previa 4w: power/mid/light/newbie.'")
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_driver_behavior_shifts_weekly IS 'Drop/spike/stable vs media 4 semanas previas.'")
    op.execute("COMMENT ON MATERIALIZED VIEW ops.mv_driver_park_shock_weekly IS 'Park shock: cambio de park dominante (últimas 8w vs baseline 12-5).'")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_park_shock_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_behavior_shifts_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_churn_segments_weekly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_driver_weekly_behavior CASCADE")
