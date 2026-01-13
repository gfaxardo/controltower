import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def inspect_dim_park():
    init_db_pool()
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'dim' AND table_name = 'dim_park'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        
        print("=== Estructura de dim.dim_park ===\n")
        for col in columns:
            nullable = "NULL" if col[2] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col[3]}" if col[3] else ""
            print(f"{col[0]}: {col[1]} {nullable}{default}")
        
        # Get sample data
        cursor.execute("SELECT * FROM dim.dim_park LIMIT 5")
        sample_rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        
        print("\n=== Datos de muestra (primeros 5 registros) ===\n")
        if sample_rows:
            print(" | ".join(col_names))
            print("-" * 80)
            for row in sample_rows:
                print(" | ".join(str(val) if val is not None else "NULL" for val in row))
        else:
            print("(No hay datos)")
        
        # Count total
        cursor.execute("SELECT COUNT(*) FROM dim.dim_park")
        total = cursor.fetchone()[0]
        print(f"\n=== Total de registros: {total} ===\n")
        
        cursor.close()

if __name__ == "__main__":
    inspect_dim_park()
