#!/usr/bin/env python3
"""Verificar y crear vistas si faltan"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verificar si existe la vista
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.views 
                WHERE table_schema='ops' AND table_name='v_plan_vs_real_monthly_latest'
            ) as exists
        """)
        exists = cursor.fetchone()['exists']
        
        if exists:
            print("[OK] Vista ops.v_plan_vs_real_monthly_latest existe")
        else:
            print("[WARN] Vista ops.v_plan_vs_real_monthly_latest NO existe")
            print("Ejecutando migracion 007 manualmente...")
            
            # Leer y ejecutar la migración 007
            migration_file = os.path.join(os.path.dirname(__file__), '..', 'alembic', 'versions', '007_create_plan_vs_real_views.py')
            if os.path.exists(migration_file):
                from alembic import op
                from alembic.config import Config
                from alembic.script import ScriptDirectory
                from alembic.runtime.migration import MigrationContext
                
                # Ejecutar upgrade de la migración 007
                from alembic.versions import create_plan_vs_real_views
                create_plan_vs_real_views.upgrade()
                print("[OK] Migracion 007 ejecutada")
            else:
                print("[ERROR] No se encontro archivo de migracion 007")
        
        cursor.close()

if __name__ == "__main__":
    main()
