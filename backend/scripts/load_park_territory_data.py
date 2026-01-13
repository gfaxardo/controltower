"""
Script para cargar datos territoriales en dim.dim_park.

Campos requeridos:
- park_id (PK, requerido)
- country (requerido)
- city (requerido)
- park_name (opcional, default: 'Yego')

Formato esperado:
- CSV: park_id,park_name,country,city (header opcional, park_name es opcional)
- JSON: [{"park_id": "123", "park_name": "Yego Lima", "country": "Peru", "city": "Lima"}, ...]
- Excel: Columnas park_id, park_name (opcional), country, city

Uso:
    python scripts/load_park_territory_data.py --csv data.csv
    python scripts/load_park_territory_data.py --json data.json
    python scripts/load_park_territory_data.py --excel data.xlsx
    python scripts/load_park_territory_data.py --stdin  (lee CSV desde stdin)
    python scripts/load_park_territory_data.py --csv data.csv --dry-run  (solo muestra qué haría)
"""
import sys
import os
import argparse
import json
import csv
from typing import List, Dict, Optional
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
            if 'park_id' in row_dict and row_dict['park_id']:
                data.append({
                    'park_id': str(row_dict['park_id']).strip(),
                    'park_name': row_dict.get('park_name', '').strip() if row_dict.get('park_name') else '',
                    'country': row_dict.get('country', '').strip() if row_dict.get('country') else '',
                    'city': row_dict.get('city', '').strip() if row_dict.get('city') else ''
                })
    return data

