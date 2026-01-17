"""
Script para limpiar TODOS los datos de plan de TODAS las tablas relacionadas.

Limpia:
- ops.plan_trips_monthly (tabla canónica)
- plan.plan_long_raw
- plan.plan_long_valid
- plan.plan_long_out_of_universe
- plan.plan_long_missing

USO:
    python scripts/clear_all_plan_data.py [--confirm]
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def clear_all_plan_data(confirm=False):
    """Borra todos los datos de plan de todas las tablas."""
    init_db_pool()
    
    tables_to_clear = [
        ('ops.plan_trips_monthly', 'Tabla canónica de plan'),
        ('plan.plan_long_raw', 'Plan crudo (sin validar)'),
        ('plan.plan_long_valid', 'Plan válido (en universo)'),
        ('plan.plan_long_out_of_universe', 'Plan fuera de universo'),
        ('plan.plan_long_missing', 'Huecos del plan')
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("="*60)
            print("LIMPIEZA COMPLETA DE DATOS DE PLAN")
            print("="*60)
            
            total_deleted = 0
            table_counts = {}
            
            # Contar registros en cada tabla
            for table_name, description in tables_to_clear:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    table_counts[table_name] = count
                    total_deleted += count
                    print(f"  {table_name}: {count:,} registros - {description}")
                except Exception as e:
                    print(f"  {table_name}: ERROR al contar - {e}")
                    table_counts[table_name] = 0
            
            print("="*60)
            print(f"TOTAL: {total_deleted:,} registros a borrar")
            print("="*60)
            
            if total_deleted == 0:
                print("\nNo hay datos de plan para borrar.")
                return 0
            
            if not confirm:
                print("\n[ADVERTENCIA] Esto borrará TODOS los datos de plan de todas las tablas.")
                print("Para confirmar, ejecuta con --confirm")
                return 1
            
            # Borrar de cada tabla
            print("\nBorrando datos...")
            for table_name, description in tables_to_clear:
                try:
                    cursor.execute(f"DELETE FROM {table_name}")
                    deleted = cursor.rowcount
                    print(f"  ✓ {table_name}: {deleted:,} registros borrados")
                except Exception as e:
                    print(f"  ✗ {table_name}: ERROR - {e}")
            
            conn.commit()
            
            print("\n" + "="*60)
            print("✓ LIMPIEZA COMPLETA EXITOSA")
            print("="*60)
            print("Todas las tablas de plan han sido limpiadas.")
            print("Base de datos lista para nueva ingesta de plan.")
            print("="*60)
            
            return 0
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error durante la limpieza: {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            cursor.close()

if __name__ == "__main__":
    confirm = '--confirm' in sys.argv
    
    if not confirm:
        print("ADVERTENCIA: Este script borrará TODOS los datos de plan de todas las tablas")
        print("Para confirmar, ejecuta: python scripts/clear_all_plan_data.py --confirm")
        sys.exit(1)
    
    sys.exit(clear_all_plan_data(confirm=True))
