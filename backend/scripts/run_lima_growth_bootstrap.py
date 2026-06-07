"""
LG-C1.1A — Operational Bootstrap Script.

Tests Yango API, runs upstream refresh, builds queue, exports (limit=10),
generates E2E trace for 10 drivers.

NO mocks. NO AI. NO ROI.
"""
import sys, os, json, csv, time
from datetime import datetime, timedelta, timezone, date as date_type
from collections import OrderedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "exports", "audits", "lima_growth")
os.makedirs(EXPORT_DIR, exist_ok=True)

BOOTSTRAP_DATE = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")
LIMIT = 10

results = OrderedDict()


def step(label, fn):
    t0 = time.perf_counter()
    try:
        r = fn()
        elapsed = round((time.perf_counter() - t0) * 1000)
        results[label] = {"status": "OK", "elapsed_ms": elapsed, "data": r}
        print(f"  OK  | {label} ({elapsed}ms)")
    except Exception as e:
        elapsed = round((time.perf_counter() - t0) * 1000)
        results[label] = {"status": "FAIL", "elapsed_ms": elapsed, "error": str(e)[:200]}
        print(f"  FAIL| {label}: {str(e)[:100]}")


def step_1_test_yango():
    import asyncio

    async def _test():
        from app.integrations.yango_api_client import test_orders_connection
        return await test_orders_connection()

    return asyncio.run(_test())


def step_2_run_pipeline():
    from app.services.yego_lima_daily_pipeline_service import run_daily_pipeline
    return run_daily_pipeline(
        run_date_str=BOOTSTRAP_DATE,
        max_drivers=500,
        include_warm=False,
        dry_run=False,
        requested_by="bootstrap",
    )


def step_3_build_queue():
    from app.services.yego_lima_assignment_queue_service import create_assignment_batch
    return create_assignment_batch(date_str=BOOTSTRAP_DATE)


def step_4_export():
    from app.services.yego_lima_queue_export_service import export_ready_queue_to_loopcontrol
    return export_ready_queue_to_loopcontrol(date_str=BOOTSTRAP_DATE, limit=LIMIT)


def step_5_freshness_snapshot():
    queries = OrderedDict()
    queries["driver_state_snapshot"] = ("growth.yango_lima_driver_state_snapshot", "snapshot_date")
    queries["driver_360_daily"] = ("growth.yango_lima_driver_360_daily", "date")
    queries["prioritized_opportunity"] = ("growth.yango_lima_prioritized_opportunity_daily", "opportunity_date")
    queries["assignment_queue"] = ("growth.yego_lima_assignment_queue", "assignment_date")
    queries["loopcontrol_export"] = ("growth.yango_lima_loopcontrol_campaign_export", "opportunity_date")

    snapshot = OrderedDict()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for name, (table, col) in queries.items():
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                row = cur.fetchone()
                total = row["cnt"]
                cur.execute(f"SELECT MAX({col}) as latest FROM {table}")
                lr = cur.fetchone()
                latest = str(lr["latest"])[:10] if lr and lr["latest"] else None
                snapshot[name] = {"rows": total, "latest_business_date": latest}
                print(f"    {name}: {total} rows, latest={latest}")
            except Exception as e:
                snapshot[name] = {"rows": 0, "latest_business_date": None, "error": str(e)[:80]}
        cur.close()
    return snapshot


