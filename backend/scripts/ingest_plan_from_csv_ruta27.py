"""
Script para ingesta de Plan desde CSV Ruta 27 (formato real).

USO:
    python ingest_plan_from_csv_ruta27.py <csv_path> <plan_version>

El CSV tiene formato:
country,city,lob_base,segment,year,month,trips_plan,active_drivers_plan,avg_ticket_plan,revenue_plan,trips_per_driver_plan
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

def check_version_exists(plan_version: str, cursor) -> bool:
    """Verifica si la versión ya existe."""
    cursor.execute("SELECT COUNT(*) FROM ops.plan_trips_monthly WHERE plan_version = %s", (plan_version,))
    return cursor.fetchone()[0] > 0

def generate_unique_version(base_version: str, cursor) -> str:
    """Genera una versión única agregando sufijo numérico."""
    suffix = 2
    while True:
        new_version = f"{base_version}{suffix}"
        if not check_version_exists(new_version, cursor):
            return new_version
        suffix += 1

def ingest_plan_from_csv(csv_path: str, plan_version: str):
    """Ingiere plan desde CSV usando el formato real de Ruta 27."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Verificar que la tabla existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'ops' 
                    AND table_name = 'plan_trips_monthly'
                )
            """)
            if not cursor.fetchone()[0]:
                raise Exception("Tabla ops.plan_trips_monthly no existe. Ejecuta migración primero.")
            
            # Verificar si la versión ya existe
            final_version = plan_version
            if check_version_exists(plan_version, cursor):
                print(f"[WARN] Versión {plan_version} ya existe. Generando versión única...")
                final_version = generate_unique_version(plan_version, cursor)
                print(f"[INFO] Usando versión: {final_version}")
            
            # Validar archivo
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"Archivo CSV no encontrado: {csv_path}")
            
            # Leer CSV y validar columnas
            print(f"Cargando CSV: {csv_path}")
            inserted_count = 0
            errors = []
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Validar columnas (is_applicable es opcional)
                expected_cols = ['country', 'city', 'lob_base', 'segment', 'year', 'month', 
                                'trips_plan', 'active_drivers_plan', 'avg_ticket_plan']
                missing_cols = [col for col in expected_cols if col not in reader.fieldnames]
                if missing_cols:
                    raise Exception(f"CSV faltan columnas: {missing_cols}")
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Validar segment
                        segment = row.get('segment', '').strip().lower()
                        if segment not in ('b2b', 'b2c'):
                            errors.append(f"Fila {row_num}: segment inválido '{segment}' (debe ser b2b o b2c)")
                            continue
                        
                        # Construir month desde year y month
                        year = int(row.get('year', 0))
                        month_num = int(row.get('month', 0))
                        if year < 2000 or year > 2100 or month_num < 1 or month_num > 12:
                            errors.append(f"Fila {row_num}: year/month inválido ({year}/{month_num})")
                            continue
                        
                        month_date = datetime(year, month_num, 1).date()
                        
                        # Mapear columnas
                        country = row.get('country', '').strip() or None
                        city = row.get('city', '').strip() or None
                        city_norm = city.lower().strip() if city else None
                        park_id = None  # CSV no tiene park_id
                        lob_base = row.get('lob_base', '').strip() or None
                        
                        # Verificar is_applicable (opcional, default TRUE)
                        is_applicable_str = row.get('is_applicable', '').strip().upper()
                        is_applicable = True  # default
                        if is_applicable_str:
                            is_applicable = is_applicable_str in ('TRUE', '1', 'YES', 'Y', 'T')
                        
                        # Si no es aplicable, saltar esta fila
                        if not is_applicable:
                            continue
                        
                        # Resolver city_norm usando plan_city_map
                        plan_city_resolved_norm = None
                        if country and city_norm:
                            cursor.execute("""
                                SELECT real_city_norm
                                FROM ops.plan_city_map
                                WHERE country = %s
                                AND plan_city_norm = %s
                                AND is_active = TRUE
                                AND real_city_norm IS NOT NULL
                            """, (country, city_norm))
                            result = cursor.fetchone()
                            if result:
                                plan_city_resolved_norm = result[0]
                        
                        # Mapear métricas (convertir float a int si es necesario)
                        trips_plan = row.get('trips_plan', '').strip()
                        projected_trips = int(float(trips_plan)) if trips_plan else None
                        
                        active_drivers_plan = row.get('active_drivers_plan', '').strip()
                        projected_drivers = int(float(active_drivers_plan)) if active_drivers_plan else None
                        
                        avg_ticket_plan = row.get('avg_ticket_plan', '').strip()
                        projected_ticket = float(avg_ticket_plan) if avg_ticket_plan else None
                        
                        # Insertar (incluyendo plan_city_resolved_norm si existe)
                        cursor.execute("""
                            INSERT INTO ops.plan_trips_monthly (
                                plan_version,
                                country,
                                city,
                                city_norm,
                                plan_city_resolved_norm,
                                park_id,
                                lob_base,
                                segment,
                                month,
                                projected_trips,
                                projected_drivers,
                                projected_ticket
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (plan_version, COALESCE(country, ''), COALESCE(city, ''), 
                                        COALESCE(park_id, '__NA__'), COALESCE(lob_base, ''), 
                                        COALESCE(segment, ''), month) 
                            DO NOTHING
                        """, (
                            final_version,
                            country,
                            city,
                            city_norm,
                            plan_city_resolved_norm,
                            park_id,
                            lob_base,
                            segment,
                            month_date,
                            projected_trips,
                            projected_drivers,
                            projected_ticket
                        ))
                        inserted_count += 1
                        
                    except Exception as e:
                        errors.append(f"Fila {row_num}: {str(e)}")
                        continue
            
            # Mostrar resultados
            print("\n" + "="*60)
            print("INGESTA COMPLETADA")
            print("="*60)
            print(f"Plan Version: {final_version}")
            print(f"Registros insertados: {inserted_count:,}")
            if errors:
                print(f"\nErrores encontrados: {len(errors)}")
                for error in errors[:10]:
                    print(f"  - {error}")
                if len(errors) > 10:
                    print(f"  ... y {len(errors) - 10} más")
            
            conn.commit()
            return final_version, inserted_count
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error durante la ingesta: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("USO: python ingest_plan_from_csv_ruta27.py <csv_path> <plan_version>")
        print("EJEMPLO: python ingest_plan_from_csv_ruta27.py ruta27.csv ruta27_v2026_01_16_a")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    plan_version = sys.argv[2]
    
    final_version, count = ingest_plan_from_csv(csv_path, plan_version)
    print(f"\n✓ Ingesta completada: {count} registros con versión {final_version}")
