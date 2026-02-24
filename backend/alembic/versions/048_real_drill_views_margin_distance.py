"""
Vistas drill con Unit Economics y Uso: margin_total, margin_unit_avg, distance_total_km, distance_km_avg,
b2b_margin_total, b2b_margin_unit_avg, b2b_distance_total_km, b2b_distance_km_avg.
Recrear las 6 vistas (drop en 047 por CASCADE; aquí recrear con nuevas columnas).
"""
from alembic import op

revision = "048_drill_margin_distance"
down_revision = "047_real_lob_v2_margin_distance"
branch_labels = None
depends_on = None


def _cols_country():
    return """
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            SUM(margin_total) / NULLIF(SUM(trips), 0) AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            SUM(distance_total_km) / NULLIF(SUM(trips), 0) AS distance_km_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) AS b2b_margin_total,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_margin_unit_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) AS b2b_distance_total_km,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_distance_km_avg,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
    """


def _cols_lob():
    return """
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            SUM(margin_total) / NULLIF(SUM(trips), 0) AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            SUM(distance_total_km) / NULLIF(SUM(trips), 0) AS distance_km_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) AS b2b_margin_total,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_margin_unit_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) AS b2b_distance_total_km,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_distance_km_avg,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
    """


def _cols_park():
    return """
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            SUM(margin_total) / NULLIF(SUM(trips), 0) AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            SUM(distance_total_km) / NULLIF(SUM(trips), 0) AS distance_km_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) AS b2b_margin_total,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_margin_unit_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) AS b2b_distance_total_km,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_distance_km_avg,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
    """


def upgrade() -> None:
    # A) Country + monthly
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_month AS
        SELECT
            'monthly'::TEXT AS period_type,
            'country'::TEXT AS level,
            country,
            NULL::TEXT AS city,
            NULL::TEXT AS park_id,
            NULL::TEXT AS park_name,
            NULL::TEXT AS lob_group,
            month_start AS period_start,
            """ + _cols_country() + """
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country, month_start, segment_tag
    """)

    # B) Country + weekly
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_country_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_week AS
        SELECT
            'weekly'::TEXT AS period_type,
            'country'::TEXT AS level,
            country,
            NULL::TEXT AS city,
            NULL::TEXT AS park_id,
            NULL::TEXT AS park_name,
            NULL::TEXT AS lob_group,
            week_start AS period_start,
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            SUM(margin_total) / NULLIF(SUM(trips), 0) AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            SUM(distance_total_km) / NULLIF(SUM(trips), 0) AS distance_km_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) AS b2b_margin_total,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_margin_unit_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) AS b2b_distance_total_km,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_distance_km_avg,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country, week_start, segment_tag
    """)

    # C) LOB + monthly
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_month AS
        SELECT
            'monthly'::TEXT AS period_type,
            'lob'::TEXT AS level,
            country,
            NULL::TEXT AS city,
            NULL::TEXT AS park_id,
            NULL::TEXT AS park_name,
            lob_group,
            month_start AS period_start,
            """ + _cols_lob() + """
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
        GROUP BY country, month_start, lob_group, segment_tag
    """)

    # D) LOB + weekly
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_lob_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_week AS
        SELECT
            'weekly'::TEXT AS period_type,
            'lob'::TEXT AS level,
            country,
            NULL::TEXT AS city,
            NULL::TEXT AS park_id,
            NULL::TEXT AS park_name,
            lob_group,
            week_start AS period_start,
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            SUM(margin_total) / NULLIF(SUM(trips), 0) AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            SUM(distance_total_km) / NULLIF(SUM(trips), 0) AS distance_km_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) AS b2b_margin_total,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_margin_unit_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) AS b2b_distance_total_km,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_distance_km_avg,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
        GROUP BY country, week_start, lob_group, segment_tag
    """)

    # E) Park + monthly
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_month CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_month AS
        SELECT
            'monthly'::TEXT AS period_type,
            'park'::TEXT AS level,
            country,
            city,
            park_id::TEXT AS park_id,
            COALESCE(NULLIF(TRIM(park_name::TEXT), ''), park_id::TEXT) AS park_name,
            NULL::TEXT AS lob_group,
            month_start AS period_start,
            """ + _cols_park() + """
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND park_id IS NOT NULL
        GROUP BY country, city, park_id, park_name, month_start, segment_tag
    """)

    # F) Park + weekly
    op.execute("DROP VIEW IF EXISTS ops.v_real_drill_park_week CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_week AS
        SELECT
            'weekly'::TEXT AS period_type,
            'park'::TEXT AS level,
            country,
            city,
            park_id::TEXT AS park_id,
            COALESCE(NULLIF(TRIM(park_name::TEXT), ''), park_id::TEXT) AS park_name,
            NULL::TEXT AS lob_group,
            week_start AS period_start,
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            SUM(margin_total) AS margin_total,
            SUM(margin_total) / NULLIF(SUM(trips), 0) AS margin_unit_avg,
            SUM(distance_total_km) AS distance_total_km,
            SUM(distance_total_km) / NULLIF(SUM(trips), 0) AS distance_km_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) AS b2b_margin_total,
            SUM(CASE WHEN segment_tag = 'B2B' THEN margin_total ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_margin_unit_avg,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) AS b2b_distance_total_km,
            SUM(CASE WHEN segment_tag = 'B2B' THEN distance_total_km ELSE 0 END) / NULLIF(SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END), 0) AS b2b_distance_km_avg,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND park_id IS NOT NULL
        GROUP BY country, city, park_id, park_name, week_start, segment_tag
    """)


