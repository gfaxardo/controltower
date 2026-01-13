from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()
with get_db() as conn:
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'trips_all' 
        ORDER BY ordinal_position
    """)
    cols = cursor.fetchall()
    print("\nColumnas en trips_all:")
    print("-" * 60)
    for c in cols:
        print(f"{c['column_name']:<40} {c['data_type']}")
    cursor.close()
