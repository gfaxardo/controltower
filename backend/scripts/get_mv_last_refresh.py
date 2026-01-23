#!/usr/bin/env python3
"""
Script simple para obtener la última actualización de la vista materializada.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def main():
    init_db_pool()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Verificar si existe columna refreshed_at
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns
                WHERE table_schema = 'ops'
                AND table_name = 'mv_real_trips_monthly'
                AND column_name = 'refreshed_at';
            """)
            has_refreshed_at = cursor.fetchone() is not None
            
            if has_refreshed_at:
                # Obtener el máximo refreshed_at
                cursor.execute("""
                    SELECT 
                        MAX(refreshed_at) as last_refresh,
                        MIN(refreshed_at) as first_refresh,
                        COUNT(DISTINCT refreshed_at) as distinct_refreshes
                    FROM ops.mv_real_trips_monthly;
                """)
                refresh_info = cursor.fetchone()
                if refresh_info:
                    print(f"ULTIMA ACTUALIZACION: {refresh_info['last_refresh']}")
                    print(f"Primera actualizacion: {refresh_info['first_refresh']}")
                    print(f"Numero de refreshes: {refresh_info['distinct_refreshes']}")
            else:
                # Si no tiene refreshed_at, verificar el último mes con datos
                cursor.execute("""
                    SELECT 
                        MAX(month) as last_month,
                        COUNT(*) as rows_in_last_month
                    FROM ops.mv_real_trips_monthly;
                """)
                month_info = cursor.fetchone()
                if month_info:
                    print(f"La vista NO tiene columna 'refreshed_at'")
                    print(f"Ultimo mes con datos: {month_info['last_month']}")
                    print(f"Registros en ultimo mes: {month_info['rows_in_last_month']:,}")
                    print("\nNOTA: Para conocer la ultima actualizacion exacta, ejecuta:")
                    print("  REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;")
                    print("  Y luego consulta la columna refreshed_at (si existe)")
            
            cursor.close()
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
