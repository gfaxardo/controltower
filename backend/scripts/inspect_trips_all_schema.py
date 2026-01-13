import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def inspect_trips_all():
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_all'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        print("=== Estructura de public.trips_all ===\n")
        for col in columns:
            nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
            print(f"{col[0]}: {col[1]} {nullable}")
        
        # Check specific columns
        col_names = [col[0] for col in columns]
        print("\n=== Columnas relevantes detectadas ===")
        print(f"id: {'✓' if 'id' in col_names else '✗'}")
        print(f"codigo_pedido: {'✓' if 'codigo_pedido' in col_names else '✗'}")
        print(f"park_id: {'✓' if 'park_id' in col_names else '✗'}")
        print(f"fecha_inicio_viaje: {'✓' if 'fecha_inicio_viaje' in col_names else '✗'}")
        print(f"created_at: {'✓' if 'created_at' in col_names else '✗'}")
        
        # Sample data
        cursor.execute("SELECT id, codigo_pedido, park_id, fecha_inicio_viaje, created_at FROM public.trips_all LIMIT 3")
        sample_rows = cursor.fetchall()
        
        print("\n=== Datos de muestra ===")
        if sample_rows:
            for i, row in enumerate(sample_rows, 1):
                print(f"\nRegistro {i}:")
                print(f"  id: {row[0]}")
                print(f"  codigo_pedido: {row[1]}")
                print(f"  park_id: {row[2]}")
                print(f"  fecha_inicio_viaje: {row[3]}")
                print(f"  created_at: {row[4]}")
        
        cursor.close()

if __name__ == "__main__":
    inspect_trips_all()
