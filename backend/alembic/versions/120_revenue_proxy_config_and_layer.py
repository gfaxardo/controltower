"""
Revenue proxy: tabla de configuración de comisión, función de resolución,
vista de auditoría, y columnas proxy en fact tables de business slice.

NO modifica v_real_trips_enriched_base ni sus dependientes.
NO sobreescribe comision_empresa_asociada.
Agrega capa paralela de revenue proxy con trazabilidad.

Revision ID: 120_revenue_proxy_config_and_layer
Revises: 119_business_slice_day_week_facts
"""
from alembic import op

revision = "120_revenue_proxy_config_and_layer"
down_revision = "119_business_slice_day_week_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =====================================================================
    # 1. Tabla de configuración de comisión proxy
    # =====================================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS ops.yego_commission_proxy_config (
            id SERIAL PRIMARY KEY,
            country TEXT,
            city TEXT,
            park_id TEXT,
            tipo_servicio TEXT,
            commission_pct NUMERIC NOT NULL,
            valid_from DATE NOT NULL DEFAULT '2020-01-01',
            valid_to DATE NOT NULL DEFAULT '2099-12-31',
            priority INT NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        COMMENT ON TABLE ops.yego_commission_proxy_config IS
        'Configuración versionada de porcentaje de comisión para revenue proxy YEGO. '
        'Resolución: match más específico (más campos no-null) gana; luego priority DESC; '
        'luego valid_from más reciente. Ver docs/REVENUE_PROXY_DESIGN.md.'
    """)

    # Seed: default global 3%
    op.execute("""
        INSERT INTO ops.yego_commission_proxy_config
            (country, city, park_id, tipo_servicio, commission_pct, valid_from, valid_to, priority, is_active, notes)
        VALUES
            (NULL, NULL, NULL, NULL, 0.03, '2020-01-01', '2099-12-31', 0, TRUE,
             'Default global 3%%. Fallback cuando no hay regla más específica.')
        ON CONFLICT DO NOTHING
    """)

    # =====================================================================
    # 2. Función SQL de resolución de commission_pct
    # =====================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.resolve_commission_pct(
            p_country TEXT DEFAULT NULL,
            p_city TEXT DEFAULT NULL,
            p_park_id TEXT DEFAULT NULL,
            p_tipo_servicio TEXT DEFAULT NULL,
            p_trip_date DATE DEFAULT CURRENT_DATE
        )
        RETURNS NUMERIC
        LANGUAGE sql STABLE
        AS $fn$
            SELECT commission_pct
            FROM ops.yego_commission_proxy_config
            WHERE is_active
              AND p_trip_date >= valid_from
              AND p_trip_date <= valid_to
              AND (country IS NULL OR lower(trim(country)) = lower(trim(p_country)))
              AND (city IS NULL OR lower(trim(city)) = lower(trim(p_city)))
              AND (park_id IS NULL OR lower(trim(park_id)) = lower(trim(p_park_id)))
              AND (tipo_servicio IS NULL OR lower(trim(tipo_servicio)) = lower(trim(p_tipo_servicio)))
            ORDER BY
                (CASE WHEN park_id IS NOT NULL THEN 1 ELSE 0 END
                 + CASE WHEN tipo_servicio IS NOT NULL THEN 1 ELSE 0 END
                 + CASE WHEN city IS NOT NULL THEN 1 ELSE 0 END
                 + CASE WHEN country IS NOT NULL THEN 1 ELSE 0 END
                ) DESC,
                priority DESC,
                valid_from DESC
            LIMIT 1
        $fn$
    """)
    op.execute("""
        COMMENT ON FUNCTION ops.resolve_commission_pct IS
        'Resuelve el porcentaje de comisión proxy para un viaje dado contexto territorial. '
        'Match más específico (más campos no-null) gana, luego priority DESC, luego valid_from DESC.'
    """)

    # =====================================================================
    # 3. Vista de auditoría de revenue (sobre enriched_base, no la toca)
    # =====================================================================
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_revenue_proxy_audit AS
        SELECT
            e.trip_id,
            e.driver_id,
            e.park_id,
            e.park_name,
            e.country,
            e.city,
            e.tipo_servicio,
            e.completed_flag,
            e.cancelled_flag,
            e.trip_date,
            e.trip_month,
            e.trip_week,
            e.trip_hour_start,
            e.ticket,
            e.total_fare,
            e.condicion,
            e.source_table,

            -- revenue_yego_real: ABS del dato original, solo si completado y no-null/no-0
            CASE
                WHEN e.completed_flag
                     AND e.revenue_yego_net IS NOT NULL
                THEN ABS(e.revenue_yego_net)
                ELSE NULL
            END AS revenue_yego_real,

            -- revenue_yego_proxy: ticket * commission_pct, solo completados
            CASE
                WHEN e.completed_flag
                     AND e.ticket IS NOT NULL
                     AND e.ticket > 0
                THEN e.ticket * ops.resolve_commission_pct(
                    e.country, e.city, e.park_id, e.tipo_servicio, e.trip_date
                )
                ELSE NULL
            END AS revenue_yego_proxy,

            -- revenue_yego_final: real si existe, sino proxy
            CASE
                WHEN e.completed_flag
                     AND e.revenue_yego_net IS NOT NULL
                THEN ABS(e.revenue_yego_net)
                WHEN e.completed_flag
                     AND e.ticket IS NOT NULL
                     AND e.ticket > 0
                THEN e.ticket * ops.resolve_commission_pct(
                    e.country, e.city, e.park_id, e.tipo_servicio, e.trip_date
                )
                ELSE NULL
            END AS revenue_yego_final,

            -- revenue_source
            CASE
                WHEN NOT e.completed_flag THEN NULL
                WHEN e.revenue_yego_net IS NOT NULL THEN 'real'
                WHEN e.ticket IS NOT NULL AND e.ticket > 0 THEN 'proxy'
                ELSE 'missing'
            END AS revenue_source,

            -- commission_pct_applied (solo para proxy)
            CASE
                WHEN e.completed_flag
                     AND e.revenue_yego_net IS NULL
                     AND e.ticket IS NOT NULL
                     AND e.ticket > 0
                THEN ops.resolve_commission_pct(
                    e.country, e.city, e.park_id, e.tipo_servicio, e.trip_date
                )
                ELSE NULL
            END AS commission_pct_applied,

            -- revenue_yego_net original (preservado sin modificar)
            e.revenue_yego_net AS revenue_yego_net_original

        FROM ops.v_real_trips_enriched_base e
    """)
    op.execute("""
        COMMENT ON VIEW ops.v_real_revenue_proxy_audit IS
        'Vista de auditoría: revenue real vs proxy por viaje. '
        'NO modifica enriched_base. Usa ops.resolve_commission_pct() para proxy. '
        'revenue_yego_real = ABS(comision_empresa_asociada) cuando disponible; '
        'revenue_yego_proxy = ticket * commission_pct configurado; '
        'revenue_yego_final = COALESCE(real, proxy).'
    """)

    # =====================================================================
    # 4. Vista de cobertura de revenue proxy (agregada por mes/ciudad)
    # =====================================================================
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_real_revenue_proxy_coverage AS
        SELECT
            trip_month,
            country,
            city,
            source_table,
            COUNT(*) FILTER (WHERE completed_flag) AS total_completed,
            COUNT(*) FILTER (WHERE completed_flag AND revenue_source = 'real') AS revenue_real_trips,
            COUNT(*) FILTER (WHERE completed_flag AND revenue_source = 'proxy') AS revenue_proxy_trips,
            COUNT(*) FILTER (WHERE completed_flag AND revenue_source = 'missing') AS revenue_missing_trips,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE completed_flag AND revenue_source = 'real')
                / NULLIF(COUNT(*) FILTER (WHERE completed_flag), 0), 2
            ) AS pct_real,
            ROUND(
                100.0 * COUNT(*) FILTER (WHERE completed_flag AND revenue_source = 'proxy')
                / NULLIF(COUNT(*) FILTER (WHERE completed_flag), 0), 2
            ) AS pct_proxy,
            SUM(revenue_yego_real) FILTER (WHERE completed_flag) AS sum_revenue_real,
            SUM(revenue_yego_proxy) FILTER (WHERE completed_flag) AS sum_revenue_proxy,
            SUM(revenue_yego_final) FILTER (WHERE completed_flag) AS sum_revenue_final
        FROM ops.v_real_revenue_proxy_audit
        GROUP BY trip_month, country, city, source_table
        ORDER BY trip_month, country, city
    """)

    # =====================================================================
    # 5. Columnas proxy en fact tables de Business Slice
    # =====================================================================
    for fact in (
        "ops.real_business_slice_month_fact",
        "ops.real_business_slice_day_fact",
        "ops.real_business_slice_week_fact",
    ):
        op.execute(f"""
            ALTER TABLE {fact}
            ADD COLUMN IF NOT EXISTS revenue_yego_final NUMERIC,
            ADD COLUMN IF NOT EXISTS revenue_real_coverage_pct NUMERIC,
            ADD COLUMN IF NOT EXISTS revenue_proxy_trips BIGINT DEFAULT 0,
            ADD COLUMN IF NOT EXISTS revenue_real_trips BIGINT DEFAULT 0
        """)

    # hour_fact: same columns if it exists
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'ops' AND table_name = 'real_business_slice_hour_fact'
            ) THEN
                ALTER TABLE ops.real_business_slice_hour_fact
                    ADD COLUMN IF NOT EXISTS revenue_yego_final NUMERIC,
                    ADD COLUMN IF NOT EXISTS revenue_real_coverage_pct NUMERIC,
                    ADD COLUMN IF NOT EXISTS revenue_proxy_trips BIGINT DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS revenue_real_trips BIGINT DEFAULT 0;
            END IF;
        END $$
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_real_revenue_proxy_coverage CASCADE")
    op.execute("DROP VIEW IF EXISTS ops.v_real_revenue_proxy_audit CASCADE")
    op.execute("DROP FUNCTION IF EXISTS ops.resolve_commission_pct CASCADE")
    op.execute("DROP TABLE IF EXISTS ops.yego_commission_proxy_config CASCADE")

    for fact in (
        "ops.real_business_slice_month_fact",
        "ops.real_business_slice_day_fact",
        "ops.real_business_slice_week_fact",
        "ops.real_business_slice_hour_fact",
    ):
        op.execute(f"""
            ALTER TABLE {fact}
            DROP COLUMN IF EXISTS revenue_yego_final,
            DROP COLUMN IF EXISTS revenue_real_coverage_pct,
            DROP COLUMN IF EXISTS revenue_proxy_trips,
            DROP COLUMN IF EXISTS revenue_real_trips
        """)
