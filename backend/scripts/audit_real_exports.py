import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("""
        SELECT export_id, campaign_id_external, campaign_name, export_status,
               contacts_sent, contacts_inserted, contacts_skipped, program_code,
               exported_at, error_message
        FROM growth.yango_lima_loopcontrol_campaign_export
        WHERE export_status = 'exported'
        ORDER BY exported_at DESC
    """)
    print("REAL EXPORTS:")
    for r in cur.fetchall():
        print(f"  {r['exported_at']} | {r['campaign_id_external']:<6s} | {r['campaign_name']:<30s} | {r['program_code']:<20s} | sent={r['contacts_sent']} inserted={r['contacts_inserted']} skipped={r['contacts_skipped']}")

    print()
    cur.execute("""
        SELECT SUBSTRING(exported_at::text, 1, 10) as day, export_status, COUNT(*) as cnt
        FROM growth.yango_lima_loopcontrol_campaign_export
        WHERE campaign_id_external IS NOT NULL
        GROUP BY day, export_status ORDER BY day DESC
    """)
    print("Real exports by day:")
    for r in cur.fetchall():
        print(f"  {r['day']}: {r['cnt']} exports")

    cur.execute("""
        SELECT MAX(exported_at) FROM growth.yango_lima_loopcontrol_campaign_export
        WHERE campaign_id_external IS NOT NULL
    """)
    last_real = cur.fetchone()
    print(f"\nLast real export: {last_real[0]}")

    cur.close()
