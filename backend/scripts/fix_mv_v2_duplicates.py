#!/usr/bin/env python3
"""
Script para corregir duplicados en MV v2 agregando una capa final de agregación.
NOTA: Este script crea la MV v2 (previa al swap).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_mv_v2():
    """Recrea MV v2 con agregación final para eliminar duplicados"""
    print("=" * 80)
    print("CORRIGIENDO DUPLICADOS EN MV v2")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Aumentar timeout
            cursor.execute("SET statement_timeout = '7200000ms'")
            conn.commit()
            
            print("\n1. Eliminando MV v2 actual...")
            cursor.execute("DROP MATERIALIZED VIEW IF EXISTS ops.mv_real_trips_monthly_v2")
            conn.commit()
            print("   [OK] MV v2 eliminada")
            
            print("\n2. Creando MV v2 con agregación final para eliminar duplicados...")
            cursor.execute("""
                CREATE MATERIALIZED VIEW ops.mv_real_trips_monthly_v2 AS
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
                ),
                joined_data AS (
                    SELECT 
                        r.month,
                        COALESCE(dp.country, '') as country,
                        COALESCE(dp.city, '') as city,
                        LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm,
                        COALESCE(dp.default_line_of_business, r.lob_raw) as lob_base,
                        r.segment,
                        
                        r.trips_real_completed,
                        r.active_drivers_real,
                        r.avg_ticket_real,
                        r.revenue_real_yego,
                        r.gmv_passenger_paid,
                        r.gmv_total
                    FROM real_aggregated r
                    LEFT JOIN dim_park_unique dp ON r.park_id = dp.park_id
                )
                -- Agregación final para eliminar duplicados por (month, country, city_norm, lob_base, segment)
                SELECT 
                    month,
                    country,
                    MAX(city) as city,  -- Tomar cualquier city (deben ser iguales por city_norm)
                    city_norm,
                    lob_base,
                    segment,
                    
                    SUM(trips_real_completed) as trips_real_completed,
                    SUM(active_drivers_real) as active_drivers_real,
                    AVG(avg_ticket_real) FILTER (WHERE avg_ticket_real IS NOT NULL) as avg_ticket_real,
                    
                    SUM(COALESCE(revenue_real_yego, 0)) as revenue_real_yego,
                    
                    SUM(gmv_passenger_paid) as gmv_passenger_paid,
                    SUM(gmv_total) as gmv_total,
                    
                    CASE 
                        WHEN SUM(active_drivers_real) > 0 
                        THEN SUM(trips_real_completed)::NUMERIC / SUM(active_drivers_real)
                        ELSE NULL
                    END as trips_per_driver,
                    
                    CASE
                        WHEN SUM(gmv_passenger_paid) > 0 AND SUM(COALESCE(revenue_real_yego, 0)) IS NOT NULL
                        THEN ROUND(
                            SUM(COALESCE(revenue_real_yego, 0)) / NULLIF(SUM(gmv_passenger_paid), 0),
                            4
                        )
                        ELSE NULL
                    END as take_rate_yego,
                    
                    NOW() as refreshed_at,
                    
                    (month = DATE_TRUNC('month', NOW())::DATE) as is_partial_real
                    
                FROM joined_data
                GROUP BY month, country, city_norm, lob_base, segment;
            """)
            conn.commit()
            print("   [OK] MV v2 recreada con agregación final")
            
            # Recrear índices
            print("\n3. Recreando indices...")
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
                    print(f"   [OK] Indice {idx_name} recreado")
                except Exception as e:
                    print(f"   [WARNING] Error al recrear indice {idx_name}: {e}")
            
            conn.commit()
            
            # Poblar la vista
            print("\n4. Poblando MV v2...")
            cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly_v2")
            conn.commit()
            print("   [OK] MV v2 poblada")
            
            # Verificar unicidad
            print("\n5. Verificando unicidad...")
            cursor.execute("""
                SELECT 
                    month, country, city_norm, lob_base, segment,
                    COUNT(*) as duplicate_count
                FROM ops.mv_real_trips_monthly_v2
                GROUP BY month, country, city_norm, lob_base, segment
                HAVING COUNT(*) > 1
                LIMIT 5;
            """)
            duplicates = cursor.fetchall()
            
            if duplicates:
                print(f"   [ERROR] Aun hay {len(duplicates)} grupos con duplicados")
                for dup in duplicates:
                    print(f"     - {dup[0]} | {dup[1]} | {dup[2]} | {dup[3]} | {dup[4]} ({dup[5]} veces)")
                return 1
            else:
                print("   [OK] No hay duplicados. Unicidad garantizada.")
            
            # Verificar conteo
            cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly_v2")
            count = cursor.fetchone()[0]
            print(f"\n   Total de registros: {count:,}")
            
            cursor.close()
            
            print("\n" + "=" * 80)
            print("CORRECCION DE DUPLICADOS COMPLETADA")
            print("=" * 80)
            return 0
            
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(fix_mv_v2())
