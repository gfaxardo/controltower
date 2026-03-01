"""Script para refrescar vistas y ejecutar validaciones de KPIs financieros."""
import sys
import os
import io

# Configurar UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def refresh_view():
    """Refrescar vista materializada."""
    print("=" * 80)
    print("REFRESCAR VISTA MATERIALIZADA")
    print("=" * 80)
    
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("\nRefrescando ops.mv_real_financials_monthly...")
            cursor.execute("REFRESH MATERIALIZED VIEW ops.mv_real_financials_monthly")
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) FROM ops.mv_real_financials_monthly")
            count = cursor.fetchone()[0]
            print("OK Vista refrescada correctamente")
            print(f"OK Registros en vista: {count:,}")
            
            return True
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            cursor.close()

def run_validations():
    """Ejecutar validaciones."""
    print("\n" + "=" * 80)
    print("EJECUTAR VALIDACIONES")
    print("=" * 80)
    
    sql_path = os.path.join(os.path.dirname(__file__), 'sql', 'validate_financials_canonical.sql')
    
    if not os.path.exists(sql_path):
        print(f"⚠ Advertencia: No se encuentra {sql_path}")
        return False
    
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            print("\nEjecutando queries de validación...")
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql = f.read()
                # Dividir por queries individuales (separados por ;)
                queries = []
                current_query = []
                for line in sql.split('\n'):
                    line = line.strip()
                    if not line or line.startswith('--'):
                        continue
                    current_query.append(line)
                    if line.endswith(';'):
                        query = ' '.join(current_query).rstrip(';').strip()
                        if query:
                            queries.append(query)
                        current_query = []
                
                for i, query in enumerate(queries, 1):
                    try:
                        print(f"\n[{i}] Ejecutando validación...")
                        cursor.execute(query)
                        result = cursor.fetchall()
                        if result:
                            print(f"  Resultado:")
                            for row in result:
                                for key, value in row.items():
                                    print(f"    {key}: {value}")
                    except Exception as e:
                        print(f"  ⚠ Error: {e}")
            
            print("\nOK Validaciones ejecutadas")
            return True
            
        except Exception as e:
            print(f"\nERROR al ejecutar validaciones: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            cursor.close()

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("NORMALIZACIÓN DE KPIs FINANCIEROS - REFRESH Y VALIDACIÓN")
    print("=" * 80)
    
    # Refresh
    if not refresh_view():
        print("\n✗ Falló refresh de vistas")
        sys.exit(1)
    
    # Validaciones
    if not run_validations():
        print("\n⚠ Advertencia: Fallaron algunas validaciones")
    
    print("\n" + "=" * 80)
    print("OK PROCESO COMPLETADO")
    print("=" * 80)
