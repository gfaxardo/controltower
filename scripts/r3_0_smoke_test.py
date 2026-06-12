"""R3.0 — Program Explainability Smoke Test"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2, json
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

# Get 3 real drivers from queue
cur.execute("""
    SELECT driver_id, program_code, queue_status
    FROM growth.yego_lima_assignment_queue
    WHERE assignment_date = '2026-06-05'
    LIMIT 3
""")
drivers = cur.fetchall()

print("=" * 60)
print("R3.0 PROGRAM EXPLAINABILITY SMOKE TEST")
print("=" * 60)

from app.services.yego_lima_program_explainability_service import (
    get_driver_program_explainability, get_program_rules, get_program_coverage
)

# Test rules endpoint
rules = get_program_rules()
print(f"\nPrograms defined: {rules['total_programs']}")
print(f"Total rules: {rules['total_rules']}")
for pcode, pdef in rules['programs'].items():
    print(f"  {pcode}: {len(pdef['rules'])} rules")

# Test coverage
cov = get_program_coverage('2026-06-05')
print(f"\nCoverage for 2026-06-05:")
for prog, data in cov['programs'].items():
    print(f"  {prog}: eligible={data['eligible']}, prioritized={data['prioritized']}, queued={data['queued']}, empty={data['empty']}")

# Test explainability for 3 real drivers
for d in drivers:
    did = d[0]
    print(f"\n{'='*60}")
    print(f"DRIVER: {did[:16]}...")
    result = get_driver_program_explainability(did)
    
    if result.get('found'):
        print(f"  Snapshot: {result['snapshot_date']}")
        s = result['snapshot']
        print(f"  State: lifecycle={s['lifecycle_state']}, perf={s['performance_state']}, retention={s['retention_state']}")
        print(f"  Orders week: {s['completed_orders_week']}, supply: {s['supply_hours_week']:.1f}h")
        print(f"  Distance to target: {s['distance_to_weekly_target']}")
        print(f"  In programs: {result['in_programs']}")
        print(f"  Not in: {result['not_in_programs']}")
        
        for prog in result['programs']:
            print(f"\n  [{prog['program_code']}] eligible={prog['eligible']}")
            if prog['eligible']:
                print(f"    Reason: {prog['eligibility_reason']}")
            for rule in prog['rules']:
                icon = "[MATCH]" if rule['matched'] else "[FAIL]"
                print(f"    {icon} {rule['rule_id']}: {rule['description']}")
                print(f"         field={rule['source_field']}, value={rule['value']}")
    else:
        print(f"  NOT FOUND: {result.get('error')}")

cur.close()
conn.close()
print("\nSmoke test complete.")
