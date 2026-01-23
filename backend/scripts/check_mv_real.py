#!/usr/bin/env python3
"""
Script para verificar la vista materializada ops.mv_real_trips_monthly
y mostrar información sobre su estructura y datos.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    print("=" * 80)
    print("  VERIFICACIÓN DE VISTA MATERIALIZADA: ops.mv_real_trips_monthly")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Verificar que existe
            print("\n1. Verificando existencia de la vista materializada...")
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM pg_matviews 
                    WHERE schemaname = 'ops' 
                    AND matviewname = 'mv_real_trips_monthly'
                ) as exists;
            """)
            exists = cursor.fetchone()['exists']
            if exists:
                print("   [OK] Vista materializada existe")
            else:
                print("   [ERROR] Vista materializada NO existe")
                return 1
            
            # 2. Información de la vista
            print("\n2. Información de la vista materializada...")
            cursor.execute("""
                SELECT 
                    schemaname,
                    matviewname,
                    hasindexes,
                    ispopulated
                FROM pg_matviews 
                WHERE schemaname = 'ops' 
                AND matviewname = 'mv_real_trips_monthly';
            """)
            mv_info = cursor.fetchone()
            if mv_info:
                print(f"   Schema: {mv_info['schemaname']}")
                print(f"   Nombre: {mv_info['matviewname']}")
                print(f"   Tiene índices: {mv_info['hasindexes']}")
                print(f"   Está poblada: {mv_info['ispopulated']}")
            
            # 3. Columnas de la vista
            print("\n3. Columnas de la vista materializada...")
            cursor.execute("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'ops'
                AND table_name = 'mv_real_trips_monthly'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            print(f"   Total de columnas: {len(columns)}")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"   - {col['column_name']}: {col['data_type']} ({nullable})")
            
            # 4. Conteo de registros
            print("\n4. Conteo de registros...")
            cursor.execute("SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly;")
            count = cursor.fetchone()['count']
            print(f"   Total de registros: {count:,}")
            
            # 5. Rango de fechas
            print("\n5. Rango de meses disponibles...")
            cursor.execute("""
                SELECT 
                    MIN(month) as min_month,
                    MAX(month) as max_month,
                    COUNT(DISTINCT month) as distinct_months
                FROM ops.mv_real_trips_monthly;
            """)
            date_range = cursor.fetchone()
            if date_range:
                print(f"   Mes mínimo: {date_range['min_month']}")
                print(f"   Mes máximo: {date_range['max_month']}")
                print(f"   Meses distintos: {date_range['distinct_months']}")
            
            # 6. Países disponibles
            print("\n6. Países disponibles...")
            cursor.execute("""
                SELECT DISTINCT country
                FROM ops.mv_real_trips_monthly
                WHERE country IS NOT NULL
                ORDER BY country;
            """)
            countries = cursor.fetchall()
            print(f"   Total de países: {len(countries)}")
            for country in countries[:10]:  # Mostrar primeros 10
                print(f"   - {country['country']}")
            if len(countries) > 10:
                print(f"   ... y {len(countries) - 10} más")
            
            # 7. Muestra de datos
            print("\n7. Muestra de datos (últimos 5 registros)...")
            cursor.execute("""
                SELECT 
                    month,
                    country,
                    city,
                    lob_base,
                    trips_real_completed,
                    active_drivers_real,
                    avg_ticket_real,
                    commission_yego_signed,
                    revenue_real_yego,
                    margen_unitario_yego
                FROM ops.mv_real_trips_monthly
                ORDER BY month DESC, country, city, lob_base
                LIMIT 5;
            """)
            samples = cursor.fetchall()
            for i, row in enumerate(samples, 1):
                print(f"\n   Registro {i}:")
                print(f"   - Mes: {row['month']}")
                print(f"   - País: {row['country']}")
                print(f"   - Ciudad: {row['city']}")
                print(f"   - LOB: {row['lob_base']}")
                print(f"   - Viajes completados: {row['trips_real_completed']:,}")
                print(f"   - Conductores activos: {row['active_drivers_real']:,}")
                print(f"   - Ticket promedio: {row['avg_ticket_real']}")
                print(f"   - Commission signed: {row['commission_yego_signed']}")
                print(f"   - Revenue real yego: {row['revenue_real_yego']}")
                print(f"   - Margen unitario yego: {row['margen_unitario_yego']}")
            
            # 8. Última actualización (si hay información)
            print("\n8. Verificando última actualización...")
            # Nota: last_refresh_time solo está disponible en PostgreSQL 13+
            # Para versiones anteriores, no hay forma directa de obtener esta información
            print("   (Información de última actualización no disponible en esta versión de PostgreSQL)")
            
            cursor.close()
            
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    print("  VERIFICACIÓN COMPLETADA")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
