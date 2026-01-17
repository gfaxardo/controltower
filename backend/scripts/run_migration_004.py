"""Script para ejecutar la migración 004 directamente."""
import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def run_migration():
    init_db_pool()
    
    sql_statements = [
        # 1. Agregar columna city_norm
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = 'ops' 
                AND table_name = 'plan_trips_monthly' 
                AND column_name = 'city_norm'
            ) THEN
                ALTER TABLE ops.plan_trips_monthly 
                ADD COLUMN city_norm TEXT;
                
                UPDATE ops.plan_trips_monthly
                SET city_norm = LOWER(TRIM(COALESCE(city, '')));
            END IF;
        END $$;
        """,
        
        # 2. Eliminar constraint UNIQUE antiguo
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conname = 'plan_trips_monthly_unique'
                AND conrelid = 'ops.plan_trips_monthly'::regclass
            ) THEN
                ALTER TABLE ops.plan_trips_monthly 
                DROP CONSTRAINT plan_trips_monthly_unique;
            END IF;
        END $$;
        """,
        
        # 3. Crear nuevo índice UNIQUE que maneja park_id NULL
        "DROP INDEX IF EXISTS ops.plan_trips_monthly_unique_idx",
        """
        CREATE UNIQUE INDEX plan_trips_monthly_unique_idx ON ops.plan_trips_monthly (
            plan_version,
            COALESCE(country, ''),
            COALESCE(city, ''),
            COALESCE(park_id, '__NA__'),
            COALESCE(lob_base, ''),
            COALESCE(segment, ''),
            month
        )
        """,
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("Ejecutando migración 004...")
            for i, sql in enumerate(sql_statements, 1):
                cursor.execute(sql)
                print(f"  [{i}/{len(sql_statements)}] Ejecutado correctamente")
            conn.commit()
            print("\n✓ Migración 004 completada exitosamente")
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    run_migration()
