"""
Script para ejecutar la migración 003 directamente.

Ejecuta: python scripts/run_migration_003.py
"""

import sys
import os
import io

# Configurar codificación UTF-8 para salida
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def run_migration():
    """Ejecuta la migración 003."""
    init_db_pool()
    
    sql_statements = [
        # Asegurar que existe el esquema ops
        "CREATE SCHEMA IF NOT EXISTS ops",
        
        # Crear tabla canónica
        """
        DROP TABLE IF EXISTS ops.plan_trips_monthly CASCADE;
        CREATE TABLE ops.plan_trips_monthly (
            id BIGSERIAL PRIMARY KEY,
            plan_version TEXT NOT NULL,
            country TEXT,
            city TEXT,
            park_id TEXT,
            lob_base TEXT,
            segment TEXT CHECK (segment IN ('b2b', 'b2c')),
            month DATE NOT NULL,
            projected_trips INTEGER,
            projected_drivers INTEGER,
            projected_ticket NUMERIC,
            projected_trips_per_driver NUMERIC GENERATED ALWAYS AS (
                CASE 
                    WHEN projected_drivers > 0 THEN projected_trips::NUMERIC / projected_drivers
                    ELSE NULL
                END
            ) STORED,
            projected_revenue NUMERIC GENERATED ALWAYS AS (
                CASE
                    WHEN projected_trips IS NOT NULL AND projected_ticket IS NOT NULL 
                    THEN projected_trips::NUMERIC * projected_ticket
                    ELSE NULL
                END
            ) STORED,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT plan_trips_monthly_unique 
                UNIQUE (plan_version, country, city, park_id, lob_base, segment, month)
        )
        """,
        
        # Crear índices
        "CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_version ON ops.plan_trips_monthly(plan_version)",
        "CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_month ON ops.plan_trips_monthly(month)",
        "CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_park ON ops.plan_trips_monthly(park_id)",
        "CREATE INDEX IF NOT EXISTS idx_plan_trips_monthly_country_city_lob ON ops.plan_trips_monthly(country, city, lob_base)",
        
        # Crear vista v_plan_trips_monthly
        """
        DROP VIEW IF EXISTS ops.v_plan_trips_monthly CASCADE;
        CREATE VIEW ops.v_plan_trips_monthly AS
        SELECT 
            plan_version,
            country,
            city,
            park_id,
            lob_base,
            segment,
            month,
            projected_trips,
            projected_drivers,
            projected_ticket,
            projected_trips_per_driver,
            projected_revenue,
            created_at
        FROM ops.plan_trips_monthly
        ORDER BY plan_version DESC, month, country, city, lob_base, segment
        """,
        
        # Crear vista v_plan_trips_daily_equivalent
        """
        DROP VIEW IF EXISTS ops.v_plan_trips_daily_equivalent CASCADE;
        CREATE VIEW ops.v_plan_trips_daily_equivalent AS
        SELECT 
            plan_version,
            country,
            city,
            park_id,
            lob_base,
            segment,
            month,
            projected_trips,
            projected_drivers,
            projected_ticket,
            projected_trips_per_driver,
            projected_revenue,
            CASE 
                WHEN projected_trips IS NOT NULL 
                THEN projected_trips::NUMERIC / EXTRACT(DAY FROM (DATE_TRUNC('month', month) + INTERVAL '1 month - 1 day')::DATE)
                ELSE NULL
            END AS projected_trips_daily,
            CASE 
                WHEN projected_revenue IS NOT NULL 
                THEN projected_revenue::NUMERIC / EXTRACT(DAY FROM (DATE_TRUNC('month', month) + INTERVAL '1 month - 1 day')::DATE)
                ELSE NULL
            END AS projected_revenue_daily,
            EXTRACT(DAY FROM (DATE_TRUNC('month', month) + INTERVAL '1 month - 1 day')::DATE) AS days_in_month,
            created_at
        FROM ops.plan_trips_monthly
        ORDER BY plan_version DESC, month, country, city, lob_base, segment
        """,
        
        # Crear vista v_plan_kpis_monthly
        """
        DROP VIEW IF EXISTS ops.v_plan_kpis_monthly CASCADE;
        CREATE VIEW ops.v_plan_kpis_monthly AS
        SELECT 
            plan_version,
            country,
            city,
            park_id,
            lob_base,
            segment,
            month,
            projected_trips AS kpi_trips,
            projected_drivers AS kpi_drivers,
            projected_revenue AS kpi_revenue,
            projected_trips_per_driver AS kpi_productivity_required,
            projected_ticket AS kpi_ticket_avg,
            CASE 
                WHEN projected_drivers > 0 
                THEN projected_trips::NUMERIC / projected_drivers
                ELSE NULL
            END AS kpi_trips_per_driver,
            created_at
        FROM ops.plan_trips_monthly
        ORDER BY plan_version DESC, month, country, city, lob_base, segment
        """,
        
        # Crear tabla de validación
        """
        DROP TABLE IF EXISTS ops.plan_validation_results CASCADE;
        CREATE TABLE ops.plan_validation_results (
            id BIGSERIAL PRIMARY KEY,
            plan_version TEXT NOT NULL,
            validation_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            validation_type TEXT NOT NULL CHECK (validation_type IN ('orphan_plan', 'orphan_real', 'missing_combo')),
            country TEXT,
            city TEXT,
            park_id TEXT,
            lob_base TEXT,
            segment TEXT,
            month DATE,
            severity TEXT CHECK (severity IN ('error', 'warning', 'info')),
            message TEXT,
            row_count BIGINT
        )
        """,
        
        # Crear índices para validaciones
        "CREATE INDEX IF NOT EXISTS idx_plan_validation_version ON ops.plan_validation_results(plan_version, validation_date)",
        "CREATE INDEX IF NOT EXISTS idx_plan_validation_type ON ops.plan_validation_results(validation_type, severity)",
    ]
    
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            print("Ejecutando migración 003...")
            
            for i, sql in enumerate(sql_statements, 1):
                try:
                    cursor.execute(sql)
                    print(f"  [{i}/{len(sql_statements)}] Ejecutado correctamente")
                except Exception as e:
                    # Si la tabla/vista ya existe, continuar
                    if "already exists" in str(e).lower() or "does not exist" in str(e).lower():
                        print(f"  [{i}/{len(sql_statements)}] Advertencia: {str(e)[:100]}")
                    else:
                        raise
            
            conn.commit()
            print("\n✓ Migración 003 completada exitosamente")
            print("\nTablas y vistas creadas:")
            print("  - ops.plan_trips_monthly")
            print("  - ops.v_plan_trips_monthly")
            print("  - ops.v_plan_trips_daily_equivalent")
            print("  - ops.v_plan_kpis_monthly")
            print("  - ops.plan_validation_results")
            
        except Exception as e:
            conn.rollback()
            print(f"\n✗ Error durante la migración: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            cursor.close()

if __name__ == "__main__":
    run_migration()
