"""
Diagnóstico rápido: verificar rangos de meses en PLAN y REAL.
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def diagnose():
    init_db_pool()
    
    print("="*70)
    print("DIAGNOSTICO: RANGOS DE MESES PLAN vs REAL")
    print("="*70)
    
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # PLAN latest meses
        print("\n[1] PLAN (ops.v_plan_trips_monthly_latest):")
        cursor.execute("""
            SELECT 
                MIN(month) as min_month,
                MAX(month) as max_month,
                COUNT(*) as total_rows,
                COUNT(DISTINCT month) as distinct_months
            FROM ops.v_plan_trips_monthly_latest;
        """)
        plan_info = cursor.fetchone()
        if plan_info and plan_info['min_month']:
            print(f"  Min month: {plan_info['min_month']}")
            print(f"  Max month: {plan_info['max_month']}")
            print(f"  Total rows: {plan_info['total_rows']:,}")
            print(f"  Distinct months: {plan_info['distinct_months']}")
        else:
            print("  [WARN] No hay datos en PLAN latest")
        
        # REAL mv meses
        print("\n[2] REAL (ops.mv_real_trips_monthly):")
        cursor.execute("""
            SELECT 
                MIN(month) as min_month,
                MAX(month) as max_month,
                COUNT(*) as total_rows,
                COUNT(DISTINCT month) as distinct_months
            FROM ops.mv_real_trips_monthly;
        """)
        real_info = cursor.fetchone()
        if real_info and real_info['min_month']:
            print(f"  Min month: {real_info['min_month']}")
            print(f"  Max month: {real_info['max_month']}")
            print(f"  Total rows: {real_info['total_rows']:,}")
            print(f"  Distinct months: {real_info['distinct_months']}")
        else:
            print("  [WARN] No hay datos en REAL mv")
        
        # REAL 2025 por mes
        print("\n[3] REAL 2025 por mes (conteos):")
        cursor.execute("""
            SELECT 
                month,
                SUM(trips_real_completed) as trips,
                COUNT(*) as rows
            FROM ops.mv_real_trips_monthly
            WHERE EXTRACT(YEAR FROM month) = 2025
            GROUP BY month
            ORDER BY month;
        """)
        real_2025 = cursor.fetchall()
        if real_2025:
            print(f"  Meses encontrados: {len(real_2025)}")
            for row in real_2025:
                print(f"    {row['month']}: {row['trips']:,} trips ({row['rows']} rows)")
            
            # Verificar enero 2025
            enero_2025 = [r for r in real_2025 if r['month'].month == 1 and r['month'].year == 2025]
            if enero_2025:
                print(f"\n  [OK] Enero 2025 existe: {enero_2025[0]['trips']:,} trips")
            else:
                print(f"\n  [WARN] Enero 2025 NO encontrado en REAL")
        else:
            print("  [WARN] No hay datos REAL para 2025")
        
        # PLAN 2026 por mes
        print("\n[4] PLAN 2026 por mes (conteos):")
        cursor.execute("""
            SELECT 
                month,
                SUM(projected_trips) as trips,
                COUNT(*) as rows
            FROM ops.v_plan_trips_monthly_latest
            WHERE EXTRACT(YEAR FROM month) = 2026
            GROUP BY month
            ORDER BY month;
        """)
        plan_2026 = cursor.fetchall()
        if plan_2026:
            print(f"  Meses encontrados: {len(plan_2026)}")
            for row in plan_2026:
                print(f"    {row['month']}: {row['trips']:,} trips ({row['rows']} rows)")
        else:
            print("  [WARN] No hay datos PLAN para 2026")
        
        # Overlap temporal
        print("\n[5] OVERLAP TEMPORAL:")
        if real_info and plan_info and real_info['min_month'] and plan_info['min_month']:
            real_min_year = real_info['min_month'].year
            real_max_year = real_info['max_month'].year
            plan_min_year = plan_info['min_month'].year
            plan_max_year = plan_info['max_month'].year
            
            overlap_years = set(range(real_min_year, real_max_year + 1)) & set(range(plan_min_year, plan_max_year + 1))
            if overlap_years:
                print(f"  Años con overlap: {sorted(overlap_years)}")
            else:
                print(f"  [INFO] No hay overlap temporal: Real {real_min_year}-{real_max_year} vs Plan {plan_min_year}-{plan_max_year}")
        
        cursor.close()
    
    print("\n" + "="*70)
    print("DIAGNOSTICO COMPLETADO")
    print("="*70)

if __name__ == "__main__":
    diagnose()
