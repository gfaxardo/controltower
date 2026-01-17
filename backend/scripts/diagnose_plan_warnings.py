"""
Script para diagnosticar warnings del Plan:
- city_mismatch
- invalid_metrics

USO:
    python diagnose_plan_warnings.py <plan_version>
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def diagnose_city_mismatch(plan_version: str):
    """Diagnostica city_mismatch: ciudades del plan que no existen en dim_park."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # A) city_mismatch en plan
            print("\n" + "="*80)
            print("A) CITY_MISMATCH - CIUDADES DEL PLAN SIN EQUIVALENTE EN REAL")
            print("="*80 + "\n")
            
            cursor.execute("""
                SELECT 
                    p.country,
                    p.city,
                    p.city_norm,
                    COUNT(DISTINCT (p.lob_base, p.segment)) as distinct_combos,
                    STRING_AGG(DISTINCT p.lob_base || '/' || p.segment, ', ') as ejemplos
                FROM ops.plan_trips_monthly p
                WHERE p.plan_version = %s
                AND p.city_norm IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM dim.dim_park dp
                    WHERE LOWER(TRIM(COALESCE(dp.city, ''))) = p.city_norm
                )
                GROUP BY p.country, p.city, p.city_norm
                ORDER BY p.country, p.city_norm
            """, (plan_version,))
            
            mismatches = cursor.fetchall()
            
            print(f"Total city_mismatch encontrados: {len(mismatches)}\n")
            print("| Country | City (Raw) | City (Norm) | Combos LOB/Seg | Ejemplos |")
            print("|---------|------------|-------------|----------------|----------|")
            
            for row in mismatches:
                country, city, city_norm, combos, ejemplos = row
                city_display = city or 'NULL'
                city_norm_display = city_norm or 'NULL'
                ejemplos_display = (ejemplos or '')[:50]  # Truncar si es muy largo
                print(f"| {country or 'NULL'} | {city_display} | {city_norm_display} | {combos} | {ejemplos_display} |")
            
            # B) Ciudades disponibles en dim_park
            print("\n" + "="*80)
            print("B) CIUDADES DISPONIBLES EN dim.dim_park")
            print("="*80 + "\n")
            
            cursor.execute("""
                SELECT DISTINCT
                    COALESCE(dp.country, '') as country,
                    COALESCE(dp.city, '') as city,
                    LOWER(TRIM(COALESCE(dp.city, ''))) as city_norm
                FROM dim.dim_park dp
                WHERE dp.city IS NOT NULL AND TRIM(dp.city) != ''
                ORDER BY country, city_norm
            """)
            
            available_cities = cursor.fetchall()
            
            print(f"Total ciudades disponibles en dim_park: {len(available_cities)}\n")
            print("| Country | City (Raw) | City (Norm) |")
            print("|---------|------------|-------------|")
            
            for row in available_cities[:50]:  # Mostrar primeras 50
                country, city, city_norm = row
                print(f"| {country or ''} | {city or ''} | {city_norm or ''} |")
            
            if len(available_cities) > 50:
                print(f"\n... y {len(available_cities) - 50} más")
            
            cursor.close()
            
            return mismatches, available_cities
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error durante diagnóstico: {e}")
            import traceback
            traceback.print_exc()
            raise

def diagnose_invalid_metrics(plan_version: str):
    """Diagnostica invalid_metrics: filas con métricas nulas o <= 0."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("\n" + "="*80)
            print("INVALID_METRICS - FILAS CON MÉTRICAS NULAS O <= 0")
            print("="*80 + "\n")
            
            cursor.execute("""
                SELECT 
                    country,
                    city,
                    lob_base,
                    segment,
                    month,
                    projected_trips,
                    projected_drivers,
                    projected_ticket,
                    CASE 
                        WHEN projected_trips IS NULL OR projected_trips <= 0 THEN 'trips'
                        WHEN projected_drivers IS NULL OR projected_drivers <= 0 THEN 'drivers'
                        WHEN projected_ticket IS NULL OR projected_ticket <= 0 THEN 'ticket'
                        ELSE 'unknown'
                    END as metric_invalid
                FROM ops.plan_trips_monthly
                WHERE plan_version = %s
                AND (
                    projected_trips IS NULL OR projected_trips <= 0
                    OR projected_drivers IS NULL OR projected_drivers <= 0
                    OR projected_ticket IS NULL OR projected_ticket <= 0
                )
                ORDER BY country, city, lob_base, segment, month
                LIMIT 50
            """, (plan_version,))
            
            invalid_rows = cursor.fetchall()
            
            print(f"Total invalid_metrics encontrados (mostrando primeros 50): {len(invalid_rows)}\n")
            print("| Country | City | LOB | Segment | Month | Trips | Drivers | Ticket | Invalid |")
            print("|---------|------|-----|---------|-------|-------|---------|--------|---------|")
            
            for row in invalid_rows:
                country, city, lob, seg, month, trips, drivers, ticket, invalid = row
                trips_display = trips if trips is not None else 'NULL'
                drivers_display = drivers if drivers is not None else 'NULL'
                ticket_display = f"{ticket:.2f}" if ticket is not None else 'NULL'
                print(f"| {country or 'NULL'} | {city or 'NULL'} | {lob or 'NULL'} | {seg or 'NULL'} | {month} | {trips_display} | {drivers_display} | {ticket_display} | {invalid} |")
            
            # Conteo por tipo de métrica inválida
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN projected_trips IS NULL OR projected_trips <= 0 THEN 'trips'
                        WHEN projected_drivers IS NULL OR projected_drivers <= 0 THEN 'drivers'
                        WHEN projected_ticket IS NULL OR projected_ticket <= 0 THEN 'ticket'
                        ELSE 'multiple'
                    END as metric_invalid,
                    COUNT(*) as count
                FROM ops.plan_trips_monthly
                WHERE plan_version = %s
                AND (
                    projected_trips IS NULL OR projected_trips <= 0
                    OR projected_drivers IS NULL OR projected_drivers <= 0
                    OR projected_ticket IS NULL OR projected_ticket <= 0
                )
                GROUP BY metric_invalid
                ORDER BY count DESC
            """, (plan_version,))
            
            counts = cursor.fetchall()
            
            print("\n" + "="*80)
            print("Conteo por tipo de métrica inválida:")
            print("| Métrica Inválida | Cantidad |")
            print("|------------------|----------|")
            
            for row in counts:
                metric, count = row
                print(f"| {metric} | {count} |")
            
            cursor.close()
            
            return invalid_rows
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error durante diagnóstico: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python diagnose_plan_warnings.py <plan_version>")
        print("EJEMPLO: python diagnose_plan_warnings.py ruta27_v2026_01_16_a")
        sys.exit(1)
    
    plan_version = sys.argv[1]
    
    print("\n" + "="*80)
    print(f"DIAGNÓSTICO DE WARNINGS DEL PLAN: {plan_version}")
    print("="*80)
    
    # Diagnóstico city_mismatch
    mismatches, available = diagnose_city_mismatch(plan_version)
    
    # Diagnóstico invalid_metrics
    invalid_metrics = diagnose_invalid_metrics(plan_version)
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO COMPLETADO")
    print("="*80)
    print(f"\nResumen:")
    print(f"  - city_mismatch: {len(mismatches)} ciudades únicas")
    print(f"  - invalid_metrics: {len(invalid_metrics)} filas (mostradas 50)")
