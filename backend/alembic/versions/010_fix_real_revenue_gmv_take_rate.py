"""fix_real_revenue_gmv_take_rate

Revision ID: 010_fix_real_revenue_gmv_take_rate
Revises: 009_fix_revenue_plan_input
Create Date: 2026-01-27 20:00:00.000000

CORRECCIÓN CRÍTICA: Revenue Real NO es GMV
- Revenue YEGO = comision_empresa_asociada (normalizado con ABS)
- Exponer GMV explícitamente (passenger_paid + extras)
- Calcular take rates (revenue / GMV)
- Mantener backward compatibility con revenue_real_proxy
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '010_fix_real_rev_gmv'
down_revision: Union[str, None] = '009_fix_revenue_plan_input'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    CORRECCIÓN CRÍTICA: Revenue Real es comision_empresa_asociada, NO GMV.
    
    Cambios:
    - revenue_real_proxy ahora es revenue_yego_real (comision_empresa_asociada con ABS)
    - Agregar gmv_passenger_paid, gmv_extras, gmv_total
    - Agregar revenue_yango_real
    - Agregar take_rate_yego y take_rate_total
    - Mantener avg_ticket_real (precio_yango_pro) para compatibilidad
    """
    
    # Recrear MV con revenue correcto y GMV explícito
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly CASCADE")
    
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_monthly AS
        WITH real_aggregated AS (
            SELECT 
                DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE as month,
                t.park_id,
                t.tipo_servicio as lob_raw,
                -- Segment: b2b si pago_corporativo tiene valor, si no b2c
                CASE 
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END as segment,
                
                -- Métricas base (REAL canónico)
                COUNT(*) as trips_real_completed,
                COUNT(DISTINCT t.conductor_id) as active_drivers_real,
                
                -- GMV base: lo que paga el pasajero
                SUM(
                    COALESCE(t.efectivo, 0) +
                    COALESCE(t.tarjeta, 0) +
                    COALESCE(t.pago_corporativo, 0)
                ) as gmv_passenger_paid,
                
                -- Extras (propinas, bonificaciones, etc)
                SUM(
                    COALESCE(t.propina, 0) +
                    COALESCE(t.otros_pagos, 0) +
                    COALESCE(t.bonificaciones, 0) +
                    COALESCE(t.promocion, 0)
                ) as gmv_extras,
                
                -- GMV total (passenger_paid + extras)
                SUM(
                    COALESCE(t.efectivo, 0) +
                    COALESCE(t.tarjeta, 0) +
                    COALESCE(t.pago_corporativo, 0) +
                    COALESCE(t.propina, 0) +
                    COALESCE(t.otros_pagos, 0) +
                    COALESCE(t.bonificaciones, 0) +
                    COALESCE(t.promocion, 0)
                ) as gmv_total,
                
                -- Revenue real YEGO: comision_empresa_asociada (normalizado a positivo)
                SUM(ABS(COALESCE(t.comision_empresa_asociada, 0))) as revenue_yego_real,
                
                -- Revenue real YANGO: comision_servicio (normalizado a positivo)
                SUM(ABS(COALESCE(t.comision_servicio, 0))) as revenue_yango_real,
                
                -- Avg ticket (precio_yango_pro) - mantener para compatibilidad
                AVG(t.precio_yango_pro) FILTER (WHERE t.precio_yango_pro IS NOT NULL) as avg_ticket_real
                
            FROM public.trips_all t
            WHERE t.condicion = 'Completado'
            AND t.fecha_inicio_viaje IS NOT NULL
            GROUP BY 
                DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE,
                t.park_id,
                t.tipo_servicio,
                CASE 
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END
        )
        SELECT 
            -- Dimensiones
            r.month,
            COALESCE(dp.country, '') as country,
            COALESCE(dp.city, '') as city,
            LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
            r.park_id,
            COALESCE(dp.default_line_of_business, r.lob_raw) as lob_base,
            r.segment,
            
            -- Métricas base (REAL canónico)
            r.trips_real_completed,
            r.active_drivers_real,
            r.avg_ticket_real,
            
            -- GMV explícito (trazable)
            r.gmv_passenger_paid,
            r.gmv_extras,
            r.gmv_total,
            
            -- Revenue real (YEGO = nuestro revenue)
            r.revenue_yego_real,
            r.revenue_yango_real,
            
            -- BACKWARD COMPATIBILITY: revenue_real_proxy ahora apunta a revenue_yego_real
            r.revenue_yego_real as revenue_real_proxy,
            
            -- Indicadores derivados básicos (DERIVADAS)
            CASE 
                WHEN r.active_drivers_real > 0 
                THEN r.trips_real_completed::NUMERIC / r.active_drivers_real
                ELSE NULL
            END as trips_per_driver,
            
            -- Take rates (revenue / GMV base)
            CASE
                WHEN r.gmv_passenger_paid > 0
                THEN ROUND(
                    r.revenue_yego_real / NULLIF(r.gmv_passenger_paid, 0),
                    4
                )
                ELSE NULL
            END as take_rate_yego,
            
            CASE
                WHEN r.gmv_passenger_paid > 0
                THEN ROUND(
                    (r.revenue_yego_real + r.revenue_yango_real) / NULLIF(r.gmv_passenger_paid, 0),
                    4
                )
                ELSE NULL
            END as take_rate_total,
            
            -- Economía PROXY (TEMPORAL - placeholder para FASE 2B)
            -- NOTA: Esta comisión será reemplazada por reglas reales en FASE 2B
            0.03::NUMERIC as commission_rate_default,
            r.revenue_yego_real * 0.03::NUMERIC as profit_proxy,
            CASE 
                WHEN r.trips_real_completed > 0 
                THEN (r.revenue_yego_real * 0.03::NUMERIC) / r.trips_real_completed
                ELSE NULL
            END as profit_per_trip_proxy,
            
            -- Metadata
            NOW() as refreshed_at
        FROM real_aggregated r
        LEFT JOIN dim.dim_park dp ON r.park_id = dp.park_id
    """)
    
    # Recrear índices para performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_country 
        ON ops.mv_real_trips_monthly(country)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_city_norm 
        ON ops.mv_real_trips_monthly(city_norm)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_lob_segment 
        ON ops.mv_real_trips_monthly(lob_base, segment)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month_city_lob_seg 
        ON ops.mv_real_trips_monthly(month, city_norm, lob_base, segment)
    """)
    
    # Comentarios para documentación
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_trips_monthly IS 
        'Agregado mensual de REAL (completados). Revenue YEGO = comision_empresa_asociada (no GMV). GMV explícito: passenger_paid + extras. Take rates calculados contra GMV base.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.revenue_yego_real IS 
        'Revenue real de YEGO = ABS(comision_empresa_asociada). Este es nuestro revenue, NO es GMV.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.gmv_passenger_paid IS 
        'GMV base: efectivo + tarjeta + pago_corporativo (lo que paga el pasajero).';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.gmv_total IS 
        'GMV total: passenger_paid + extras (propina, bonificaciones, promociones).';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.revenue_real_proxy IS 
        'BACKWARD COMPATIBILITY: ahora mapea a revenue_yego_real (comision_empresa_asociada). NO es GMV.';
    """)
    
    # Refrescar vista materializada
    op.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly")


def downgrade() -> None:
    """
    Revertir a versión anterior donde revenue_real_proxy = precio_yango_pro (GMV).
    """
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly CASCADE")
    
    # Recrear versión anterior (008)
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_monthly AS
        WITH real_aggregated AS (
            SELECT 
                DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE as month,
                t.park_id,
                t.tipo_servicio as lob_raw,
                CASE 
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END as segment,
                COUNT(*) as trips_real_completed,
                COUNT(DISTINCT t.conductor_id) as active_drivers_real,
                AVG(t.precio_yango_pro) FILTER (WHERE t.precio_yango_pro IS NOT NULL) as avg_ticket_real,
                SUM(t.precio_yango_pro) FILTER (WHERE t.precio_yango_pro IS NOT NULL) as revenue_real_proxy
            FROM public.trips_all t
            WHERE t.condicion = 'Completado'
            AND t.fecha_inicio_viaje IS NOT NULL
            GROUP BY 
                DATE_TRUNC('month', t.fecha_inicio_viaje)::DATE,
                t.park_id,
                t.tipo_servicio,
                CASE 
                    WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b'
                    ELSE 'b2c'
                END
        )
        SELECT 
            r.month,
            COALESCE(dp.country, '') as country,
            COALESCE(dp.city, '') as city,
            LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
            r.park_id,
            COALESCE(dp.default_line_of_business, r.lob_raw) as lob_base,
            r.segment,
            r.trips_real_completed,
            r.active_drivers_real,
            r.avg_ticket_real,
            r.revenue_real_proxy,
            CASE 
                WHEN r.active_drivers_real > 0 
                THEN r.trips_real_completed::NUMERIC / r.active_drivers_real
                ELSE NULL
            END as trips_per_driver,
            0.03::NUMERIC as commission_rate_default,
            r.revenue_real_proxy * 0.03::NUMERIC as profit_proxy,
            CASE 
                WHEN r.trips_real_completed > 0 
                THEN (r.revenue_real_proxy * 0.03::NUMERIC) / r.trips_real_completed
                ELSE NULL
            END as profit_per_trip_proxy,
            NOW() as refreshed_at
        FROM real_aggregated r
        LEFT JOIN dim.dim_park dp ON r.park_id = dp.park_id
    """)
    
    # Recrear índices
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_city_norm 
        ON ops.mv_real_trips_monthly(city_norm)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_lob_segment 
        ON ops.mv_real_trips_monthly(lob_base, segment)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month_city_lob_seg 
        ON ops.mv_real_trips_monthly(month, city_norm, lob_base, segment)
    """)
    
    op.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly")
