"""
FIX DEFINITIVO: Revenue Plan en Vista
Reemplaza la vista que calcula revenue como GMV
"""

import sys
import os
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

print("=" * 70)
print("FIX: Reemplazando vista que calcula revenue como GMV")
print("=" * 70)

# Vista correcta: ops.v_plan_trips_monthly_latest
view_name = "ops.v_plan_trips_monthly_latest"

print(f"\n1. Obteniendo definicion actual de {view_name}...")
with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Obtener definicion actual
    cursor.execute(f"SELECT pg_get_viewdef('{view_name}', true) as def;")
    current_def = cursor.fetchone()['def']
    
    print("\nDefinicion actual (primeros 500 chars):")
    print(current_def[:500])
    
    # Verificar si usa projected_revenue GENERATED
    print("\n2. Verificando si projected_revenue es GENERATED en la tabla...")
    cursor.execute("""
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_schema = 'ops' 
        AND table_name = 'plan_trips_monthly'
        AND column_name = 'projected_revenue';
    """)
    col_info = cursor.fetchone()
    if col_info:
        print(f"  Column: {col_info['column_name']}")
        print(f"  Default: {col_info['column_default']}")
        if 'GENERATED' in str(col_info.get('column_default', '')):
            print("  [WARN] projected_revenue es GENERATED - necesita migracion 009")
        else:
            print("  [OK] projected_revenue NO es GENERATED")
    
    cursor.close()

print("\n3. La migracion 009 debe ejecutarse primero para cambiar")
print("   projected_revenue de GENERATED a campo normal.")
print("\n   Ejecutar: alembic upgrade head")
