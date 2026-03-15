"""
Fase 2A — Base analítica Real vs Proyección.

- ops.projection_upload_staging: carga cruda de proyección (Excel/CSV).
- ops.projection_dimension_mapping: mapping raw_label -> canonical (ciudad, país, LOB, etc.).
- ops.v_real_metrics_monthly: métricas reales mensuales comparables (desde mv_real_trips_monthly).
- ops.v_real_vs_projection_system_segmentation: comparativo por segmentación del sistema (placeholder si no hay proyección).
- ops.v_real_vs_projection_projection_segmentation: comparativo por segmentación proyección (placeholder).

Aditivo: no modifica tablas ni vistas existentes. Placeholders seguros cuando no hay datos de proyección.
"""
from alembic import op

revision = "097_real_vs_projection"
down_revision = "096_real_lob_mvs_partial_120d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1) Staging para carga de proyección ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.projection_upload_staging (
            id serial PRIMARY KEY,
            period_type text NOT NULL DEFAULT 'month',
            period text NOT NULL,
            raw_country text,
            raw_city text,
            raw_line_of_business text,
            raw_segment text,
            raw_service_type text,
            drivers_plan numeric,
            trips_plan numeric,
            revenue_plan numeric,
            avg_ticket_plan numeric,
            avg_trips_per_driver_plan numeric,
            source_file_name text,
            uploaded_at timestamptz NOT NULL DEFAULT now(),
            notes text
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.projection_upload_staging IS
        'Carga cruda de proyección (Excel/CSV). Fase 2A. Normalización vía projection_dimension_mapping.'
    """)

    # --- 2) Mapping de dimensiones (proyección -> sistema) ---
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.projection_dimension_mapping (
            id serial PRIMARY KEY,
            dimension_type text NOT NULL,
            source_raw_label text NOT NULL,
            normalized_label text,
            target_canonical_label text NOT NULL,
            matching_status text NOT NULL DEFAULT 'matched',
            confidence numeric DEFAULT 1.0,
            manual_override boolean DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.projection_dimension_mapping IS
        'Mapping nomenclatura proyección -> canónico sistema. dimension_type: country, city, lob, segment, service_type.'
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_projection_dimension_mapping_type ON ops.projection_dimension_mapping (dimension_type)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_projection_dimension_mapping_type_raw ON ops.projection_dimension_mapping (dimension_type, source_raw_label)")

    # --- 3) Vista de métricas reales mensuales comparables ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_metrics_monthly CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_metrics_monthly AS
        SELECT
            r.month AS period_date,
            TO_CHAR(r.month, 'YYYY-MM') AS period,
            COALESCE(r.country, '') AS country,
            COALESCE(r.city, '') AS city,
            COALESCE(r.city_norm, '') AS city_norm,
            COALESCE(r.lob_base, '') AS line_of_business,
            COALESCE(r.segment, '') AS segment,
            r.park_id,
            r.trips_real_completed AS trips_real,
            r.active_drivers_real AS drivers_real,
            r.revenue_real_yego AS revenue_real,
            r.avg_ticket_real AS avg_ticket_real,
            CASE WHEN r.active_drivers_real > 0
                 THEN r.trips_real_completed::numeric / r.active_drivers_real
                 ELSE NULL END AS avg_trips_per_driver_real,
            CASE WHEN r.trips_real_completed > 0
                 THEN r.revenue_real_yego::numeric / r.trips_real_completed
                 ELSE NULL END AS revenue_per_trip_real,
            CASE WHEN r.active_drivers_real > 0
                 THEN r.revenue_real_yego::numeric / r.active_drivers_real
                 ELSE NULL END AS revenue_per_driver_real
        FROM ops.mv_real_trips_monthly r
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_metrics_monthly IS
        'Métricas reales mensuales para comparativo Real vs Proyección. Fuente: ops.mv_real_trips_monthly. Fase 2A.'
    """)

    # --- 4) Vista comparativa por segmentación del sistema (placeholder: sin proyección = solo real) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_vs_projection_system_segmentation CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_vs_projection_system_segmentation AS
        SELECT
            m.period_date,
            m.period,
            m.country,
            m.city,
            m.city_norm,
            m.line_of_business,
            m.segment,
            m.park_id,
            m.drivers_real,
            m.trips_real,
            m.avg_trips_per_driver_real,
            m.avg_ticket_real,
            m.revenue_real,
            m.revenue_per_driver_real,
            m.revenue_per_trip_real,
            NULL::numeric AS drivers_plan,
            NULL::numeric AS trips_plan,
            NULL::numeric AS avg_trips_per_driver_plan,
            NULL::numeric AS avg_ticket_plan,
            NULL::numeric AS revenue_plan,
            NULL::numeric AS drivers_gap,
            NULL::numeric AS trips_gap,
            NULL::numeric AS revenue_gap,
            NULL::numeric AS gap_explained_by_driver_count,
            NULL::numeric AS gap_explained_by_productivity,
            NULL::numeric AS gap_explained_by_ticket
        FROM ops.v_real_metrics_monthly m
        WHERE 1=1
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_vs_projection_system_segmentation IS
        'Real vs Proyección por segmentación del sistema. Sin proyección cargada: solo columnas real; plan y gaps NULL. Fase 2A.'
    """)

    # --- 5) Vista comparativa por segmentación proyección (placeholder) ---
    op.execute("DROP VIEW IF EXISTS ops.v_real_vs_projection_projection_segmentation CASCADE")
    op.execute("""
        CREATE VIEW ops.v_real_vs_projection_projection_segmentation AS
        SELECT
            m.period_date,
            m.period,
            m.country,
            m.city,
            m.line_of_business,
            m.drivers_real,
            m.trips_real,
            m.avg_trips_per_driver_real,
            m.avg_ticket_real,
            m.revenue_real,
            NULL::numeric AS drivers_plan,
            NULL::numeric AS trips_plan,
            NULL::numeric AS avg_ticket_plan,
            NULL::numeric AS revenue_plan,
            NULL::numeric AS drivers_gap,
            NULL::numeric AS trips_gap,
            NULL::numeric AS revenue_gap
        FROM ops.v_real_metrics_monthly m
        WHERE 1=1
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_vs_projection_projection_segmentation IS
        'Real vs Proyección por segmentación de la proyección. Placeholder hasta carga de Excel. Fase 2A.'
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_vs_projection_projection_segmentation CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_vs_projection_system_segmentation CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_metrics_monthly CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.projection_dimension_mapping CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.projection_upload_staging CASCADE")
