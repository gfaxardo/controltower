"""
Restaurar vistas sobre ops.mv_real_lob_day_v2 tras DROP CASCADE en 135.

La migración 135 recreó las MV hourly-first con CASCADE; PostgreSQL eliminó vistas
dependientes (p. ej. ops.v_real_rollup_day_from_day_v2, ops.real_rollup_day_fact,
ops.mv_real_rollup_day, ops.v_real_lob_coverage, ops.v_real_data_coverage,
ops.v_revenue_quality_daily_summary). Este revision las vuelve a crear con la
misma semántica que 101 + 122.
"""
from alembic import op

revision = "136_restore_real_rollup_views_after_hourly_mv_rebuild"
down_revision = "135_fix_hourly_first_mv_source_live_fact"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_revenue_quality_daily_summary CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.real_rollup_day_fact CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_rollup_day_from_day_v2 CASCADE")

    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_rollup_day_from_day_v2 AS
        SELECT
            trip_date AS trip_day, country, city, park_id,
            COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text, '')
                AS park_name_resolved,
            CASE WHEN park_id IS NOT NULL AND TRIM(COALESCE(park_id,'')) <> ''
                 THEN 'OK' ELSE 'SIN_PARK' END AS park_bucket,
            lob_group, segment_tag,
            SUM(completed_trips)::bigint AS trips,
            SUM(CASE WHEN segment_tag = 'B2B'
                THEN completed_trips ELSE 0 END)::bigint AS b2b_trips,
            SUM(margin_total) AS margin_total_raw,
            ABS(SUM(margin_total)) AS margin_total_pos,
            CASE WHEN SUM(completed_trips) > 0
                THEN ABS(SUM(margin_total)) / SUM(completed_trips)
                ELSE NULL END AS margin_unit_pos,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL
                THEN SUM(distance_total_km) / SUM(completed_trips)
                ELSE NULL END AS km_prom,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_day_v2
        GROUP BY trip_date, country, city, park_id, park_name, lob_group, segment_tag
    """)
    op.execute(
        "CREATE VIEW ops.real_rollup_day_fact AS SELECT * FROM ops.v_real_rollup_day_from_day_v2"
    )
    op.execute(
        "COMMENT ON VIEW ops.real_rollup_day_fact IS "
        "'Derivado de mv_real_lob_day_v2 (hourly-first). Restaurado por 136 tras rebuild MV.'"
    )
    op.execute("CREATE VIEW ops.mv_real_rollup_day AS SELECT * FROM ops.real_rollup_day_fact")
    op.execute("""
        CREATE VIEW ops.v_real_lob_coverage AS
        SELECT
            (SELECT MIN(trip_day) FROM ops.real_rollup_day_fact) AS min_trip_date_loaded,
            (SELECT MAX(trip_day) FROM ops.real_rollup_day_fact) AS max_trip_date_loaded,
            120 AS recent_days_config,
            NOW() AS computed_at
    """)
    op.execute("""
        CREATE VIEW ops.v_real_data_coverage AS
        SELECT
            country,
            MIN(trip_day) AS min_trip_date,
            MAX(trip_day) AS last_trip_date,
            MAX(last_trip_ts) AS last_trip_ts,
            date_trunc('month', MIN(trip_day))::date AS min_month,
            date_trunc('week', MIN(trip_day))::date AS min_week,
            date_trunc('month', MAX(trip_day))::date AS last_month_with_data,
            date_trunc('week', MAX(trip_day))::date AS last_week_with_data
        FROM ops.mv_real_rollup_day
        WHERE country IN ('co','pe')
        GROUP BY country
    """)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_revenue_quality_daily_summary AS
        SELECT
            trip_date,
            country,
            city,
            SUM(completed_trips) AS completed_trips,
            SUM(gross_revenue) AS total_gross_revenue,
            SUM(margin_total) AS total_margin,
            CASE WHEN SUM(completed_trips) > 0
                THEN ROUND(SUM(gross_revenue) / SUM(completed_trips), 2)
                ELSE NULL
            END AS avg_revenue_per_trip,
            CASE WHEN SUM(gross_revenue) > 0 THEN 'healthy'
                 WHEN SUM(completed_trips) > 0 THEN 'zero_revenue'
                 ELSE 'no_data'
            END AS revenue_health
        FROM ops.mv_real_lob_day_v2
        GROUP BY trip_date, country, city
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_revenue_quality_daily_summary CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_data_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_lob_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.mv_real_rollup_day CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.real_rollup_day_fact CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_rollup_day_from_day_v2 CASCADE")
