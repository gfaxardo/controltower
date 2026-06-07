import sys, os, time as _time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

t0 = _time.perf_counter()
from app.services.yego_lima_opportunity_worklist_service import get_opportunity_worklist
wl = get_opportunity_worklist("2026-06-02")
t1 = _time.perf_counter()
print(f"Worklist: {len(wl['records'])} records in {round((t1-t0)*1000)}ms")

if wl["records"]:
    r = wl["records"][0]
    print(f"Sample: driver={r['driver_id'][:12]} phone={'SET' if r.get('phone') else 'NULL'} channel={r.get('assigned_channel')}")

    from app.services.yego_lima_assignment_queue_service import create_assignment_batch, get_assignment_queue
    t2 = _time.perf_counter()
    result = create_assignment_batch(date_str="2026-06-02")
    t3 = _time.perf_counter()
    print(f"Build: {result['created_count']} created, {result['ready_count']} READY, {result['held_count']} HELD in {round((t3-t2)*1000)}ms")
    print(f"  Skipped duplicates: {result['skipped_duplicates']}, invalid: {result['skipped_invalid']}")

    q = get_assignment_queue(date_str="2026-06-02")
    print(f"Queue: {q['total_records']} total, {q['ready_count']} READY, {q['held_count']} HELD")
