"""
Script para generar reporte final confirmando que Plan está listo para comparación.

USO:
    python report_plan_ready_for_comparison.py <plan_version>
"""

import sys
import os
import io

# Configurar codificación UTF-8 para salida
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def generate_report(plan_version: str):
    """Genera reporte final de confirmación."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("\n" + "="*80)
            print("REPORTE FINAL: PLAN LISTO PARA COMPARACIÓN")
            print("="*80 + "\n")
            print(f"Plan Version: {plan_version}\n")
            
            # 1. Estadísticas básicas del plan
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total_rows,
                    COUNT(DISTINCT country) as countries,
                    COUNT(DISTINCT city) as cities,
                    COUNT(DISTINCT park_id) as parks,
                    COUNT(DISTINCT lob_base) as lobs,
                    COUNT(DISTINCT segment) as segments,
                    MIN(month) as min_month,
                    MAX(month) as max_month,
                    SUM(projected_trips) as total_trips,
                    SUM(projected_drivers) as total_drivers,
                    AVG(projected_ticket) as avg_ticket,
                    SUM(projected_revenue) as total_revenue
                FROM ops.plan_trips_monthly
                WHERE plan_version = %s
            """, (plan_version,))
            
            stats = cursor.fetchone()
            
            print("## 1. ESTADÍSTICAS DEL PLAN\n")
            print(f"- Total de registros: {stats[0]:,}")
            print(f"- Países: {stats[1]}")
            print(f"- Ciudades: {stats[2]}")
            print(f"- Parks: {stats[3]}")
            print(f"- LOBs: {stats[4]}")
            print(f"- Segmentos: {stats[5]}")
            print(f"- Rango de meses: {stats[6]} a {stats[7]}")
            print(f"- Total trips proyectados: {stats[8]:,.0f}")
            print(f"- Total drivers proyectados: {stats[9]:,.0f}")
            print(f"- Ticket promedio: {stats[10]:,.2f}")
            print(f"- Revenue total proyectado: {stats[11]:,.2f}\n")
            
            # 2. Validaciones
            cursor.execute(f"""
                SELECT 
                    validation_type,
                    severity,
                    COUNT(*) as count,
                    SUM(row_count) as total_rows
                FROM ops.plan_validation_results
                WHERE plan_version = %s
                GROUP BY validation_type, severity
                ORDER BY 
                    CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                    validation_type
            """, (plan_version,))
            
            validations = cursor.fetchall()
            
            print("## 2. VALIDACIONES\n")
            if validations:
                print("| Tipo | Severidad | Cantidad | Filas Afectadas |")
                print("|------|-----------|----------|-----------------|")
                for row in validations:
                    print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]:,} |")
            else:
                print("✓ No se encontraron validaciones\n")
            
            # 3. Verificar vistas
            print("\n## 3. VISTAS DISPONIBLES\n")
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.views 
                WHERE table_schema = 'ops' 
                AND table_name LIKE 'v_plan%'
                ORDER BY table_name
            """)
            
            views = cursor.fetchall()
            for view in views:
                # Contar registros en vista
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM ops.{view[0]} WHERE plan_version = %s", (plan_version,))
                    count = cursor.fetchone()[0]
                    print(f"- ✓ ops.{view[0]}: {count:,} registros")
                except:
                    print(f"- ⚠ ops.{view[0]}: no disponible")
            
            # 4. Resumen de warnings/errores
            cursor.execute(f"""
                SELECT severity, COUNT(*) 
                FROM ops.plan_validation_results
                WHERE plan_version = %s
                GROUP BY severity
            """, (plan_version,))
            
            severity_counts = dict(cursor.fetchall())
            errors = severity_counts.get('error', 0)
            warnings = severity_counts.get('warning', 0)
            info = severity_counts.get('info', 0)
            
            print("\n## 4. RESUMEN DE VALIDACIONES\n")
            print(f"- Errores: {errors}")
            print(f"- Warnings: {warnings}")
            print(f"- Info: {info}")
            
            # 5. Confirmación final
            print("\n" + "="*80)
            print("CONFIRMACIÓN FINAL")
            print("="*80 + "\n")
            
            is_ready = errors == 0
            
            if is_ready:
                print("✓ PLAN ESTÁ LISTO PARA COMPARACIÓN CON REAL\n")
                print("El plan cumple con los requisitos:")
                print("  - Tabla canónica creada (ops.plan_trips_monthly)")
                print("  - Datos ingeridos correctamente")
                print("  - Vistas disponibles para consulta")
                if warnings > 0:
                    print(f"  - ⚠ {warnings} warning(s) encontrado(s) (revisar pero no bloqueante)")
                else:
                    print("  - Sin warnings críticos")
                print("  - Sin errores de validación\n")
                
                print("VISTAS DISPONIBLES PARA CONSULTA:")
                print("  - ops.v_plan_trips_monthly")
                print("  - ops.v_plan_trips_daily_equivalent")
                print("  - ops.v_plan_kpis_monthly\n")
                
                print("PRÓXIMOS PASOS:")
                print("  - El plan está versionado y listo para comparación Plan vs Real")
                print("  - Usar las vistas para consultas de plan")
                print("  - Comparar con Real usando los campos canónicos establecidos\n")
            else:
                print("✗ PLAN NO ESTÁ LISTO PARA COMPARACIÓN\n")
                print(f"Se encontraron {errors} error(es) que deben resolverse antes de continuar.\n")
            
            print("="*80 + "\n")
            
            conn.commit()
            
            return is_ready
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error durante la generación del reporte: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python report_plan_ready_for_comparison.py <plan_version>")
        print("EJEMPLO: python report_plan_ready_for_comparison.py ruta27_v1")
        sys.exit(1)
    
    plan_version = sys.argv[1]
    is_ready = generate_report(plan_version)
    sys.exit(0 if is_ready else 1)
