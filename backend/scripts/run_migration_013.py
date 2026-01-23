#!/usr/bin/env python3
"""
Script para ejecutar la migración 013 que crea MV v2 sin proxies.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Ejecuta la migración 013"""
    print("=" * 80)
    print("EJECUTANDO MIGRACION 013: Crear MV v2 sin proxies")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Aumentar timeout para creación de MV
            cursor.execute("SET statement_timeout = '7200000ms'")  # 2 horas
            conn.commit()
            print("   Timeout configurado a 2 horas")
            
            # Leer el archivo de migración
            migration_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'alembic', 'versions', '013_create_mv_real_trips_monthly_v2_no_proxy.py'
            )
            
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extraer la función upgrade
            import re
            upgrade_match = re.search(r'def upgrade\(\) -> None:.*?"""(.*?)"""', content, re.DOTALL)
            if not upgrade_match:
                print("[ERROR] No se pudo encontrar la función upgrade en la migración")
                return 1
            
            # Ejecutar las sentencias SQL de la migración
            print("\n1. Creando MV v2 sin proxies...")
            
            # Crear MV v2
            cursor.execute("""
                CREATE MATERIALIZED VIEW IF NOT EXISTS ops.mv_real_trips_monthly_v2 AS
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
                        
                        SUM(NULLIF(t.comision_empresa_asociada, 0)) as revenue_real_yego,
                        
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
                    
                    COALESCE(r.revenue_real_yego, 0) as revenue_real_yego,
                    
                    r.gmv_passenger_paid,
                    r.gmv_total,
                    
                    CASE 
                        WHEN r.active_drivers_real > 0 
                        THEN r.trips_real_completed::NUMERIC / r.active_drivers_real
                        ELSE NULL
                    END as trips_per_driver,
                    
                    CASE
                        WHEN r.gmv_passenger_paid > 0 AND r.revenue_real_yego IS NOT NULL
                        THEN ROUND(
                            r.revenue_real_yego / NULLIF(r.gmv_passenger_paid, 0),
                            4
                        )
                        ELSE NULL
                    END as take_rate_yego,
                    
                    NOW() as refreshed_at,
                    
                    (r.month = DATE_TRUNC('month', NOW())::DATE) as is_partial_real
                    
                FROM real_aggregated r
                LEFT JOIN dim_park_unique dp ON r.park_id = dp.park_id;
            """)
            conn.commit()
            print("   [OK] MV v2 creada")
            
            # Crear índices
            print("\n2. Creando indices...")
            indices = [
                ("idx_mv_real_trips_monthly_v2_month", "month"),
                ("idx_mv_real_trips_monthly_v2_country_city_lob_seg_month", "country, city_norm, lob_base, segment, month"),
                ("idx_mv_real_trips_monthly_v2_country", "country"),
                ("idx_mv_real_trips_monthly_v2_city_norm", "city_norm")
            ]
            
            for idx_name, cols in indices:
                try:
                    cursor.execute(f"""
                        CREATE INDEX IF NOT EXISTS {idx_name}
                        ON ops.mv_real_trips_monthly_v2({cols});
                    """)
                    print(f"   [OK] Indice {idx_name} creado")
                except Exception as e:
                    print(f"   [WARNING] Error al crear indice {idx_name}: {e}")
            
            conn.commit()
            
            # Crear función de refresh
            print("\n3. Creando funcion de refresh...")
            cursor.execute("""
                CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly_v2()
                RETURNS void AS $$
                BEGIN
                    REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly_v2;
                END;
                $$ LANGUAGE plpgsql;
            """)
            conn.commit()
            print("   [OK] Funcion de refresh creada")
            
            # Poblar la vista
            print("\n4. Poblando MV v2...")
            cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly_v2")
            conn.commit()
            print("   [OK] MV v2 poblada")
            
            # Verificar conteo
            cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly_v2")
            count = cursor.fetchone()[0]
            print(f"   Total de registros: {count:,}")
            
            cursor.close()
            
            print("\n" + "=" * 80)
            print("MIGRACION 013 COMPLETADA EXITOSAMENTE")
            print("=" * 80)
            return 0
            
    except Exception as e:
        logger.error(f"Error en migracion: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_migration())
