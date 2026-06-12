"""C2.1B — Link 5 queue entries to campaign 121 + sync results"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

# 1. Find 5 queue entries that are READY and link to campaign 121
print("1. Linking 5 queue entries to campaign 121...")
cur.execute("""
    UPDATE growth.yego_lima_assignment_queue
    SET campaign_id_external = '121',
        queue_status = 'EXPORTED',
        exported_at = now()
    WHERE id IN (
        SELECT id FROM growth.yego_lima_assignment_queue
        WHERE queue_status = 'READY' AND assignment_date = '2026-06-05'
        LIMIT 5
    )
    RETURNING driver_id, phone, driver_name, program_code, assigned_channel
""")
contacts = cur.fetchall()
print(f"   Linked: {len(contacts)} contacts")
phones = []
for r in contacts:
    print(f"   driver={r[0][:20]}... phone={r[1]}, prog={r[3]}, chan={r[4]}")
    phones.append(r[1])

if len(contacts) < 5:
    print("   BLOCKED: Not enough READY contacts")
    conn.close()
    exit(1)

# 2. Build and execute controlled payload
print("\n2. Syncing controlled results...")
payload = {
    "campaign_id_external": "121",
    "results": [
        {"phone": phones[0], "attempts": 2, "status": "CONTACTED", "disposition": "INTERESTED", "last_call_at": "2026-06-08T10:00:00-05:00", "notes": "Interesado en volver", "agent": "QA Agent"},
        {"phone": phones[1], "attempts": 1, "status": "CONTACTED", "disposition": "NOT_INTERESTED", "last_call_at": "2026-06-08T10:05:00-05:00", "notes": "No interesado", "agent": "QA Agent"},
        {"phone": phones[2], "attempts": 3, "status": "NO_ANSWER", "disposition": None, "last_call_at": "2026-06-08T10:10:00-05:00", "notes": "No contesta", "agent": "QA Agent"},
        {"phone": phones[3], "attempts": 1, "status": "WRONG_NUMBER", "disposition": None, "last_call_at": "2026-06-08T10:15:00-05:00", "notes": "Numero equivocado", "agent": "QA Agent"},
        {"phone": phones[4], "attempts": 2, "status": "CONTACTED", "disposition": "INTERESTED", "last_call_at": "2026-06-08T10:20:00-05:00", "notes": "WhatsApp info", "agent": "QA Agent"},
    ]
}

from app.services.yego_lima_result_sync_service import sync_results, get_result_summary, get_result_records
result = sync_results(payload)
print(f"   Sync: {json.dumps(result, indent=2)}")

# 3. Validate summary
print("\n3. Summary validation...")
summary = get_result_summary("121")
print(f"   Total: {summary['total_results']}, Matched: {summary['matched_queue_count']}, Contacted: {summary['contacted_count']}, Interested: {summary['interested_count']}")
assert summary['total_results'] == 5, f"Expected 5, got {summary['total_results']}"
assert summary['matched_queue_count'] == 5, f"Expected 5 matched, got {summary['matched_queue_count']}"
print("   PASS")

# 4. Validate records
print("\n4. Records validation...")
records = get_result_records("121")
print(f"   Records: {records['total']}")
for r in records['records'][:3]:
    print(f"   {r['driver_name'] or r['phone']}: {r['status']} / {r['disposition']} / {r['agent']}")
assert records['total'] == 5
print("   PASS")

# 5. Idempotency
print("\n5. Idempotency test (re-send same payload)...")
result2 = sync_results(payload)
print(f"   Sync2: received={result2['received_count']}, inserted={result2['inserted']}, updated={result2['updated']}")
summary2 = get_result_summary("121")
assert summary2['total_results'] == 5, f"Duplicated! Expected 5, got {summary2['total_results']}"
print("   PASS (no duplication)")

# 6. Unmatched test
print("\n6. Unmatched test...")
unmatched_payload = {
    "campaign_id_external": "121",
    "results": [{"phone": "+51999000000", "attempts": 1, "status": "NO_ANSWER", "disposition": None, "agent": "QA Agent"}]
}
result3 = sync_results(unmatched_payload)
summary3 = get_result_summary("121")
print(f"   Total: {summary3['total_results']}, Matched: {summary3['matched_queue_count']}, Unmatched: {summary3['unmatched_count']}")
assert summary3['total_results'] == 6, f"Expected 6, got {summary3['total_results']}"
assert summary3['unmatched_count'] == 1, f"Expected 1 unmatched, got {summary3['unmatched_count']}"
print("   PASS")

conn.close()
print("\nALL TESTS PASSED")
