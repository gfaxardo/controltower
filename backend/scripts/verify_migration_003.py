"""Script para verificar que la migración 003 se ejecutó correctamente."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import init_db_pool, get_db

init_db_pool()
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'ops' AND table_name LIKE '%plan%' ORDER BY table_name")
    tables = cursor.fetchall()
    print("Tablas creadas:")
    for t in tables:
        print(f"  - ops.{t[0]}")
    
    cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'ops' AND table_name LIKE 'v_plan%' ORDER BY table_name")
    views = cursor.fetchall()
    print("\nVistas creadas:")
    for v in views:
        print(f"  - ops.{v[0]}")
    cursor.close()
