"""Script para crear vistas 'latest' del plan."""
import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def create_latest_views():
    init_db_pool()
    
    sql_statements = [
        # Vista de versiones
        """
        DROP VIEW IF EXISTS ops.v_plan_versions CASCADE;
        CREATE VIEW ops.v_plan_versions AS
        SELECT 
            plan_version,
            MIN(created_at) as first_created_at,
            MAX(created_at) as last_created_at,
            COUNT(*) as row_count,
            MIN(month) as min_month,
            MAX(month) as max_month,
            COUNT(DISTINCT country) as countries,
            COUNT(DISTINCT city) as cities,
            COUNT(DISTINCT lob_base) as lobs
        FROM ops.plan_trips_monthly
        GROUP BY plan_version
        ORDER BY last_created_at DESC
        """,
        
        # Vista latest de trips mensual
        """
        DROP VIEW IF EXISTS ops.v_plan_trips_monthly_latest CASCADE;
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
        """,
        
        # Vista latest de KPIs
        """
        DROP VIEW IF EXISTS ops.v_plan_kpis_monthly_latest CASCADE;
        CREATE VIEW ops.v_plan_kpis_monthly_latest AS
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
            p.projected_trips AS kpi_trips,
            p.projected_drivers AS kpi_drivers,
            p.projected_revenue AS kpi_revenue,
            p.projected_trips_per_driver AS kpi_productivity_required,
            p.projected_ticket AS kpi_ticket_avg,
            CASE 
                WHEN p.projected_drivers > 0 
                THEN p.projected_trips::NUMERIC / p.projected_drivers
                ELSE NULL
            END AS kpi_trips_per_driver,
            p.created_at
        FROM ops.plan_trips_monthly p
        INNER JOIN latest_version lv ON p.plan_version = lv.plan_version
        ORDER BY p.month, p.country, p.city, p.lob_base, p.segment
        """,
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("Creando vistas 'latest'...")
            for i, sql in enumerate(sql_statements, 1):
                cursor.execute(sql)
                print(f"  [{i}/{len(sql_statements)}] Vista creada correctamente")
            conn.commit()
            print("\n✓ Vistas 'latest' creadas exitosamente")
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    create_latest_views()
