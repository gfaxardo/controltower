"""
132 — Control Loop: real alineado a tajadas Omniview (business_slice) + puente plan_line → slice.

- ops.control_loop_plan_line_to_business_slice: mapeo auditable opcional.
- ops.v_real_monthly_control_loop_from_tajadas: agregado mensual desde v_real_trips_business_slice_resolved.
- ops.v_plan_projection_control_loop: incluye linea_negocio_excel para resolución.

down_revision: 131_control_loop_projection_phase1
"""

from alembic import op

revision = "132_control_loop_tajadas_realignment"
down_revision = "131_control_loop_projection_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.control_loop_plan_line_to_business_slice (
            id SERIAL PRIMARY KEY,
            plan_line_key TEXT NOT NULL,
            business_slice_name TEXT NOT NULL,
            country TEXT,
            city TEXT,
            priority INT NOT NULL DEFAULT 10,
            notes TEXT,
            active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_loop_slice_map_key
        ON ops.control_loop_plan_line_to_business_slice (plan_line_key)
        WHERE active
        """
    )
    op.execute(
        """
        COMMENT ON TABLE ops.control_loop_plan_line_to_business_slice IS
        'Puente opcional plan_line_key → business_slice_name para Control Loop. '
        'La coincidencia principal sigue siendo el texto Excel vs business_slice_mapping_rules por ciudad.'
        """
    )

    op.execute(
        """
        INSERT INTO ops.control_loop_plan_line_to_business_slice (plan_line_key, business_slice_name, priority, notes)
        SELECT x.plan_line_key, x.business_slice_name, x.priority, x.notes
        FROM (
            VALUES
                ('pro', 'PRO', 5, 'Nombre típico tajada PRO'),
                ('yma', 'YMA', 5, 'Nombre típico tajada YMA'),
                ('ymm', 'YMM', 5, 'Nombre típico tajada YMM'),
                ('auto_taxi', 'Auto regular', 20, 'Fallback si el Excel no coincide literal con reglas')
        ) AS x(plan_line_key, business_slice_name, priority, notes)
        WHERE NOT EXISTS (
            SELECT 1 FROM ops.control_loop_plan_line_to_business_slice o
            WHERE o.plan_line_key = x.plan_line_key
              AND lower(trim(o.business_slice_name)) = lower(trim(x.business_slice_name))
              AND o.country IS NULL AND o.city IS NULL
        )
        """
    )

    op.execute("DROP VIEW IF EXISTS ops.v_plan_projection_control_loop CASCADE")
    op.execute(
        """
        CREATE VIEW ops.v_plan_projection_control_loop AS
        SELECT
            plan_version,
            to_date(period, 'YYYY-MM') AS period_date,
            country AS country_norm,
            city AS city_norm,
            country,
            city,
            linea_negocio_canonica,
            MAX(linea_negocio_excel) AS linea_negocio_excel,
            MAX(CASE WHEN metric = 'trips' THEN value_numeric END) AS projected_trips,
            MAX(CASE WHEN metric = 'revenue' THEN value_numeric END) AS projected_revenue,
            MAX(CASE WHEN metric = 'active_drivers' THEN value_numeric END) AS projected_active_drivers,
            MAX(created_at) AS last_loaded_at
        FROM staging.control_loop_plan_metric_long
        GROUP BY plan_version, to_date(period, 'YYYY-MM'), country, city, linea_negocio_canonica
        """
    )
    op.execute(
        "COMMENT ON VIEW ops.v_plan_projection_control_loop IS "
        "'Plan Control Loop pivot; linea_negocio_excel para alinear con business_slice_name (Omniview).'"
    )

    op.execute("DROP VIEW IF EXISTS ops.v_real_monthly_control_loop_from_tajadas CASCADE")
    op.execute(
        """
        CREATE VIEW ops.v_real_monthly_control_loop_from_tajadas AS
        SELECT
            b.trip_month::date AS month,
            lower(trim(b.country::text)) AS country_norm,
            lower(trim(b.city::text)) AS city_norm,
            max(b.country::text) AS country,
            max(b.city::text) AS city,
            trim(b.business_slice_name::text) AS business_slice_name,
            COUNT(*) FILTER (WHERE b.completed_flag) AS real_trips,
            SUM(COALESCE(b.revenue_yego_net, 0::numeric)) FILTER (WHERE b.completed_flag) AS real_revenue,
            COUNT(DISTINCT b.driver_id) FILTER (WHERE b.completed_flag AND b.driver_id IS NOT NULL) AS real_active_drivers,
            CASE lower(trim(max(b.country::text)))
                WHEN 'pe' THEN 'PEN'
                WHEN 'co' THEN 'COP'
                ELSE NULL
            END AS currency,
            'business_slice_resolved'::text AS source_rule_type,
            'aggregate:v_real_trips_business_slice_resolved'::text AS source_match_detail
        FROM ops.v_real_trips_business_slice_resolved b
        WHERE b.resolution_status = 'resolved'
          AND b.business_slice_name IS NOT NULL
          AND trim(b.business_slice_name::text) <> ''
        GROUP BY
            b.trip_month::date,
            lower(trim(b.country::text)),
            lower(trim(b.city::text)),
            trim(b.business_slice_name::text)
        """
    )
    op.execute(
        "COMMENT ON VIEW ops.v_real_monthly_control_loop_from_tajadas IS "
        "'Real mensual por tajada (business_slice_name) alineado a Omniview: mismo resolved que Matrix.'"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_monthly_control_loop_from_tajadas CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.control_loop_plan_line_to_business_slice CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_plan_projection_control_loop CASCADE")
    op.execute(
        """
        CREATE VIEW ops.v_plan_projection_control_loop AS
        SELECT
            plan_version,
            to_date(period, 'YYYY-MM') AS period_date,
            country AS country_norm,
            city AS city_norm,
            country,
            city,
            linea_negocio_canonica,
            MAX(CASE WHEN metric = 'trips' THEN value_numeric END) AS projected_trips,
            MAX(CASE WHEN metric = 'revenue' THEN value_numeric END) AS projected_revenue,
            MAX(CASE WHEN metric = 'active_drivers' THEN value_numeric END) AS projected_active_drivers,
            MAX(created_at) AS last_loaded_at
        FROM staging.control_loop_plan_metric_long
        GROUP BY plan_version, to_date(period, 'YYYY-MM'), country, city, linea_negocio_canonica
        """
    )
