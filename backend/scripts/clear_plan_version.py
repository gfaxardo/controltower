"""
Script para limpiar una versión específica de plan de ops.plan_trips_monthly.

USO:
    python scripts/clear_plan_version.py <plan_version> [--confirm]

EJEMPLO:
    python scripts/clear_plan_version.py ruta27_v2026_01_16_a --confirm
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def clear_plan_version(plan_version: str, confirm=False):
    """Borra una versión específica de plan."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Verificar que la versión existe
            cursor.execute("""
                SELECT COUNT(*) 
                FROM ops.plan_trips_monthly 
                WHERE plan_version = %s
            """, (plan_version,))
            count = cursor.fetchone()[0]
            
            if count == 0:
                print(f"No se encontraron registros para la versión: {plan_version}")
                return 1
            
            print("="*60)
            print(f"VERSIÓN DE PLAN A BORRAR: {plan_version}")
            print("="*60)
            print(f"Registros a borrar: {count:,}")
            print("="*60)
            
            if not confirm:
                print(f"\n[ADVERTENCIA] Esto borrará la versión '{plan_version}'.")
                print("Para confirmar, ejecuta con --confirm")
                return 1
            
            # Borrar la versión específica
            print(f"\nBorrando versión {plan_version}...")
            cursor.execute("""
                DELETE FROM ops.plan_trips_monthly 
                WHERE plan_version = %s
            """, (plan_version,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            
            print(f"\n✓ Borrados {deleted_count:,} registros de la versión {plan_version}")
            
            return 0
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error al borrar versión: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            cursor.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USO: python scripts/clear_plan_version.py <plan_version> [--confirm]")
        print("EJEMPLO: python scripts/clear_plan_version.py ruta27_v2026_01_16_a --confirm")
        sys.exit(1)
    
    plan_version = sys.argv[1]
    confirm = '--confirm' in sys.argv
    
    if not confirm:
        print(f"ADVERTENCIA: Este script borrará la versión '{plan_version}'")
        print("Para confirmar, ejecuta: python scripts/clear_plan_version.py <version> --confirm")
        sys.exit(1)
    
    sys.exit(clear_plan_version(plan_version, confirm=True))
