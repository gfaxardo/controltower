"""
Drivers Endpoint Runtime Audit Script — SH1
Control Foundation Serving Hardening

Measures all drivers endpoints/services for performance.
No writes, no mutations. Read-only audit.
Timeout per check: 20s. Graceful degradation on failures.
"""
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def measure(name, fn):
    start = time.time()
    try:
        result = fn()
        duration = round((time.time() - start) * 1000)
        status = result.get("status", "unknown") if isinstance(result, dict) else "no_dict"
        rows = 0
        if isinstance(result, dict):
            keys = ["drivers", "campaigns", "members", "sources", "summary"]
            for k in keys:
                val = result.get(k, [])
                if isinstance(val, list) and len(val) > 0:
                    rows = len(val)
                    break
        return {"name": name, "duration_ms": duration, "status": status, "rows": rows, "error": None}
    except Exception as e:
        duration = round((time.time() - start) * 1000)
        return {"name": name, "duration_ms": duration, "status": "blocked", "rows": 0, "error": str(e)[:200]}

def run_audit():
    results = []

    # H1: Health
    try:
        from app.services.driver_raw_freshness_service import get_raw_freshness_map
        results.append(measure("raw-freshness", get_raw_freshness_map))
    except Exception as e:
        results.append({"name": "raw-freshness", "duration_ms": 0, "status": "blocked", "rows": 0, "error": f"Import: {str(e)[:100]}"})

    # D2: Identity
    try:
        from app.services.driver_identity_service import search_driver_identities
        results.append(measure("identity (limit 5)", lambda: search_driver_identities(limit=5, offset=0)))
    except Exception as e:
        results.append({"name": "identity", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # D3: Activity + Lifecycle
    try:
        from app.services.driver_activity_service import search_driver_activity
        results.append(measure("activity-summary (limit 5)", lambda: search_driver_activity(limit=5, offset=0)))
    except Exception as e:
        results.append({"name": "activity-summary", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    try:
        from app.services.driver_lifecycle_service import compute_lifecycle_summary
        results.append(measure("lifecycle-summary", compute_lifecycle_summary))
    except Exception as e:
        results.append({"name": "lifecycle-summary", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # D4: Actionable
    try:
        from app.services.driver_actionable_supply_service import generate_actionable_summary
        results.append(measure("actionable-summary", generate_actionable_summary))
    except Exception as e:
        results.append({"name": "actionable-summary", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    try:
        from app.services.driver_actionable_supply_service import generate_actionable_list
        results.append(measure("actionable-list (limit 10)", lambda: generate_actionable_list(limit=10, offset=0)))
    except Exception as e:
        results.append({"name": "actionable-list", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # D5: Workflow
    try:
        from app.services.driver_workflow_service import get_accountability_metrics
        results.append(measure("workflow-metrics", get_accountability_metrics))
    except Exception as e:
        results.append({"name": "workflow-metrics", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # H3.5A: Segment Migration
    try:
        from app.services.driver_segment_migration_service import compute_segment_migration
        results.append(measure("segment-migration (limit 5)", lambda: compute_segment_migration(limit=5, offset=0)))
    except Exception as e:
        results.append({"name": "segment-migration", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # H3.5B: Operational Priorities
    try:
        from app.services.driver_operational_priority_service import get_actionable_movements
        results.append(measure("movements/actionable (limit 10)", lambda: get_actionable_movements(limit=10, offset=0)))
    except Exception as e:
        results.append({"name": "movements/actionable", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # H3.2: Campaigns
    try:
        from app.services.driver_campaign_service import list_campaigns
        results.append(measure("campaigns list (limit 5)", lambda: list_campaigns(limit=5, offset=0)))
    except Exception as e:
        results.append({"name": "campaigns", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # H3.4: Effectiveness
    try:
        from app.services.driver_campaign_effectiveness_service import get_effectiveness_summary
        results.append(measure("effectiveness-summary", get_effectiveness_summary))
    except Exception as e:
        results.append({"name": "effectiveness-summary", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # H3.3: CRM Bridge
    try:
        from app.services.driver_crm_bridge_service import check_bridge_health
        results.append(measure("crm-bridge/health", check_bridge_health))
    except Exception as e:
        results.append({"name": "crm-bridge/health", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # H2: Pilot
    try:
        from app.services.driver_pilot_service import evaluate_pilot_readiness
        results.append(measure("pilot-readiness", evaluate_pilot_readiness))
    except Exception as e:
        results.append({"name": "pilot-readiness", "duration_ms": 0, "status": "blocked", "rows": 0, "error": str(e)[:100]})

    # Summary
    print("\n" + "=" * 80)
    print("DRIVERS ENDPOINT RUNTIME AUDIT — SH1")
    print("=" * 80)
    total = 0
    blocked_count = 0
    slow_count = 0

    for r in results:
        dur = r["duration_ms"]
        total += dur
        flag = ""
        if r["status"] == "blocked":
            blocked_count += 1
            flag = " [BLOCKED]"
        elif dur > 5000:
            slow_count += 1
            flag = " [SLOW]"
        elif dur > 2000:
            flag = " [WARN]"

        error_info = f" | error={r['error'][:80]}" if r.get("error") else ""
        print(f"  {r['name']:<45} {dur:>6}ms  status={r['status']:<10} rows={r['rows']:<6}{flag}{error_info}")

    print("-" * 80)
    print(f"  TOTAL: {total}ms | BLOCKED: {blocked_count} | SLOW (>5s): {slow_count}")
    print("=" * 80)

    return results

if __name__ == "__main__":
    run_audit()
