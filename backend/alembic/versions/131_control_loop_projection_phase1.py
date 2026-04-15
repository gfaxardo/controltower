"""
131 — Control Loop: staging de proyección agregada (plan_version + métricas wide→long)
y vistas ops para comparación Plan vs Real sin tocar Omniview ni v_plan_vs_real_realkey_final.

down_revision: 130_omniview_matrix_canonical_aggregation
"""

from alembic import op

revision = "131_control_loop_projection_phase1"
down_revision = "130_omniview_matrix_canonical_aggregation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS staging.control_loop_plan_metric_long (
            id BIGSERIAL PRIMARY KEY,
            upload_batch_id UUID NOT NULL,
            plan_version TEXT NOT NULL,
            period TEXT NOT NULL,
            country TEXT NOT NULL,
            city TEXT NOT NULL,
            linea_negocio_excel TEXT NOT NULL,
            linea_negocio_canonica TEXT NOT NULL,
            metric TEXT NOT NULL,
            value_numeric NUMERIC NOT NULL DEFAULT 0,
            source_sheet TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_control_loop_metric CHECK (metric IN ('trips', 'revenue', 'active_drivers')),
            CONSTRAINT uq_control_loop_plan_logical UNIQUE (plan_version, period, country, city, linea_negocio_canonica, metric)
        )
        """
    )
    op.execute(
        "COMMENT ON TABLE staging.control_loop_plan_metric_long IS "
        "'Plan Control Loop: country/city en minúsculas (pe/co, lima); append-only por plan_version.'"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_loop_plan_version_period
        ON staging.control_loop_plan_metric_long (plan_version, period)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS staging.control_loop_plan_reject (
            id BIGSERIAL PRIMARY KEY,
            upload_batch_id UUID NOT NULL,
            plan_version TEXT NOT NULL,
            reject_kind TEXT NOT NULL,
            reason TEXT NOT NULL,
            row_detail JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_control_loop_reject_batch
        ON staging.control_loop_plan_reject (upload_batch_id)
        """
    )

    # Grano viaje + conductor + misma normalización LOB que v_real_trips_with_lob_v2 (064), solo Control Loop.
    op.execute("DROP VIEW IF EXISTS ops.v_control_loop_trip_grain CASCADE")
    op.execute(
        """
        CREATE VIEW ops.v_control_loop_trip_grain AS
        WITH base AS (
            SELECT
                t.conductor_id,
                t.park_id,
                t.tipo_servicio,
                t.fecha_inicio_viaje,
                t.comision_empresa_asociada,
                t.pago_corporativo,
                p.id AS park_id_raw,
                p.name AS park_name_raw,
                p.city AS park_city_raw
            FROM ops.v_trips_real_canon t
            JOIN public.parks p ON LOWER(TRIM(p.id::text)) = LOWER(TRIM(t.park_id::text))
            WHERE t.tipo_servicio IS NOT NULL
              AND t.condicion = 'Completado'
              AND LENGTH(TRIM(t.tipo_servicio::text)) < 100
              AND t.tipo_servicio::text NOT LIKE '%%->%%'
              AND t.conductor_id IS NOT NULL
        ),
        with_city AS (
            SELECT
                conductor_id,
                park_id,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                park_id_raw,
                COALESCE(NULLIF(TRIM(park_name_raw::text), ''), NULLIF(TRIM(park_city_raw::text), ''), park_id_raw::text) AS park_name,
                CASE
                    WHEN park_name_raw::text ILIKE '%%cali%%' THEN 'cali'
                    WHEN park_name_raw::text ILIKE '%%bogot%%' THEN 'bogota'
                    WHEN park_name_raw::text ILIKE '%%barranquilla%%' THEN 'barranquilla'
                    WHEN park_name_raw::text ILIKE '%%medell%%' THEN 'medellin'
                    WHEN park_name_raw::text ILIKE '%%cucut%%' THEN 'cucuta'
                    WHEN park_name_raw::text ILIKE '%%bucaramanga%%' THEN 'bucaramanga'
                    WHEN park_name_raw::text ILIKE '%%lima%%' OR TRIM(park_name_raw::text) = 'Yego' THEN 'lima'
                    WHEN park_name_raw::text ILIKE '%%arequip%%' THEN 'arequipa'
                    WHEN park_name_raw::text ILIKE '%%trujill%%' THEN 'trujillo'
                    ELSE LOWER(TRIM(COALESCE(park_city_raw::text, '')))
                END AS city_norm
            FROM base
        ),
        with_key AS (
            SELECT
                conductor_id,
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                comision_empresa_asociada,
                pago_corporativo,
                LOWER(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                    COALESCE(NULLIF(TRIM(city_norm), ''), ''),
                    'á','a'), 'é','e'), 'í','i'), 'ó','o'), 'ú','u'), 'ñ','n')) AS city_key
            FROM with_city
        ),
        with_country AS (
            SELECT
                conductor_id,
                park_id,
                park_name,
                tipo_servicio,
                fecha_inicio_viaje,
                pago_corporativo,
                COALESCE(NULLIF(city_key, ''), '') AS city,
                CASE
                    WHEN city_key IN ('cali','bogota','barranquilla','medellin','cucuta','bucaramanga') THEN 'co'
                    WHEN city_key IN ('lima','arequipa','trujillo') THEN 'pe'
                    ELSE ''
                END AS country
            FROM with_key
        ),
        with_norm AS (
            SELECT
                country,
                city,
                conductor_id,
                fecha_inicio_viaje,
                CASE
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('economico', 'económico') THEN 'economico'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('confort', 'comfort') THEN 'confort'
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'confort+' THEN 'confort+'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('mensajeria','mensajería') THEN 'mensajería'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('exprés','exprs') THEN 'express'
                    WHEN LOWER(TRIM(tipo_servicio::text)) IN ('minivan','express','premier','moto','cargo','standard','start')
                        THEN LOWER(TRIM(tipo_servicio::text))
                    WHEN LOWER(TRIM(tipo_servicio::text)) = 'tuk-tuk' THEN 'tuk-tuk'
                    WHEN LENGTH(TRIM(tipo_servicio::text)) > 30 THEN 'UNCLASSIFIED'
                    ELSE LOWER(TRIM(tipo_servicio::text))
                END AS real_tipo_servicio_norm
            FROM with_country
        )
        SELECT
            v.country,
            v.city,
            v.conductor_id,
            v.fecha_inicio_viaje,
            v.real_tipo_servicio_norm,
            COALESCE(m.lob_group, 'UNCLASSIFIED') AS lob_group
        FROM with_norm v
        LEFT JOIN canon.map_real_tipo_servicio_to_lob_group m ON m.real_tipo_servicio = v.real_tipo_servicio_norm
        """
    )
    op.execute(
        "COMMENT ON VIEW ops.v_control_loop_trip_grain IS "
        "'Control Loop: viajes reales con lob_group para COUNT(DISTINCT conductor_id) por ciudad/mes/línea canónica.'"
    )

    op.execute("DROP VIEW IF EXISTS ops.v_real_monthly_control_loop_drivers CASCADE")
    op.execute(
        """
        CREATE VIEW ops.v_real_monthly_control_loop_drivers AS
        WITH g AS (
            SELECT
                country,
                city,
                (DATE_TRUNC('month', fecha_inicio_viaje)::DATE) AS month_start,
                lob_group,
                real_tipo_servicio_norm,
                conductor_id
            FROM ops.v_control_loop_trip_grain
        ),
        canon AS (
            SELECT
                *,
                CASE
                    WHEN lob_group = 'auto taxi' THEN 'auto_taxi'
                    WHEN lob_group = 'tuk tuk' THEN 'tuk_tuk'
                    WHEN lob_group = 'taxi moto' THEN 'taxi_moto'
                    WHEN real_tipo_servicio_norm = 'cargo' THEN 'carga'
                    WHEN lob_group = 'delivery' AND real_tipo_servicio_norm IN ('express', 'mensajería') THEN 'delivery'
                    ELSE NULL
                END AS linea_negocio_canonica
            FROM g
        )
        SELECT
            country,
            city,
            month_start,
            linea_negocio_canonica,
            COUNT(DISTINCT conductor_id)::BIGINT AS active_drivers_real
        FROM canon
        WHERE linea_negocio_canonica IS NOT NULL
        GROUP BY country, city, month_start, linea_negocio_canonica
        """
    )

    op.execute("DROP VIEW IF EXISTS ops.v_real_monthly_control_loop_trips_revenue CASCADE")
    op.execute(
        """
        CREATE VIEW ops.v_real_monthly_control_loop_trips_revenue AS
        WITH agg AS (
            SELECT
                country,
                city,
                month_start,
                lob_group,
                real_tipo_servicio_norm,
                SUM(trips)::BIGINT AS trips,
                SUM(revenue)::NUMERIC AS revenue
            FROM ops.mv_real_lob_month_v2
            GROUP BY country, city, month_start, lob_group, real_tipo_servicio_norm
        ),
        canon AS (
            SELECT
                *,
                CASE
                    WHEN lob_group = 'auto taxi' THEN 'auto_taxi'
                    WHEN lob_group = 'tuk tuk' THEN 'tuk_tuk'
                    WHEN lob_group = 'taxi moto' THEN 'taxi_moto'
                    WHEN real_tipo_servicio_norm = 'cargo' THEN 'carga'
                    WHEN lob_group = 'delivery' AND real_tipo_servicio_norm IN ('express', 'mensajería') THEN 'delivery'
                    ELSE NULL
                END AS linea_negocio_canonica
            FROM agg
        )
        SELECT
            country,
            city,
            month_start,
            linea_negocio_canonica,
            SUM(trips)::BIGINT AS trips_real,
            SUM(revenue)::NUMERIC AS revenue_real
        FROM canon
        WHERE linea_negocio_canonica IS NOT NULL
        GROUP BY country, city, month_start, linea_negocio_canonica
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
            MAX(CASE WHEN metric = 'trips' THEN value_numeric END) AS projected_trips,
            MAX(CASE WHEN metric = 'revenue' THEN value_numeric END) AS projected_revenue,
            MAX(CASE WHEN metric = 'active_drivers' THEN value_numeric END) AS projected_active_drivers,
            MAX(created_at) AS last_loaded_at
        FROM staging.control_loop_plan_metric_long
        GROUP BY plan_version, to_date(period, 'YYYY-MM'), country, city, linea_negocio_canonica
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_plan_projection_control_loop CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_monthly_control_loop_trips_revenue CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_monthly_control_loop_drivers CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_control_loop_trip_grain CASCADE")
    op.execute("DROP TABLE IF EXISTS staging.control_loop_plan_reject CASCADE")
    op.execute("DROP TABLE IF EXISTS staging.control_loop_plan_metric_long CASCADE")
