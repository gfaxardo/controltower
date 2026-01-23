#!/usr/bin/env python3
"""
Script para crear un índice único en la vista materializada ops.mv_real_trips_monthly.
Analiza los duplicados y propone la mejor solución.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def check_duplicates_with_park_id(conn):
    """Verifica si hay duplicados incluso con park_id"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # Verificar duplicados con park_id
    cursor.execute("""
        SELECT 
            month,
            country,
            city_norm,
            park_id,
            lob_base,
            segment,
            COUNT(*) as count
        FROM ops.mv_real_trips_monthly
        GROUP BY month, country, city_norm, park_id, lob_base, segment
        HAVING COUNT(*) > 1
        LIMIT 5;
    """)
    duplicates = cursor.fetchall()
    
    if duplicates:
        print("ADVERTENCIA: Aun hay duplicados con park_id:")
        for dup in duplicates:
            print(f"  - {dup['month']} | {dup['country']} | {dup['city_norm']} | park_id={dup['park_id']} | {dup['lob_base']} | {dup['segment']} ({dup['count']} veces)")
        
        # Ver detalles de un duplicado
        if duplicates:
            first = duplicates[0]
            cursor.execute("""
                SELECT 
                    month, country, city_norm, park_id, lob_base, segment,
                    trips_real_completed, active_drivers_real, refreshed_at
                FROM ops.mv_real_trips_monthly
                WHERE month = %s
                AND country = %s
                AND city_norm = %s
                AND park_id = %s
                AND lob_base = %s
                AND segment = %s
                ORDER BY refreshed_at DESC;
            """, (first['month'], first['country'], first['city_norm'], 
                  first['park_id'], first['lob_base'], first['segment']))
            
            dup_rows = cursor.fetchall()
            print(f"\nDetalles de las {len(dup_rows)} filas duplicadas:")
            for i, row in enumerate(dup_rows, 1):
                print(f"  Fila {i}: trips={row['trips_real_completed']}, drivers={row['active_drivers_real']}, refreshed={row['refreshed_at']}")
        
        cursor.close()
        return True
    else:
        cursor.close()
        return False

def create_unique_index_with_park_id(conn):
    """Crea índice único incluyendo park_id"""
    cursor = conn.cursor()
    try:
        print("\nCreando indice unico con park_id...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_unique
            ON ops.mv_real_trips_monthly(month, country, city_norm, park_id, lob_base, segment);
        """)
        conn.commit()
        print("[OK] Indice unico creado exitosamente")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] No se pudo crear el indice: {error_msg}")
        conn.rollback()
        return False

def create_unique_index_with_all_dims(conn):
    """Crea índice único con todas las dimensiones"""
    cursor = conn.cursor()
    try:
        print("\nCreando indice unico con todas las dimensiones...")
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_real_trips_monthly_unique
            ON ops.mv_real_trips_monthly(month, country, city, city_norm, park_id, lob_base, segment);
        """)
        conn.commit()
        print("[OK] Indice unico creado exitosamente")
        return True
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] No se pudo crear el indice: {error_msg}")
        conn.rollback()
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Crear indice unico en vista materializada')
    parser.add_argument('--force', action='store_true',
                       help='Forzar creacion incluso si hay duplicados (no recomendado)')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("CREACION DE INDICE UNICO: ops.mv_real_trips_monthly")
    print("=" * 80)
    
    init_db_pool()
    
    try:
        with get_db() as conn:
            # Verificar duplicados
            print("\n1. Verificando duplicados...")
            has_duplicates = check_duplicates_with_park_id(conn)
            
            if has_duplicates and not args.force:
                print("\n" + "=" * 80)
                print("NO SE PUEDE CREAR INDICE UNICO")
                print("=" * 80)
                print("\nHay duplicados incluso con park_id.")
                print("Esto indica un problema en la definicion de la vista materializada.")
                print("\nOpciones:")
                print("1. Revisar la definicion de la vista materializada")
                print("2. Verificar si hay problemas en public.trips_all")
                print("3. Usar --force para intentar crear el indice (fallara)")
                return 1
            
            # Intentar crear índice con park_id primero
            print("\n2. Intentando crear indice unico con park_id...")
            success = create_unique_index_with_park_id(conn)
            
            if not success:
                print("\n3. Intentando crear indice unico con todas las dimensiones...")
                success = create_unique_index_with_all_dims(conn)
            
            if success:
                print("\n" + "=" * 80)
                print("INDICE UNICO CREADO EXITOSAMENTE")
                print("=" * 80)
                print("\nAhora puedes usar REFRESH MATERIALIZED VIEW CONCURRENTLY")
                return 0
            else:
                print("\n" + "=" * 80)
                print("NO SE PUDO CREAR EL INDICE UNICO")
                print("=" * 80)
                print("\nNecesitas resolver los duplicados primero.")
                return 1
                
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
