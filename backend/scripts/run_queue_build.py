import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.yego_lima_assignment_queue_service import create_assignment_batch, get_assignment_queue

result = create_assignment_batch(date_str="2026-06-02")
print("Build result:")
for k, v in result.items():
    print(f"  {k}: {v}")
print()

q = get_assignment_queue(date_str="2026-06-02")
print(f"Queue: {q['total_records']} total, {q['ready_count']} READY, {q['held_count']} HELD")
