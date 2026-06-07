"""
LG-C1.1 — Detailed Freshness Query

Queries detailed metrics from Lima Growth tables.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=== OPPORTUNITY FRESHNESS (last 7 days) ===")
    cur.execute("""
        SELECT opportunity_date, COUNT(*) as cnt,
               COUNT(DISTINCT driver_profile_id) as drivers,
               COUNT(DISTINCT selected_program_code) as programs
        FROM growth.yango_lima_prioritized_opportunity_daily
        WHERE opportunity_date >= current_date - interval '7 days'
        GROUP BY opportunity_date ORDER BY opportunity_date DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['opportunity_date']}: {r['cnt']} opps, {r['drivers']} drivers, {r['programs']} programs")

    print()
    print("=== STATE SNAPSHOT (last 7 days) ===")
    cur.execute("""
        SELECT snapshot_date, COUNT(*) as cnt, COUNT(DISTINCT lifecycle_state) as states
        FROM growth.yango_lima_driver_state_snapshot
        WHERE snapshot_date >= current_date - interval '7 days'
        GROUP BY snapshot_date ORDER BY snapshot_date DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['snapshot_date']}: {r['cnt']} drivers, {r['states']} lifecycle states")

    print()
    print("=== DRIVER 360 (last 7 days) ===")
    cur.execute("""
        SELECT date, COUNT(*) as cnt, SUM(completed_orders) as orders
        FROM growth.yango_lima_driver_360_daily
        WHERE date >= current_date - interval '7 days'
        GROUP BY date ORDER BY date DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['date']}: {r['cnt']} drivers, {r['orders']} orders")

    print()
    print("=== EXPORT HISTORY ===")
    cur.execute("""
        SELECT opportunity_date, campaign_id_external, export_status, contacts_sent
        FROM growth.yango_lima_loopcontrol_campaign_export
        ORDER BY exported_at DESC LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {r['opportunity_date']} | {r['campaign_id_external'] or 'N/A':15s} | {r['export_status']} | {r['contacts_sent']} contacts")

    cur.close()
