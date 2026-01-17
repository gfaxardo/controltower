"""consolidate_real_monthly_phase2a

Revision ID: 008_consolidate_real_monthly_phase2a
Revises: 007_create_plan_vs_real_views
Create Date: 2026-01-27 15:00:00.000000

FASE 2A - Consolidación REAL Operativo
- Extiende ops.mv_real_trips_monthly con métricas derivadas y proxies económicos
- Placeholder para economía avanzada (FASE 2B)
- Sin lógica económica compleja, solo proxies simples
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008_consolidate_real_phase2a'
down_revision: Union[str, None] = '007_create_plan_vs_real_views'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    FASE 2A: Consolidar agregado REAL mensual con:
    - Métricas base (ya existentes)
    - Indicadores derivados básicos
    - Ganancia PROXY simple (placeholder temporal)
    """
    
    # Recrear MV con extensiones FASE 2A
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
            r.revenue_real_proxy,
            
            -- Indicadores derivados básicos (DERIVADAS)
            CASE 
                WHEN r.active_drivers_real > 0 
                THEN r.trips_real_completed::NUMERIC / r.active_drivers_real
                ELSE NULL
            END as trips_per_driver,
            
            -- Economía PROXY (TEMPORAL - placeholder para FASE 2B)
            -- NOTA: Esta comisión será reemplazada por reglas reales en FASE 2B
            -- Ver: canon.commission_rules (estructura preparada pero no activada)
            0.03::NUMERIC as commission_rate_default,
            r.revenue_real_proxy * 0.03::NUMERIC as profit_proxy,
            CASE 
                WHEN r.trips_real_completed > 0 
                THEN (r.revenue_real_proxy * 0.03::NUMERIC) / r.trips_real_completed
                ELSE NULL
            END as profit_per_trip_proxy,
            
            -- Metadata
            NOW() as refreshed_at
        FROM real_aggregated r
        LEFT JOIN dim.dim_park dp ON r.park_id = dp.park_id
    """)
    
    # Recrear índices para performance
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month ON ops.mv_real_trips_monthly(month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_city_norm ON ops.mv_real_trips_monthly(city_norm)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_lob_segment ON ops.mv_real_trips_monthly(lob_base, segment)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month_city_lob_seg ON ops.mv_real_trips_monthly(month, city_norm, lob_base, segment)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_country ON ops.mv_real_trips_monthly(country)")
    
    # Comentarios descriptivos
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_trips_monthly IS 
        'FASE 2A: Agregado mensual de REAL (completados) consolidado. 
        Grano: (country, city, city_norm, lob_base, segment, month).
        Métricas: REAL (trips, drivers, revenue), DERIVADAS (trips_per_driver), PROXY (profit con commission_rate_default=0.03).
        Refrescar manualmente cuando se actualicen trips_all.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.trips_real_completed IS 
        'REAL: Conteo de viajes completados (condicion=''Completado'')';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.revenue_real_proxy IS 
        'REAL: Suma de precio_yango_pro (proxy de revenue, no incluye comisiones reales)';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.trips_per_driver IS 
        'DERIVADA: trips_real_completed / active_drivers_real (productividad)';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.commission_rate_default IS 
        'PROXY TEMPORAL: Tasa de comisión fija 3% (placeholder para FASE 2B). 
        En FASE 2B se reemplazará por reglas dinámicas desde canon.commission_rules.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.profit_proxy IS 
        'PROXY TEMPORAL: revenue_real_proxy * commission_rate_default (ganancia estimada simple). 
        En FASE 2B se calculará con reglas reales de comisión.';
    """)
    
    op.execute("""
        COMMENT ON COLUMN ops.mv_real_trips_monthly.profit_per_trip_proxy IS 
        'PROXY TEMPORAL: profit_proxy / trips_real_completed (ganancia por viaje estimada). 
        En FASE 2B se calculará con reglas reales de comisión.';
    """)
    
    # Asegurar función de refresh (mejorada con manejo de errores)
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly()
        RETURNS void AS $$
        BEGIN
            -- Intentar refresh concurrente (requiere índice único)
            BEGIN
                REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly;
            EXCEPTION
                WHEN OTHERS THEN
                    -- Si falla (falta índice único o conflicto), usar refresh normal
                    REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;
            END;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Preparar estructura para FASE 2B (SIN ACTIVAR - solo documentación)
    # Esta tabla NO se usará en FASE 2A, solo se prepara para futuro
    # La estructura DDL está documentada en backend/FASE_2A_CIERRE.md
    # No ejecutamos nada aquí, solo comentarios en código Python
    pass  # FASE 2B: canon.commission_rules será creada en migración futura


def downgrade() -> None:
    """
    Revertir a versión anterior (sin extensiones FASE 2A).
    Mantener MV básica si se necesita.
    """
    # Eliminar función de refresh
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_real_trips_monthly()")
    
    # Recrear MV básica (versión anterior sin proxies económicos)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly CASCADE")
    
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
            NOW() as refreshed_at
        FROM real_aggregated r
        LEFT JOIN dim.dim_park dp ON r.park_id = dp.park_id
    """)
    
    # Recrear índices básicos
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month ON ops.mv_real_trips_monthly(month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_city_norm ON ops.mv_real_trips_monthly(city_norm)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_lob_segment ON ops.mv_real_trips_monthly(lob_base, segment)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month_city_lob_seg ON ops.mv_real_trips_monthly(month, city_norm, lob_base, segment)")
