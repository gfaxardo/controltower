from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    tables = [
        ("public.trips_2026", "Raw trips"),
        ("ops.real_business_slice_day_fact", "Day fact"),
        ("ops.real_business_slice_week_fact", "Week fact"),
        ("ops.real_business_slice_month_fact", "Month fact"),
        ("ops.v_real_trips_enriched_base", "Enriched base"),
        ("ops.v_real_trips_business_slice_resolved", "Resolved view"),
    ]
    
    for tbl, desc in tables:
        try:
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema || '.' || table_name = '{tbl.split('.')[1]}'
                  AND table_schema = '{tbl.split('.')[0]}'
                ORDER BY ordinal_position
            """)
            cols = cur.fetchall()
            if cols:
                print(f"\n=== {desc}: {tbl} ===")
                for c in cols:
                    print(f"  {c['column_name']} ({c['data_type']})")
        except Exception as e:
            # Try without schema prefix
            parts = tbl.split(".")
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = %s
                ORDER BY ordinal_position
            """, (parts[1], parts[0]))
            cols = cur.fetchall()
            if cols:
                print(f"\n=== {desc}: {tbl} ===")
                for c in cols:
                    print(f"  {c['column_name']} ({c['data_type']})")
    
    cur.close()
