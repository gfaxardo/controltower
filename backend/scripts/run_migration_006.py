"""
Script para ejecutar la migración 006 directamente desde Python.

USO:
    python run_migration_006.py
"""

import sys
import os
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def run_migration_006():
    """Ejecuta la migración 006 para crear plan_city_map."""
    init_db_pool()
    
    print("Ejecutando migración 006...")
    print("Creando tabla ops.plan_city_map y agregando columna plan_city_resolved_norm...")
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            # 1. Crear tabla ops.plan_city_map
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ops.plan_city_map (
                    country TEXT NOT NULL,
                    plan_city_raw TEXT NOT NULL,
                    plan_city_norm TEXT NOT NULL,
                    real_city_norm TEXT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    notes TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (country, plan_city_norm)
                )
            """)
            print("  [1/6] Tabla ops.plan_city_map creada")
            
            # 2. Agregar columna plan_city_resolved_norm
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = 'ops' 
                        AND table_name = 'plan_trips_monthly' 
                        AND column_name = 'plan_city_resolved_norm'
                    ) THEN
                        ALTER TABLE ops.plan_trips_monthly 
                        ADD COLUMN plan_city_resolved_norm TEXT NULL;
                    END IF;
                END $$;
            """)
            print("  [2/6] Columna plan_city_resolved_norm agregada a ops.plan_trips_monthly")
            
            # 3. Crear índices
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_city_map_country_norm ON ops.plan_city_map(country, plan_city_norm)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_city_map_real_norm ON ops.plan_city_map(real_city_norm) WHERE real_city_norm IS NOT NULL")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_plan_trips_resolved_norm ON ops.plan_trips_monthly(plan_city_resolved_norm) WHERE plan_city_resolved_norm IS NOT NULL")
            print("  [3/6] Índices creados")
            
            # 4. Crear función para updated_at
            cursor.execute("""
                CREATE OR REPLACE FUNCTION ops.update_plan_city_map_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)
            print("  [4/6] Función update_plan_city_map_updated_at creada")
            
            # 5. Crear trigger
            cursor.execute("""
                DROP TRIGGER IF EXISTS trigger_plan_city_map_updated_at ON ops.plan_city_map;
                CREATE TRIGGER trigger_plan_city_map_updated_at
                BEFORE UPDATE ON ops.plan_city_map
                FOR EACH ROW
                EXECUTE FUNCTION ops.update_plan_city_map_updated_at();
            """)
            print("  [5/6] Trigger creado")
            
            # 6. Agregar comentarios
            cursor.execute("""
                COMMENT ON TABLE ops.plan_city_map IS 
                'Diccionario de mapeo de ciudades: Plan (city_norm) -> Real (city_norm). Permite resolver diferencias de nombres entre Plan y Real.';
            """)
            cursor.execute("""
                COMMENT ON COLUMN ops.plan_trips_monthly.plan_city_resolved_norm IS 
                'City normalizado resuelto desde plan_city_map.real_city_norm (si existe). Usado para matching con Real.';
            """)
            print("  [6/6] Comentarios agregados")
            
            conn.commit()
            
            print("\n✓ Migración 006 completada exitosamente\n")
            
            print("Tablas creadas:")
            print("  - ops.plan_city_map")
            
            print("\nColumnas agregadas:")
            print("  - ops.plan_trips_monthly.plan_city_resolved_norm")
            
            cursor.close()
            
        except Exception as e:
            conn.rollback()
            print(f"\n[ERROR] Error ejecutando migración: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    run_migration_006()
