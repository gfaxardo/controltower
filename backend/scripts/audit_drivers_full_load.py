"""
Drivers Full Load & Freshness Audit — D1.3
Probes every Drivers tab/endpoint for:
  - load status (ok / warning / blocked / timeout)
  - duration_ms
  - freshness_status
  - rows
  - source fact/MV/table
  - error
  - remediation

FAIL criteria:
  - timeout (>20s default)
  - freshness missing on critical endpoints
  - endpoint without remediation
  - critical endpoint >5s
"""
import time
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TIMEOUT_S = 20
CRITICAL_THRESHOLD_MS = 5000
WARN_THRESHOLD_MS = 2000


def probe(name, fn, source="", critical=False, needs_freshness=False, remediation_hint=""):
    start = time.time()
    try:
        result = fn()
        duration = round((time.time() - start) * 1000)

        if result is None:
            return {
                "endpoint": name, "duration_ms": duration, "status": "blocked",
                "freshness_status": "unknown", "rows": 0, "source": source,
                "error": "Returned None", "remediation": remediation_hint or "Check DB connectivity",
                "fail": True,
            }

        status = "ok"
        freshness = "n/a"
        rows = 0
        error_msg = None
        remed = ""

        if isinstance(result, dict):
            status = result.get("status", "ok")
            freshness = result.get("freshness_status", "n/a")
            remed = result.get("remediation", "")
            if result.get("error"):
                error_msg = str(result["error"])[:200]

            for k in ["drivers", "campaigns", "members", "sources", "summary",
                       "facts", "series", "data", "movements", "workflows",
                       "checks", "cohort_members", "syncs"]:
                val = result.get(k)
                if isinstance(val, list) and val:
                    rows = len(val)
                    break

        elif isinstance(result, list):
            rows = len(result)

        is_fail = False
        if status in ("blocked",):
            is_fail = True
        if duration > TIMEOUT_S * 1000:
            is_fail = True
            error_msg = f"Timeout: {duration}ms > {TIMEOUT_S}s"
        if critical and duration > CRITICAL_THRESHOLD_MS:
            is_fail = True
        if needs_freshness and freshness in ("unknown", "n/a"):
            is_fail = True

        return {
            "endpoint": name, "duration_ms": duration, "status": status,
            "freshness_status": freshness, "rows": rows, "source": source,
            "error": error_msg, "remediation": remed or remediation_hint,
            "fail": is_fail,
        }
    except Exception as e:
        duration = round((time.time() - start) * 1000)
        return {
            "endpoint": name, "duration_ms": duration, "status": "blocked",
            "freshness_status": "unknown", "rows": 0, "source": source,
            "error": str(e)[:200], "remediation": remediation_hint or "Check import/DB",
            "fail": True,
        }


