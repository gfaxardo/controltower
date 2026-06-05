from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT table_schema, table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema IN ('public', 'ops')
          AND table_name IN ('trips_2026', 'real_business_slice_day_fact',
                             'real_business_slice_week_fact', 'real_business_slice_month_fact',
                             'v_real_trips_enriched_base', 'v_real_trips_business_slice_resolved')
        ORDER BY table_schema, table_name, ordinal_position
    """)
    
    current = None
    for r in cur.fetchall():
        key = f"{r['table_schema']}.{r['table_name']}"
        if key != current:
            current = key
            print(f"\n{key}:")
        print(f"  {r['column_name']} ({r['data_type']})")
    
    cur.close()