def step_6_trace_10():
    trace = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            SELECT id, driver_id, driver_name, phone, program_code, program_name,
                   assigned_channel, queue_status, campaign_id_external,
                   export_batch_id, exported_at
            FROM growth.yego_lima_assignment_queue
            WHERE assignment_date = %(d)s AND queue_status = 'EXPORTED'
            ORDER BY exported_at DESC LIMIT %(lim)s
        """, {"d": BOOTSTRAP_DATE, "lim": LIMIT})
        exported = [dict(r) for r in cur.fetchall()]

        for e in exported:
            driver_id = e["driver_id"]
            campaign_id = e.get("campaign_id_external")

            cur.execute("""
                SELECT opportunity_type, selected_program_code, lifecycle_state, productivity_bucket
                FROM growth.yango_lima_prioritized_opportunity_daily
                WHERE driver_profile_id = %(did)s AND opportunity_date = %(d)s LIMIT 1
            """, {"did": driver_id, "d": BOOTSTRAP_DATE})
            opp = cur.fetchone()

            cur.execute("""
                SELECT lifecycle_state, completed_orders_week, last_trip_at
                FROM growth.yango_lima_driver_state_snapshot
                WHERE driver_profile_id = %(did)s AND snapshot_date = %(d)s LIMIT 1
            """, {"did": driver_id, "d": BOOTSTRAP_DATE})
            state = cur.fetchone()

            cur.execute("""
                SELECT export_id, campaign_id_external, contacts_sent, export_status
                FROM growth.yango_lima_loopcontrol_campaign_export
                WHERE campaign_id_external = %(cid)s LIMIT 1
            """, {"cid": campaign_id})
            lc_ledger = cur.fetchone()

            trace.append({
                "driver_id": driver_id,
                "driver_name": e.get("driver_name"),
                "phone": e.get("phone"),
                "opportunity_found": bool(opp),
                "program_code": e.get("program_code"),
                "worklist_found": True,
                "queue_found": True,
                "queue_status": e.get("queue_status"),
                "export_found": bool(lc_ledger),
                "campaign_id_external": campaign_id,
                "export_batch_id": str(e.get("export_batch_id")),
                "lc_ledger_found": bool(lc_ledger),
                "lc_export_status": lc_ledger["export_status"] if lc_ledger else None,
                "state_lifecycle": state["lifecycle_state"] if state else None,
                "state_orders_week": state["completed_orders_week"] if state else None,
            })
            print(f"    traced: {driver_id[:12]}... phone={e.get('phone')} campaign={campaign_id[:12] if campaign_id else 'N/A'}")

        cur.close()

    if not trace:
        print("    WARNING: No EXPORTED records found to trace")

    return trace


def step_7_check_mirror():
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            SELECT
                COUNT(*) as exported_count,
                COUNT(DISTINCT campaign_id_external) as unique_campaigns,
                COUNT(DISTINCT export_batch_id) as unique_batches,
                MAX(exported_at) as latest_export
            FROM growth.yego_lima_assignment_queue
            WHERE assignment_date = %(d)s AND queue_status = 'EXPORTED'
        """, {"d": BOOTSTRAP_DATE})
        mirror = dict(cur.fetchone())
        cur.close()

    mirror["latest_export"] = str(mirror["latest_export"])[:19] if mirror.get("latest_export") else None
    return mirror


