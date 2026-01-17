"""
Script para limpiar TODOS los datos de plan de ops.plan_trips_monthly.

USO:
    python scripts/clear_all_plans.py [--confirm]

ADVERTENCIA: Esto borra TODOS los planes, no solo una versión.
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def clear_all_plans(confirm=False):
    """Borra todos los datos de ops.plan_trips_monthly."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Mostrar qué se va a borrar
            cursor.execute("""
                SELECT 
                    plan_version, 
                    COUNT(*) as count,
                    MIN(created_at) as first_created,
                    MAX(created_at) as last_created
                FROM ops.plan_trips_monthly 
                GROUP BY plan_version 
                ORDER BY MAX(created_at) DESC
            """)
            existing_versions = cursor.fetchall()
            
            if not existing_versions:
                print("No hay planes para borrar.")
                return 0
            
            print("="*60)
            print("PLANES EXISTENTES QUE SE BORRARÁN:")
            print("="*60)
            total_rows = 0
            for version, count, first_created, last_created in existing_versions:
                print(f"  - {version}: {count:,} registros")
                print(f"    Creado: {first_created} - {last_created}")
                total_rows += count
            print("="*60)
            print(f"TOTAL: {total_rows:,} registros a borrar")
            print("="*60)
            
            if not confirm:
                print("\n[ADVERTENCIA] Esto borrará TODOS los planes.")
                print("Para confirmar, ejecuta con --confirm")
                return 1
            
            # Borrar todos los planes
            print("\nBorrando todos los planes...")
            cursor.execute("DELETE FROM ops.plan_trips_monthly")
            deleted_count = cursor.rowcount
            
            conn.commit()
            
            print(f"\n✓ Borrados {deleted_count:,} registros de ops.plan_trips_monthly")
            print("✓ Base de datos lista para nueva ingesta de plan")
            
            return 0
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error al borrar planes: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            cursor.close()

if __name__ == "__main__":
    confirm = '--confirm' in sys.argv
    
    if not confirm:
        print("ADVERTENCIA: Este script borrará TODOS los planes de ops.plan_trips_monthly")
        print("Para confirmar, ejecuta: python scripts/clear_all_plans.py --confirm")
        sys.exit(1)
    
    sys.exit(clear_all_plans(confirm=True))
