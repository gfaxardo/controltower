"""141 — Business Slice: audit view for fast coverage checks. Fase 1C.2."""
from alembic import op
revision = "141_business_slice_performance_indexes"
down_revision = "140_supply_serving_views"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_mapping_coverage CASCADE")
    op.execute("""
        CREATE VIEW ops.v_business_slice_mapping_coverage AS
        WITH raw_counts AS (
            SELECT
                date_trunc('month', fecha_inicio_viaje)::date AS trip_month,
                lower(trim(COALESCE(dp.country::text, ''))) AS country,
                lower(trim(COALESCE(dp.city::text, ''))) AS city,
                count(*)::bigint AS raw_completed
            FROM public.trips_2026 t
            LEFT JOIN dim.dim_park dp
                ON lower(trim(dp.park_id::text)) = lower(trim(t.park_id::text))
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje >= '2026-01-01'
            GROUP BY 1, 2, 3
        ),
        fact_counts AS (
            SELECT
                month AS trip_month,
                lower(trim(COALESCE(country, ''))) AS country,
                lower(trim(COALESCE(city, ''))) AS city,
                sum(trips_completed)::bigint AS fact_mapped,
                count(DISTINCT business_slice_name) AS slices_count
            FROM ops.real_business_slice_month_fact
            WHERE month >= '2026-01-01'
            GROUP BY 1, 2, 3
        )
        SELECT
            r.trip_month, r.country, r.city,
            r.raw_completed,
            coalesce(f.fact_mapped, 0) AS fact_mapped,
            r.raw_completed - coalesce(f.fact_mapped, 0) AS unmatched_estimate,
            CASE WHEN r.raw_completed > 0
                THEN round(100.0 * coalesce(f.fact_mapped, 0) / r.raw_completed, 2)
                ELSE NULL END AS coverage_pct,
            f.slices_count
        FROM raw_counts r
        LEFT JOIN fact_counts f
            ON r.trip_month = f.trip_month AND r.country = f.country AND r.city = f.city
        ORDER BY r.trip_month, r.country, r.city
    """)

def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_business_slice_mapping_coverage CASCADE")
