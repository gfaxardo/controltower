"""create_real_financials_monthly_view

Revision ID: 011_create_real_financials_monthly_view
Revises: 010_fix_real_revenue_gmv_take_rate
Create Date: 2026-01-28 10:00:00.000000

NORMALIZACIÓN DEFINITIVA DE KPIs FINANCIEROS REAL
- Vista canónica ops.mv_real_financials_monthly con KPIs financieros normalizados
- Revenue YEGO REAL = SUM(comision_empresa_asociada)
- GMV = SUM(efectivo + tarjeta + otros_pagos)
- Take Rate REAL = revenue_yego_real / GMV
- Margen unitario = revenue_yego_real / trips
- PROHIBIDO proxy 3% en REAL
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011_real_financials'
down_revision: Union[str, None] = '010_fix_real_rev_gmv'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Crear vista materializada canónica para KPIs financieros REAL.
    
    DECISIONES CANÓNICAS:
    1) Revenue YEGO REAL = SUM(comision_empresa_asociada)
    2) GMV = SUM(efectivo + tarjeta + otros_pagos)
    3) Take Rate REAL = revenue_yego_real / GMV
    4) Margen unitario = revenue_yego_real / trips
    5) PROHIBIDO proxy 3% en REAL
    """
    
    # Crear vista materializada canónica
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_financials_monthly CASCADE")
    
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_financials_monthly AS
        SELECT
            -- Dimensiones
            COALESCE(dp.country, '') as country,
            COALESCE(dp.city, '') as city,
            COALESCE(dp.default_line_of_business, t.tipo_servicio) as lob_base,
            CASE 
                WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                ELSE 'b2c'
            END as segment,
            EXTRACT(YEAR FROM t.fecha_inicio_viaje)::int AS year,
            EXTRACT(MONTH FROM t.fecha_inicio_viaje)::int AS month,
            
            -- KPIs Canónicos REAL
            COUNT(*) AS trips_real,
            
            -- GMV = efectivo + tarjeta + otros_pagos (lo que paga el pasajero)
            SUM(
                COALESCE(t.efectivo, 0) +
                COALESCE(t.tarjeta, 0) +
                COALESCE(t.pago_corporativo, 0)
            ) AS gmv_real,
            
            -- Revenue YEGO REAL = comision_empresa_asociada (normalizado con ABS)
            SUM(ABS(COALESCE(t.comision_empresa_asociada, 0))) AS revenue_yego_real,
            
            -- Take Rate REAL = revenue_yego_real / GMV
            CASE
                WHEN SUM(
                    COALESCE(t.efectivo, 0) +
                    COALESCE(t.tarjeta, 0) +
                    COALESCE(t.pago_corporativo, 0)
                ) > 0
                THEN
                    SUM(ABS(COALESCE(t.comision_empresa_asociada, 0))) /
                    NULLIF(SUM(
                        COALESCE(t.efectivo, 0) +
                        COALESCE(t.tarjeta, 0) +
                        COALESCE(t.pago_corporativo, 0)
                    ), 0)
                ELSE NULL
            END AS take_rate_real,
            
            -- Margen unitario = revenue_yego_real / trips
            CASE
                WHEN COUNT(*) > 0
                THEN SUM(ABS(COALESCE(t.comision_empresa_asociada, 0))) / COUNT(*)::NUMERIC
                ELSE NULL
            END AS margin_per_trip_real
            
        FROM public.trips_all t
        LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
        WHERE t.condicion = 'Completado'
        AND t.fecha_inicio_viaje IS NOT NULL
        GROUP BY 
            COALESCE(dp.country, ''),
            COALESCE(dp.city, ''),
            COALESCE(dp.default_line_of_business, t.tipo_servicio),
            CASE 
                WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                ELSE 'b2c'
            END,
            EXTRACT(YEAR FROM t.fecha_inicio_viaje)::int,
            EXTRACT(MONTH FROM t.fecha_inicio_viaje)::int
    """)
    
    # Crear índices para performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_financials_country 
        ON ops.mv_real_financials_monthly(country)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_financials_city 
        ON ops.mv_real_financials_monthly(city)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_financials_lob_segment 
        ON ops.mv_real_financials_monthly(lob_base, segment)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_financials_year_month 
        ON ops.mv_real_financials_monthly(year, month)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_financials_full 
        ON ops.mv_real_financials_monthly(country, city, lob_base, segment, year, month)
    """)
    
    # Comentarios para documentación
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_financials_monthly IS 
        'Vista canónica de KPIs financieros REAL. Revenue YEGO = comision_empresa_asociada. GMV = efectivo + tarjeta + pago_corporativo. PROHIBIDO proxy 3% en REAL.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_financials_monthly.revenue_yego_real IS 
        'Revenue real de YEGO = SUM(ABS(comision_empresa_asociada)). Este es nuestro revenue REAL, NO es GMV.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_financials_monthly.gmv_real IS 
        'GMV = SUM(efectivo + tarjeta + pago_corporativo). Lo que paga el pasajero.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_financials_monthly.take_rate_real IS 
        'Take Rate REAL = revenue_yego_real / gmv_real. Calculado solo cuando GMV > 0.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_financials_monthly.margin_per_trip_real IS 
        'Margen unitario REAL = revenue_yego_real / trips_real. Revenue por viaje.';
    """)
    
    # Refrescar vista materializada
    op.execute("REFRESH MATERIALIZED VIEW ops.mv_real_financials_monthly")


def downgrade() -> None:
    """
    Eliminar vista materializada de KPIs financieros.
    """
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_financials_monthly CASCADE")
