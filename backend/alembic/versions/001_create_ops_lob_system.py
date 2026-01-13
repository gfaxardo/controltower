"""create_ops_lob_system

Revision ID: 001_create_ops_lob_system
Revises: 
Create Date: 2025-01-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_create_ops_lob_system'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    
    op.execute("""
        CREATE TABLE IF NOT EXISTS canon.lob_tipo_servicio_map (
            tipo_servicio_norm text PRIMARY KEY,
            line_of_business_base text NOT NULL,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    
    op.execute("""
        INSERT INTO canon.lob_tipo_servicio_map (tipo_servicio_norm, line_of_business_base) VALUES
        ('economico', 'Auto Taxi'),
        ('económico', 'Auto Taxi'),
        ('confort', 'Auto Taxi'),
        ('confort+', 'Auto Taxi'),
        ('premier', 'Auto Taxi'),
        ('standard', 'Auto Taxi'),
        ('start', 'Auto Taxi'),
        ('minivan', 'Auto Taxi'),
        ('tuk-tuk', 'Auto Taxi'),
        ('mensajeria', 'Delivery'),
        ('mensajería', 'Delivery'),
        ('expres', 'Delivery'),
        ('exprés', 'Delivery'),
        ('cargo', 'Delivery'),
        ('envios', 'Delivery'),
        ('envíos', 'Delivery'),
        ('moto', 'Moto')
        ON CONFLICT (tipo_servicio_norm) DO NOTHING
    """)
    
    op.execute("DROP VIEW IF EXISTS ops.v_trip_lob_canonical")
    op.execute("""
        CREATE VIEW ops.v_trip_lob_canonical AS
        SELECT 
            t.id as trip_id,
            t.fecha_inicio_viaje as trip_date,
            t.park_id,
            COALESCE(d.country, '') as country,
            COALESCE(d.city, '') as city,
            t.tipo_servicio as tipo_servicio_raw,
            COALESCE(d.default_line_of_business, '') as default_lob_raw,
            t.pago_corporativo as pago_corporativo_raw,
            (t.pago_corporativo IS NOT NULL AND t.pago_corporativo::text NOT IN ('', '0', 'false', 'False')) as is_b2b,
            CASE 
                WHEN (t.pago_corporativo IS NOT NULL AND t.pago_corporativo::text NOT IN ('', '0', 'false', 'False')) 
                THEN 'b2b' 
                ELSE 'b2c' 
            END as segment,
            COALESCE(m.line_of_business_base, COALESCE(d.default_line_of_business, '')) as line_of_business_base,
            CASE 
                WHEN m.line_of_business_base IS NOT NULL THEN 'tipo_servicio'
                WHEN COALESCE(d.default_line_of_business, '') != '' THEN 'default_lob'
                ELSE 'unknown'
            END as resolution_source,
            (t.tipo_servicio IS NOT NULL AND m.line_of_business_base IS NULL) as is_unmapped_tipo_servicio,
            (m.line_of_business_base IS NOT NULL AND d.default_line_of_business IS NOT NULL 
             AND lower(trim(m.line_of_business_base)) != lower(trim(d.default_line_of_business))) as is_conflict,
            CASE 
                WHEN COALESCE(m.line_of_business_base, COALESCE(d.default_line_of_business, '')) != '' 
                THEN COALESCE(m.line_of_business_base, COALESCE(d.default_line_of_business, '')) || ' - ' || 
                     CASE 
                         WHEN (t.pago_corporativo IS NOT NULL AND t.pago_corporativo::text NOT IN ('', '0', 'false', 'False')) 
                         THEN 'b2b' 
                         ELSE 'b2c' 
                     END
                ELSE NULL
            END as lob_bucket
        FROM public.trips_all t
        LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
        LEFT JOIN canon.lob_tipo_servicio_map m ON lower(trim(t.tipo_servicio)) = m.tipo_servicio_norm AND m.is_active = true
    """)
    
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_kpis")
    op.execute("""
        CREATE VIEW ops.v_lob_mapping_quality_kpis AS
        SELECT 
            COUNT(*) as total_trips,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'tipo_servicio') / NULLIF(COUNT(*), 0), 2) as pct_resolved_by_tipo_servicio,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'default_lob') / NULLIF(COUNT(*), 0), 2) as pct_resolved_by_default_lob,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'unknown') / NULLIF(COUNT(*), 0), 2) as pct_unknown,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_conflict = true) / NULLIF(COUNT(*), 0), 2) as pct_conflict,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_unmapped_tipo_servicio = true) / NULLIF(COUNT(*), 0), 2) as pct_unmapped_tipo_servicio
        FROM ops.v_trip_lob_canonical
    """)
    
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_kpis_weekly")
    op.execute("""
        CREATE VIEW ops.v_lob_mapping_quality_kpis_weekly AS
        SELECT 
            date_trunc('week', trip_date)::date as week_start,
            COUNT(*) as total_trips,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'tipo_servicio') / NULLIF(COUNT(*), 0), 2) as pct_resolved_by_tipo_servicio,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'default_lob') / NULLIF(COUNT(*), 0), 2) as pct_resolved_by_default_lob,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'unknown') / NULLIF(COUNT(*), 0), 2) as pct_unknown,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_conflict = true) / NULLIF(COUNT(*), 0), 2) as pct_conflict,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_unmapped_tipo_servicio = true) / NULLIF(COUNT(*), 0), 2) as pct_unmapped_tipo_servicio
        FROM ops.v_trip_lob_canonical
        GROUP BY date_trunc('week', trip_date)::date
        ORDER BY week_start DESC
    """)
    
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_kpis_weekly_segment")
    op.execute("""
        CREATE VIEW ops.v_lob_mapping_quality_kpis_weekly_segment AS
        SELECT 
            date_trunc('week', trip_date)::date as week_start,
            segment,
            COUNT(*) as total_trips,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'tipo_servicio') / NULLIF(COUNT(*), 0), 2) as pct_resolved_by_tipo_servicio,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'default_lob') / NULLIF(COUNT(*), 0), 2) as pct_resolved_by_default_lob,
            ROUND(100.0 * COUNT(*) FILTER (WHERE resolution_source = 'unknown') / NULLIF(COUNT(*), 0), 2) as pct_unknown,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_conflict = true) / NULLIF(COUNT(*), 0), 2) as pct_conflict,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_unmapped_tipo_servicio = true) / NULLIF(COUNT(*), 0), 2) as pct_unmapped_tipo_servicio
        FROM ops.v_trip_lob_canonical
        GROUP BY date_trunc('week', trip_date)::date, segment
        ORDER BY week_start DESC, segment
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_kpis_weekly_segment")
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_kpis_weekly")
    op.execute("DROP VIEW IF EXISTS ops.v_lob_mapping_quality_kpis")
    op.execute("DROP VIEW IF EXISTS ops.v_trip_lob_canonical")
    op.execute("DROP TABLE IF EXISTS canon.lob_tipo_servicio_map")
    op.execute("DROP SCHEMA IF EXISTS ops")
