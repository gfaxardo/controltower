"""
Diagnóstico: Plan reingestado con 0 registros
"""

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

print("=" * 70)
print("DIAGNOSTICO: Plan con 0 registros")
print("=" * 70)

with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # 1. Verificar versiones del plan
    print("\n1. VERSIONES DEL PLAN:")
    cursor.execute("""
        SELECT plan_version, COUNT(*) as count, MAX(created_at) as last_created
        FROM ops.plan_trips_monthly
        GROUP BY plan_version
        ORDER BY last_created DESC
        LIMIT 5;
    """)
    versions = cursor.fetchall()
    if versions:
        for v in versions:
            print(f"  - {v['plan_version']}: {v['count']} registros (creado: {v['last_created']})")
    else:
        print("  [ERROR] No hay versiones del plan en la tabla")
    
    # 2. Verificar última versión
    print("\n2. ULTIMA VERSION:")
    cursor.execute("""
        SELECT plan_version, MAX(created_at) as last_created
        FROM ops.plan_trips_monthly
        GROUP BY plan_version
        ORDER BY last_created DESC
        LIMIT 1;
    """)
    last_version = cursor.fetchone()
    if last_version:
        print(f"  Version: {last_version['plan_version']}")
        print(f"  Creada: {last_version['last_created']}")
        
        # Contar registros de esa versión
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM ops.plan_trips_monthly
            WHERE plan_version = %s
        """, (last_version['plan_version'],))
        count = cursor.fetchone()['count']
        print(f"  Registros: {count}")
    else:
        print("  [ERROR] No hay versiones del plan")
    
    # 3. Verificar vista latest
    print("\n3. VISTA LATEST:")
    cursor.execute("""
        SELECT COUNT(*) as count,
               MIN(month) as min_month,
               MAX(month) as max_month
        FROM ops.v_plan_trips_monthly_latest;
    """)
    view_data = cursor.fetchone()
    if view_data:
        print(f"  Registros en vista: {view_data['count']}")
        print(f"  Rango meses: {view_data['min_month']} a {view_data['max_month']}")
    
    # 4. Verificar estructura de tabla
    print("\n4. ESTRUCTURA DE TABLA:")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'ops'
        AND table_name = 'plan_trips_monthly'
        AND column_name IN ('projected_trips', 'projected_revenue', 'projected_drivers', 'month', 'country')
        ORDER BY column_name;
    """)
    cols = cursor.fetchall()
    for col in cols:
        print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
    
    cursor.close()

print("\n" + "=" * 70)
print("DIAGNOSTICO COMPLETADO")
print("=" * 70)
