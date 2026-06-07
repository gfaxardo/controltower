import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.db.connection import get_db
from app.services.yego_lima_assignment_queue_service import create_assignment_batch, get_assignment_queue

with get_db() as conn:
    cur = conn.cursor()
    cur.execute("DELETE FROM growth.yego_lima_assignment_queue")
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM growth.yego_lima_assignment_queue")
    remaining = cur.fetchone()[0]
    print(f"Cleared queue. Remaining: {remaining}")
    cur.close()

t0 = time.time()
result = create_assignment_batch(date_str="2026-06-02")
t1 = time.time()
print(f"Build {result['created_count']} records in {round(t1-t0)}s")
print(f"  READY: {result['ready_count']}, HELD: {result['held_count']}")
print(f"  Duplicates: {result['skipped_duplicates']}, Invalid: {result['skipped_invalid']}")

q = get_assignment_queue(date_str="2026-06-02")
print(f"Queue: {q['total_records']} total, {q['ready_count']} READY, {q['held_count']} HELD")

if q['ready_count'] > 0:
    print(f"\nREADY for export: {q['ready_count']} drivers")
