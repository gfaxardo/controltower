"""enhance_phase2b_weekly_views_margin

Revision ID: 016_enhance_phase2b_weekly_views_margin
Revises: 015_create_phase2b_actions_table
Create Date: 2026-01-22 21:25:07.000000

FASE 2B: Extender vistas semanales con margen unitario y alertas mejoradas.
Enfoque en ingreso por viaje y alertas accionables.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '016_enhance_weekly_margin'
down_revision = '015_create_phase2b_actions_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Actualizar ops.v_plan_vs_real_weekly para agregar gap_unitario_pct
    # Necesitamos DROP primero porque PostgreSQL no permite cambiar orden de columnas con CREATE OR REPLACE
    op.execute("DROP VIEW IF EXISTS ops.v_plan_vs_real_weekly CASCADE")
    op.execute("""
        CREATE VIEW ops.v_plan_vs_real_weekly AS
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
            CASE
                WHEN p.ingreso_por_viaje_plan > 0
                THEN (r.ingreso_por_viaje_real - p.ingreso_por_viaje_plan) / p.ingreso_por_viaje_plan
                ELSE NULL
            END as gap_unitario_pct,
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

    # 2) Actualizar ops.v_alerts_2b_weekly con campos mejorados
    # Necesitamos DROP primero porque PostgreSQL no permite cambiar orden de columnas con CREATE OR REPLACE
    op.execute("DROP VIEW IF EXISTS ops.v_alerts_2b_weekly CASCADE")
    op.execute("""
        CREATE VIEW ops.v_alerts_2b_weekly AS
        WITH base AS (
            SELECT *
            FROM ops.v_plan_vs_real_weekly
            WHERE week_start < DATE_TRUNC('week', NOW())::DATE
              AND trips_plan IS NOT NULL
              AND trips_real IS NOT NULL
        ),
        enriched AS (
            SELECT
                *,
                -- dominant_driver mejorado
                CASE
                    WHEN ingreso_por_viaje_plan IS NOT NULL 
                         AND ABS(efecto_unitario) > ABS(efecto_volumen) 
                    THEN 'UNIT'
                    WHEN ingreso_por_viaje_plan IS NOT NULL 
                    THEN 'VOL'
                    ELSE 'VOL'  -- fallback si no hay plan unitario
                END as dominant_driver,
                -- severity_score: priorizar money
                (ABS(gap_revenue) * 1.0) + (ABS(gap_trips) * 0.0) as severity_score,
                -- unit_alert: solo si gap_unitario_pct <= -0.10, trips >= 10k, semana pasada
                CASE
                    WHEN gap_unitario_pct IS NOT NULL 
                         AND gap_unitario_pct <= -0.10
                         AND trips_real >= 10000
                         AND week_start < DATE_TRUNC('week', NOW())::DATE
                    THEN true
                    ELSE false
                END as unit_alert,
                -- alert_key estable
                CONCAT(
                    week_start, '|',
                    COALESCE(country, ''), '|',
                    COALESCE(city_norm, ''), '|',
                    COALESCE(lob_base, ''), '|',
                    COALESCE(segment, '')
                ) as alert_key
            FROM base
        ),
        ranked AS (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    ORDER BY severity_score DESC NULLS LAST,
                             ABS(gap_revenue) DESC NULLS LAST,
                             ABS(gap_trips) DESC NULLS LAST
                ) as impacto_rank
            FROM enriched
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
            gap_unitario_pct,
            efecto_volumen,
            efecto_unitario,
            trips_teoricos_por_drivers,
            trips_teoricos_por_prod,
            -- why mejorado
            CASE
                WHEN dominant_driver = 'UNIT' 
                     AND gap_unitario_pct IS NOT NULL 
                     AND gap_unitario_pct < 0
                    THEN 'Cae ingreso por viaje (unitario) — revisar promos/take/reversos/mix'
                WHEN dominant_driver = 'VOL' 
                     AND gap_trips_pct IS NOT NULL 
                     AND gap_trips_pct < 0
                    THEN 'Cae volumen — revisar supply/productividad'
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
            dominant_driver,
            severity_score,
            unit_alert,
            alert_key,
            impacto_rank
        FROM ranked
        WHERE gap_trips_pct <= -0.10
           OR gap_revenue_pct <= -0.10
           OR gap_unitario_pct <= -0.10
           OR impacto_rank <= 20
        ORDER BY severity_score DESC NULLS LAST, ABS(gap_revenue) DESC NULLS LAST, ABS(gap_trips) DESC NULLS LAST;
    """)


def downgrade() -> None:
    # Downgrade intencionalmente no destructivo
    pass
