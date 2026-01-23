#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()
conn = get_db().__enter__()
cursor = conn.cursor(cursor_factory=RealDictCursor)

cursor.execute("SELECT definition FROM pg_matviews WHERE schemaname='ops' AND matviewname='mv_real_trips_monthly'")
result = cursor.fetchone()

if result:
    definition = result['definition']
    print("DEFINICION DE LA VISTA MATERIALIZADA:")
    print("=" * 80)
    # Buscar el GROUP BY para ver cómo se agrega
    if 'GROUP BY' in definition.upper():
        idx = definition.upper().find('GROUP BY')
        print("GROUP BY encontrado en la definicion:")
        print(definition[idx:idx+500])
    else:
        print("No se encontro GROUP BY en la definicion")
        print(definition[:1000])

cursor.close()
conn.close()