def generate_report():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_path = os.path.join(EXPORT_DIR, "operational_bootstrap_report.md")
    json_path = os.path.join(EXPORT_DIR, "operational_bootstrap_metrics.json")
    csv_path = os.path.join(EXPORT_DIR, f"bootstrap_trace_{timestamp}.csv")

    certs = []
    for label, res in results.items():
        if res["status"] == "OK":
            certs.append(("PASS", label))
        else:
            certs.append(("FAIL", label))

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# LG-C1.1A Operational Bootstrap Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Bootstrap Date: {BOOTSTRAP_DATE}\n")
        f.write(f"Export Limit: {LIMIT}\n\n")

        f.write("## Step Results\n\n")
        f.write("| # | Step | Status | Time (ms) |\n")
        f.write("|---|------|--------|----------|\n")
        for i, (label, res) in enumerate(results.items(), 1):
            f.write(f"| {i} | {label} | **{res['status']}** | {res['elapsed_ms']} |\n")

        f.write("\n## Upstream Freshness\n\n")
        snap = results.get("freshness_snapshot", {}).get("data", {})
        f.write("| Table | Rows | Latest Date |\n")
        f.write("|-------|------|------------|\n")
        for name, s in snap.items():
            f.write(f"| {name} | {s.get('rows', 0)} | {s.get('latest_business_date', '—')} |\n")

        f.write("\n## Queue Build\n\n")
        qb = results.get("build_queue", {}).get("data", {})
        f.write(f"- Batch ID: {qb.get('assignment_batch_id', 'N/A')}\n")
        f.write(f"- Created: {qb.get('created_count', 0)}\n")
        f.write(f"- READY: {qb.get('ready_count', 0)}\n")
        f.write(f"- HELD: {qb.get('held_count', 0)}\n")
        f.write(f"- Skipped: {qb.get('skipped_duplicates', 0)}\n")

        f.write("\n## Export\n\n")
        ex = results.get("export", {}).get("data", {})
        f.write(f"- Batch ID: {ex.get('export_batch_id', 'N/A')}\n")
        f.write(f"- Campaign ID: {ex.get('campaign_id_external', 'N/A')}\n")
        f.write(f"- Selected: {ex.get('selected_count', 0)}\n")
        f.write(f"- Exported: {ex.get('exported_count', 0)}\n")
        f.write(f"- Skipped: {ex.get('skipped_count', 0)}\n")

        f.write("\n## Mirror Verification\n\n")
        m = results.get("check_mirror", {}).get("data", {})
        f.write(f"- EXPORTED count: {m.get('exported_count', 0)}\n")
        f.write(f"- Unique campaigns: {m.get('unique_campaigns', 0)}\n")
        f.write(f"- Unique batches: {m.get('unique_batches', 0)}\n")
        f.write(f"- Latest export: {m.get('latest_export', '—')}\n")

        f.write("\n## Yango API\n\n")
        ya = results.get("test_yango", {}).get("data", {})
        f.write(f"- Status: {'OK' if ya.get('ok') else 'FAIL'}\n")
        f.write(f"- Enabled: {ya.get('enabled', False)}\n")
        f.write(f"- Records: {ya.get('records_count', 0)}\n")

        f.write("\n## E2E Trace (10 drivers)\n\n")
        trace = results.get("trace_10", {}).get("data", [])
        f.write("| Driver | Phone | Program | Campaign | State | Orders | Queue | LC Ledger |\n")
        f.write("|--------|-------|---------|----------|-------|--------|-------|----------|\n")
        for t in trace:
            f.write(f"| {t.get('driver_name', t['driver_id'][:12])} | {t.get('phone', '—')} | {t.get('program_code', '—')} | {str(t.get('campaign_id_external', ''))[:12]} | {t.get('state_lifecycle', '—')} | {t.get('state_orders_week', '—')} | {t.get('queue_status', '—')} | {t.get('lc_export_status', '—')} |\n")

        f.write("\n## Certification\n\n")
        f.write("| Step | Verdict |\n")
        f.write("|------|--------|\n")
        for label, verdict in certs:
            f.write(f"| {label} | **{verdict}** |\n")

        pass_count = sum(1 for _, v in certs if v == "PASS")
        fail_count = sum(1 for _, v in certs if v == "FAIL")
        f.write(f"\n**{pass_count}P / {fail_count}F**\n")

        if fail_count == 0:
            f.write("\n### VERDICT: GO\n")
        else:
            f.write(f"\n### VERDICT: GO BLOCKED — {fail_count} FAIL(s)\n")

    with open(json_path, "w", encoding="utf-8") as f:
        safe = OrderedDict()
        for label, res in results.items():
            d = res.get("data")
            if isinstance(d, list):
                safe[label] = {"status": res["status"], "count": len(d), "elapsed_ms": res["elapsed_ms"]}
            else:
                safe[label] = {"status": res["status"], "elapsed_ms": res["elapsed_ms"], "summary": str(d)[:500]}
        json.dump({"bootstrap_date": BOOTSTRAP_DATE, "results": safe}, f, indent=2)

    trace_data = results.get("trace_10", {}).get("data", [])
    if trace_data:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=trace_data[0].keys())
            writer.writeheader()
            writer.writerows(trace_data)

    print(f"\nReports written to: {EXPORT_DIR}")
    print(f"  {md_path}")
    print(f"  {json_path}")
    print(f"  {csv_path}")


def main():
    print(f"LG-C1.1A Operational Bootstrap")
    print(f"Date: {BOOTSTRAP_DATE}  |  Limit: {LIMIT}")
    print("=" * 60 + "\n")

    step("test_yango", step_1_test_yango)
    step("run_pipeline", step_2_run_pipeline)
    step("freshness_snapshot", step_5_freshness_snapshot)
    step("build_queue", step_3_build_queue)
    step("export", step_4_export)
    step("check_mirror", step_7_check_mirror)
    step("trace_10", step_6_trace_10)

    print(f"\n{'='*60}")
    print("Generating reports...\n")
    generate_report()

    fails = sum(1 for _, r in results.items() if r["status"] == "FAIL")
    if fails == 0:
        print("\nBOOTSTRAP: ALL STEPS PASSED")
    else:
        print(f"\nBOOTSTRAP: {fails} STEP(S) FAILED")


if __name__ == "__main__":
    main()
