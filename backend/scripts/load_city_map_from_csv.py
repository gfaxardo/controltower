"""
Script para cargar city mapping desde CSV completado.

USO:
    python load_city_map_from_csv.py <csv_path>

CSV debe tener columnas: country, plan_city_raw, plan_city_norm, real_city_norm, notes
"""

import sys
import os
import io
import csv

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def load_city_map_from_csv(csv_path: str):
    """Carga city mapping desde CSV completado."""
    init_db_pool()
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Archivo CSV no encontrado: {csv_path}")
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Limpiar mapeos existentes (opcional - comentado para no borrar trabajo previo)
            # cursor.execute("DELETE FROM ops.plan_city_map")
            
            loaded_count = 0
            updated_count = 0
            errors = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Validar columnas
                expected_cols = ['country', 'plan_city_raw', 'plan_city_norm', 'real_city_norm', 'notes']
                missing_cols = [col for col in expected_cols if col not in reader.fieldnames]
                if missing_cols:
                    raise Exception(f"CSV faltan columnas: {missing_cols}")
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        country = row.get('country', '').strip() or None
                        plan_city_raw = row.get('plan_city_raw', '').strip() or None
                        plan_city_norm = row.get('plan_city_norm', '').strip() or None
                        real_city_norm = row.get('real_city_norm', '').strip() or None
                        notes = row.get('notes', '').strip() or None
                        
                        if not country or not plan_city_norm:
                            errors.append(f"Fila {row_num}: country o plan_city_norm vacío")
                            continue
                        
                        # Upsert (INSERT ... ON CONFLICT UPDATE)
                        cursor.execute("""
                            INSERT INTO ops.plan_city_map (
                                country,
                                plan_city_raw,
                                plan_city_norm,
                                real_city_norm,
                                notes,
                                is_active
                            ) VALUES (%s, %s, %s, %s, %s, TRUE)
                            ON CONFLICT (country, plan_city_norm)
                            DO UPDATE SET
                                plan_city_raw = EXCLUDED.plan_city_raw,
                                real_city_norm = EXCLUDED.real_city_norm,
                                notes = EXCLUDED.notes,
                                updated_at = NOW()
                        """, (country, plan_city_raw, plan_city_norm, real_city_norm, notes))
                        
                        if cursor.rowcount > 0:
                            if cursor.rowcount == 1:
                                loaded_count += 1
                            else:
                                updated_count += 1
                        
                    except Exception as e:
                        errors.append(f"Fila {row_num}: {str(e)}")
                        continue
            
            conn.commit()
            
            print(f"\n{'='*80}")
            print("CITY MAP CARGADO")
            print(f"{'='*80}\n")
            print(f"Registros nuevos: {loaded_count}")
            print(f"Registros actualizados: {updated_count}")
            
            if errors:
                print(f"\nErrores encontrados: {len(errors)}")
                for error in errors[:10]:
                    print(f"  - {error}")
                if len(errors) > 10:
                    print(f"  ... y {len(errors) - 10} más")
            
            # Mostrar resumen de mapeos activos
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(real_city_norm) as mapped,
                    COUNT(*) - COUNT(real_city_norm) as unmapped
                FROM ops.plan_city_map
                WHERE is_active = TRUE
            """)
            
            stats = cursor.fetchone()
            total, mapped, unmapped = stats
            
            print(f"\nResumen de mapeos activos:")
            print(f"  Total: {total}")
            print(f"  Mapeados (con real_city_norm): {mapped}")
            print(f"  Sin mapear: {unmapped}")
            
            cursor.close()
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error cargando city map: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("USO: python load_city_map_from_csv.py <csv_path>")
        print("EJEMPLO: python load_city_map_from_csv.py exports/plan_city_map_seed.csv")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    load_city_map_from_csv(csv_path)
