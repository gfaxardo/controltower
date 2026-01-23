"""create mv_real_trips_monthly_v2 without proxies

Revision ID: 013_create_mv_real_trips_monthly_v2_no_proxy
Revises: 010_fix_real_rev_gmv
Create Date: 2026-01-20 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '013_create_mv_real_trips_monthly_v2_no_proxy'
down_revision = '010_fix_real_rev_gmv'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Crear ops.mv_real_trips_monthly_v2 sin proxies.
    Revenue real = SUM(NULLIF(comision_empresa_asociada, 0))
    Sin profit_proxy, revenue_real_proxy, commission_rate_default.
    """
    
    # Crear MV v2 sin proxies
    op.execute("""
        CREATE MATERIALIZED VIEW ops.mv_real_trips_monthly_v2 AS
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
                
                -- Revenue real YEGO: comision_empresa_asociada (sin ABS, según regla canónica)
                -- NULLIF convierte 0 a NULL, que se ignora en SUM
                SUM(NULLIF(t.comision_empresa_asociada, 0)) as revenue_real_yego,
                
                -- GMV real (opcional, si existe y está bien definido)
                SUM(
                    COALESCE(t.efectivo, 0) +
                    COALESCE(t.tarjeta, 0) +
                    COALESCE(t.pago_corporativo, 0)
                ) as gmv_passenger_paid,
                
                SUM(
                    COALESCE(t.efectivo, 0) +
                    COALESCE(t.tarjeta, 0) +
                    COALESCE(t.pago_corporativo, 0) +
                    COALESCE(t.propina, 0) +
                    COALESCE(t.otros_pagos, 0) +
                    COALESCE(t.bonificaciones, 0) +
                    COALESCE(t.promocion, 0)
                ) as gmv_total,
                
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
        ),
        -- Evitar duplicados en JOIN con dim_park usando DISTINCT ON
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
            -- Dimensiones
            r.month,
            COALESCE(dp.country, '') as country,
            COALESCE(dp.city, '') as city,
            LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
            r.park_id,
            COALESCE(dp.default_line_of_business, r.lob_raw) as lob_base,
            r.segment,
            
            -- Métricas base (REAL canónico - SIN PROXIES)
            r.trips_real_completed,
            r.active_drivers_real,
            r.avg_ticket_real,
            
            -- Revenue real YEGO (canónico, sin proxy)
            COALESCE(r.revenue_real_yego, 0) as revenue_real_yego,
            
            -- GMV real (opcional, si existe)
            r.gmv_passenger_paid,
            r.gmv_total,
            
            -- Indicadores derivados (calculados desde datos reales)
            CASE 
                WHEN r.active_drivers_real > 0 
                THEN r.trips_real_completed::NUMERIC / r.active_drivers_real
                ELSE NULL
            END as trips_per_driver,
            
            -- Take rate (solo si gmv existe y es > 0)
            CASE
                WHEN r.gmv_passenger_paid > 0 AND r.revenue_real_yego IS NOT NULL
                THEN ROUND(
                    r.revenue_real_yego / NULLIF(r.gmv_passenger_paid, 0),
                    4
                )
                ELSE NULL
            END as take_rate_yego,
            
            -- Metadata
            NOW() as refreshed_at,
            
            -- Flag para meses parciales (mes actual)
            (r.month = DATE_TRUNC('month', NOW())::DATE) as is_partial_real
            
        FROM real_aggregated r
        LEFT JOIN dim_park_unique dp ON r.park_id = dp.park_id
    """)
    
    # Crear índices para performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_v2_month 
        ON ops.mv_real_trips_monthly_v2(month)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_v2_country_city_lob_seg_month 
        ON ops.mv_real_trips_monthly_v2(country, city_norm, lob_base, segment, month)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_v2_country 
        ON ops.mv_real_trips_monthly_v2(country)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_v2_city_norm 
        ON ops.mv_real_trips_monthly_v2(city_norm)
    """)
    
    # Comentarios para documentación
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_trips_monthly_v2 IS 
        'Agregado mensual REAL sin proxies. Revenue YEGO = SUM(comision_empresa_asociada). Sin profit_proxy, revenue_real_proxy, commission_rate_default.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly_v2.revenue_real_yego IS 
        'Revenue real YEGO = SUM(NULLIF(comision_empresa_asociada, 0)). Canónico, sin proxy.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly_v2.is_partial_real IS 
        'TRUE si el mes es el mes actual (datos parciales). FALSE si el mes está cerrado.';
    """)
    
    # Crear función de refresh
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly_v2()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly_v2;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Poblar la vista inicialmente
    op.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly_v2")


def downgrade() -> None:
    """
    Eliminar MV v2 y función de refresh.
    """
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_real_trips_monthly_v2()")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly_v2")
