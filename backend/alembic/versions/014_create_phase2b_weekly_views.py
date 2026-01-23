"""create_phase2b_weekly_views

Revision ID: 014_create_phase2b_weekly_views
Revises: 013_create_mv_real_trips_monthly_v2_no_proxy
Create Date: 2026-01-20 18:30:00.000000

FASE 2B: MV REAL semanal + views Plan vs Real semanal (sin proxies).
Cambios idempotentes, sin DROP ... CASCADE.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '014_create_phase2b_weekly_views'
down_revision = '013_create_mv_real_trips_monthly_v2_no_proxy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asegurar esquema ops
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    # 1) MV REAL SEMANAL (sin proxies)
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_real_trips_weekly AS
        WITH real_aggregated AS (
            SELECT
                DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE as week_start,
                t.park_id,
                t.tipo_servicio as lob_raw,
                CASE
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END as segment,
                COUNT(*) as trips_real_completed,
                COUNT(DISTINCT t.conductor_id) as active_drivers_real,
                SUM(NULLIF(t.comision_empresa_asociada, 0)) as commission_yego_signed
            FROM public.trips_all t
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje IS NOT NULL
            GROUP BY
                DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE,
                t.park_id,
                t.tipo_servicio,
                CASE
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END
        ),
        dim_park_unique AS (
            SELECT DISTINCT ON (park_id)
                park_id,
                country,
                city,
                default_line_of_business
            FROM dim.dim_park
            ORDER BY park_id, country, city, default_line_of_business
        )
        SELECT
            NOW() as refreshed_at,
            r.week_start,
            COALESCE(dp.country, '') as country,
            LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
            COALESCE(dp.default_line_of_business, r.lob_raw) as lob_base,
            r.segment,
            r.trips_real_completed,
            r.active_drivers_real,
            r.commission_yego_signed,
            (-1 * COALESCE(r.commission_yego_signed, 0)) as revenue_real_yego,
            CASE
                WHEN r.trips_real_completed > 0
                THEN (-1 * COALESCE(r.commission_yego_signed, 0)) / r.trips_real_completed
                ELSE NULL
            END as margen_unitario_yego,
            CASE
                WHEN r.active_drivers_real > 0
                THEN r.trips_real_completed::NUMERIC / r.active_drivers_real
                ELSE NULL
            END as productividad_real
        FROM real_aggregated r
        LEFT JOIN dim_park_unique dp ON r.park_id = dp.park_id;
    """)

    # Índices para MV semanal
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_weekly_week_start
        ON ops.mv_real_trips_weekly(week_start)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_weekly_country_city_lob_seg_week
        ON ops.mv_real_trips_weekly(country, city_norm, lob_base, segment, week_start)
    """)

    # Función de refresh semanal
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_real_trips_weekly()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW ops.mv_real_trips_weekly;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 2) PLAN semanal desde PLAN mensual (desagregación uniforme)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_trips_weekly_from_monthly AS
        WITH plan_latest AS (
            SELECT *
            FROM ops.v_plan_trips_monthly_latest
        ),
        weeks_per_month AS (
            SELECT
                m.month,
                COUNT(DISTINCT DATE_TRUNC('week', gs)::DATE) as weeks_in_month
            FROM (SELECT DISTINCT month FROM plan_latest) m
            CROSS JOIN LATERAL generate_series(
                DATE_TRUNC('month', m.month)::DATE,
                (DATE_TRUNC('month', m.month) + INTERVAL '1 month - 1 day')::DATE,
                INTERVAL '1 week'
            ) gs
            GROUP BY m.month
        )
        SELECT
            p.plan_version,
            p.month,
            DATE_TRUNC('week', gs)::DATE as week_start,
            p.country,
            COALESCE(p.plan_city_resolved_norm, p.city_norm) as city_norm,
            p.lob_base,
            p.segment,
            w.weeks_in_month,
            p.projected_trips,
            p.projected_drivers,
            p.projected_revenue,
            CASE
                WHEN p.projected_trips IS NOT NULL
                THEN p.projected_trips::NUMERIC / w.weeks_in_month
                ELSE NULL
            END as trips_plan_week,
            CASE
                WHEN p.projected_drivers IS NOT NULL
                THEN p.projected_drivers::NUMERIC / w.weeks_in_month
                ELSE NULL
            END as drivers_plan_week,
            CASE
                WHEN p.projected_revenue IS NOT NULL
                THEN p.projected_revenue::NUMERIC / w.weeks_in_month
                ELSE NULL
            END as revenue_plan_week,
            CASE
                WHEN p.projected_revenue IS NOT NULL
                    AND p.projected_trips IS NOT NULL
                    AND p.projected_trips <> 0
                THEN (p.projected_revenue::NUMERIC / w.weeks_in_month) /
                     (p.projected_trips::NUMERIC / w.weeks_in_month)
                ELSE NULL
            END as ingreso_por_viaje_plan_week,
            CASE
                WHEN p.projected_drivers IS NOT NULL
                    AND p.projected_drivers <> 0
                    AND p.projected_trips IS NOT NULL
                THEN (p.projected_trips::NUMERIC / w.weeks_in_month) /
                     (p.projected_drivers::NUMERIC / w.weeks_in_month)
                ELSE NULL
            END as productividad_plan_week
        FROM plan_latest p
        INNER JOIN weeks_per_month w ON p.month = w.month
        CROSS JOIN LATERAL generate_series(
            DATE_TRUNC('month', p.month)::DATE,
            (DATE_TRUNC('month', p.month) + INTERVAL '1 month - 1 day')::DATE,
            INTERVAL '1 week'
        ) gs;
    """)

    # 3) Dim de llaves semanal (solo keys)
    op.execute("""
        CREATE OR REPLACE VIEW ops.dim_kpi_keys_weekly AS
        SELECT DISTINCT country, city_norm, lob_base, segment
        FROM ops.mv_real_trips_weekly
        UNION
        SELECT DISTINCT country, city_norm, lob_base, segment
        FROM ops.v_plan_trips_weekly_from_monthly;
    """)

    # 4) Vista principal Plan vs Real semanal (explicable)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_plan_vs_real_weekly AS
        WITH plan_weekly AS (
            SELECT
                week_start,
                country,
                city_norm,
                lob_base,
                segment,
                SUM(trips_plan_week) as trips_plan,
                SUM(drivers_plan_week) as drivers_plan,
                SUM(revenue_plan_week) as revenue_plan,
                CASE
                    WHEN SUM(trips_plan_week) > 0
                    THEN SUM(revenue_plan_week) / SUM(trips_plan_week)
                    ELSE NULL
                END as ingreso_por_viaje_plan,
                CASE
                    WHEN SUM(drivers_plan_week) > 0
                    THEN SUM(trips_plan_week) / SUM(drivers_plan_week)
                    ELSE NULL
                END as productividad_plan
            FROM ops.v_plan_trips_weekly_from_monthly
            GROUP BY week_start, country, city_norm, lob_base, segment
        ),
        real_weekly AS (
            SELECT
                week_start,
                country,
                city_norm,
                lob_base,
                segment,
                SUM(trips_real_completed) as trips_real,
                SUM(active_drivers_real) as drivers_real,
                SUM(revenue_real_yego) as revenue_real,
                CASE
                    WHEN SUM(trips_real_completed) > 0
                    THEN SUM(revenue_real_yego) / SUM(trips_real_completed)
                    ELSE NULL
                END as ingreso_por_viaje_real,
                CASE
                    WHEN SUM(active_drivers_real) > 0
                    THEN SUM(trips_real_completed)::NUMERIC / SUM(active_drivers_real)
                    ELSE NULL
                END as productividad_real
            FROM ops.mv_real_trips_weekly
            GROUP BY week_start, country, city_norm, lob_base, segment
        )
        SELECT
            COALESCE(r.week_start, p.week_start) as week_start,
            COALESCE(r.country, p.country) as country,
            COALESCE(r.city_norm, p.city_norm) as city_norm,
            COALESCE(r.lob_base, p.lob_base) as lob_base,
            COALESCE(r.segment, p.segment) as segment,
            -- Trips
            r.trips_real,
            p.trips_plan,
            (r.trips_real - p.trips_plan) as gap_trips,
            CASE
                WHEN p.trips_plan > 0
                THEN (r.trips_real - p.trips_plan) / p.trips_plan
                ELSE NULL
            END as gap_trips_pct,
            -- Drivers
            r.drivers_real,
            p.drivers_plan,
            (r.drivers_real - p.drivers_plan) as gap_drivers,
            CASE
                WHEN p.drivers_plan > 0
                THEN (r.drivers_real - p.drivers_plan) / p.drivers_plan
                ELSE NULL
            END as gap_drivers_pct,
            -- Productividad
            r.productividad_real,
            p.productividad_plan,
            (r.productividad_real - p.productividad_plan) as gap_prod,
            -- Revenue
            r.revenue_real,
            p.revenue_plan,
            (r.revenue_real - p.revenue_plan) as gap_revenue,
            CASE
                WHEN p.revenue_plan > 0
                THEN (r.revenue_real - p.revenue_plan) / p.revenue_plan
                ELSE NULL
            END as gap_revenue_pct,
            -- Ingreso por viaje
            r.ingreso_por_viaje_real,
            p.ingreso_por_viaje_plan,
            (r.ingreso_por_viaje_real - p.ingreso_por_viaje_plan) as gap_unitario,
            -- Descomposición revenue
            CASE
                WHEN p.ingreso_por_viaje_plan IS NOT NULL
                THEN (r.trips_real - p.trips_plan) * p.ingreso_por_viaje_plan
                ELSE NULL
            END as efecto_volumen,
            CASE
                WHEN p.ingreso_por_viaje_plan IS NOT NULL
                THEN r.trips_real * (r.ingreso_por_viaje_real - p.ingreso_por_viaje_plan)
                ELSE NULL
            END as efecto_unitario,
            -- Palancas trips
            CASE
                WHEN p.productividad_plan IS NOT NULL AND r.drivers_real IS NOT NULL
                THEN (r.drivers_real - p.drivers_plan) * p.productividad_plan
                ELSE NULL
            END as trips_teoricos_por_drivers,
            CASE
                WHEN p.productividad_plan IS NOT NULL AND r.drivers_real IS NOT NULL
                THEN r.drivers_real * (r.productividad_real - p.productividad_plan)
                ELSE NULL
            END as trips_teoricos_por_prod
        FROM plan_weekly p
        FULL OUTER JOIN real_weekly r ON (
            p.week_start = r.week_start
            AND p.country = r.country
            AND p.city_norm = r.city_norm
            AND p.lob_base = r.lob_base
            AND p.segment = r.segment
        );
    """)

    # 5) Vista de alertas semanales (accionables)
    op.execute("""
        CREATE OR REPLACE VIEW ops.v_alerts_2b_weekly AS
        WITH base AS (
            SELECT *
            FROM ops.v_plan_vs_real_weekly
            WHERE week_start < DATE_TRUNC('week', NOW())::DATE
              AND trips_plan IS NOT NULL
              AND trips_real IS NOT NULL
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    ORDER BY ABS(gap_revenue) DESC NULLS LAST,
                             ABS(gap_trips) DESC NULLS LAST
                ) as impacto_rank
            FROM base
        )
        SELECT
            week_start,
            country,
            city_norm,
            lob_base,
            segment,
            trips_real,
            trips_plan,
            gap_trips,
            gap_trips_pct,
            drivers_real,
            drivers_plan,
            gap_drivers,
            gap_drivers_pct,
            productividad_real,
            productividad_plan,
            gap_prod,
            revenue_real,
            revenue_plan,
            gap_revenue,
            gap_revenue_pct,
            ingreso_por_viaje_real,
            ingreso_por_viaje_plan,
            gap_unitario,
            efecto_volumen,
            efecto_unitario,
            trips_teoricos_por_drivers,
            trips_teoricos_por_prod,
            CASE
                WHEN gap_trips IS NOT NULL AND gap_trips < 0
                     AND gap_drivers IS NOT NULL AND gap_drivers < 0
                    THEN 'Falta supply (drivers por debajo del plan)'
                WHEN gap_trips IS NOT NULL AND gap_trips < 0
                     AND (gap_drivers IS NULL OR gap_drivers >= 0)
                     AND gap_prod IS NOT NULL AND gap_prod < 0
                    THEN 'Baja productividad (trips/driver)'
                WHEN gap_trips_pct IS NOT NULL AND ABS(gap_trips_pct) <= 0.05
                     AND gap_revenue IS NOT NULL AND gap_revenue < 0
                    THEN 'Cae ingreso por viaje (take/promos/reversos)'
                WHEN gap_revenue IS NOT NULL AND gap_revenue < 0
                     AND ABS(efecto_unitario) >= ABS(efecto_volumen)
                    THEN 'Principalmente unitario'
                WHEN gap_revenue IS NOT NULL AND gap_revenue < 0
                     AND ABS(efecto_volumen) > ABS(efecto_unitario)
                    THEN 'Principalmente volumen'
                ELSE 'Sin clasificar'
            END as why,
            CASE
                WHEN ABS(efecto_unitario) > ABS(efecto_volumen) THEN 'UNIT'
                WHEN ABS(efecto_volumen) > ABS(efecto_unitario) THEN 'VOL'
                ELSE NULL
            END as dominant_effect,
            impacto_rank
        FROM ranked
        WHERE gap_trips_pct <= -0.10
           OR gap_revenue_pct <= -0.10
           OR impacto_rank <= 20
        ORDER BY ABS(gap_revenue) DESC NULLS LAST, ABS(gap_trips) DESC NULLS LAST;
    """)


def downgrade() -> None:
    # Downgrade intencionalmente no destructivo (sin DROP ... CASCADE)
    pass
