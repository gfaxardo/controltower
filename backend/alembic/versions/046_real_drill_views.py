"""
Vistas drill-down jerárquico Real LOB (Fase 2C+).
Fuente única: ops.mv_real_lob_month_v2, ops.mv_real_lob_week_v2.
Firma común: period_type, level, country, city, park_id, park_name, lob_group,
  period_start, trips, b2b_trips, segment_tag, last_trip_ts.
No mezcla Plan; segment_tag B2B/B2C por pago_corporativo.
"""
from alembic import op

revision = "046_real_drill_views"
down_revision = "045_real_lob_strategy"
branch_labels = None
depends_on = None


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
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country, month_start, segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_drill_country_month IS 'Drill Real: país + mes + segment_tag. Fuente mv_real_lob_month_v2.'")

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
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> ''
        GROUP BY country, week_start, segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_drill_country_week IS 'Drill Real: país + semana + segment_tag. Fuente mv_real_lob_week_v2.'")

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
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
        GROUP BY country, month_start, lob_group, segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_drill_lob_month IS 'Drill Real: país + mes + lob_group + segment_tag.'")

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
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND lob_group IS NOT NULL
        GROUP BY country, week_start, lob_group, segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_drill_lob_week IS 'Drill Real: país + semana + lob_group + segment_tag.'")

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
            SUM(trips) AS trips,
            SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips,
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_month_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND park_id IS NOT NULL
        GROUP BY country, city, park_id, park_name, month_start, segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_drill_park_month IS 'Drill Real: país + ciudad + park + mes + segment_tag.'")

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
            segment_tag,
            MAX(max_trip_ts) AS last_trip_ts
        FROM ops.mv_real_lob_week_v2
        WHERE country IS NOT NULL AND TRIM(country) <> '' AND park_id IS NOT NULL
        GROUP BY country, city, park_id, park_name, week_start, segment_tag
    """)
    op.execute("COMMENT ON VIEW ops.v_real_drill_park_week IS 'Drill Real: país + ciudad + park + semana + segment_tag.'")


def downgrade() -> None:
    for name in [
        "ops.v_real_drill_park_week",
        "ops.v_real_drill_park_month",
        "ops.v_real_drill_lob_week",
        "ops.v_real_drill_lob_month",
        "ops.v_real_drill_country_week",
        "ops.v_real_drill_country_month",
    ]:
        op.execute(f"DROP VIEW IF EXISTS {name} CASCADE")
