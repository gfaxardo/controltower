"""Script para ejecutar la migración 005 directamente."""
import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def run_migration():
    init_db_pool()
    
    sql_statements = [
        # Crear materialized view
        """
        DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly CASCADE;
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
        """,
        
        # Crear índices
        "CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month ON ops.mv_real_trips_monthly(month)",
        "CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_city_norm ON ops.mv_real_trips_monthly(city_norm)",
        "CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_lob_segment ON ops.mv_real_trips_monthly(lob_base, segment)",
        "CREATE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_month_city_lob_seg ON ops.mv_real_trips_monthly(month, city_norm, lob_base, segment)",
        
        # Crear función de refresh
        """
        CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly;
        EXCEPTION
            WHEN OTHERS THEN
                -- Si CONCURRENTLY falla (falta índice único), usar refresh normal
                REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;
        END;
        $$ LANGUAGE plpgsql;
        """,
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("Ejecutando migración 005...")
            print("Creando agregado mensual de REAL (esto puede tardar)...")
            for i, sql in enumerate(sql_statements, 1):
                cursor.execute(sql)
                print(f"  [{i}/{len(sql_statements)}] Ejecutado correctamente")
            conn.commit()
            print("\n✓ Migración 005 completada exitosamente")
            print("\nMaterialized View creada:")
            print("  - ops.mv_real_trips_monthly")
            print("\nFunción de refresh:")
            print("  - ops.refresh_real_trips_monthly()")
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    run_migration()