def downgrade() -> None:
    # Recreate drill views without margin/distance (046 style)
    for name in [
        "ops.v_real_drill_park_week",
        "ops.v_real_drill_park_month",
        "ops.v_real_drill_lob_week",
        "ops.v_real_drill_lob_month",
        "ops.v_real_drill_country_week",
        "ops.v_real_drill_country_month",
    ]:
        op.execute(f"DROP VIEW IF EXISTS {name} CASCADE")
    # Recreate minimal 046 views (trips, b2b_trips, last_trip_ts only)
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_month AS
        SELECT 'monthly'::TEXT AS period_type, 'country'::TEXT AS level, country,
            NULL::TEXT AS city, NULL::TEXT AS park_id, NULL::TEXT AS park_name, NULL::TEXT AS lob_group,
            month_start AS period_start,
            SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag, MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country, month_start, segment_tag
    """)
    op.execute("""
        CREATE VIEW ops.v_real_drill_country_week AS
        SELECT 'weekly'::TEXT AS period_type, 'country'::TEXT AS level, country,
            NULL::TEXT AS city, NULL::TEXT AS park_id, NULL::TEXT AS park_name, NULL::TEXT AS lob_group,
            week_start AS period_start,
            SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag, MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country, week_start, segment_tag
    """)
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_month AS
        SELECT 'monthly'::TEXT AS period_type, 'lob'::TEXT AS level, country,
            NULL::TEXT AS city, NULL::TEXT AS park_id, NULL::TEXT AS park_name, lob_group,
            month_start AS period_start,
            SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag, MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
        GROUP BY country, month_start, lob_group, segment_tag
    """)
    op.execute("""
        CREATE VIEW ops.v_real_drill_lob_week AS
        SELECT 'weekly'::TEXT AS period_type, 'lob'::TEXT AS level, country,
            NULL::TEXT AS city, NULL::TEXT AS park_id, NULL::TEXT AS park_name, lob_group,
            week_start AS period_start,
            SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag, MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
        GROUP BY country, week_start, lob_group, segment_tag
    """)
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_month AS
        SELECT 'monthly'::TEXT AS period_type, 'park'::TEXT AS level, country, city,
            park_id::TEXT AS park_id, COALESCE(NULLIF(TRIM(park_name::TEXT), ''), park_id::TEXT) AS park_name,
            NULL::TEXT AS lob_group, month_start AS period_start,
            SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag, MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND park_id IS NOT NULL
        GROUP BY country, city, park_id, park_name, month_start, segment_tag
    """)
    op.execute("""
        CREATE VIEW ops.v_real_drill_park_week AS
        SELECT 'weekly'::TEXT AS period_type, 'park'::TEXT AS level, country, city,
            park_id::TEXT AS park_id, COALESCE(NULLIF(TRIM(park_name::TEXT), ''), park_id::TEXT) AS park_name,
            NULL::TEXT AS lob_group, week_start AS period_start,
            SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag, MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND park_id IS NOT NULL
        GROUP BY country, city, park_id, park_name, week_start, segment_tag
    """)
