"""Script para verificar el esquema de ops.plan_trips_monthly."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import init_db_pool, get_db

init_db_pool()
with get_db() as conn:
    cursor = conn.cursor()
    
    # Verificar columnas de park_id
    cursor.execute("""
        SELECT column_name, is_nullable, data_type
        FROM information_schema.columns
        WHERE table_schema = 'ops' 
        AND table_name = 'plan_trips_monthly'
        AND column_name IN ('park_id', 'city', 'city_norm')
        ORDER BY column_name
    """)
    columns = cursor.fetchall()
    print("Columnas relevantes:")
    for col in columns:
        print(f"  - {col[0]}: {col[2]}, nullable: {col[1]}")
    
    # Verificar constraints UNIQUE
    cursor.execute("""
        SELECT conname, pg_get_constraintdef(oid) as definition
        FROM pg_constraint
        WHERE conrelid = 'ops.plan_trips_monthly'::regclass
        AND contype = 'u'
    """)
    constraints = cursor.fetchall()
    print("\nConstraints UNIQUE:")
    for con in constraints:
        print(f"  - {con[0]}: {con[1]}")
    
    cursor.close()
