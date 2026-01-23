#!/usr/bin/env python3
"""
Script para analizar duplicados en la vista materializada ops.mv_real_trips_monthly
y proponer soluciones para crear un índice único.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

def analyze_duplicates(conn):
    """Analiza duplicados en la vista materializada"""
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("ANALISIS DE DUPLICADOS EN ops.mv_real_trips_monthly")
    print("=" * 80)
    
    # 1. Verificar duplicados en la combinación propuesta
    print("\n1. Duplicados en (month, country, city_norm, lob_base, segment):")
    cursor.execute("""
        SELECT 
            month,
            country,
            city_norm,
            lob_base,
            segment,
            COUNT(*) as duplicate_count
        FROM ops.mv_real_trips_monthly
        GROUP BY month, country, city_norm, lob_base, segment
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, month DESC
        LIMIT 20;
    """)
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"   Encontrados {len(duplicates)} grupos con duplicados:")
        for dup in duplicates:
            print(f"   - {dup['month']} | {dup['country']} | {dup['city_norm']} | {dup['lob_base']} | {dup['segment']} ({dup['duplicate_count']} veces)")
        
        # Mostrar detalles de un duplicado específico
        print("\n2. Detalles de un duplicado (primer caso):")
        first_dup = duplicates[0]
        cursor.execute("""
            SELECT *
            FROM ops.mv_real_trips_monthly
            WHERE month = %s
            AND country = %s
            AND city_norm = %s
            AND lob_base = %s
            AND segment = %s
            ORDER BY refreshed_at DESC;
        """, (first_dup['month'], first_dup['country'], first_dup['city_norm'], 
              first_dup['lob_base'], first_dup['segment']))
        
        dup_rows = cursor.fetchall()
        print(f"   Total de filas duplicadas: {len(dup_rows)}")
        for i, row in enumerate(dup_rows, 1):
            print(f"\n   Fila {i}:")
            print(f"   - park_id: {row.get('park_id')}")
            print(f"   - city: {row.get('city')}")
            print(f"   - trips_real_completed: {row.get('trips_real_completed')}")
            print(f"   - active_drivers_real: {row.get('active_drivers_real')}")
            print(f"   - refreshed_at: {row.get('refreshed_at')}")
    else:
        print("   [OK] No se encontraron duplicados en esta combinacion")
    
    # 3. Verificar si agregar park_id resuelve los duplicados
    print("\n3. Verificando si agregar 'park_id' resuelve los duplicados:")
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
        LIMIT 10;
    """)
    dup_with_park = cursor.fetchall()
    
    if dup_with_park:
        print(f"   [ADVERTENCIA] Aun hay {len(dup_with_park)} duplicados incluso con park_id")
        for dup in dup_with_park[:5]:
            print(f"   - {dup['month']} | {dup['country']} | {dup['city_norm']} | park_id={dup['park_id']} | {dup['lob_base']} | {dup['segment']}")
    else:
        print("   [OK] Con park_id no hay duplicados")
    
    # 4. Verificar todas las columnas disponibles
    print("\n4. Columnas disponibles en la vista:")
    cursor.execute("SELECT * FROM ops.mv_real_trips_monthly LIMIT 1")
    if cursor.description:
        cols = [desc[0] for desc in cursor.description]
        print(f"   Total de columnas: {len(cols)}")
        for i, col in enumerate(cols, 1):
            print(f"   {i:2d}. {col}")
    
    # 5. Proponer soluciones
    print("\n" + "=" * 80)
    print("SOLUCIONES PROPUESTAS:")
    print("=" * 80)
    
    if duplicates:
        print("\nOpcion 1: Agregar 'park_id' al indice unico")
        print("   CREATE UNIQUE INDEX idx_mv_real_trips_monthly_unique")
        print("   ON ops.mv_real_trips_monthly(month, country, city_norm, park_id, lob_base, segment);")
        print("   [Ventaja: Incluye park_id que puede diferenciar los duplicados]")
        
        print("\nOpcion 2: Agregar 'city' al indice unico")
        print("   CREATE UNIQUE INDEX idx_mv_real_trips_monthly_unique")
        print("   ON ops.mv_real_trips_monthly(month, country, city, city_norm, lob_base, segment);")
        print("   [Ventaja: Incluye city que puede diferenciar los duplicados]")
        
        print("\nOpcion 3: Usar todas las columnas de dimension")
        print("   CREATE UNIQUE INDEX idx_mv_real_trips_monthly_unique")
        print("   ON ops.mv_real_trips_monthly(month, country, city, city_norm, park_id, lob_base, segment);")
        print("   [Ventaja: Maxima diferenciacion, pero indice mas grande]")
        
        print("\nOpcion 4: Investigar y limpiar duplicados en la fuente")
        print("   [Recomendado si los duplicados son un error de datos]")
        print("   Los duplicados pueden venir de public.trips_all")
        
    else:
        print("\n[OK] No hay duplicados. Puedes crear el indice unico sin problemas.")
    
    cursor.close()

def main():
    init_db_pool()
    
    try:
        with get_db() as conn:
            analyze_duplicates(conn)
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
