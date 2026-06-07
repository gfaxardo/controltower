import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("""
        SELECT queue_status, COUNT(*) as cnt,
               SUM(CASE WHEN phone IS NOT NULL AND phone != '' THEN 1 ELSE 0 END) as has_phone,
               SUM(CASE WHEN assigned_channel != 'UNASSIGNED' THEN 1 ELSE 0 END) as has_channel
        FROM growth.yego_lima_assignment_queue
        WHERE assignment_date = '2026-06-02'
        GROUP BY queue_status
    """)
    for r in cur.fetchall():
        print(f"{r['queue_status']}: {r['cnt']} records, {r['has_phone']} w/ phone, {r['has_channel']} w/ channel")
    
    print()
    cur.execute("""
        SELECT COUNT(*) as exported, COUNT(DISTINCT campaign_id_external) as campaigns
        FROM growth.yego_lima_assignment_queue
        WHERE queue_status = 'EXPORTED'
    """)
    r = cur.fetchone()
    print(f"EXPORTED total: {r['exported']} records across {r['campaigns']} campaigns")
    
    print()
    cur.execute("""
        SELECT assigned_channel, COUNT(*) as cnt
        FROM growth.yego_lima_assignment_queue
        WHERE assignment_date = '2026-06-02' AND queue_status = 'READY'
        GROUP BY assigned_channel ORDER BY cnt DESC
    """)
    print("READY by channel:")
    for r in cur.fetchall():
        print(f"  {r['assigned_channel']}: {r['cnt']}")
    
    cur.close()
