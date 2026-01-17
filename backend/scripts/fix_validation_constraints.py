"""Script para actualizar constraints de validación."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def fix_constraints():
    init_db_pool()
    
    sql_statements = [
        # Eliminar constraints antiguos
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conrelid = 'ops.plan_validation_results'::regclass
                AND conname LIKE '%validation_type%'
            ) THEN
                ALTER TABLE ops.plan_validation_results 
                DROP CONSTRAINT plan_validation_results_validation_type_check;
            END IF;
            
            IF EXISTS (
                SELECT 1 FROM pg_constraint 
                WHERE conrelid = 'ops.plan_validation_results'::regclass
                AND conname LIKE '%severity%'
            ) THEN
                ALTER TABLE ops.plan_validation_results 
                DROP CONSTRAINT plan_validation_results_severity_check;
            END IF;
        END $$;
        """,
        
        # Crear nuevos constraints con tipos adicionales
        """
        ALTER TABLE ops.plan_validation_results
        ADD CONSTRAINT plan_validation_results_validation_type_check
        CHECK (validation_type IN (
            'orphan_plan', 'orphan_real', 'missing_combo',
            'duplicate_plan', 'invalid_segment', 'invalid_month', 
            'invalid_metrics', 'city_mismatch'
        ));
        """,
        
        """
        ALTER TABLE ops.plan_validation_results
        ADD CONSTRAINT plan_validation_results_severity_check
        CHECK (severity IN ('error', 'warning', 'info'));
        """,
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("Actualizando constraints de validación...")
            for i, sql in enumerate(sql_statements, 1):
                cursor.execute(sql)
                print(f"  [{i}/{len(sql_statements)}] Ejecutado correctamente")
            conn.commit()
            print("\n[OK] Constraints actualizados exitosamente")
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    fix_constraints()
