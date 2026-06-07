import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.yego_lima_queue_export_service import export_ready_queue_to_loopcontrol
from app.services.yego_lima_assignment_queue_service import get_assignment_queue

print("Exporting limit=10 from READY queue...")
result = export_ready_queue_to_loopcontrol(date_str="2026-06-02", limit=10)
print(f"Export result:")
for k, v in result.items():
    print(f"  {k}: {v}")

q = get_assignment_queue(date_str="2026-06-02")
print(f"\nAfter export: {q['total_records']} total, {q['ready_count']} READY, {sum(1 for r in q['records'] if r['queue_status']=='EXPORTED')} EXPORTED")

exported = [r for r in q['records'] if r['queue_status'] == 'EXPORTED']
if exported:
    print(f"\nFirst 3 exported:")
    for e in exported[:3]:
        print(f"  {e['driver_name']}: {e['phone']} -> campaign={e.get('campaign_id_external','N/A')[:16]} batch={str(e.get('export_batch_id',''))[:8]}")
