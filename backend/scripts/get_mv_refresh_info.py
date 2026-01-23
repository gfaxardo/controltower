#!/usr/bin/env python3
"""
Script para obtener información sobre la última actualización de la vista materializada.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    print("=" * 80)
    print("INFORMACION DE ULTIMA ACTUALIZACION: ops.mv_real_trips_monthly")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Listar todas las columnas
            print("\n1. Columnas de la vista materializada:")
            cursor.execute("""
                SELECT column_name, data_type, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'ops'
                AND table_name = 'mv_real_trips_monthly'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            if columns:
                for col in columns:
                    print(f"   {col['ordinal_position']}. {col['column_name']} ({col['data_type']})")
            else:
                print("   [ERROR] No se encontraron columnas")
            
            # 2. Verificar si tiene refreshed_at
            has_refreshed_at = any(col['column_name'] == 'refreshed_at' for col in columns)
            
            if has_refreshed_at:
                print("\n2. Informacion de refreshed_at:")
                cursor.execute("""
                    SELECT 
                        MAX(refreshed_at) as last_refresh,
                        MIN(refreshed_at) as first_refresh,
                        COUNT(DISTINCT refreshed_at) as distinct_refreshes
                    FROM ops.mv_real_trips_monthly;
                """)
                refresh_info = cursor.fetchone()
                if refresh_info:
                    print(f"   Ultima actualizacion: {refresh_info['last_refresh']}")
                    print(f"   Primera actualizacion: {refresh_info['first_refresh']}")
                    print(f"   Refreshes distintos: {refresh_info['distinct_refreshes']}")
            else:
                print("\n2. La vista NO tiene columna 'refreshed_at'")
            
            # 3. Información del catálogo del sistema
            print("\n3. Informacion del catalogo del sistema:")
            cursor.execute("""
                SELECT 
                    c.relname,
                    c.relkind,
                    pg_size_pretty(pg_total_relation_size(c.oid)) as total_size,
                    pg_size_pretty(pg_relation_size(c.oid)) as table_size,
                    c.reltuples::bigint as estimated_rows,
                    c.relpages as pages
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'ops'
                AND c.relname = 'mv_real_trips_monthly'
                AND c.relkind = 'm';
            """)
            class_info = cursor.fetchone()
            if class_info:
                print(f"   Nombre: {class_info['relname']}")
                print(f"   Tipo: Materialized View (relkind='m')")
                print(f"   Tamaño total: {class_info['total_size']}")
                print(f"   Tamaño tabla: {class_info['table_size']}")
                print(f"   Filas estimadas: {class_info['estimated_rows']:,}")
                print(f"   Paginas: {class_info['pages']:,}")
            
            # 4. Último mes con datos
            print("\n4. Ultimo mes con datos:")
            cursor.execute("""
                SELECT 
                    MAX(month) as last_month,
                    MIN(month) as first_month,
                    COUNT(DISTINCT month) as distinct_months,
                    COUNT(*) as total_rows
                FROM ops.mv_real_trips_monthly;
            """)
            month_info = cursor.fetchone()
            if month_info:
                print(f"   Ultimo mes: {month_info['last_month']}")
                print(f"   Primer mes: {month_info['first_month']}")
                print(f"   Meses distintos: {month_info['distinct_months']}")
                print(f"   Total de registros: {month_info['total_rows']:,}")
            
            # 5. Información de pg_matviews
            print("\n5. Informacion de pg_matviews:")
            cursor.execute("""
                SELECT 
                    schemaname,
                    matviewname,
                    hasindexes,
                    ispopulated,
                    definition
                FROM pg_matviews 
                WHERE schemaname = 'ops' 
                AND matviewname = 'mv_real_trips_monthly';
            """)
            mv_info = cursor.fetchone()
            if mv_info:
                print(f"   Schema: {mv_info['schemaname']}")
                print(f"   Nombre: {mv_info['matviewname']}")
                print(f"   Tiene indices: {mv_info['hasindexes']}")
                print(f"   Esta poblada: {mv_info['ispopulated']}")
                # Verificar si la definición incluye refreshed_at
                if 'refreshed_at' in mv_info['definition'].lower():
                    print("   [INFO] La definicion incluye 'refreshed_at' pero puede no estar en los datos actuales")
            
            # 6. Verificar función de refresh
            print("\n6. Funcion de refresh:")
            cursor.execute("""
                SELECT 
                    routine_name,
                    routine_type,
                    last_altered
                FROM information_schema.routines
                WHERE routine_schema = 'ops'
                AND routine_name = 'refresh_real_trips_monthly';
            """)
            func_info = cursor.fetchone()
            if func_info:
                print(f"   Funcion existe: {func_info['routine_name']}")
                print(f"   Tipo: {func_info['routine_type']}")
                print(f"   Ultima modificacion: {func_info['last_altered']}")
            else:
                print("   Funcion refresh_real_trips_monthly() no existe")
            
            cursor.close()
            
            # Resumen final
            print("\n" + "=" * 80)
            print("RESUMEN:")
            print("=" * 80)
            if has_refreshed_at:
                print("La vista tiene columna 'refreshed_at' - consulta el MAX(refreshed_at) para")
                print("obtener la ultima actualizacion exacta.")
            else:
                print("La vista NO tiene columna 'refreshed_at'.")
                print("Para conocer la ultima actualizacion, puedes:")
                print("1. Verificar logs de aplicacion/base de datos")
                print("2. Ejecutar REFRESH MATERIALIZED VIEW y registrar la fecha")
                print("3. Verificar el ultimo mes con datos (indicador indirecto)")
                if month_info:
                    print(f"   Ultimo mes con datos: {month_info['last_month']}")
            
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
