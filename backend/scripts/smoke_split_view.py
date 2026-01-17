"""
Smoke test para verificar que los endpoints de split view funcionan correctamente.
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from app.services.plan_real_split_service import get_real_monthly, get_plan_monthly, get_overlap_monthly
from psycopg2.extras import RealDictCursor

def smoke_test():
    init_db_pool()
    
    print("="*70)
    print("SMOKE TEST - SPLIT VIEW ENDPOINTS")
    print("="*70)
    
    errors = []
    
    # Test 1: Real monthly 2025
    print("\n[1] Test: get_real_monthly(year=2025)")
    try:
        real_data = get_real_monthly(year=2025)
        if len(real_data) > 0:
            print(f"  [OK] Real monthly devuelve {len(real_data)} períodos")
            print(f"  [OK] Primer período: {real_data[0]['period']} - {real_data[0]['trips_real_completed']:,} trips")
            if len(real_data) == 12:
                print(f"  [OK] 12 meses encontrados (esperado)")
            else:
                print(f"  [WARN] Se esperaban 12 meses, se encontraron {len(real_data)}")
        else:
            print(f"  [WARN] Real monthly devuelve 0 períodos")
            errors.append("Real monthly vacío")
    except Exception as e:
        print(f"  [ERROR] {e}")
        errors.append(f"Real monthly error: {e}")
    
    # Test 2: Plan monthly 2026
    print("\n[2] Test: get_plan_monthly(year=2026)")
    try:
        plan_data = get_plan_monthly(year=2026)
        if len(plan_data) > 0:
            print(f"  [OK] Plan monthly devuelve {len(plan_data)} períodos")
            print(f"  [OK] Primer período: {plan_data[0]['period']} - {plan_data[0]['projected_trips']:,} trips")
            if len(plan_data) == 12:
                print(f"  [OK] 12 meses encontrados (esperado)")
            else:
                print(f"  [WARN] Se esperaban 12 meses, se encontraron {len(plan_data)}")
        else:
            print(f"  [WARN] Plan monthly devuelve 0 períodos")
            errors.append("Plan monthly vacío")
    except Exception as e:
        print(f"  [ERROR] {e}")
        errors.append(f"Plan monthly error: {e}")
    
    # Test 3: Overlap monthly
    print("\n[3] Test: get_overlap_monthly()")
    try:
        overlap_data = get_overlap_monthly()
        if len(overlap_data) > 0:
            print(f"  [OK] Overlap monthly devuelve {len(overlap_data)} períodos comparables")
            print(f"  [OK] Primer período: {overlap_data[0]['period']}")
        else:
            print(f"  [INFO] Overlap monthly devuelve 0 períodos (sin overlap temporal - esperado si años diferentes)")
    except Exception as e:
        print(f"  [ERROR] {e}")
        errors.append(f"Overlap monthly error: {e}")
    
    # Test 4: Verificar que no hay errores con filtros
    print("\n[4] Test: Filtros (country=PE)")
    try:
        real_pe = get_real_monthly(country='PE', year=2025)
        plan_pe = get_plan_monthly(country='PE', year=2026)
        print(f"  [OK] Real PE: {len(real_pe)} períodos")
        print(f"  [OK] Plan PE: {len(plan_pe)} períodos")
    except Exception as e:
        print(f"  [ERROR] {e}")
        errors.append(f"Filtros error: {e}")
    
    # Resumen
    print("\n" + "="*70)
    if errors:
        print(f"[ERROR] {len(errors)} errores encontrados:")
        for error in errors:
            print(f"  - {error}")
        print("="*70)
        return 1
    else:
        print("[OK] SMOKE TEST PASADO - Split view funcionando correctamente")
        print("="*70)
        return 0

if __name__ == "__main__":
    sys.exit(smoke_test())
