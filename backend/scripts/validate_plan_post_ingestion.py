"""
Script para validación post-ingesta de Plan.

USO:
    python validate_plan_post_ingestion.py <plan_version>
"""

import sys
import os
import io

# Configurar codificación UTF-8 para salida
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def validate_plan(plan_version: str):
    """Ejecuta validaciones post-ingesta."""
    init_db_pool()
    
    sql_file = os.path.join(os.path.dirname(__file__), 'sql', 'validate_plan_trips_monthly.sql')
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Reemplazar placeholder con el valor real
            sql_content = sql_content.replace("{PLAN_VERSION_PLACEHOLDER}", plan_version)
            
            # Ejecutar validaciones
            cursor.execute(sql_content)
            
            # Obtener resumen
            cursor.execute(f"""
                SELECT 
                    validation_type,
                    severity,
                    COUNT(*) as count,
                    SUM(row_count) as total_rows_affected
                FROM ops.plan_validation_results
                WHERE plan_version = %s
                GROUP BY validation_type, severity
                ORDER BY 
                    CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                    validation_type
            """, (plan_version,))
            
            results = cursor.fetchall()
            
            print("\n" + "="*60)
            print("VALIDACIONES POST-INGESTA")
            print("="*60)
            print(f"Plan Version: {plan_version}\n")
            
            if results:
                print("| Tipo | Severidad | Cantidad | Filas Afectadas |")
                print("|------|-----------|----------|-----------------|")
                for row in results:
                    print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]:,} |")
            else:
                print("✓ No se encontraron validaciones (todo OK)")
            
            print("\n" + "="*60)
            
            # Obtener conteos por severidad
            cursor.execute(f"""
                SELECT 
                    severity,
                    COUNT(*) as count
                FROM ops.plan_validation_results
                WHERE plan_version = %s
                GROUP BY severity
            """, (plan_version,))
            
            severity_counts = cursor.fetchall()
            if severity_counts:
                errors = sum(1 for s, _ in severity_counts if s == 'error')
                warnings = sum(c for s, c in severity_counts if s == 'warning')
                info = sum(c for s, c in severity_counts if s == 'info')
                
                print(f"\nResumen:")
                print(f"  Errores: {errors}")
                print(f"  Warnings: {warnings}")
                print(f"  Info: {info}")
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error durante la validación: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python validate_plan_post_ingestion.py <plan_version>")
        print("EJEMPLO: python validate_plan_post_ingestion.py ruta27_v1")
        sys.exit(1)
    
    plan_version = sys.argv[1]
    validate_plan(plan_version)
