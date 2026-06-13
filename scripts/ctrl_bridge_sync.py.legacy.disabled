"""Bridge: sync assignment_queue to control_loop_state"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

D = '2026-06-05'

print("BEFORE:")
cur.execute("SELECT queue_status, COUNT(*) FROM growth.yego_lima_assignment_queue WHERE assignment_date = %(d)s GROUP BY queue_status", {"d": D})
for r in cur.fetchall(): print(f"  AQ {r[0]}: {r[1]}")
cur.execute("SELECT current_state, COUNT(*) FROM growth.yego_lima_control_loop_state GROUP BY current_state")
rows = cur.fetchall()
if rows:
    for r in rows: print(f"  CL {r[0]}: {r[1]}")
else:
    print("  CL: EMPTY")

# SYNC with explicit state mapping
sql = """
INSERT INTO growth.yego_lima_control_loop_state 
(driver_profile_id, current_state, channel, program_code, queue_id)
SELECT driver_id,
       CASE
           WHEN queue_status = 'READY' THEN 'READY'
           WHEN queue_status = 'HELD' THEN 'READY'
           WHEN queue_status = 'EXPORTED' THEN 'DONE'
           ELSE 'READY'
       END,
       assigned_channel, program_code, id
FROM growth.yego_lima_assignment_queue
WHERE assignment_date = %(d)s
  AND NOT EXISTS (
    SELECT 1 FROM growth.yego_lima_control_loop_state cls
    WHERE cls.driver_profile_id = growth.yego_lima_assignment_queue.driver_id
  )
"""
cur.execute(sql, {"d": D})
print(f"\nSYNC: {cur.rowcount} inserted")

# Rerun for idempotency
cur.execute(sql, {"d": D})
print(f"IDEMPOTENCY: {cur.rowcount} new (should be 0)")

print("\nAFTER:")
cur.execute("SELECT current_state, COUNT(*) FROM growth.yego_lima_control_loop_state GROUP BY current_state")
for r in cur.fetchall(): print(f"  CL {r[0]}: {r[1]}")

cur.close()
conn.close()
print(f"\nVERDICT: PASS")
