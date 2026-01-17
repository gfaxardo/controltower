"""
Script para ingesta de Plan desde CSV Ruta 27.

USO:
    python ingest_plan_from_csv.py <csv_path> <plan_version>

EJEMPLO:
    python ingest_plan_from_csv.py ruta27_proyeccion.csv ruta27_v1
"""

import sys
import os
import io

# Configurar codificación UTF-8 para salida
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
import csv

def ingest_plan_from_csv(csv_path: str, plan_version: str):
    """Ingiere plan desde CSV usando COPY."""
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # Validar que el archivo existe
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"Archivo CSV no encontrado: {csv_path}")
            
            # Verificar que la tabla existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'ops' 
                    AND table_name = 'plan_trips_monthly'
                )
            """)
            if not cursor.fetchone()[0]:
                raise Exception("Tabla ops.plan_trips_monthly no existe. Ejecuta migración Alembic primero.")
            
            # Crear tabla temporal staging
            cursor.execute("""
                DROP TABLE IF EXISTS ops.stg_plan_trips_monthly;
                CREATE TEMP TABLE ops.stg_plan_trips_monthly (
                    country TEXT,
                    city TEXT,
                    park_id TEXT,
                    lob_base TEXT,
                    segment TEXT,
                    month TEXT,
                    projected_trips INTEGER,
                    projected_drivers INTEGER,
                    projected_ticket NUMERIC
                )
            """)
            
            # Leer CSV y cargar en staging
            print(f"Cargando CSV: {csv_path}")
            inserted_staging = 0
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        cursor.execute("""
                            INSERT INTO ops.stg_plan_trips_monthly (
                                country, city, park_id, lob_base, segment, 
                                month, projected_trips, projected_drivers, projected_ticket
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            row.get('country', '').strip() if row.get('country') else None,
                            row.get('city', '').strip() if row.get('city') else None,
                            row.get('park_id', '').strip() if row.get('park_id') else None,
                            row.get('lob_base', '').strip() if row.get('lob_base') else None,
                            row.get('segment', '').strip() if row.get('segment') else None,
                            row.get('month', '').strip() if row.get('month') else None,
                            int(row['projected_trips']) if row.get('projected_trips') and row['projected_trips'].strip() else None,
                            int(row['projected_drivers']) if row.get('projected_drivers') and row['projected_drivers'].strip() else None,
                            float(row['projected_ticket']) if row.get('projected_ticket') and row['projected_ticket'].strip() else None
                        ))
                        inserted_staging += 1
                    except Exception as e:
                        print(f"[WARN] Error procesando fila: {row}, error: {e}")
                        continue
            
            print(f"Registros cargados en staging: {inserted_staging}")
            
            # Validar formato de segment
            cursor.execute("""
                SELECT COUNT(*) FROM ops.stg_plan_trips_monthly
                WHERE segment IS NOT NULL AND segment NOT IN ('b2b', 'b2c')
            """)
            invalid_segments = cursor.fetchone()[0]
            if invalid_segments > 0:
                print(f"[WARN] Se encontraron {invalid_segments} registros con segment inválido (debe ser b2b o b2c)")
            
            # Validar formato de month
            cursor.execute("""
                SELECT COUNT(*) FROM ops.stg_plan_trips_monthly
                WHERE month IS NOT NULL 
                AND month::DATE IS NULL
            """)
            invalid_months = cursor.fetchone()[0]
            if invalid_months > 0:
                raise Exception(f"Se encontraron {invalid_months} registros con month inválido (debe ser formato fecha válido)")
            
            # Insertar en tabla canónica
            cursor.execute(f"""
                INSERT INTO ops.plan_trips_monthly (
                    plan_version,
                    country,
                    city,
                    park_id,
                    lob_base,
                    segment,
                    month,
                    projected_trips,
                    projected_drivers,
                    projected_ticket
                )
                SELECT 
                    '{plan_version}'::TEXT as plan_version,
                    NULLIF(TRIM(country), '') as country,
                    NULLIF(TRIM(city), '') as city,
                    NULLIF(TRIM(park_id), '') as park_id,
                    NULLIF(TRIM(lob_base), '') as lob_base,
                    CASE 
                        WHEN NULLIF(TRIM(segment), '') IN ('b2b', 'b2c') THEN NULLIF(TRIM(segment), '')
                        ELSE NULL
                    END as segment,
                    CASE 
                        WHEN month IS NOT NULL AND month::DATE IS NOT NULL THEN month::DATE
                        ELSE NULL
                    END as month,
                    projected_trips,
                    projected_drivers,
                    projected_ticket
                FROM ops.stg_plan_trips_monthly
                ON CONFLICT (plan_version, country, city, park_id, lob_base, segment, month) 
                DO NOTHING
            """)
            
            # Contar insertados
            cursor.execute(f"""
                SELECT COUNT(*) FROM ops.plan_trips_monthly 
                WHERE plan_version = %s 
                AND created_at >= NOW() - INTERVAL '1 minute'
            """, (plan_version,))
            inserted_count = cursor.fetchone()[0]
            duplicates_count = inserted_staging - inserted_count
            
            print("\n" + "="*60)
            print("INGESTA COMPLETADA")
            print("="*60)
            print(f"Plan Version: {plan_version}")
            print(f"Registros en CSV: {inserted_staging:,}")
            print(f"Registros insertados: {inserted_count:,}")
            print(f"Registros duplicados (ignorados): {duplicates_count:,}")
            print("="*60 + "\n")
            
            conn.commit()
            
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
        print("USO: python ingest_plan_from_csv.py <csv_path> <plan_version>")
        print("EJEMPLO: python ingest_plan_from_csv.py ruta27_proyeccion.csv ruta27_v1")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    plan_version = sys.argv[2]
    
    ingest_plan_from_csv(csv_path, plan_version)
