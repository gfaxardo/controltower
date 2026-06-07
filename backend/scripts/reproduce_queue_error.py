"""
LG-C1.1B — Error Reproduction Script.

Captures exact failing row from worklist -> queue insert.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from app.services.yego_lima_opportunity_worklist_service import get_opportunity_worklist
from uuid import uuid4

date_str = "2026-06-02"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"

worklist = get_opportunity_worklist(date_str=date_str)
records = worklist.get("records", [])
print(f"Worklist: {len(records)} records")

# Check for NULLs in critical fields
nulls = {"driver_id": 0, "program_code": 0, "driver_name": 0, "phone": 0, "last_trip_date": 0, "country": 0, "city": 0, "park": 0}
for r in records:
    for key in nulls:
        if not r.get(key):
            nulls[key] += 1
print("NULL stats in worklist records:")
for k, v in nulls.items():
    print(f"  {k}: {v} nulls")

# Try inserting row by row to find first failure
batch_id = str(uuid4())
failed_row = None
first_error = None
created = 0

with get_db() as conn:
    cur = conn.cursor()

    for i, r in enumerate(records):
        phone_val = r.get("phone")
        chan = r.get("assigned_channel", "")
        status = "HELD" if (not phone_val or chan == "UNASSIGNED") else "READY"

        did = r.get("driver_id") or "MISSING"
        pc = r.get("program_code") or "MISSING"

        try:
            cur.execute(f"""
                INSERT INTO {TABLE_QUEUE}
                (assignment_batch_id, assignment_date, driver_id, driver_name, phone,
                 program_code, program_name, priority_rank, assigned_channel,
                 opportunity_reason, last_trip_date, recent_trips,
                 country, city, park, queue_status)
                VALUES (%(bid)s, %(d)s, %(did)s, %(dn)s, %(ph)s,
                 %(pc)s, %(pn)s, %(pr)s, %(ch)s,
                 %(or)s, %(ltd)s, %(rt)s,
                 %(co)s, %(ci)s, %(pa)s, %(st)s)
                ON CONFLICT ON CONSTRAINT idx_aq_unique_driver_program_date DO NOTHING
            """, {
                "bid": batch_id, "d": date_str,
                "did": did, "dn": r.get("driver_name"),
                "ph": phone_val, "pc": pc,
                "pn": r.get("program_name"), "pr": r.get("priority_rank"),
                "ch": chan, "or": r.get("opportunity_reason"),
                "ltd": r.get("last_trip_date"), "rt": r.get("recent_trips"),
                "co": r.get("country"), "ci": r.get("city"),
                "pa": r.get("park"), "st": status,
            })

            if cur.rowcount > 0:
                created += 1
                if created <= 5:
                    print(f"  OK row {i}: driver={did[:12]}... phone={'SET' if phone_val else 'NULL'} status={status}")

            if cur.rowcount == 0 and i < 10:
                pass  # Duplicate, skip silently

        except Exception as e:
            first_error = str(e)
            failed_row = i
            print(f"  FAIL row {i}: driver={did[:12]}... ERROR={str(e)[:200]}")
            print(f"  Row data: phone={type(phone_val).__name__}={repr(phone_val)[:50]}, chan={repr(chan)}, driver_id={repr(did)[:50]}, prog={repr(pc)}")
            try:
                conn.rollback()
            except:
                pass
            break

    if failed_row is None:
        conn.commit()
        print(f"\nSUCCESS: All {created} rows inserted OK")
    else:
        print(f"\nFAILED at row {failed_row}/{len(records)}: {first_error}")

    cur.close()
