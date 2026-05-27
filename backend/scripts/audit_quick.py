import time, sys
sys.path.insert(0, ".")

errors = 0

def test(name, fn):
    global errors
    try:
        t0 = time.time()
        r = fn()
        dur = int((time.time() - t0) * 1000)
        status = r.get("status", "?") if isinstance(r, dict) else "ok"
        rows = 0
        if isinstance(r, dict):
            for k in ["drivers", "campaigns", "members", "sources", "summary"]:
                v = r.get(k, [])
                if isinstance(v, list) and len(v) > 0:
                    rows = len(v)
                    break
        print(f"{name:<40} {dur:>6}ms  status={status:<12} rows={rows}")
        return True
    except Exception as e:
        print(f"{name:<40} FAILED: {str(e)[:120]}")
        errors += 1
        return False

# Test key services
from app.services.driver_raw_freshness_service import get_raw_freshness_map
test("raw-freshness", get_raw_freshness_map)

from app.services.driver_identity_service import search_driver_identities
test("identity (limit 3)", lambda: search_driver_identities(limit=3, offset=0))

from app.services.driver_lifecycle_service import compute_lifecycle_summary
test("lifecycle-summary", compute_lifecycle_summary)

from app.services.driver_activity_service import search_driver_activity
test("activity-summary (limit 3)", lambda: search_driver_activity(limit=3, offset=0))

from app.services.driver_actionable_supply_service import generate_actionable_summary
test("actionable-summary", generate_actionable_summary)

from app.services.driver_actionable_supply_service import generate_actionable_list
test("actionable-list (limit 5)", lambda: generate_actionable_list(limit=5, offset=0))

from app.services.driver_workflow_service import get_accountability_metrics
test("workflow-metrics", get_accountability_metrics)

from app.services.driver_segment_migration_service import compute_segment_migration
test("segment-migration (limit 5)", lambda: compute_segment_migration(limit=5, offset=0))

from app.services.driver_operational_priority_service import get_actionable_movements
test("movements/actionable (10)", lambda: get_actionable_movements(limit=10, offset=0))

from app.services.driver_campaign_service import list_campaigns
test("campaigns list (5)", lambda: list_campaigns(limit=5, offset=0))

from app.services.driver_campaign_effectiveness_service import get_effectiveness_summary
test("effectiveness-summary", get_effectiveness_summary)

from app.services.driver_crm_bridge_service import check_bridge_health
test("crm-bridge health", check_bridge_health)

from app.services.driver_pilot_service import evaluate_pilot_readiness
test("pilot-readiness", evaluate_pilot_readiness)

print(f"\nTotal tests: {len(tests_ran)} | Errors: {errors}")
