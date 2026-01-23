"""
Script para generar reportes de homologación LOB.
Muestra qué LOB del REAL y del PLAN no tienen homologación.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_homologation_reports():
    """
    Genera reportes de homologación LOB.
    """
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        try:
            print("\n" + "=" * 80)
            print("REPORTE: LOB REAL sin Homologación")
            print("=" * 80)
            
            cursor.execute("""
                SELECT 
                    country,
                    city,
                    real_tipo_servicio,
                    trips_count,
                    first_seen_date,
                    last_seen_date
                FROM ops.v_real_lob_without_homologation
                ORDER BY trips_count DESC
                LIMIT 50
            """)
            
            real_unmatched = cursor.fetchall()
            
            if real_unmatched:
                print(f"\nTotal: {len(real_unmatched)} LOB del REAL sin homologación\n")
                print(f"{'País':<15} {'Ciudad':<20} {'Tipo Servicio':<30} {'Viajes':>12} {'Primer Viaje':<12} {'Último Viaje':<12}")
                print("-" * 120)
                for row in real_unmatched:
                    country, city, tipo_servicio, trips, first_seen, last_seen = row
                    print(f"{str(country or ''):<15} {str(city or ''):<20} {str(tipo_servicio or ''):<30} {trips:>12,} {str(first_seen or ''):<12} {str(last_seen or ''):<12}")
            else:
                print("\n✅ Todas las LOB del REAL tienen homologación")
            
            print("\n" + "=" * 80)
            print("REPORTE: LOB PLAN sin Homologación")
            print("=" * 80)
            
            cursor.execute("""
                SELECT 
                    country,
                    city,
                    plan_lob_name,
                    trips_plan,
                    revenue_plan,
                    first_period,
                    last_period
                FROM ops.v_plan_lob_without_homologation
                ORDER BY trips_plan DESC
                LIMIT 50
            """)
            
            plan_unmatched = cursor.fetchall()
            
            if plan_unmatched:
                print(f"\nTotal: {len(plan_unmatched)} LOB del PLAN sin homologación\n")
                print(f"{'País':<15} {'Ciudad':<20} {'LOB Plan':<30} {'Viajes Plan':>15} {'Revenue Plan':>15}")
                print("-" * 120)
                for row in plan_unmatched:
                    country, city, lob_name, trips, revenue, first_period, last_period = row
                    print(f"{str(country or ''):<15} {str(city or ''):<20} {str(lob_name or ''):<30} {float(trips or 0):>15,.0f} {float(revenue or 0):>15,.0f}")
            else:
                print("\n✅ Todas las LOB del PLAN tienen homologación")
            
            print("\n" + "=" * 80)
            print("SUGERENCIAS DE HOMOLOGACIÓN")
            print("=" * 80)
            
            cursor.execute("""
                SELECT 
                    country,
                    city,
                    real_tipo_servicio,
                    plan_lob_name,
                    real_trips_count,
                    plan_trips,
                    suggested_confidence,
                    already_homologated
                FROM ops.v_lob_homologation_suggestions
                WHERE NOT already_homologated
                ORDER BY 
                    CASE suggested_confidence
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    real_trips_count DESC
                LIMIT 30
            """)
            
            suggestions = cursor.fetchall()
            
            if suggestions:
                print(f"\nTotal: {len(suggestions)} sugerencias\n")
                print(f"{'País':<15} {'Ciudad':<20} {'REAL':<25} {'PLAN':<25} {'Confianza':<12} {'Viajes Real':>15} {'Viajes Plan':>15}")
                print("-" * 140)
                for row in suggestions:
                    country, city, real_lob, plan_lob, real_trips, plan_trips, confidence, already = row
                    print(f"{str(country or ''):<15} {str(city or ''):<20} {str(real_lob or ''):<25} {str(plan_lob or ''):<25} {str(confidence or ''):<12} {float(real_trips or 0):>15,.0f} {float(plan_trips or 0):>15,.0f}")
            else:
                print("\n⚠️ No hay sugerencias disponibles (puede que no haya datos en staging.plan_projection_raw)")
            
            print("\n" + "=" * 80)
            print("RESUMEN")
            print("=" * 80)
            
            cursor.execute("""
                SELECT COUNT(*) FROM ops.v_real_lob_without_homologation
            """)
            total_real_unmatched = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM ops.v_plan_lob_without_homologation
            """)
            total_plan_unmatched = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*) FROM ops.lob_homologation
            """)
            total_homologations = cursor.fetchone()[0]
            
            print(f"\nHomologaciones existentes: {total_homologations}")
            print(f"LOB REAL sin homologación: {total_real_unmatched}")
            print(f"LOB PLAN sin homologación: {total_plan_unmatched}")
            
        except Exception as e:
            logger.error(f"Error al generar reportes: {e}")
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    generate_homologation_reports()
