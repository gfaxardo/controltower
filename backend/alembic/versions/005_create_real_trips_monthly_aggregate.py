"""create_real_trips_monthly_aggregate

Revision ID: 005_create_real_trips_monthly_aggregate
Revises: 004_fix_plan_trips_nullable_park_id_and_city_norm
Create Date: 2026-01-16 12:00:00.000000

PASO B: Agregado mensual de REAL para validaciones rápidas (no escanear trips_all)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_create_real_trips_monthly_aggregate'
down_revision: Union[str, None] = '004_fix_plan_trips_nullable_park_id_and_city_norm'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crear materialized view para agregado mensual de REAL
    # Usado para validaciones rápidas Plan vs Real (sin escanear trips_all)
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
                -- Métricas
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
            -- Mapeo de lob: usar default_line_of_business si existe, si no tipo_servicio
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
    
    # Crear índices para performance
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month ON ops.mv_real_trips_monthly(month)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_city_norm ON ops.mv_real_trips_monthly(city_norm)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_lob_segment ON ops.mv_real_trips_monthly(lob_base, segment)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month_city_lob_seg ON ops.mv_real_trips_monthly(month, city_norm, lob_base, segment)")
    
    # Comentarios
    op.execute("""
        COMMENT ON MATERIALIZED VIEW ops.mv_real_trips_monthly IS 
        'Agregado mensual de REAL (completados) para validaciones rápidas Plan vs Real. Grano: (country, city, city_norm, lob_base, segment, month). Refrescar manualmente cuando se actualicen trips_all.';
    """)
    
    # Crear función para refresh (opcional)
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS ops.refresh_real_trips_monthly()")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly CASCADE")
