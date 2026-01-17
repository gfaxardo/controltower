"""
Script para generar CSV seed de city mapping desde plan existente.

USO:
    python generate_city_map_seed.py <plan_version> [output_path]

Genera CSV con ciudades del plan para que el usuario complete real_city_norm.
"""

import sys
import os
import io
import csv
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def generate_city_map_seed(plan_version: str, output_path: str = None):
    """Genera CSV seed con ciudades del plan para mapeo."""
    init_db_pool()
    
    if not output_path:
        # Crear directorio exports si no existe
        exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        output_path = os.path.join(exports_dir, 'plan_city_map_seed.csv')
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Obtener todas las ciudades únicas del plan
            cursor.execute("""
                SELECT DISTINCT
                    country,
                    city,
                    city_norm,
                    COUNT(*) as row_count
                FROM ops.plan_trips_monthly
                WHERE plan_version = %s
                AND city IS NOT NULL
                AND city_norm IS NOT NULL
                GROUP BY country, city, city_norm
                ORDER BY country, city_norm
            """, (plan_version,))
            
            cities = cursor.fetchall()
            
            if not cities:
                print(f"[WARN] No se encontraron ciudades en el plan version {plan_version}")
                return output_path
            
            # Escribir CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Headers
                writer.writerow([
                    'country',
                    'plan_city_raw',
                    'plan_city_norm',
                    'real_city_norm',
                    'notes'
                ])
                
                # Datos
                for country, city, city_norm, row_count in cities:
                    writer.writerow([
                        country or '',
                        city or '',
                        city_norm or '',
                        '',  # real_city_norm - vacío para que el usuario complete
                        f'Encontrado en {row_count} filas del plan'  # notas
                    ])
            
            print(f"\n{'='*80}")
            print("CSV SEED GENERADO")
            print(f"{'='*80}\n")
            print(f"Archivo: {output_path}")
            print(f"Total ciudades: {len(cities)}")
            print(f"\nInstrucciones:")
            print(f"  1. Abre el CSV generado")
            print(f"  2. Completa la columna 'real_city_norm' con el city_norm correspondiente de dim_park")
            print(f"  3. Guarda el CSV")
            print(f"  4. Ejecuta: python scripts/load_city_map_from_csv.py <csv_path>")
            print(f"\nPara ver ciudades disponibles en dim_park:")
            print(f"  python scripts/diagnose_plan_warnings.py {plan_version}")
            
            cursor.close()
            
            return output_path
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error generando CSV seed: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("USO: python generate_city_map_seed.py <plan_version> [output_path]")
        print("EJEMPLO: python generate_city_map_seed.py ruta27_v2026_01_16_a")
        sys.exit(1)
    
    plan_version = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    generate_city_map_seed(plan_version, output_path)
