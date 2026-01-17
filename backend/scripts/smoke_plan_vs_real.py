#!/usr/bin/env python3
"""
Smoke test para verificar que el sistema Plan vs Real está funcionando correctamente.
Verifica que las vistas latest existen y tienen datos.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def execute_query(cursor, query, description):
    """Ejecuta query y retorna resultados"""
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        return results
    except Exception as e:
        print(f"  [ERROR] en {description}: {e}")
        return None

def main():
    print("=" * 80)
    print("  SMOKE TEST - PLAN VS REAL SYSTEM")
    print("=" * 80)
    print(f"\nDB: {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME} (user: {settings.DB_USER})")
    
    init_db_pool()
    
    all_ok = True
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Q2: Latest plan count y rango
            print_section("Q2: Plan Latest (ops.v_plan_trips_monthly_latest)")
            q2 = """
                SELECT 
                    COUNT(*) as rows,
                    MIN(month) as min_month,
                    MAX(month) as max_month
                FROM ops.v_plan_trips_monthly_latest;
            """
            results_q2 = execute_query(cursor, q2, "Q2")
            if results_q2 and results_q2[0]:
                row = results_q2[0]
                print(f"  [OK] Rows: {row.get('rows', 0)}")
                print(f"  [OK] Min month: {row.get('min_month', 'N/A')}")
                print(f"  [OK] Max month: {row.get('max_month', 'N/A')}")
            else:
                print("  [ERROR] No se pudo obtener datos del plan latest")
                all_ok = False
            
            # Q4: Real agregado existe
            print_section("Q4: Real Agregado (ops.mv_real_trips_monthly)")
            q4 = "SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly;"
            results_q4 = execute_query(cursor, q4, "Q4")
            if results_q4 and results_q4[0]:
                count = results_q4[0].get('count', 0)
                print(f"  [OK] Materialized view existe con {count} registros")
            else:
                print("  [ERROR] Materialized view no existe o esta vacia")
                all_ok = False
            
            # Q5: Comparación existe
            print_section("Q5: Comparación Plan vs Real (ops.v_plan_vs_real_monthly_latest)")
            q5 = "SELECT COUNT(*) as count FROM ops.v_plan_vs_real_monthly_latest;"
            results_q5 = execute_query(cursor, q5, "Q5")
            if results_q5 and results_q5[0]:
                count = results_q5[0].get('count', 0)
                print(f"  [OK] Vista comparativa existe con {count} registros")
            else:
                print("  [ERROR] Vista comparativa no existe o esta vacia")
                all_ok = False
            
            # Sample de comparación
            print_section("Sample: Comparación Plan vs Real (últimos 20)")
            q_sample = """
                SELECT 
                    country,
                    month,
                    city_norm_real,
                    lob_base,
                    segment,
                    plan_version,
                    projected_trips,
                    trips_real_completed,
                    gap_trips,
                    status_bucket
                FROM ops.v_plan_vs_real_monthly_latest 
                ORDER BY month DESC 
                LIMIT 20;
            """
            results_sample = execute_query(cursor, q_sample, "Sample")
            if results_sample:
                print(f"  [OK] Sample de {len(results_sample)} registros:")
                matched_count = sum(1 for r in results_sample if r.get('status_bucket') == 'matched')
                plan_only_count = sum(1 for r in results_sample if r.get('status_bucket') == 'plan_only')
                real_only_count = sum(1 for r in results_sample if r.get('status_bucket') == 'real_only')
                print(f"  - Matched: {matched_count}")
                print(f"  - Plan only: {plan_only_count}")
                print(f"  - Real only: {real_only_count}")
                print("\n  Primeros 5 registros:")
                for i, row in enumerate(results_sample[:5], 1):
                    print(f"    {i}. {row.get('country')} | {row.get('month')} | {row.get('city_norm_real')} | {row.get('lob_base')} | {row.get('segment')}")
                    print(f"       Plan: {row.get('projected_trips')} | Real: {row.get('trips_real_completed')} | Gap: {row.get('gap_trips')} | Status: {row.get('status_bucket')}")
            else:
                print("  [ERROR] No se pudo obtener sample")
                all_ok = False
            
            # Verificar plan_version latest
            print_section("Plan Version Latest")
            q_version = """
                SELECT plan_version, COUNT(*) as count
                FROM ops.v_plan_trips_monthly_latest
                GROUP BY plan_version
                LIMIT 1;
            """
            results_version = execute_query(cursor, q_version, "Version")
            if results_version and results_version[0]:
                version = results_version[0].get('plan_version')
                count = results_version[0].get('count', 0)
                print(f"  [OK] Plan version latest: {version} ({count} registros)")
            else:
                print("  [WARN] No se pudo obtener plan version")
            
            cursor.close()
            
    except Exception as e:
        print(f"\n[ERROR GENERAL]: {e}")
        import traceback
        traceback.print_exc()
        all_ok = False
    
    print("\n" + "=" * 80)
    if all_ok:
        print("  [OK] SMOKE TEST PASADO - Sistema funcionando correctamente")
    else:
        print("  [ERROR] SMOKE TEST FALLIDO - Revisar errores arriba")
    print("=" * 80)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