def load_from_json(file_path: str) -> List[Dict[str, str]]:
    """Carga datos desde JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data_raw = json.load(f)
    
    data = []
    for item in data_raw:
        if isinstance(item, dict) and 'park_id' in item:
            data.append({
                'park_id': str(item['park_id']).strip(),
                'park_name': str(item.get('park_name', '')).strip(),
                'country': str(item.get('country', '')).strip(),
                'city': str(item.get('city', '')).strip()
            })
    return data

def load_from_excel(file_path: str) -> List[Dict[str, str]]:
    """Carga datos desde Excel"""
    try:
        import pandas as pd
    except ImportError:
        print("Error: pandas no está instalado. Instala con: pip install pandas openpyxl")
        sys.exit(1)
    
    df = pd.read_excel(file_path)
    
    # Normalizar nombres de columnas
    df.columns = [col.lower().strip() for col in df.columns]
    
    data = []
    for _, row in df.iterrows():
        if pd.notna(row.get('park_id')):
            data.append({
                'park_id': str(row['park_id']).strip(),
                'park_name': str(row.get('park_name', '')).strip() if pd.notna(row.get('park_name')) else '',
                'country': str(row.get('country', '')).strip() if pd.notna(row.get('country')) else '',
                'city': str(row.get('city', '')).strip() if pd.notna(row.get('city')) else ''
            })
    return data

def load_from_stdin() -> List[Dict[str, str]]:
    """Carga datos desde stdin (CSV)"""
    data = []
    reader = csv.DictReader(sys.stdin)
    for row in reader:
        row_dict = {k.lower().strip(): v.strip() if v else None for k, v in row.items()}
        if 'park_id' in row_dict and row_dict['park_id']:
            data.append({
                'park_id': str(row_dict['park_id']).strip(),
                'park_name': row_dict.get('park_name', '').strip() if row_dict.get('park_name') else '',
                'country': row_dict.get('country', '').strip() if row_dict.get('country') else '',
                'city': row_dict.get('city', '').strip() if row_dict.get('city') else ''
            })
    return data

def upsert_park_data(data: List[Dict[str, str]], dry_run: bool = False):
    """Inserta o actualiza datos en dim.dim_park
    
    NOTA: Los campos requeridos son:
    - park_id (PK)
    - park_name (requerido)
    - city (requerido)
    - country (requerido)
    - default_line_of_business (requerido)
    
    Si park_name está vacío, usa 'Yego' como default.
    Si default_line_of_business está vacío, mantiene el valor existente (para UPDATE) o deja NULL (para INSERT nuevo).
    """
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        inserted = 0
        updated = 0
        skipped = 0
        errors = []
        
        for item in data:
            park_id = item['park_id']
            park_name = item.get('park_name', '').strip()
            country = item.get('country', '').strip()
            city = item.get('city', '').strip()
            
            if not park_id:
                skipped += 1
                continue
            
            # Validar campos requeridos para INSERT
            if not country or not city:
                errors.append(f"park_id={park_id}: country y city son requeridos")
                skipped += 1
                continue
            
            # Default para park_name si está vacío
            if not park_name:
                park_name = 'Yego'
            
            # Check if park_id exists
            cursor.execute("SELECT park_id, default_line_of_business FROM dim.dim_park WHERE park_id = %s", (park_id,))
            exists_row = cursor.fetchone()
            
            if dry_run:
                if exists_row:
                    print(f"[DRY RUN] UPDATE: park_id={park_id}, park_name={park_name}, country={country}, city={city}")
                    updated += 1
                else:
                    print(f"[DRY RUN] INSERT: park_id={park_id}, park_name={park_name}, country={country}, city={city}")
                    print(f"  WARNING: default_line_of_business será NULL (debe definirse después)")
                    inserted += 1
            else:
                if exists_row:
                    # UPDATE: solo actualiza park_name, country, city (no toca default_line_of_business)
                    cursor.execute("""
                        UPDATE dim.dim_park 
                        SET park_name = %s, country = %s, city = %s
                        WHERE park_id = %s
                    """, (park_name, country, city, park_id))
                    updated += 1
                else:
                    # INSERT: para default_line_of_business, intentamos NULL primero
                    # Si hay constraint NOT NULL, necesitaríamos un valor por defecto
                    try:
                        cursor.execute("""
                            INSERT INTO dim.dim_park (park_id, park_name, country, city, default_line_of_business)
                            VALUES (%s, %s, %s, %s, NULL)
                        """, (park_id, park_name, country, city))
                        inserted += 1
                    except Exception as e:
                        # Si falla por default_line_of_business NOT NULL, usamos un valor temporal
                        print(f"Warning: park_id={park_id} requiere default_line_of_business. Usando 'Auto Taxi' temporalmente.")
                        cursor.execute("""
                            INSERT INTO dim.dim_park (park_id, park_name, country, city, default_line_of_business)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (park_id, park_name, country, city, 'Auto Taxi'))
                        inserted += 1
        
        cursor.close()
        
        print(f"\n=== Resumen ===")
        print(f"Insertados: {inserted}")
        print(f"Actualizados: {updated}")
        print(f"Omitidos: {skipped}")
        print(f"Total procesados: {len(data)}")
        
        if errors:
            print(f"\n=== Errores encontrados ({len(errors)}) ===")
            for error in errors[:10]:  # Mostrar solo primeros 10
                print(f"  - {error}")
            if len(errors) > 10:
                print(f"  ... y {len(errors) - 10} más")

def main():
    parser = argparse.ArgumentParser(description='Carga datos territoriales en dim.dim_park')
    parser.add_argument('--csv', help='Archivo CSV con datos')
    parser.add_argument('--json', help='Archivo JSON con datos')
    parser.add_argument('--excel', help='Archivo Excel con datos')
    parser.add_argument('--stdin', action='store_true', help='Lee CSV desde stdin')
    parser.add_argument('--dry-run', action='store_true', help='Solo muestra qué haría sin hacer cambios')
    
    args = parser.parse_args()
    
    if args.csv:
        data = load_from_csv(args.csv)
    elif args.json:
        data = load_from_json(args.json)
    elif args.excel:
        data = load_from_excel(args.excel)
    elif args.stdin:
        data = load_from_stdin()
    else:
        parser.print_help()
        sys.exit(1)
    
    if not data:
        print("Error: No se encontraron datos válidos")
        sys.exit(1)
    
    print(f"Se encontraron {len(data)} registros para procesar")
    
    if args.dry_run:
        print("\n=== MODO DRY RUN (no se harán cambios) ===\n")
    
    upsert_park_data(data, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
