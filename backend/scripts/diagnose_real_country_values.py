"""
Diagnóstico: Valores de country en ops.mv_real_trips_monthly
"""

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

print("=" * 70)
print("DIAGNOSTICO: Valores de country en Real")
print("=" * 70)

with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Ver valores distintos de country en Real
    print("\n1. VALORES DISTINTOS DE COUNTRY EN ops.mv_real_trips_monthly:")
    cursor.execute("""
        SELECT DISTINCT country, COUNT(*) as count
        FROM ops.mv_real_trips_monthly
        WHERE EXTRACT(YEAR FROM month) = 2025
        GROUP BY country
        ORDER BY count DESC;
    """)
    countries = cursor.fetchall()
    if countries:
        for c in countries:
            print(f"  - '{c['country']}': {c['count']} registros")
    else:
        print("  [ERROR] No hay valores de country")
    
    # Verificar si hay datos cuando country = 'PE'
    print("\n2. VERIFICAR FILTRO country = 'PE':")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM ops.mv_real_trips_monthly
        WHERE EXTRACT(YEAR FROM month) = 2025
        AND country = 'PE';
    """)
    count_pe = cursor.fetchone()['count']
    print(f"  Registros con country = 'PE': {count_pe}")
    
    # Verificar si hay datos cuando country LIKE '%peru%'
    print("\n3. VERIFICAR FILTRO country LIKE '%peru%':")
    cursor.execute("""
        SELECT DISTINCT country, COUNT(*) as count
        FROM ops.mv_real_trips_monthly
        WHERE EXTRACT(YEAR FROM month) = 2025
        AND LOWER(country) LIKE '%peru%'
        GROUP BY country;
    """)
    peru_variants = cursor.fetchall()
    if peru_variants:
        for p in peru_variants:
            print(f"  - '{p['country']}': {p['count']} registros")
    
    # Verificar total sin filtro de país
    print("\n4. TOTAL SIN FILTRO DE PAIS (2025):")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM ops.mv_real_trips_monthly
        WHERE EXTRACT(YEAR FROM month) = 2025;
    """)
    total = cursor.fetchone()['count']
    print(f"  Total registros: {total}")
    
    cursor.close()

print("\n" + "=" * 70)
print("DIAGNOSTICO COMPLETADO")
print("=" * 70)