def run_audit():
    results = []

    # 1. Serving Freshness (Data Foundation)
    try:
        from app.services.driver_serving_freshness_service import check_all_facts
        results.append(probe(
            "serving-freshness", check_all_facts,
            source="ops.driver_serving_freshness_fact", critical=True, needs_freshness=False,
            remediation_hint="Run refresh_driver_supply_facts.py",
        ))
    except Exception as e:
        results.append({"endpoint": "serving-freshness", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_serving_freshness_fact",
                        "error": f"Import: {e}", "remediation": "Verify driver_serving_freshness_service.py", "fail": True})

    # 2. Supply Overview Fact
    try:
        from app.services.driver_serving_freshness_service import require_fact
        def _supply_overview():
            f = require_fact("driver_supply_overview_weekly_fact")
            return f
        results.append(probe(
            "supply-overview-fact", _supply_overview,
            source="ops.driver_supply_overview_weekly_fact", critical=True, needs_freshness=True,
            remediation_hint="Run refresh_driver_supply_facts.py",
        ))
    except Exception as e:
        results.append({"endpoint": "supply-overview-fact", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_supply_overview_weekly_fact",
                        "error": f"Import: {e}", "remediation": "Run refresh_driver_supply_facts.py", "fail": True})

    # 3. Segment Composition Fact
    try:
        from app.services.driver_serving_freshness_service import require_fact
        def _segment_comp():
            return require_fact("driver_weekly_segment_fact")
        results.append(probe(
            "segment-composition-fact", _segment_comp,
            source="ops.driver_weekly_segment_fact", critical=True, needs_freshness=True,
            remediation_hint="Run refresh_driver_supply_facts.py",
        ))
    except Exception as e:
        results.append({"endpoint": "segment-composition-fact", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_weekly_segment_fact",
                        "error": f"Import: {e}", "remediation": "Run refresh_driver_supply_facts.py", "fail": True})

    # 4. Segment Migration
    try:
        from app.services.driver_segment_migration_service import compute_segment_migration
        results.append(probe(
            "segment-migration", lambda: compute_segment_migration(limit=5, offset=0),
            source="ops.driver_segment_migration_fact", critical=True, needs_freshness=True,
            remediation_hint="Run refresh_driver_supply_facts.py",
        ))
    except Exception as e:
        results.append({"endpoint": "segment-migration", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_segment_migration_fact",
                        "error": f"Import: {e}", "remediation": "Run refresh_driver_supply_facts.py", "fail": True})

    # 5. Operational Priorities / Movements
    try:
        from app.services.driver_operational_priority_service import get_actionable_movements
        results.append(probe(
            "movements/actionable", lambda: get_actionable_movements(limit=10, offset=0),
            source="ops.driver_operational_priority_fact", critical=True, needs_freshness=True,
            remediation_hint="Run refresh_driver_supply_facts.py",
        ))
    except Exception as e:
        results.append({"endpoint": "movements/actionable", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_operational_priority_fact",
                        "error": f"Import: {e}", "remediation": "Run refresh_driver_supply_facts.py", "fail": True})

    # 6. Lifecycle Summary
    try:
        from app.services.driver_lifecycle_service import compute_lifecycle_summary
        results.append(probe(
            "lifecycle-summary", compute_lifecycle_summary,
            source="ops.driver_daily_activity_fact + public.drivers", critical=False,
            remediation_hint="Verify ops.driver_daily_activity_fact exists",
        ))
    except Exception as e:
        results.append({"endpoint": "lifecycle-summary", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_daily_activity_fact",
                        "error": f"Import: {e}", "remediation": "Verify lifecycle service", "fail": True})

    # 7. Actionable List
    try:
        from app.services.driver_actionable_supply_service import generate_actionable_list
        results.append(probe(
            "actionable-list (limit 10)", lambda: generate_actionable_list(limit=10, offset=0),
            source="ops.driver_daily_activity_fact + public.drivers", critical=False,
            remediation_hint="Verify actionable supply service",
        ))
    except Exception as e:
        results.append({"endpoint": "actionable-list", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "",
                        "error": f"Import: {e}", "remediation": "Verify actionable supply service", "fail": True})

    # 8. Workflow Metrics
    try:
        from app.services.driver_workflow_service import get_accountability_metrics
        results.append(probe(
            "workflow-metrics", get_accountability_metrics,
            source="ops.driver_supply_workflow", critical=False,
            remediation_hint="Verify workflow tables exist",
        ))
    except Exception as e:
        results.append({"endpoint": "workflow-metrics", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_supply_workflow",
                        "error": f"Import: {e}", "remediation": "Create workflow tables", "fail": True})

    # 9. Campaigns List
    try:
        from app.services.driver_campaign_service import list_campaigns
        results.append(probe(
            "campaigns (limit 5)", lambda: list_campaigns(limit=5, offset=0),
            source="ops.driver_campaigns", critical=False,
            remediation_hint="Verify campaigns table exists",
        ))
    except Exception as e:
        results.append({"endpoint": "campaigns", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_campaigns",
                        "error": f"Import: {e}", "remediation": "Verify campaigns table", "fail": True})

    # 10. Campaign Effectiveness Summary
    try:
        from app.services.driver_campaign_effectiveness_service import get_effectiveness_summary
        results.append(probe(
            "effectiveness-summary", get_effectiveness_summary,
            source="ops.driver_campaign_effectiveness", critical=False,
            remediation_hint="Verify effectiveness table exists",
        ))
    except Exception as e:
        results.append({"endpoint": "effectiveness-summary", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_campaign_effectiveness",
                        "error": f"Import: {e}", "remediation": "Verify effectiveness service", "fail": True})

    # 11. CRM Bridge Health
    try:
        from app.services.driver_crm_bridge_service import check_bridge_health
        results.append(probe(
            "crm-bridge/health", check_bridge_health,
            source="ops.driver_campaign_sync", critical=False,
            remediation_hint="Verify CRM sync tables exist",
        ))
    except Exception as e:
        results.append({"endpoint": "crm-bridge/health", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_campaign_sync",
                        "error": f"Import: {e}", "remediation": "Verify CRM bridge service", "fail": True})

    # 12. Geo Options
    try:
        from app.db.connection import get_db
        def _geo():
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SET LOCAL statement_timeout = '5000'")
                cur.execute("""
                    SELECT COUNT(DISTINCT country), COUNT(DISTINCT city)
                    FROM ops.driver_supply_overview_weekly_fact
                    WHERE country IS NOT NULL AND country != 'Unknown'
                """)
                row = cur.fetchone()
                return {"status": "ok", "countries": row[0] if row else 0, "cities": row[1] if row else 0}
        results.append(probe(
            "geo-options", _geo,
            source="ops.driver_supply_overview_weekly_fact", critical=True,
            remediation_hint="Run refresh_driver_supply_facts.py",
        ))
    except Exception as e:
        results.append({"endpoint": "geo-options", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_supply_overview_weekly_fact",
                        "error": f"Import: {e}", "remediation": "Run refresh_driver_supply_facts.py", "fail": True})

    # 13. Operational Loop Model (static, should always work)
    try:
        from app.services.driver_operational_loop_service import get_operational_loop_model
        results.append(probe(
            "operational-loop/model", get_operational_loop_model,
            source="static", critical=False,
            remediation_hint="This is static data, should always work",
        ))
    except Exception as e:
        results.append({"endpoint": "operational-loop/model", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "n/a", "rows": 0, "source": "static",
                        "error": f"Import: {e}", "remediation": "Verify operational loop service", "fail": True})

    # 14. Campaigns Operating Board
    try:
        from app.services.driver_operational_loop_service import get_operating_board
        results.append(probe(
            "campaigns/operating-board", get_operating_board,
            source="ops.driver_campaigns + ops.driver_campaign_members", critical=False,
            remediation_hint="Verify campaigns and members tables exist",
        ))
    except Exception as e:
        results.append({"endpoint": "campaigns/operating-board", "duration_ms": 0, "status": "blocked",
                        "freshness_status": "unknown", "rows": 0, "source": "ops.driver_campaigns",
                        "error": f"Import: {e}", "remediation": "Verify operational loop service", "fail": True})

    # Report
    print()
    print("=" * 100)
    print("DRIVERS FULL LOAD & FRESHNESS AUDIT — D1.3")
    print("=" * 100)
    print(f"{'Endpoint':<40} {'ms':>6} {'Status':<10} {'Freshness':<10} {'Rows':>5} {'Fail':>5} {'Source'}")
    print("-" * 100)

    total_ms = 0
    fail_count = 0
    ok_count = 0
    warn_count = 0
    blocked_count = 0

    for r in results:
        dur = r["duration_ms"]
        total_ms += dur
        fail_flag = "FAIL" if r.get("fail") else ""
        if r["status"] == "blocked":
            blocked_count += 1
        elif r.get("fail"):
            fail_count += 1
        elif r["status"] == "warning":
            warn_count += 1
        else:
            ok_count += 1

        print(f"  {r['endpoint']:<38} {dur:>6} {r['status']:<10} {r.get('freshness_status','n/a'):<10} {r['rows']:>5} {fail_flag:>5} {r.get('source','')}")
        if r.get("error"):
            print(f"    ERROR: {r['error'][:80]}")
        if r.get("remediation") and r.get("fail"):
            print(f"    REMEDIATION: {r['remediation'][:80]}")

    print("-" * 100)
    print(f"  TOTAL: {total_ms}ms | OK: {ok_count} | WARN: {warn_count} | BLOCKED: {blocked_count} | FAIL: {fail_count}")
    print()

    overall = "GO" if fail_count == 0 and blocked_count == 0 else "NO-GO"
    print(f"  VERDICT: {overall}")
    if blocked_count > 0:
        print(f"    {blocked_count} endpoint(s) blocked — not ready for human testing")
    if fail_count > 0:
        print(f"    {fail_count} endpoint(s) failed criteria — needs fix before human testing")
    print("=" * 100)

    return results, overall


if __name__ == "__main__":
    results, verdict = run_audit()
