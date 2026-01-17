#!/usr/bin/env python3
"""
Script de verificación de estructura de BD para YEGO CONTROL TOWER.
Verifica que las vistas latest existan y tengan datos.
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
    print("  VERIFICACIÓN DE ESTRUCTURA DE BD - YEGO CONTROL TOWER")
    print("=" * 80)
    print(f"\nDB_HOST: {settings.DB_HOST}")
    print(f"DB_PORT: {settings.DB_PORT}")
    print(f"DB_NAME: {settings.DB_NAME}")
    print(f"DB_USER: {settings.DB_USER}")
    print(f"DATABASE_URL configurado: {'Sí' if settings.DATABASE_URL else 'No'}")
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Q1: Versiones del plan
            print_section("Q1: Versiones del Plan (ops.v_plan_versions)")
            q1 = """
                SELECT * FROM ops.v_plan_versions 
                ORDER BY last_created_at DESC 
                LIMIT 10;
            """
            results_q1 = execute_query(cursor, q1, "Q1")
            if results_q1:
                print(f"  [OK] Encontradas {len(results_q1)} versiones:")
                for i, row in enumerate(results_q1, 1):
                    print(f"    {i}. {row.get('plan_version', 'N/A')} - Creado: {row.get('last_created_at', 'N/A')} - Rows: {row.get('row_count', 'N/A')}")
            else:
                print("  [WARN] No se encontraron versiones o la vista no existe")
            
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
            
            # Q3: Confirmar versión específica
            print_section("Q3: Verificar versión ruta27_v2026_01_16_a")
            q3 = """
                SELECT plan_version, COUNT(*) as count
                FROM ops.plan_trips_monthly
                WHERE plan_version = 'ruta27_v2026_01_16_a'
                GROUP BY plan_version;
            """
            results_q3 = execute_query(cursor, q3, "Q3")
            if results_q3 and len(results_q3) > 0:
                row = results_q3[0]
                print(f"  [OK] Version encontrada: {row.get('plan_version')} con {row.get('count', 0)} registros")
            else:
                print("  [WARN] Version 'ruta27_v2026_01_16_a' NO encontrada")
                # Verificar qué versiones existen
                q3_alt = "SELECT DISTINCT plan_version FROM ops.plan_trips_monthly ORDER BY plan_version DESC LIMIT 5;"
                results_q3_alt = execute_query(cursor, q3_alt, "Q3-Alt")
                if results_q3_alt:
                    print("  Versiones disponibles:")
                    for row in results_q3_alt:
                        print(f"    - {row.get('plan_version')}")
            
            # Q4: Real agregado existe
            print_section("Q4: Real Agregado (ops.mv_real_trips_monthly)")
            q4 = "SELECT COUNT(*) as count FROM ops.mv_real_trips_monthly;"
            results_q4 = execute_query(cursor, q4, "Q4")
            if results_q4 and results_q4[0]:
                count = results_q4[0].get('count', 0)
                print(f"  [OK] Materialized view existe con {count} registros")
            else:
                print("  [ERROR] Materialized view no existe o esta vacia")
            
            # Q5: Comparación existe
            print_section("Q5: Comparación Plan vs Real (ops.v_plan_vs_real_monthly_latest)")
            q5 = "SELECT COUNT(*) as count FROM ops.v_plan_vs_real_monthly_latest;"
            results_q5 = execute_query(cursor, q5, "Q5")
            if results_q5 and results_q5[0]:
                count = results_q5[0].get('count', 0)
                print(f"  [OK] Vista comparativa existe con {count} registros")
            else:
                print("  [ERROR] Vista comparativa no existe o esta vacia")
            
            # Sample de comparación
            print_section("Sample: Comparación Plan vs Real (últimos 5)")
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
                LIMIT 5;
            """
            results_sample = execute_query(cursor, q_sample, "Sample")
            if results_sample:
                print(f"  [OK] Sample de {len(results_sample)} registros:")
                for i, row in enumerate(results_sample, 1):
                    print(f"    {i}. {row.get('country')} | {row.get('month')} | {row.get('city_norm_real')} | {row.get('lob_base')} | {row.get('segment')}")
                    print(f"       Plan: {row.get('projected_trips')} | Real: {row.get('trips_real_completed')} | Gap: {row.get('gap_trips')} | Status: {row.get('status_bucket')}")
            
            cursor.close()
            
    except Exception as e:
        print(f"\n[ERROR GENERAL]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print("\n" + "=" * 80)
    print("  VERIFICACIÓN COMPLETADA")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(main())
