"""add_plan_financials_canonical

Revision ID: 012_add_plan_financials_canonical
Revises: 011_create_real_financials_monthly_view
Create Date: 2026-01-28 11:00:00.000000

NORMALIZACIÓN DEFINITIVA DE KPIs FINANCIEROS PLAN
- Ajustar vista plan mensual con KPIs financieros canónicos
- revenue_yego_plan: usar projected_revenue explícito si existe, si no calcular con proxy 3%
- take_rate_plan: revenue_yego_plan / GMV estimado
- margin_per_trip_plan: revenue_yego_plan / projected_trips
- is_estimated: true si se usó proxy, false si viene del archivo
- PROHIBIDO inferir GMV como revenue
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '012_plan_financials'
down_revision: Union[str, None] = '011_real_financials'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ajustar vista plan mensual para incluir KPIs financieros canónicos.
    
    REGLAS:
    - Si projected_revenue existe → revenue_yego_plan = projected_revenue, is_estimated = false
    - Si NO existe projected_revenue → revenue_yego_plan = projected_trips * projected_ticket * 0.03, is_estimated = true
    - take_rate_plan = revenue_yego_plan / (projected_trips * projected_ticket)
    - margin_per_trip_plan = revenue_yego_plan / projected_trips
    - JAMÁS inferir GMV como revenue
    """
    
    # Recrear vista latest con KPIs financieros canónicos
    op.execute("DROP VIEW IF EXISTS ops.v_plan_trips_monthly_latest CASCADE")
    
    op.execute("""
        CREATE VIEW ops.v_plan_trips_monthly_latest AS
        WITH latest_version AS (
            SELECT plan_version
            FROM ops.plan_trips_monthly
            GROUP BY plan_version
            ORDER BY MAX(created_at) DESC
            LIMIT 1
        )
        SELECT 
            p.plan_version,
            p.country,
            p.city,
            p.city_norm,
            p.park_id,
            p.lob_base,
            p.segment,
            p.month,
            p.projected_trips,
            p.projected_drivers,
            p.projected_ticket,
            p.projected_trips_per_driver,
            p.projected_revenue,
            p.created_at,
            
            -- KPIs Financieros Canónicos PLAN
            -- Revenue YEGO Plan: usar projected_revenue explícito si existe, si no calcular con proxy 3%
            CASE
                WHEN p.projected_revenue IS NOT NULL AND p.projected_revenue > 0
                THEN p.projected_revenue
                WHEN p.projected_trips IS NOT NULL AND p.projected_ticket IS NOT NULL
                THEN p.projected_trips * p.projected_ticket * 0.03::NUMERIC
                ELSE NULL
            END AS revenue_yego_plan,
            
            -- Take Rate Plan: revenue_yego_plan / GMV estimado
            CASE
                WHEN p.projected_trips IS NOT NULL 
                    AND p.projected_ticket IS NOT NULL 
                    AND p.projected_trips * p.projected_ticket > 0
                THEN
                    CASE
                        WHEN p.projected_revenue IS NOT NULL AND p.projected_revenue > 0
                        THEN p.projected_revenue / NULLIF(p.projected_trips * p.projected_ticket, 0)
                        ELSE 0.03::NUMERIC
                    END
                ELSE NULL
            END AS take_rate_plan,
            
            -- Margen unitario Plan: revenue_yego_plan / projected_trips
            CASE
                WHEN p.projected_trips IS NOT NULL AND p.projected_trips > 0
                THEN
                    CASE
                        WHEN p.projected_revenue IS NOT NULL AND p.projected_revenue > 0
                        THEN p.projected_revenue / p.projected_trips::NUMERIC
                        WHEN p.projected_ticket IS NOT NULL
                        THEN p.projected_ticket * 0.03::NUMERIC
                        ELSE NULL
                    END
                ELSE NULL
            END AS margin_per_trip_plan,
            
            -- Flag de estimación: true si se usó proxy, false si viene del archivo
            CASE
                WHEN p.projected_revenue IS NOT NULL AND p.projected_revenue > 0
                THEN false
                ELSE true
            END AS is_estimated
            
        FROM ops.plan_trips_monthly p
        INNER JOIN latest_version lv ON p.plan_version = lv.plan_version
        ORDER BY p.month, p.country, p.city, p.lob_base, p.segment
    """)
    
    # Comentarios para documentación
    op.execute("""
        COMMENT ON VIEW ops.v_plan_trips_monthly_latest IS 
        'Vista latest de plan mensual con KPIs financieros canónicos. revenue_yego_plan usa projected_revenue explícito si existe, si no calcula con proxy 3%.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.v_plan_trips_monthly_latest.revenue_yego_plan IS 
        'Revenue YEGO Plan: projected_revenue explícito si existe, si no projected_trips * projected_ticket * 0.03. JAMÁS inferir GMV como revenue.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.v_plan_trips_monthly_latest.take_rate_plan IS 
        'Take Rate Plan = revenue_yego_plan / (projected_trips * projected_ticket). Calculado solo cuando GMV estimado > 0.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.v_plan_trips_monthly_latest.margin_per_trip_plan IS 
        'Margen unitario Plan = revenue_yego_plan / projected_trips. Revenue por viaje proyectado.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.v_plan_trips_monthly_latest.is_estimated IS 
        'Flag de estimación: true si se usó proxy 3% (no había projected_revenue explícito), false si viene del archivo.';
    """)


def downgrade() -> None:
    """
    Revertir vista a versión anterior sin KPIs financieros canónicos.
    """
    op.execute("DROP VIEW IF EXISTS ops.v_plan_trips_monthly_latest CASCADE")
    
    # Recrear vista básica
    op.execute("""
        CREATE VIEW ops.v_plan_trips_monthly_latest AS
        WITH latest_version AS (
            SELECT plan_version
            FROM ops.plan_trips_monthly
            GROUP BY plan_version
            ORDER BY MAX(created_at) DESC
            LIMIT 1
        )
        SELECT 
            p.plan_version,
            p.country,
            p.city,
            p.city_norm,
            p.park_id,
            p.lob_base,
            p.segment,
            p.month,
            p.projected_trips,
            p.projected_drivers,
            p.projected_ticket,
            p.projected_trips_per_driver,
            p.projected_revenue,
            p.created_at
        FROM ops.plan_trips_monthly p
        INNER JOIN latest_version lv ON p.plan_version = lv.plan_version
        ORDER BY p.month, p.country, p.city, p.lob_base, p.segment
    """)
