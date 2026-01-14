"""
Script para cargar datos territoriales (park_id, country, city, default_line_of_business) desde CSV a dim.dim_park.

Usa staging table ops.stg_park_territory y función ops.merge_park_territory_from_staging().

Formato CSV esperado: park_id,country,city,default_line_of_business (header opcional)
Si default_line_of_business no está presente, se usará 'Auto Taxi' por defecto.

Uso:
    python scripts/load_park_territory_csv.py --csv data.csv
    python scripts/load_park_territory_csv.py --csv data.csv --dry-run
"""
import sys
import os
import argparse
import csv
from typing import List, Dict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def load_from_csv(file_path: str) -> List[Dict[str, str]]:
    """Carga datos desde CSV"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalizar nombres de columnas (case insensitive)
            row_dict = {k.lower().strip(): v.strip() if v else None for k, v in row.items()}
            if 'park_id' in row_dict:
                data.append({
                    'park_id': str(row_dict['park_id']).strip() if row_dict['park_id'] else '',
                    'country': row_dict.get('country', '').strip() if row_dict.get('country') else '',
                    'city': row_dict.get('city', '').strip() if row_dict.get('city') else '',
                    'default_line_of_business': row_dict.get('default_line_of_business', '').strip() if row_dict.get('default_line_of_business') else ''
                })
    return data

def validate_data(data: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], List[str]]:
    """Valida datos y retorna (validos, errores)"""
    valid = []
    errors = []
    seen_park_ids = set()
    
    for i, item in enumerate(data, start=2):  # start=2 porque header es línea 1
        park_id = item.get('park_id', '').strip()
        country = item.get('country', '').strip()
        city = item.get('city', '').strip()
        
        item_errors = []
        
        # Validar park_id
        if not park_id:
            item_errors.append("park_id vacío")
        
        # Validar duplicados en CSV
        if park_id and park_id in seen_park_ids:
            item_errors.append(f"park_id duplicado en CSV: {park_id}")
        seen_park_ids.add(park_id)
        
        # Validar country/city (advertir pero permitir)
        if not country:
            item_errors.append("country vacío")
        if not city:
            item_errors.append("city vacío")
        
        if item_errors:
            errors.append(f"Línea {i} (park_id={park_id}): {', '.join(item_errors)}")
        else:
            valid.append(item)
    
    return valid, errors

def load_to_staging(data: List[Dict[str, str]], loaded_by: str = None, dry_run: bool = False):
    """Carga datos a staging table"""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if dry_run:
            print(f"\n[DRY RUN] Se cargarían {len(data)} registros a ops.stg_park_territory")
            for item in data[:5]:  # Mostrar primeros 5
                lob = item.get('default_line_of_business', '') or '(vacío)'
                print(f"  park_id={item['park_id']}, country={item['country']}, city={item['city']}, lob={lob}")
            if len(data) > 5:
                print(f"  ... y {len(data) - 5} más")
            return
        
        # Limpiar staging table
        cursor.execute("TRUNCATE TABLE ops.stg_park_territory")
        
        # Insertar datos
        for item in data:
            cursor.execute("""
                INSERT INTO ops.stg_park_territory (park_id, country, city, default_line_of_business, loaded_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                item['park_id'], 
                item['country'], 
                item['city'], 
                item.get('default_line_of_business', '') if item.get('default_line_of_business') else None,
                loaded_by
            ))
        
        cursor.close()
        print(f"Cargados {len(data)} registros a ops.stg_park_territory")

def run_merge(dry_run: bool = False):
    """Ejecuta función de merge desde staging"""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        if dry_run:
            print("\n[DRY RUN] Se ejecutaría ops.merge_park_territory_from_staging()")
            return
        
        cursor.execute("SELECT * FROM ops.merge_park_territory_from_staging()")
        result = cursor.fetchone()
        
        inserted = result[0]
        updated = result[1]
        rejected = result[2]
        
        cursor.close()
        
        print(f"\n=== Resumen del merge ===")
        print(f"Insertados: {inserted}")
        print(f"Actualizados: {updated}")
        print(f"Rechazados: {rejected}")

def main():
    parser = argparse.ArgumentParser(description='Carga datos territoriales desde CSV')
    parser.add_argument('--csv', required=True, help='Archivo CSV con datos (park_id,country,city)')
    parser.add_argument('--dry-run', action='store_true', help='Solo muestra qué haría sin hacer cambios')
    parser.add_argument('--loaded-by', default=None, help='Usuario que carga los datos (opcional)')
    
    args = parser.parse_args()
    
    print(f"Leyendo CSV: {args.csv}")
    data = load_from_csv(args.csv)
    print(f"Se encontraron {len(data)} registros en CSV")
    
    # Validar datos
    valid_data, errors = validate_data(data)
    
    if errors:
        print(f"\n=== Errores de validación encontrados ({len(errors)}) ===")
        for error in errors[:20]:  # Mostrar primeros 20
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... y {len(errors) - 20} más")
        
        if not valid_data:
            print("\nError: No hay registros válidos para procesar")
            sys.exit(1)
    
    print(f"Registros válidos: {len(valid_data)}")
    
    # Cargar a staging
    load_to_staging(valid_data, loaded_by=args.loaded_by, dry_run=args.dry_run)
    
    # Ejecutar merge
    if not args.dry_run:
        run_merge(dry_run=False)
    else:
        run_merge(dry_run=True)

if __name__ == "__main__":
    main()
