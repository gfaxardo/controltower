"""create_territory_mapping_system

Revision ID: 002_create_territory_mapping_system
Revises: 001_create_ops_lob_system
Create Date: 2025-01-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_create_territory_mapping_system'
down_revision: Union[str, None] = '001_create_ops_lob_system'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")
    
    # Staging table para cargas
    op.execute("DROP TABLE IF EXISTS ops.stg_park_territory")
    op.execute("""
        CREATE TABLE ops.stg_park_territory (
            park_id text NOT NULL,
            country text,
            city text,
            default_line_of_business text,
            loaded_at timestamptz NOT NULL DEFAULT now(),
            loaded_by text
        )
    """)
    
    # Función/procedimiento para merge desde staging
    op.execute("DROP FUNCTION IF EXISTS ops.merge_park_territory_from_staging()")
    op.execute("""
        CREATE OR REPLACE FUNCTION ops.merge_park_territory_from_staging()
        RETURNS TABLE(inserted_count bigint, updated_count bigint, rejected_count bigint) AS $$
        DECLARE
            v_inserted bigint := 0;
            v_updated bigint := 0;
            v_rejected bigint := 0;
            v_park_id text;
            v_country text;
            v_city text;
        BEGIN
            -- Rechazar registros con park_id nulo o vacío
            SELECT COUNT(*) INTO v_rejected
            FROM ops.stg_park_territory
            WHERE park_id IS NULL OR trim(park_id) = '';
            
            -- Insertar nuevos parks (solo park_id que no existe en dim_park)
            INSERT INTO dim.dim_park (park_id, park_name, country, city, partner, default_line_of_business, active)
            SELECT 
                stg.park_id,
                COALESCE(stg.park_id, 'Yego') as park_name,
                COALESCE(stg.country, '') as country,
                COALESCE(stg.city, '') as city,
                'Yego' as partner,
                COALESCE(NULLIF(trim(stg.default_line_of_business), ''), 'Auto Taxi') as default_line_of_business,
                true as active
            FROM ops.stg_park_territory stg
            WHERE stg.park_id IS NOT NULL AND trim(stg.park_id) != ''
              AND stg.country IS NOT NULL AND trim(stg.country) != ''
              AND stg.city IS NOT NULL AND trim(stg.city) != ''
              AND NOT EXISTS (
                  SELECT 1 FROM dim.dim_park dp WHERE dp.park_id = stg.park_id
              )
            ON CONFLICT (park_id) DO NOTHING;
            
            GET DIAGNOSTICS v_inserted = ROW_COUNT;
            
            -- Actualizar parks existentes (solo si country, city o default_line_of_business cambian)
            UPDATE dim.dim_park dp
            SET 
                country = COALESCE(stg.country, dp.country),
                city = COALESCE(stg.city, dp.city),
                default_line_of_business = COALESCE(
                    NULLIF(trim(stg.default_line_of_business), ''),
                    dp.default_line_of_business
                )
            FROM ops.stg_park_territory stg
            WHERE dp.park_id = stg.park_id
              AND stg.park_id IS NOT NULL AND trim(stg.park_id) != ''
              AND stg.country IS NOT NULL AND trim(stg.country) != ''
              AND stg.city IS NOT NULL AND trim(stg.city) != ''
              AND (
                  dp.country IS DISTINCT FROM stg.country 
                  OR dp.city IS DISTINCT FROM stg.city
                  OR dp.default_line_of_business IS DISTINCT FROM NULLIF(trim(stg.default_line_of_business), '')
              );
            
            GET DIAGNOSTICS v_updated = ROW_COUNT;
            
            -- Retornar conteos
            RETURN QUERY SELECT v_inserted, v_updated, v_rejected;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Vista principal: trip territory canonical
    op.execute("DROP VIEW IF EXISTS ops.v_trip_territory_canonical")
    op.execute("""
        CREATE VIEW ops.v_trip_territory_canonical AS
        SELECT 
            t.id as trip_id,
            t.fecha_inicio_viaje as trip_date,
            t.park_id,
            COALESCE(d.country, '') as country,
            COALESCE(d.city, '') as city,
            CASE 
                WHEN d.park_id IS NULL THEN true
                WHEN d.country IS NULL OR trim(d.country) = '' THEN true
                WHEN d.city IS NULL OR trim(d.city) = '' THEN true
                ELSE false
            END as is_territory_unknown
        FROM public.trips_all t
        LEFT JOIN dim.dim_park d ON t.park_id = d.park_id
    """)
    
    # Vista KPIs totales
    op.execute("DROP VIEW IF EXISTS ops.v_territory_mapping_quality_kpis")
    op.execute("""
        CREATE VIEW ops.v_territory_mapping_quality_kpis AS
        SELECT 
            COUNT(*) as total_trips,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_territory_unknown = false) / NULLIF(COUNT(*), 0), 2) as pct_territory_resolved,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_territory_unknown = true) / NULLIF(COUNT(*), 0), 2) as pct_territory_unknown,
            COUNT(DISTINCT park_id) FILTER (WHERE park_id IS NOT NULL) as parks_in_trips,
            COUNT(DISTINCT park_id) FILTER (
                WHERE park_id IS NOT NULL 
                AND NOT EXISTS (SELECT 1 FROM dim.dim_park dp WHERE dp.park_id = v_trip_territory_canonical.park_id)
            ) as parks_unmapped,
            COUNT(DISTINCT park_id) FILTER (
                WHERE park_id IS NOT NULL
                AND EXISTS (SELECT 1 FROM dim.dim_park dp WHERE dp.park_id = v_trip_territory_canonical.park_id)
                AND (COALESCE((SELECT country FROM dim.dim_park dp WHERE dp.park_id = v_trip_territory_canonical.park_id), '') = ''
                     OR COALESCE((SELECT city FROM dim.dim_park dp WHERE dp.park_id = v_trip_territory_canonical.park_id), '') = '')
            ) as parks_with_null_country_city
        FROM ops.v_trip_territory_canonical
    """)
    
    # Vista KPIs semanales
    op.execute("DROP VIEW IF EXISTS ops.v_territory_mapping_quality_kpis_weekly")
    op.execute("""
        CREATE VIEW ops.v_territory_mapping_quality_kpis_weekly AS
        SELECT 
            date_trunc('week', trip_date)::date as week_start,
            COUNT(*) as total_trips,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_territory_unknown = false) / NULLIF(COUNT(*), 0), 2) as pct_territory_resolved,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_territory_unknown = true) / NULLIF(COUNT(*), 0), 2) as pct_territory_unknown,
            COUNT(DISTINCT park_id) FILTER (WHERE park_id IS NOT NULL) as parks_in_trips,
            COUNT(DISTINCT park_id) FILTER (
                WHERE park_id IS NOT NULL 
                AND NOT EXISTS (SELECT 1 FROM dim.dim_park dp WHERE dp.park_id = v_trip_territory_canonical.park_id)
            ) as parks_unmapped
        FROM ops.v_trip_territory_canonical
        WHERE trip_date IS NOT NULL
        GROUP BY date_trunc('week', trip_date)::date
        ORDER BY week_start DESC
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ops.v_territory_mapping_quality_kpis_weekly")
    op.execute("DROP VIEW IF EXISTS ops.v_territory_mapping_quality_kpis")
    op.execute("DROP VIEW IF EXISTS ops.v_trip_territory_canonical")
    op.execute("DROP FUNCTION IF EXISTS ops.merge_park_territory_from_staging()")
    op.execute("DROP TABLE IF EXISTS ops.stg_park_territory")
