#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()
conn = get_db().__enter__()
cursor = conn.cursor(cursor_factory=RealDictCursor)

# Obtener columnas directamente de la vista
cursor.execute("SELECT * FROM ops.mv_real_trips_monthly LIMIT 1")
if cursor.description:
    cols = [desc[0] for desc in cursor.description]
    print(f"Columnas encontradas: {len(cols)}")
    for i, c in enumerate(cols, 1):
        print(f"  {i}. {c}")
    
    # Verificar si tiene refreshed_at
    if 'refreshed_at' in cols:
        cursor.execute("SELECT MAX(refreshed_at) as last_refresh FROM ops.mv_real_trips_monthly")
        result = cursor.fetchone()
        if result and result['last_refresh']:
            print(f"\nULTIMA ACTUALIZACION: {result['last_refresh']}")
    else:
        print("\nLa vista NO tiene columna 'refreshed_at'")

cursor.close()
conn.close()
