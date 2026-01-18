"""
Script de prueba para verificar formato de CSV antes de ingesta
"""

import sys
import os
import csv

if len(sys.argv) < 2:
    print("USO: python test_csv_ingestion.py <csv_path>")
    sys.exit(1)

csv_path = sys.argv[1]

print("=" * 70)
print("VERIFICACION DE CSV PARA INGESTA")
print("=" * 70)

if not os.path.exists(csv_path):
    print(f"[ERROR] Archivo no encontrado: {csv_path}")
    sys.exit(1)

print(f"\nArchivo: {csv_path}")

# Leer CSV
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    
    print(f"\nColumnas encontradas: {reader.fieldnames}")
    
    # Columnas esperadas
    expected_cols = ['country', 'city', 'lob_base', 'segment', 'year', 'month', 
                    'trips_plan', 'active_drivers_plan', 'avg_ticket_plan']
    missing_cols = [col for col in expected_cols if col not in reader.fieldnames]
    
    if missing_cols:
        print(f"\n[ERROR] Faltan columnas: {missing_cols}")
    else:
        print("[OK] Todas las columnas requeridas presentes")
    
    has_revenue_plan = 'revenue_plan' in reader.fieldnames
    print(f"[INFO] revenue_plan presente: {'SI' if has_revenue_plan else 'NO'}")
    
    # Leer primeras filas
    print("\nPrimeras 3 filas del CSV:")
    row_count = 0
    valid_rows = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        if row_num > 4:  # Solo primeras 3
            break
        
        row_count += 1
        print(f"\nFila {row_num}:")
        print(f"  country: '{row.get('country', '')}'")
        print(f"  city: '{row.get('city', '')}'")
        print(f"  lob_base: '{row.get('lob_base', '')}'")
        print(f"  segment: '{row.get('segment', '')}'")
        print(f"  year: '{row.get('year', '')}'")
        print(f"  month: '{row.get('month', '')}'")
        print(f"  trips_plan: '{row.get('trips_plan', '')}'")
        print(f"  active_drivers_plan: '{row.get('active_drivers_plan', '')}'")
        print(f"  avg_ticket_plan: '{row.get('avg_ticket_plan', '')}'")
        if has_revenue_plan:
            print(f"  revenue_plan: '{row.get('revenue_plan', '')}'")
        
        # Validar fila
        segment = row.get('segment', '').strip().lower()
        if segment not in ('b2b', 'b2c'):
            errors.append(f"Fila {row_num}: segment invalido '{segment}'")
        
        try:
            year = int(row.get('year', 0))
            month = int(row.get('month', 0))
            if year < 2000 or year > 2100 or month < 1 or month > 12:
                errors.append(f"Fila {row_num}: year/month invalido ({year}/{month})")
        except:
            errors.append(f"Fila {row_num}: year/month no numerico")
    
    # Contar total de filas
    print(f"\n[INFO] Filas revisadas: {row_count}")
    
    if errors:
        print(f"\n[ERRORES ENCONTRADOS]:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("\n[OK] Primeras filas parecen validas")
