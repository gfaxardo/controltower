"""Script para verificar ingesta completa del plan y generar reporte."""
import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def verify_plan_ingestion(plan_version: str = None):
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("\n" + "="*80)
            print("VERIFICACIÓN DE INGESTA DE PLAN")
            print("="*80 + "\n")
            
            # Si no se especifica versión, usar la última
            if not plan_version:
                cursor.execute("""
                    SELECT plan_version 
                    FROM ops.plan_trips_monthly 
                    GROUP BY plan_version 
                    ORDER BY MAX(created_at) DESC 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                if result:
                    plan_version = result[0]
                    print(f"Usando última versión: {plan_version}\n")
            
            if plan_version:
                # Estadísticas por versión
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total_rows,
                        COUNT(DISTINCT country) as countries,
                        COUNT(DISTINCT city) as cities,
                        COUNT(DISTINCT park_id) FILTER (WHERE park_id IS NOT NULL) as parks_with_id,
                        COUNT(*) FILTER (WHERE park_id IS NULL) as rows_without_park_id,
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
                
                print(f"## Estadísticas - Versión: {plan_version}\n")
                print(f"- Total registros: {stats[0]:,}")
                print(f"- Países: {stats[1]}")
                print(f"- Ciudades: {stats[2]}")
                print(f"- Parks con ID: {stats[3]}")
                print(f"- Registros sin park_id: {stats[4]:,}")
                print(f"- LOBs: {stats[5]}")
                print(f"- Segmentos: {stats[6]}")
                print(f"- Rango de meses: {stats[7]} a {stats[8]}")
                print(f"- Total trips proyectados: {stats[9]:,.0f}")
                print(f"- Total drivers proyectados: {stats[10]:,.0f}")
                print(f"- Ticket promedio: {stats[11]:,.2f}")
                print(f"- Revenue total proyectado: {stats[12]:,.2f}\n")
                
                # Conteo por city/lob/segment/month
                print("## Conteo por city/lob/segment/month (top 10)\n")
                cursor.execute(f"""
                    SELECT 
                        city,
                        lob_base,
                        segment,
                        month,
                        COUNT(*) as count,
                        SUM(projected_trips) as trips
                    FROM ops.plan_trips_monthly
                    WHERE plan_version = %s
                    GROUP BY city, lob_base, segment, month
                    ORDER BY trips DESC
                    LIMIT 10
                """, (plan_version,))
                
                print("| City | LOB | Segment | Month | Count | Trips |")
                print("|------|-----|---------|-------|-------|-------|")
                for row in cursor.fetchall():
                    print(f"| {row[0] or 'NULL'} | {row[1] or 'NULL'} | {row[2] or 'NULL'} | {row[3]} | {row[4]} | {row[5]:,.0f} |")
                print()
                
                # Top 10 validaciones
                print("## Top 10 Validaciones\n")
                cursor.execute(f"""
                    SELECT 
                        validation_type,
                        severity,
                        country,
                        city,
                        lob_base,
                        month,
                        row_count
                    FROM ops.plan_validation_results
                    WHERE plan_version = %s
                    ORDER BY 
                        CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
                        row_count DESC
                    LIMIT 10
                """, (plan_version,))
                
                validations = cursor.fetchall()
                if validations:
                    print("| Tipo | Severidad | Country | City | LOB | Month | Count |")
                    print("|------|-----------|---------|------|-----|-------|-------|")
                    for row in validations:
                        print(f"| {row[0]} | {row[1]} | {row[2] or 'NULL'} | {row[3] or 'NULL'} | {row[4] or 'NULL'} | {row[5] or 'NULL'} | {row[6]:,} |")
                else:
                    print("No se encontraron validaciones")
                print()
                
                # Verificar vistas latest
                print("## Verificación de Vistas Latest\n")
                cursor.execute("SELECT COUNT(*) FROM ops.v_plan_kpis_monthly_latest")
                latest_count = cursor.fetchone()[0]
                print(f"- ops.v_plan_kpis_monthly_latest: {latest_count:,} registros")
                
            print("\n" + "="*80)
            
        except Exception as e:
            print(f"\n[ERROR] Error durante la verificación: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    plan_version = sys.argv[1] if len(sys.argv) > 1 else None
    verify_plan_ingestion(plan_version)
