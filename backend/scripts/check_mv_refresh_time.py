#!/usr/bin/env python3
"""
Script para verificar la última actualización de la vista materializada
ops.mv_real_trips_monthly usando diferentes métodos.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    print("=" * 80)
    print("  ULTIMA ACTUALIZACION DE VISTA MATERIALIZADA: ops.mv_real_trips_monthly")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Método 1: Verificar si existe columna refreshed_at en la vista
            print("\n1. Verificando columna 'refreshed_at' en la vista...")
            try:
                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'ops'
                    AND table_name = 'mv_real_trips_monthly'
                    AND column_name = 'refreshed_at';
                """)
                refreshed_at_col = cursor.fetchone()
                if refreshed_at_col:
                    print("   [OK] Columna 'refreshed_at' existe")
                    # Obtener el máximo refreshed_at
                    cursor.execute("""
                        SELECT 
                            MAX(refreshed_at) as last_refresh,
                            MIN(refreshed_at) as first_refresh,
                            COUNT(DISTINCT refreshed_at) as distinct_refreshes
                        FROM ops.mv_real_trips_monthly;
                    """)
                    refresh_info = cursor.fetchone()
                    if refresh_info:
                        print(f"   Ultima actualizacion (refreshed_at): {refresh_info['last_refresh']}")
                        print(f"   Primera actualizacion: {refresh_info['first_refresh']}")
                        print(f"   Numero de refreshes distintos: {refresh_info['distinct_refreshes']}")
                else:
                    print("   [INFO] Columna 'refreshed_at' NO existe en la vista")
            except Exception as e:
                print(f"   [ERROR] Error al verificar refreshed_at: {e}")
            
            # Método 2: Verificar last_refresh_time en pg_matviews (PostgreSQL 13+)
            print("\n2. Verificando last_refresh_time en pg_matviews (PostgreSQL 13+)...")
            try:
                cursor.execute("""
                    SELECT 
                        schemaname,
                        matviewname,
                        last_refresh_time
                    FROM pg_matviews 
                    WHERE schemaname = 'ops' 
                    AND matviewname = 'mv_real_trips_monthly';
                """)
                mv_info = cursor.fetchone()
                if mv_info and mv_info.get('last_refresh_time'):
                    print(f"   [OK] Ultima actualizacion (last_refresh_time): {mv_info['last_refresh_time']}")
                else:
                    print("   [INFO] last_refresh_time no disponible (PostgreSQL < 13 o columna no existe)")
            except Exception as e:
                error_msg = str(e)
                if 'last_refresh_time' in error_msg.lower():
                    print("   [INFO] last_refresh_time no disponible en esta version de PostgreSQL")
                else:
                    print(f"   [ERROR] Error al consultar pg_matviews: {e}")
            
            # Método 3: Verificar fecha de modificación en pg_class (última vez que se modificó el objeto)
            print("\n3. Verificando fecha de modificacion en pg_class...")
            try:
                cursor.execute("""
                    SELECT 
                        c.relname,
                        pg_size_pretty(pg_total_relation_size(c.oid)) as size,
                        c.reltuples::bigint as estimated_rows
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'ops'
                    AND c.relname = 'mv_real_trips_monthly'
                    AND c.relkind = 'm';
                """)
                class_info = cursor.fetchone()
                if class_info:
                    print(f"   Nombre: {class_info['relname']}")
                    print(f"   Tamaño estimado: {class_info['size']}")
                    print(f"   Filas estimadas: {class_info['estimated_rows']:,}")
                    print("   (Nota: No hay timestamp de modificacion directo en pg_class)")
            except Exception as e:
                print(f"   [ERROR] Error al consultar pg_class: {e}")
            
            # Método 4: Verificar el máximo month en los datos (último mes con datos)
            print("\n4. Verificando ultimo mes con datos...")
            try:
                cursor.execute("""
                    SELECT 
                        MAX(month) as last_month,
                        COUNT(*) as rows_in_last_month
                    FROM ops.mv_real_trips_monthly
                    WHERE month = (SELECT MAX(month) FROM ops.mv_real_trips_monthly);
                """)
                last_month_info = cursor.fetchone()
                if last_month_info:
                    print(f"   Ultimo mes con datos: {last_month_info['last_month']}")
                    print(f"   Registros en ultimo mes: {last_month_info['rows_in_last_month']:,}")
            except Exception as e:
                print(f"   [ERROR] Error al verificar ultimo mes: {e}")
            
            # Método 5: Verificar si hay función de refresh y cuándo fue creada/modificada
            print("\n5. Verificando funcion de refresh...")
            try:
                cursor.execute("""
                    SELECT 
                        routine_name,
                        routine_definition,
                        last_altered
                    FROM information_schema.routines
                    WHERE routine_schema = 'ops'
                    AND routine_name = 'refresh_real_trips_monthly';
                """)
                func_info = cursor.fetchone()
                if func_info:
                    print(f"   [OK] Funcion existe: {func_info['routine_name']}")
                    print(f"   Ultima modificacion de la funcion: {func_info['last_altered']}")
                else:
                    print("   [INFO] Funcion refresh_real_trips_monthly() no existe")
            except Exception as e:
                print(f"   [ERROR] Error al verificar funcion: {e}")
            
            # Método 6: Verificar logs del sistema (si es posible)
            print("\n6. Resumen de informacion disponible...")
            print("   Para obtener la ultima actualizacion exacta, se recomienda:")
            print("   1. Verificar la columna 'refreshed_at' si existe")
            print("   2. Consultar logs de aplicacion o base de datos")
            print("   3. Verificar cuando se ejecuto el ultimo REFRESH MATERIALIZED VIEW")
            print("   4. En PostgreSQL 13+, usar last_refresh_time de pg_matviews")
            
            cursor.close()
            
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    print("  VERIFICACION COMPLETADA")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
