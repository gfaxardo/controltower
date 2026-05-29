from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='ops' AND (table_name LIKE '%lifecycle%' OR table_name LIKE '%mv_driver%') ORDER BY table_name")
    print("=== TABLES ===")
    for r in c.fetchall():
        print(r["table_name"])
    
    c.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='ops' AND table_name='mv_driver_lifecycle_base' ORDER BY ordinal_position")
    print("\n=== COLS ===")
    for r in c.fetchall():
        print(f"  {r['column_name']} ({r['data_type']})")
    
    c.execute("SELECT count(*) as cnt FROM ops.mv_driver_lifecycle_base")
    print(f"\nROWS: {c.fetchone()['cnt']}")
    
    c.execute("SELECT * FROM ops.mv_driver_lifecycle_base LIMIT 1")
    row = c.fetchone()
    if row:
        print(f"SAMPLE: {dict(row)}")
    else:
        print("EMPTY")
