"""
Script de validación para FASE 2A
Verifica que las métricas derivadas y proxies no generen errores
"""
import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    init_db_pool()
    
    print("======================================================================")
    print("VALIDACIÓN FASE 2A - Métricas REAL/DERIVADAS/PROXY")
    print("======================================================================")
    
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verificar que la MV existe (usar pg_matviews para materialized views)
        cursor.execute("""
            SELECT COUNT(*) as exists_count
            FROM pg_matviews
            WHERE schemaname='ops' AND matviewname='mv_real_trips_monthly'
        """)
        mv_exists = cursor.fetchone()['exists_count'] > 0
        
        if not mv_exists:
            print("[ERROR] ops.mv_real_trips_monthly no existe. Ejecutar migración 008 primero.")
            return 1
        
        print("[OK] ops.mv_real_trips_monthly existe")
        
        # Verificar columnas nuevas (consultando directamente la MV)
        cursor.execute("SELECT * FROM ops.mv_real_trips_monthly LIMIT 0")
        actual_cols = [desc[0] for desc in cursor.description] if cursor.description else []
        
        expected_cols = ['commission_rate_default', 'profit_per_trip_proxy', 'profit_proxy', 'trips_per_driver']
        missing_cols = [c for c in expected_cols if c not in actual_cols]
        
        if missing_cols:
            print(f"[ERROR] Columnas faltantes: {missing_cols}")
            return 1
        
        new_cols_found = [c for c in expected_cols if c in actual_cols]
        print(f"[OK] Columnas FASE 2A presentes: {new_cols_found}")
        
        # Validación 1: profit_proxy puede ser NULL solo si revenue es NULL
        print("\n[1] Validación: profit_proxy NULL solo si revenue_real_proxy NULL")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(*) FILTER (WHERE profit_proxy IS NULL AND revenue_real_proxy IS NOT NULL) as invalid_null_profit,
                COUNT(*) FILTER (WHERE profit_proxy IS NOT NULL AND revenue_real_proxy IS NULL) as invalid_not_null_profit
            FROM ops.mv_real_trips_monthly
        """)
        val1 = cursor.fetchone()
        if val1['invalid_null_profit'] > 0 or val1['invalid_not_null_profit'] > 0:
            print(f"  [ERROR] Violación encontrada:")
            print(f"    - profit_proxy NULL con revenue NOT NULL: {val1['invalid_null_profit']}")
            print(f"    - profit_proxy NOT NULL con revenue NULL: {val1['invalid_not_null_profit']}")
            return 1
        print(f"  [OK] {val1['total_rows']} filas validadas correctamente")
        
        # Validación 2: trips_per_driver nunca genera división por cero
        print("\n[2] Validación: trips_per_driver sin división por cero")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(*) FILTER (WHERE active_drivers_real = 0 AND trips_per_driver IS NOT NULL) as division_by_zero_error
            FROM ops.mv_real_trips_monthly
        """)
        val2 = cursor.fetchone()
        if val2['division_by_zero_error'] > 0:
            print(f"  [ERROR] División por cero encontrada: {val2['division_by_zero_error']} filas")
            return 1
        print(f"  [OK] {val2['total_rows']} filas validadas (sin división por cero)")
        
        # Validación 3: profit_per_trip_proxy nunca genera división por cero
        print("\n[3] Validación: profit_per_trip_proxy sin división por cero")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(*) FILTER (WHERE trips_real_completed = 0 AND profit_per_trip_proxy IS NOT NULL) as division_by_zero_error
            FROM ops.mv_real_trips_monthly
        """)
        val3 = cursor.fetchone()
        if val3['division_by_zero_error'] > 0:
            print(f"  [ERROR] División por cero encontrada: {val3['division_by_zero_error']} filas")
            return 1
        print(f"  [OK] {val3['total_rows']} filas validadas (sin división por cero)")
        
        # Validación 4: commission_rate_default siempre es 0.03
        print("\n[4] Validación: commission_rate_default = 0.03")
        cursor.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(*) FILTER (WHERE commission_rate_default != 0.03) as invalid_rate
            FROM ops.mv_real_trips_monthly
        """)
        val4 = cursor.fetchone()
        if val4['invalid_rate'] > 0:
            print(f"  [WARN] commission_rate_default != 0.03 en {val4['invalid_rate']} filas")
        else:
            print(f"  [OK] {val4['total_rows']} filas con commission_rate_default = 0.03")
        
        # Muestra de datos
        print("\n[5] Muestra de datos (primeras 3 filas):")
        cursor.execute("""
            SELECT 
                month,
                country,
                city_norm,
                lob_base,
                segment,
                trips_real_completed,
                active_drivers_real,
                revenue_real_proxy,
                trips_per_driver,
                commission_rate_default,
                profit_proxy,
                profit_per_trip_proxy
            FROM ops.mv_real_trips_monthly
            ORDER BY month DESC, country, city_norm
            LIMIT 3
        """)
        sample = cursor.fetchall()
        for i, row in enumerate(sample, 1):
            print(f"\n  Fila {i}:")
            print(f"    Periodo: {row['month']} | {row['country']} | {row['city_norm']} | {row['lob_base']} | {row['segment']}")
            print(f"    Trips: {row['trips_real_completed']:,} | Drivers: {row['active_drivers_real']:,}")
            print(f"    Revenue: ${row['revenue_real_proxy']:,.2f}" if row['revenue_real_proxy'] else "    Revenue: NULL")
            print(f"    Trips/Driver: {row['trips_per_driver']:.2f}" if row['trips_per_driver'] else "    Trips/Driver: NULL")
            print(f"    Commission Rate: {row['commission_rate_default']}")
            print(f"    Profit: ${row['profit_proxy']:,.2f}" if row['profit_proxy'] else "    Profit: NULL")
            print(f"    Profit/Trip: ${row['profit_per_trip_proxy']:.4f}" if row['profit_per_trip_proxy'] else "    Profit/Trip: NULL")
        
        cursor.close()
    
    print("\n======================================================================")
    print("[OK] VALIDACIÓN FASE 2A COMPLETADA - Todas las validaciones pasaron")
    print("======================================================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
