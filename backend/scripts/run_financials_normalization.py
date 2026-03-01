"""
Script para ejecutar normalización de KPIs financieros.
Ejecuta migraciones 011 y 012, refresca vistas y ejecuta validaciones.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def run_migrations():
    """Ejecutar migraciones 011 y 012."""
    print("=" * 80)
    print("NORMALIZACIÓN DE KPIs FINANCIEROS - EJECUCIÓN DE MIGRACIONES")
    print("=" * 80)
    
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            # Leer migración 011
            migration_011_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'alembic', 'versions', '011_create_real_financials_monthly_view.py'
            )
            
            if not os.path.exists(migration_011_path):
                print(f"✗ Error: No se encuentra {migration_011_path}")
                return False
            
            print("\n[1/2] Ejecutando migración 011: Crear vista ops.mv_real_financials_monthly...")
            with open(migration_011_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extraer función upgrade
                if 'def upgrade() -> None:' in content:
                    # Ejecutar SQL directamente desde el contenido
                    import re
                    sql_match = re.search(r'op\.execute\("""(.*?)"""\)', content, re.DOTALL)
                    if sql_match:
                        sql = sql_match.group(1)
                        # Limpiar y ejecutar
                        sql_statements = [s.strip() for s in sql.split(';') if s.strip()]
                        for stmt in sql_statements:
                            if stmt:
                                cursor.execute(stmt)
                        conn.commit()
                        print("  ✓ Migración 011 ejecutada correctamente")
                    else:
                        print("  ✗ No se pudo extraer SQL de la migración 011")
                        return False
            
            # Leer migración 012
            migration_012_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'alembic', 'versions', '012_add_plan_financials_canonical.py'
            )
            
            if not os.path.exists(migration_012_path):
                print(f"✗ Error: No se encuentra {migration_012_path}")
                return False
            
            print("\n[2/2] Ejecutando migración 012: Ajustar vista plan mensual...")
            with open(migration_012_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extraer función upgrade
                if 'def upgrade() -> None:' in content:
                    import re
                    sql_match = re.search(r'op\.execute\("""(.*?)"""\)', content, re.DOTALL)
                    if sql_match:
                        sql = sql_match.group(1)
                        sql_statements = [s.strip() for s in sql.split(';') if s.strip()]
                        for stmt in sql_statements:
                            if stmt:
                                cursor.execute(stmt)
                        conn.commit()
                        print("  ✓ Migración 012 ejecutada correctamente")
                    else:
                        print("  ✗ No se pudo extraer SQL de la migración 012")
                        return False
            
            print("\n✓ Migraciones ejecutadas correctamente")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error al ejecutar migraciones: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            cursor.close()


def refresh_views():
    """Refrescar vistas materializadas."""
    print("\n" + "=" * 80)
    print("REFRESCAR VISTAS MATERIALIZADAS")
    print("=" * 80)
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            print("\n[1/1] Refrescando ops.mv_real_financials_monthly...")
            cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_financials_monthly")
            conn.commit()
            print("  ✓ Vista refrescada correctamente")
            
            # Verificar conteo
            cursor.execute("SELECT COUNT(*) FROM ops.mv_real_financials_monthly")
            count = cursor.fetchone()[0]
            print(f"  ✓ Registros en vista: {count:,}")
            
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error al refrescar vistas: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            cursor.close()


def run_validations():
    """Ejecutar queries de validación."""
    print("\n" + "=" * 80)
    print("EJECUTAR VALIDACIONES")
    print("=" * 80)
    
    validation_sql_path = os.path.join(
        os.path.dirname(__file__),
        'sql', 'validate_financials_canonical.sql'
    )
    
    if not os.path.exists(validation_sql_path):
        print(f"⚠ Advertencia: No se encuentra {validation_sql_path}")
        return False
    
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            print("\nEjecutando queries de validación...")
            with open(validation_sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()
                # Dividir por queries individuales
                queries = [q.strip() for q in sql.split(';') if q.strip() and not q.strip().startswith('--')]
                
                for i, query in enumerate(queries, 1):
                    if query:
                        try:
                            cursor.execute(query)
                            result = cursor.fetchall()
                            if result:
                                print(f"\n[{i}] Resultado:")
                                for row in result:
                                    for key, value in row.items():
                                        print(f"  {key}: {value}")
                        except Exception as e:
                            print(f"\n[{i}] Error: {e}")
            
            print("\n✓ Validaciones ejecutadas")
            return True
            
        except Exception as e:
            print(f"\n✗ Error al ejecutar validaciones: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            cursor.close()


def main():
    """Ejecutar normalización completa."""
    print("\n" + "=" * 80)
    print("NORMALIZACIÓN DEFINITIVA DE KPIs FINANCIEROS")
    print("=" * 80)
    print("\nEste script ejecutará:")
    print("  1. Migraciones 011 y 012")
    print("  2. Refresh de vistas materializadas")
    print("  3. Validaciones")
    print("\n" + "=" * 80)
    
    # Ejecutar migraciones usando alembic directamente
    print("\n⚠ NOTA: Para ejecutar migraciones, usa:")
    print("  alembic upgrade head")
    print("\nContinuando con refresh y validaciones...")
    
    # Refresh vistas
    if not refresh_views():
        print("\n✗ Falló refresh de vistas")
        return False
    
    # Validaciones
    if not run_validations():
        print("\n⚠ Advertencia: Fallaron algunas validaciones")
    
    print("\n" + "=" * 80)
    print("✓ PROCESO COMPLETADO")
    print("=" * 80)
    print("\nPróximos pasos:")
    print("  1. Ejecutar: alembic upgrade head")
    print("  2. Verificar que las vistas estén refrescadas")
    print("  3. Probar endpoints de API")
    print("  4. Verificar UI")


if __name__ == "__main__":
    main()
