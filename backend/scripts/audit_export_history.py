import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT export_status, COUNT(*) as cnt, SUM(contacts_sent) as sent,
               SUM(contacts_inserted) as inserted
        FROM growth.yango_lima_loopcontrol_campaign_export
        GROUP BY export_status ORDER BY cnt DESC
    """)
    print("Exports by status:")
    for r in cur.fetchall():
        print(f"  {r['export_status']:<20s}: {r['cnt']} exports, {r['sent']} sent, {r['inserted']} inserted")

    cur.execute("""
        SELECT COUNT(*) as cnt FROM growth.yango_lima_loopcontrol_campaign_export
        WHERE campaign_id_external IS NOT NULL
    """)
    real = cur.fetchone()["cnt"]
    print(f"\nReal campaign IDs: {real}")

    cur.execute("SELECT COUNT(*) as total FROM growth.yango_lima_loopcontrol_campaign_export")
    total = cur.fetchone()["total"]
    print(f"Total exports: {total}")
    print(f"Draft (dry_run): {total - real}")
    print(f"\nCONCLUSION: {'MIXTAS' if real > 0 else '100% SIMULADAS'} — {real} reales, {total - real} simuladas (DRY_RUN)")

    cur.close()
