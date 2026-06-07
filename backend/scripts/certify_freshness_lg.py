"""
LG-C1.1 — Freshness Certification Script.

Queries all Lima Growth tables, computes freshness metrics,
generates certification reports.

Read-only. No modifications.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import csv
from datetime import datetime, timezone, date as date_type
from collections import OrderedDict

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

TABLES = OrderedDict([
    ("driver_state_snapshot", {
        "table": "growth.yango_lima_driver_state_snapshot",
        "business_date_col": "snapshot_date",
        "insert_col": "last_calculated_at",
        "grain": "date + driver_profile_id",
        "source": "driver_state_service",
        "description": "Daily driver state snapshot (lifecycle, performance, retention)",
    }),
    ("prioritized_opportunity", {
        "table": "growth.yango_lima_prioritized_opportunity_daily",
        "business_date_col": "opportunity_date",
        "insert_col": "generated_at",
        "grain": "date + driver_profile_id",
        "source": "opportunity_policy_service",
        "description": "Daily prioritized opportunities with program assignments",
    }),
    ("driver_360_daily", {
        "table": "growth.yango_lima_driver_360_daily",
        "business_date_col": "date",
        "insert_col": "last_calculated_at",
        "grain": "date + driver_profile_id",
        "source": "driver_360_repository",
        "description": "Daily driver 360 fact table (orders, supply, revenue)",
    }),
    ("capacity_config", {
        "table": "growth.yego_lima_capacity_config",
        "business_date_col": "config_date",
        "insert_col": "updated_at",
        "grain": "config_date + channel (nullable date for default)",
        "source": "capacity_service",
        "description": "Daily capacity config per channel",
    }),
    ("loopcontrol_config", {
        "table": "growth.yango_lima_loopcontrol_config",
        "business_date_col": None,
        "insert_col": "updated_at",
        "grain": "single row config",
        "source": "loopcontrol_export_service",
        "description": "LoopControl integration configuration",
    }),
    ("loopcontrol_export", {
        "table": "growth.yango_lima_loopcontrol_campaign_export",
        "business_date_col": "opportunity_date",
        "insert_col": "exported_at",
        "grain": "export_id",
        "source": "loopcontrol_export_service",
        "description": "LoopControl campaign export history",
    }),
    ("assignment_queue", {
        "table": "growth.yego_lima_assignment_queue",
        "business_date_col": "assignment_date",
        "insert_col": "created_at",
        "grain": "assignment_date + driver_id + program_code",
        "source": "assignment_queue_service",
        "description": "Persistent operational queue from worklist",
    }),
    ("loopcontrol_result_sync", {
        "table": "growth.yego_lima_loopcontrol_result_sync",
        "business_date_col": "last_call_at",
        "insert_col": "synced_at",
        "grain": "result_id",
        "source": "result_sync_service",
        "description": "Normalized LoopControl call results",
    }),
    ("impact_tracking", {
        "table": "growth.yego_lima_impact_tracking",
        "business_date_col": "contact_date",
        "insert_col": "created_at",
        "grain": "driver_id + campaign_id_external + contact_date",
        "source": "impact_service",
        "description": "Contact-to-return impact measurement",
    }),
    ("movement_tracking", {
        "table": "growth.yego_lima_movement_tracking",
        "business_date_col": "movement_date",
        "insert_col": "created_at",
        "grain": "driver_id + impact_tracking_id",
        "source": "movement_service",
        "description": "State transitions before/after contact",
    }),
    ("attribution_candidates", {
        "table": "growth.yego_lima_attribution_candidates",
        "business_date_col": None,
        "insert_col": "created_at",
        "grain": "movement_tracking_id",
        "source": "attribution_service",
        "description": "Candidate attribution linking movements to campaigns",
    }),
])

EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "exports", "audits", "lima_growth")
os.makedirs(EXPORT_DIR, exist_ok=True)


def query_metrics():
    results = OrderedDict()

    for name, meta in TABLES.items():
        table = meta["table"]
        biz_col = meta["business_date_col"]
        insert_col = meta.get("insert_col", "created_at")

        row = {"name": name, "table": table, "description": meta["description"],
               "grain": meta["grain"], "source": meta["source"]}

        try:
            with get_db() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)

                cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                row["total_rows"] = int(cur.fetchone()["cnt"])

                if biz_col:
                    cur.execute(f"SELECT MAX({biz_col}) as latest FROM {table}")
                    latest = cur.fetchone()["latest"]
                    row["latest_business_date"] = str(latest)[:10] if latest else None

                    cur.execute(
                        f"SELECT COUNT(*) as cnt FROM {table} WHERE {biz_col} >= current_date - interval '7 days'"
                    )
                    row["rows_last_7d"] = int(cur.fetchone()["cnt"])
                else:
                    row["latest_business_date"] = None
                    row["rows_last_7d"] = None

                cur.execute(f"SELECT MAX({insert_col}) as latest_insert FROM {table}")
                insert = cur.fetchone()["latest_insert"]
                row["latest_insert"] = str(insert)[:19] if insert else None

                if row["latest_insert"]:
                    latest_dt = insert.replace(tzinfo=timezone.utc) if insert.tzinfo is None else insert
                    now_utc = datetime.now(timezone.utc)
                    lag_seconds = (now_utc - latest_dt).total_seconds()
                    row["lag_hours"] = round(lag_seconds / 3600, 1)
                else:
                    row["lag_hours"] = None

                cur.close()

            results[name] = row
            print(f"  OK: {name} ({row['total_rows']} rows, lag {row.get('lag_hours')}h)")

        except Exception as e:
            row["error"] = str(e)[:200]
            row["total_rows"] = 0
            results[name] = row
            print(f"  ERR: {name} - {str(e)[:100]}")

    return results


def certify_freshness(results):
    certified = OrderedDict()
    for name, r in results.items():
        if r.get("error"):
            cert = "FAIL"
            reason = f"Query error: {r['error'][:80]}"
        elif r["total_rows"] == 0:
            cert = "WARNING"
            reason = "Table is empty"
        elif r.get("lag_hours") is None:
            cert = "WARNING"
            reason = "No insert timestamp available"
        elif r["lag_hours"] <= 24:
            cert = "PASS"
            reason = f"Fresh within 24h (lag {r['lag_hours']}h)"
        elif r["lag_hours"] <= 72:
            cert = "WARNING"
            reason = f"Stale 1-3 days (lag {r['lag_hours']}h)"
        else:
            cert = "FAIL"
            reason = f"Stale >3 days (lag {r['lag_hours']}h)"

        if r.get("latest_business_date") and r.get("rows_last_7d", 0) == 0:
            if cert == "PASS":
                cert = "WARNING"
                reason += " | No rows in last 7 days"

        certified[name] = {
            "table": r["table"],
            "total_rows": r["total_rows"],
            "latest_business_date": r.get("latest_business_date"),
            "latest_insert": r.get("latest_insert"),
            "lag_hours": r.get("lag_hours"),
            "certification": cert,
            "reason": reason,
            "source": r["source"],
            "grain": r["grain"],
        }

    return certified


def certify_component(name, rows):
    has_7d = bool(rows.get("rows_last_7d", 0))
    has_multiple_days = rows.get("latest_business_date") is not None and rows.get("rows_last_7d", 0) > 1
    has_lag = rows.get("lag_hours")
    size = rows["total_rows"]

    if size == 0:
        return "WARNING", "Empty table"
    if has_lag is None:
        return "WARNING", "No freshness timestamp"
    if has_lag <= 24:
        return "PASS", f"{has_7d=}, {has_multiple_days=}, lag={rows['lag_hours']}h"
    if has_lag <= 72:
        return "WARNING", f"Stale but has data ({has_7d=}, lag={rows['lag_hours']}h)"
    return "FAIL", f"Very stale (lag={rows['lag_hours']}h)"


def certify_components(results):
    print("\nCertifying components (7-day window)...")
    components = {}
    for name in ["prioritized_opportunity", "driver_state_snapshot", "driver_360_daily",
                 "assignment_queue", "loopcontrol_result_sync", "impact_tracking",
                 "movement_tracking", "attribution_candidates"]:
        r = results.get(name, {})
        cert, reason = certify_component(name, r)
        components[name] = {"certification": cert, "reason": reason}
        print(f"  {cert:7s} | {name}: {reason}")
    return components


def export_reports(results, certified, components):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    md_path = os.path.join(EXPORT_DIR, "freshness_certification.md")
    csv_path = os.path.join(EXPORT_DIR, "freshness_matrix.csv")
    json_path = os.path.join(EXPORT_DIR, "freshness_metrics.json")
    txt_path = os.path.join(EXPORT_DIR, f"freshness_certification_{timestamp}.txt")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# LG-C1.1 Freshness Certification\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write("## Summary\n\n")
        f.write("| Table | Rows | Biz Date | Insert | Lag (h) | Cert |\n")
        f.write("|-------|------|----------|--------|---------|------|\n")
        for name, c in certified.items():
            f.write(f"| {name} | {c['total_rows']} | {c['latest_business_date'] or '—'} | {c['latest_insert'] or '—'} | {c['lag_hours'] or '—'} | **{c['certification']}** |\n")
        f.write("\n## Component Certification\n\n")
        f.write("| Component | Certification | Reason |\n")
        f.write("|-----------|---------------|--------|\n")
        for name, comp in components.items():
            f.write(f"| {name} | **{comp['certification']}** | {comp['reason']} |\n")
        f.write("\n## Risks\n\n")
        risks = [(n, c) for n, c in certified.items() if c['certification'] in ('WARNING', 'FAIL')]
        if risks:
            for n, c in risks:
                f.write(f"- **{c['certification']}**: `{n}` — {c['reason']}\n")
        else:
            f.write("- No risks detected\n")
        f.write("\n## Recommendations\n\n")
        f.write("- Run pipeline refresh if any table shows lag > 24h\n")
        f.write("- Ensure daily snapshots for driver_state and prioritized_opportunity\n")
        f.write("- Monitor assignment_queue for new daily batches\n")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["table", "total_rows", "latest_business_date", "latest_insert", "lag_hours", "certification", "reason"])
        for name, c in certified.items():
            writer.writerow([name, c["total_rows"], c["latest_business_date"], c["latest_insert"], c["lag_hours"], c["certification"], c["reason"]])

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "tables": {name: {k: str(v) if v is not None else None for k, v in cert.items()} for name, cert in certified.items()},
            "components": components,
            "summary": {
                "pass": sum(1 for c in certified.values() if c["certification"] == "PASS"),
                "warning": sum(1 for c in certified.values() if c["certification"] == "WARNING"),
                "fail": sum(1 for c in certified.values() if c["certification"] == "FAIL"),
            }
        }, f, indent=2)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"LG-C1.1 Freshness Certification — {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        for name, c in certified.items():
            f.write(f"{c['certification']:7s} | {name:35s} | rows={c['total_rows']:6d} | biz={str(c['latest_business_date']):10s} | lag={c['lag_hours']}h\n")

    print(f"\nReports written to: {EXPORT_DIR}")
    for fname in [md_path, csv_path, json_path, txt_path]:
        print(f"  {fname}")


def main():
    print("LG-C1.1 Freshness Certification")
    print("=" * 60)
    print("Querying all Lima Growth tables...\n")

    results = query_metrics()

    print("\n" + "=" * 60)
    print("Certification Results:\n")

    certified = certify_freshness(results)
    components = certify_components(results)

    for name, c in certified.items():
        print(f"  {c['certification']:7s} | {name:35s} | {c['total_rows']:6d} rows | lag={c['lag_hours']}h")

    summary = {
        "pass": sum(1 for c in certified.values() if c["certification"] == "PASS"),
        "warning": sum(1 for c in certified.values() if c["certification"] == "WARNING"),
        "fail": sum(1 for c in certified.values() if c["certification"] == "FAIL"),
    }
    print(f"\n{'='*60}")
    print(f"SUMMARY: {summary['pass']} PASS, {summary['warning']} WARNING, {summary['fail']} FAIL")

    export_reports(results, certified, components)

    if summary["fail"] > 0:
        print("\nVERDICT: GO BLOCKED — FAILs must be resolved")
    elif summary["warning"] > 0:
        print("\nVERDICT: GO WITH CAUTION — WARNINGs present but non-blocking")
    else:
        print("\nVERDICT: GO — All tables fresh within 24h")

    return certified


if __name__ == "__main__":
    main()
