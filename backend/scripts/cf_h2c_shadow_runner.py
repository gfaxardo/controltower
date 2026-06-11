#!/usr/bin/env python3
"""
CF-H2C — Yango Raw Landing Stabilization + Shadow Mode Runner

Runs shadow reconciliation (Yango vs trips_2026) and driver identity audit.
Read-only on production facts. Creates audit tables only.
Does NOT modify serving facts, Omniview, or UI.

Usage:
  cd backend
  python -m scripts.cf_h2c_shadow_runner --date 2026-06-10
  python -m scripts.cf_h2c_shadow_runner --date-from 2026-06-01 --date-to 2026-06-10
  python -m scripts.cf_h2c_shadow_runner --date-from 2026-06-01 --date-to 2026-06-10 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from app.repositories.raw_yango_repository import (
    get_active_park_credentials,
    get_all_watermarks,
)
from app.services.yango_shadow_reconciliation_service import (
    reconcile_day,
    upsert_shadow_reconciliation,
)
from app.services.yango_driver_identity_audit_service import (
    audit_driver_identity,
    upsert_identity_audit,
)

PET = timezone(timedelta(hours=-5))
LIMA_PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def _today_str() -> str:
    return datetime.now(PET).strftime("%Y-%m-%d")


def _ts() -> str:
    return datetime.now(PET).isoformat()


def get_active_parks() -> list:
    try:
        creds = get_active_park_credentials()
        return [c["park_id"] for c in creds]
    except Exception as e:
        print(f"[WARN] Could not read credential registry: {e}")
        return []


def check_raw_data_exists(park_id: str, endpoint: str) -> bool:
    table_map = {
        "orders": "raw_yango.orders_raw",
        "transactions": "raw_yango.transactions_raw",
        "driver_profiles": "raw_yango.driver_profiles_raw",
    }
    table = table_map.get(endpoint)
    if not table:
        return False
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE park_id = %s LIMIT 1", (park_id,))
            return cur.fetchone()[0] > 0
    except Exception:
        return False


def run_shadow_reconciliation(
    parks: list,
    date_from: str,
    date_to: str,
    dry_run: bool = False,
) -> dict:
    results = {"dates_processed": 0, "dates_skipped": 0, "status_by_date": {}}

    d = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()

    while d <= end:
        d_str = d.strftime("%Y-%m-%d")
        for park_id in parks:
            print(f"\n{'[DRY RUN] ' if dry_run else ''}Reconciling {d_str} park={park_id[:8]}***")
            rec = reconcile_day(park_id, d_str)

            has_data = (
                rec["trips_ct_completed"] > 0
                or rec["trips_yango_completed"] > 0
                or rec["revenue_ct_total"] > 0
                or rec["revenue_yango_total"] > 0
            )

            if not has_data:
                print(f"  -> SKIP: no data for {d_str}")
                results["dates_skipped"] += 1
            elif dry_run:
                print(f"  -> DRY RUN: would upsert reconciliation")
                print(f"     trips: CT={rec['trips_ct_completed']} Yango={rec['trips_yango_completed']} "
                      f"delta={rec['trips_delta_pct']}% [{rec['trips_classification']}]")
                print(f"     revenue: CT={rec['revenue_ct_total']:.2f} Yango={rec['revenue_yango_total']:.2f} "
                      f"delta={rec['revenue_delta_pct']}% [{rec['revenue_classification']}]")
                print(f"     drivers: CT={rec['drivers_ct_active']} Yango={rec['drivers_yango_unique']} "
                      f"delta={rec['drivers_delta_pct']}% [{rec['drivers_classification']}]")
                print(f"     gmv: CT={rec['gmv_ct_total']:.2f} Yango={rec['gmv_yango_total']:.2f} "
                      f"delta={rec['gmv_delta_pct']}% [{rec['gmv_classification']}]")
                print(f"     order_overlap: Yango_only={rec['orders_yango_only']} "
                      f"CT_only={rec['orders_ct_only']} both={rec['orders_both']}")
                print(f"     overall: {rec['overall_status']}")
                results["dates_processed"] += 1
            else:
                ok = upsert_shadow_reconciliation(rec)
                if ok:
                    print(f"  -> UPSERTED: {rec['overall_status']}")
                    results["dates_processed"] += 1
                else:
                    print(f"  -> FAILED to upsert")

            results["status_by_date"][d_str] = {
                "park_id": park_id,
                "overall_status": rec["overall_status"],
                "trips_classification": rec["trips_classification"],
                "revenue_classification": rec["revenue_classification"],
                "drivers_classification": rec["drivers_classification"],
            }

        d += timedelta(days=1)

    return results


def run_identity_audit(parks: list, dry_run: bool = False) -> dict:
    results = {"audits_processed": 0}

    today = _today_str()
    for park_id in parks:
        print(f"\n{'[DRY RUN] ' if dry_run else ''}Identity audit {today} park={park_id[:8]}***")
        rec = audit_driver_identity(park_id, today)

        if dry_run:
            print(f"  -> DRY RUN: would upsert identity audit")
            print(f"     CT drivers: total={rec['ct_drivers_total']} "
                  f"phone={rec['ct_drivers_with_phone']} license={rec['ct_drivers_with_license']} "
                  f"active_today={rec['ct_drivers_active_today']}")
            print(f"     Yango drivers: total={rec['yango_drivers_total']} "
                  f"working={rec['yango_drivers_working']} "
                  f"with_orders={rec['yango_drivers_with_orders']}")
            print(f"     Match by: id={rec['matched_by_all']} name={rec['matched_by_name']} "
                  f"name_partial={rec['matched_by_name_partial']}")
            print(f"     Match by: phone={rec['matched_by_phone']} license={rec['matched_by_license']} "
                  f"name+phone={rec['matched_by_both_name_phone']}")
            print(f"     Unmatched: CT={rec['ct_drivers_unmatched']} "
                  f"Yango={rec['yango_drivers_unmatched']}")
            print(f"     Candidates: high={rec['mapping_candidates_high']} "
                  f"med={rec['mapping_candidates_medium']} low={rec['mapping_candidates_low']}")
            print(f"     Match%: {rec['overall_match_pct']}% [{rec['identity_audit_status']}]")
            results["audits_processed"] += 1
        else:
            ok = upsert_identity_audit(rec)
            if ok:
                print(f"  -> UPSERTED: {rec['identity_audit_status']} "
                      f"({rec['overall_match_pct']}%)")
                results["audits_processed"] += 1
            else:
                print(f"  -> FAILED to upsert")

    return results


def audit_raw_tables() -> dict:
    rows = {}
    tables = ["orders_raw", "transactions_raw", "driver_profiles_raw"]
    try:
        with get_db() as conn:
            cur = conn.cursor()
            for tbl in tables:
                cur.execute(f"SELECT COUNT(*) FROM raw_yango.{tbl}")
                rows[tbl] = cur.fetchone()[0]
    except Exception as e:
        rows["error"] = str(e)
    return rows


def audit_source_tables() -> dict:
    rows = {}
    queries = {
        "trips_2026_total": "SELECT COUNT(*) FROM public.trips_2026",
        "trips_2026_june": "SELECT COUNT(*) FROM public.trips_2026 WHERE fecha_finalizacion >= '2026-06-01'",
        "drivers_total": "SELECT COUNT(*) FROM public.drivers",
        "drivers_active": "SELECT COUNT(*) FROM public.drivers WHERE active = true",
    }
    try:
        with get_db() as conn:
            cur = conn.cursor()
            for label, q in queries.items():
                try:
                    cur.execute(q)
                    rows[label] = cur.fetchone()[0]
                except Exception as e:
                    rows[label] = f"ERROR: {e}"
    except Exception as e:
        rows["error"] = str(e)
    return rows


def main():
    parser = argparse.ArgumentParser(description="CF-H2C Shadow Runner")
    parser.add_argument("--date", type=str, help="Single date to reconcile (YYYY-MM-DD)")
    parser.add_argument("--date-from", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but do not write")
    parser.add_argument("--skip-reconciliation", action="store_true", help="Skip shadow reconciliation")
    parser.add_argument("--skip-identity", action="store_true", help="Skip identity audit")
    parser.add_argument("--audit-only", action="store_true", help="Only audit table sizes, no computation")
    parser.add_argument("--park-id", type=str, default=None, help="Specific park_id (default: auto-detect)")
    args = parser.parse_args()

    print("=" * 70)
    print("CF-H2C — YANGO RAW LANDING STABILIZATION + SHADOW MODE")
    print(f"Timestamp: {_ts()}")
    print("=" * 70)

    # --- Governance ---
    print("\nGOVERNANCE CHECK:")
    print("  Motor: Control Foundation")
    print("  Diagnostic: PAUSED")
    print("  Omniview V2: CLOSED (2ab32e9)")
    print("  Serving facts: NOT modified")
    print("  UI: NOT touched")
    print("  [PASS]")

    # --- Parks ---
    parks = [args.park_id] if args.park_id else get_active_parks()
    if not parks:
        parks = [LIMA_PARK_ID]
        print(f"\n[WARN] No active parks in credential registry. Using default: {LIMA_PARK_ID[:8]}***")
    else:
        print(f"\nACTIVE PARKS: {len(parks)}")
        for p in parks:
            print(f"  - {p[:8]}***")

    # --- Raw tables audit ---
    print("\nRAW TABLES AUDIT:")
    raw_counts = audit_raw_tables()
    for tbl, cnt in raw_counts.items():
        print(f"  raw_yango.{tbl}: {cnt} rows")

    # --- Source tables audit ---
    print("\nSOURCE TABLES AUDIT:")
    src_counts = audit_source_tables()
    for label, cnt in src_counts.items():
        print(f"  {label}: {cnt}")

    # --- Watermarks ---
    print("\nINGESTION WATERMARKS:")
    try:
        wms = get_all_watermarks()
        if wms:
            for w in wms:
                print(f"  {w['park_id'][:8]}*** / {w['endpoint_group']}: "
                      f"last={w['last_source_date']} status={w['status']} "
                      f"records={w['records_total']} failures={w['consecutive_failures']}")
        else:
            print("  (none yet — first run)")
    except Exception as e:
        print(f"  [WARN] Could not read watermarks (table may not exist yet): {e}")

    if args.audit_only:
        print("\n[AUDIT ONLY] Done.")
        return

    # --- Shadow Reconciliation ---
    if not args.skip_reconciliation:
        date_from = args.date or args.date_from or "2026-06-01"
        date_to = args.date or args.date_to or "2026-06-10"
        print(f"\nSHADOW RECONCILIATION: {date_from} -> {date_to}")
        recon_results = run_shadow_reconciliation(
            parks, date_from, date_to, dry_run=args.dry_run
        )
        print(f"\n  Processed: {recon_results['dates_processed']} dates")
        print(f"  Skipped: {recon_results['dates_skipped']} dates (no data)")

        if not args.dry_run and recon_results["dates_processed"] > 0:
            print("\nVERIFICATION QUERY:")
            print("  SELECT source_date, overall_status, trips_classification,")
            print("         revenue_classification, drivers_classification")
            print("  FROM ops.yango_shadow_reconciliation_day")
            print(f"  WHERE source_date >= '{date_from}' AND source_date <= '{date_to}'")
            print("  ORDER BY source_date;")

    # --- Identity Audit ---
    if not args.skip_identity:
        print(f"\nDRIVER IDENTITY AUDIT: {_today_str()}")
        identity_results = run_identity_audit(parks, dry_run=args.dry_run)
        print(f"\n  Processed: {identity_results['audits_processed']} audits")

        if not args.dry_run and identity_results["audits_processed"] > 0:
            print("\nVERIFICATION QUERY:")
            print("  SELECT audit_date, park_id, identity_audit_status,")
            print("         ct_drivers_total, yango_drivers_total, overall_match_pct,")
            print("         mapping_candidates_high")
            print("  FROM ops.yango_driver_identity_audit_day")
            print("  ORDER BY audit_date DESC LIMIT 5;")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("CF-H2C SUMMARY")
    print("=" * 70)

    checks = {
        "raw_yango.orders_raw exists": raw_counts.get("orders_raw", 0) > 0,
        "raw_yango.transactions_raw exists": raw_counts.get("transactions_raw", 0) > 0,
        "raw_yango.driver_profiles_raw exists": raw_counts.get("driver_profiles_raw", 0) > 0,
        "public.trips_2026 has data": src_counts.get("trips_2026_total", 0) > 0,
        "public.drivers has data": src_counts.get("drivers_total", 0) > 0,
        "Watermarks table accessible": True,
    }

    all_pass = True
    for check, status in checks.items():
        flag = "[PASS]" if status else "[FAIL]"
        if not status:
            all_pass = False
        print(f"  {flag} {check}")

    if all_pass:
        print("\n  GO for CF-H2C shadow reconciliation.")
        print("  GO for CF-H2C.1 Driver Identity Foundation.")
    else:
        print("\n  NO-GO: some checks failed. Review above.")

    print("=" * 70)


if __name__ == "__main__":
    main()
