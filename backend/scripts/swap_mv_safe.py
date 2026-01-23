#!/usr/bin/env python3
"""
Script para hacer swap seguro de MV v2 a MV principal (sin CASCADE).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def swap_mv_safe():
    """Hace swap seguro de MV v2 a MV principal"""
    print("=" * 80)
    print("SWAP SEGURO: MV v2 -> MV principal")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            print("\n1. Verificando que MV v2 existe y está poblada...")
            cursor.execute("""
                SELECT 
                    matviewname,
                    ispopulated
                FROM pg_matviews 
                WHERE schemaname = 'ops' 
                AND matviewname = 'mv_real_trips_monthly_v2';
            """)
            mv_v2_info = cursor.fetchone()
            
            if not mv_v2_info:
                print("   [ERROR] MV v2 no existe")
                return 1
            
            if not mv_v2_info[1]:  # ispopulated
                print("   [ERROR] MV v2 no está poblada")
                return 1
            
            print(f"   [OK] MV v2 existe y está poblada")
            
            # Verificar conteo
            cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly_v2")
            count_v2 = cursor.fetchone()[0]
            print(f"   Registros en MV v2: {count_v2:,}")
            
            print("\n2. Verificando que MV actual existe...")
            cursor.execute("""
                SELECT 
                    matviewname,
                    ispopulated
                FROM pg_matviews 
                WHERE schemaname = 'ops' 
                AND matviewname = 'mv_real_trips_monthly';
            """)
            mv_current_info = cursor.fetchone()
            
            if not mv_current_info:
                print("   [WARNING] MV actual no existe (primera vez)")
            else:
                cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly")
                count_current = cursor.fetchone()[0]
                print(f"   [OK] MV actual existe con {count_current:,} registros")
            
            print("\n3. Realizando swap seguro (sin CASCADE)...")
            print("   - Renombrando MV actual a _old")
            print("   - Renombrando MV v2 a MV principal")
            
            # Swap seguro en transacción
            cursor.execute("BEGIN")
            try:
                # Renombrar MV actual a _old (si existe)
                if mv_current_info:
                    cursor.execute("""
                        ALTER MATERIALIZED VIEW ops.mv_real_trips_monthly 
                        RENAME TO mv_real_trips_monthly_old;
                    """)
                    print("   [OK] MV actual renombrada a mv_real_trips_monthly_old")
                
                # Renombrar MV v2 a MV principal
                cursor.execute("""
                    ALTER MATERIALIZED VIEW ops.mv_real_trips_monthly_v2 
                    RENAME TO mv_real_trips_monthly;
                """)
                print("   [OK] MV v2 renombrada a mv_real_trips_monthly")
                
                # Actualizar función de refresh para que apunte a la nueva MV
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION ops.refresh_real_trips_monthly()
                    RETURNS void AS $$
                    BEGIN
                        REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;
                    END;
                    $$ LANGUAGE plpgsql;
                """)
                print("   [OK] Funcion de refresh actualizada")
                
                cursor.execute("COMMIT")
                print("\n   [OK] Swap completado exitosamente")
                
            except Exception as e:
                cursor.execute("ROLLBACK")
                print(f"\n   [ERROR] Error en swap, rollback ejecutado: {e}")
                raise
            
            # Verificar resultado
            print("\n4. Verificando resultado del swap...")
            cursor.execute("""
                SELECT 
                    matviewname,
                    ispopulated
                FROM pg_matviews 
                WHERE schemaname = 'ops' 
                AND matviewname IN ('mv_real_trips_monthly', 'mv_real_trips_monthly_old', 'mv_real_trips_monthly_v2')
                ORDER BY matviewname;
            """)
            results = cursor.fetchall()
            
            for row in results:
                print(f"   - {row[0]}: {'poblada' if row[1] else 'no poblada'}")
            
            cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly")
            count_final = cursor.fetchone()[0]
            print(f"\n   Registros en MV principal: {count_final:,}")
            
            cursor.close()
            
            print("\n" + "=" * 80)
            print("SWAP COMPLETADO EXITOSAMENTE")
            print("=" * 80)
            print("\nNOTA: mv_real_trips_monthly_old se mantendrá 7 días antes de eliminarse.")
            return 0
            
    except Exception as e:
        logger.error(f"Error en swap: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(swap_mv_safe())
