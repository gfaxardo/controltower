#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OV2-B.6A — API Completeness Audit

Audits whether the Yango Fleet API ingestion retrieved 100% of available
orders for Park Lima on a given date, compared against Fleet Room ground truth.

Usage:
  cd backend
  python -m scripts.audit_api_completeness --date 2026-06-04 --fleet-room 11085
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PET = timezone(timedelta(hours=-5))

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"
PARK_NAME = "Yego (Lima)"
DEFAULT_PAGE_SIZE = 500


def _query(sql: str, params: tuple = ()) -> List[Dict]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows


def _query_one(sql: str, params: tuple = ()) -> Optional[Dict]:
    rows = _query(sql, params)
    return rows[0] if rows else None


def _fmt_dt(val: Any) -> str:
    if val is None:
        return "N/A"
    if hasattr(val, "isoformat"):
        return val.isoformat()[:19]
    return str(val)[:19]


def audit(park_id: str, date_str: str, fleet_room_trips: Optional[int]) -> Dict[str, Any]:
    """Main audit function. Returns complete audit result dict."""

    # ── 1. API orders ingested ──────────────────────────────
    orders = _query_one(
        """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT order_id) AS unique_orders,
            COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_rows,
            COUNT(DISTINCT driver_profile_id) AS unique_drivers,
            COUNT(DISTINCT car_id) AS unique_cars,
            MIN(order_created_at) AS first_order,
            MAX(order_created_at) AS last_order
        FROM raw_yango.orders_raw
        WHERE park_id = %s
          AND order_created_at::date = %s::date
        """,
        (park_id, date_str),
    )
    api_total = int(orders["total_rows"] or 0) if orders else 0
    api_unique = int(orders["unique_orders"] or 0) if orders else 0
    api_duplicates = orders["duplicate_rows"] or 0 if orders else 0

    # ── 2. MV count ─────────────────────────────────────────
    mv = _query_one(
        "SELECT COALESCE(SUM(orders_completed),0) AS n FROM raw_yango.mv_orders_day WHERE park_id=%s AND order_date=%s::date",
        (park_id, date_str),
    )
    mv_total = int(mv["n"] or 0) if mv else 0

    # ── 3. Ingestion runs ───────────────────────────────────
    runs = _query(
        """
        SELECT run_id, endpoint_group, status,
               records_fetched, records_inserted, records_updated, record_skips,
               error_count, warning_count, max_concurrency,
               started_at, finished_at, notes
        FROM raw_yango.api_ingestion_run
        WHERE park_id = %s AND date_from = %s::date
        ORDER BY started_at
        """,
        (park_id, date_str),
    )

    completed_runs = [r for r in runs if r["status"] == "completed"]
    stalled_runs = [r for r in runs if r["status"] == "started"]
    failed_runs = [r for r in runs if r["status"] == "failed"]
    total_fetched = sum(r["records_fetched"] or 0 for r in completed_runs)
    total_inserted = sum(r["records_inserted"] or 0 for r in completed_runs)

    # ── 4. Errors ───────────────────────────────────────────
    run_ids = [r["run_id"] for r in runs if r["run_id"]]
    errors = []
    if run_ids:
        placeholders = ",".join(["%s"] * len(run_ids))
        errors = _query(
            f"""
            SELECT error_type, status_code, error_message_sanitized,
                   retry_count, COUNT(*) AS n
            FROM raw_yango.ingestion_errors
            WHERE run_id IN ({placeholders})
            GROUP BY error_type, status_code, error_message_sanitized, retry_count
            ORDER BY n DESC
            """,
            tuple(run_ids),
        )

    # ── 5. Batch analysis ───────────────────────────────────
    batches = _query(
        """
        SELECT api_run_id, COUNT(*) AS n, MIN(id) AS min_row, MAX(id) AS max_row,
               MIN(order_created_at) AS first_at, MAX(order_created_at) AS last_at
        FROM raw_yango.orders_raw
        WHERE park_id = %s AND order_created_at::date = %s::date
        GROUP BY api_run_id
        ORDER BY MIN(id)
        """,
        (park_id, date_str),
    )

    # ── 6. Gap detection ────────────────────────────────────
    gaps = []
    if batches:
        prev_max = 0
        for b in batches:
            min_row = b["min_row"]
            if min_row > prev_max + 1:
                gaps.append({
                    "from_row": prev_max + 1,
                    "to_row": min_row - 1,
                    "missing": min_row - prev_max - 1,
                    "between_batches": True,
                })
            prev_max = max(prev_max, b["max_row"])

    # ── 7. Page estimation ──────────────────────────────────
    expected_pages = (fleet_room_trips // DEFAULT_PAGE_SIZE) + (1 if fleet_room_trips and fleet_room_trips % DEFAULT_PAGE_SIZE > 0 else 0) if fleet_room_trips else None
    actual_pages = len(batches) if batches else 0

    # page_size * 3 runs counts: 500 + 1000 + 3000 = 4500
    # suggesting page sizes of 500, 500, 500 but combined into 3 batches

    # ── 8. Coverage calculation ─────────────────────────────
    coverage_pct = round(api_unique / fleet_room_trips * 100, 2) if fleet_room_trips and fleet_room_trips > 0 else None
    missing_orders = fleet_room_trips - api_unique if fleet_room_trips else None

    # ── 9. Verdict ──────────────────────────────────────────
    if coverage_pct is None:
        verdict = "NO_FLEET_ROOM_DATA"
        verdict_reason = "Fleet Room trips not provided. Re-run with --fleet-room <number>."
    elif coverage_pct >= 99:
        verdict = "PASS"
        verdict_reason = f"API coverage {coverage_pct}% >= 99% threshold. API certified."
    elif coverage_pct >= 95:
        verdict = "WARNING"
        verdict_reason = f"API coverage {coverage_pct}% between 95-99%. Minor data loss."
    else:
        verdict = "FAIL"
        verdict_reason = f"API coverage {coverage_pct}% < 95% threshold. API incomplete. Missing {missing_orders} orders."

    return {
        "audit_date": datetime.now(PET).isoformat(),
        "park": {"id": park_id, "name": PARK_NAME},
        "target_date": date_str,
        "fleet_room": {
            "trips": fleet_room_trips,
            "provided": fleet_room_trips is not None,
        },
        "api_raw": {
            "total_rows": api_total,
            "unique_orders": api_unique,
            "duplicate_rows": api_duplicates,
            "unique_drivers": orders["unique_drivers"] if orders else 0,
            "unique_cars": orders["unique_cars"] if orders else 0,
            "first_order": _fmt_dt(orders["first_order"]) if orders else None,
            "last_order": _fmt_dt(orders["last_order"]) if orders else None,
        },
        "mv": {
            "orders_completed": mv_total,
            "source": "raw_yango.mv_orders_day",
        },
        "ingestion": {
            "total_runs": len(runs),
            "completed_runs": len(completed_runs),
            "stalled_runs": len(stalled_runs),
            "failed_runs": len(failed_runs),
            "total_fetched_reported": total_fetched,
            "total_inserted_reported": total_inserted,
            "counter_note": "Counters may show 0 even when data was ingested (known bug).",
        },
        "errors": {
            "total_error_types": len(errors),
            "details": [
                {
                    "type": e["error_type"],
                    "status_code": e["status_code"],
                    "message": (e["error_message_sanitized"] or "")[:100],
                    "retries": e["retry_count"],
                    "count": e["n"],
                }
                for e in errors
            ],
        },
        "pagination": {
            "batches": len(batches),
            "expected_pages": expected_pages,
            "actual_pages_ingested": actual_pages,
            "page_size_default": DEFAULT_PAGE_SIZE,
            "gaps": gaps,
            "total_missing_between_gaps": sum(g["missing"] for g in gaps),
            "batch_details": [
                {
                    "run_id": b["api_run_id"][:40] if b["api_run_id"] else None,
                    "count": b["n"],
                    "row_range": f"{b['min_row']}-{b['max_row']}",
                    "time_range": f"{_fmt_dt(b['first_at'])}..{_fmt_dt(b['last_at'])}",
                }
                for b in batches
            ],
        },
        "runs_detail": [
            {
                "run_id": r["run_id"][:40] if r["run_id"] else None,
                "endpoint": r["endpoint_group"],
                "status": r["status"],
                "fetched": r["records_fetched"],
                "inserted": r["records_inserted"],
                "skipped": r["record_skips"],
                "errors": r["error_count"],
                "concurrency": r["max_concurrency"],
                "started": _fmt_dt(r["started_at"]),
                "finished": _fmt_dt(r["finished_at"]),
            }
            for r in runs
        ],
        "coverage": {
            "api_unique": api_unique,
            "fleet_room": fleet_room_trips,
            "coverage_pct": coverage_pct,
            "missing_orders": missing_orders,
        },
        "verdict": verdict,
        "verdict_reason": verdict_reason,
    }


# ── Report Formatting ────────────────────────────────────────


def print_report(result: Dict[str, Any]) -> None:
    r = result
    fr = r["fleet_room"]
    ar = r["api_raw"]
    ing = r["ingestion"]
    cov = r["coverage"]
    pag = r["pagination"]

    print("=" * 72)
    print("  OV2-B.6A — API COMPLETENESS AUDIT")
    print("=" * 72)
    print(f"  Park:         {r['park']['name']} ({r['park']['id']})")
    print(f"  Date:         {r['target_date']}")
    print(f"  Fleet Room:   {fr['trips']:,}" if fr["provided"] else "  Fleet Room:   NOT PROVIDED")
    print()

    print(f"  [API RAW]")
    print(f"    Total rows:     {ar['total_rows']:>8,}")
    print(f"    Unique orders:  {ar['unique_orders']:>8,}")
    print(f"    Duplicates:     {ar['duplicate_rows']:>8,}")
    print(f"    Unique drivers: {ar['unique_drivers']:>8,}")
    print(f"    Unique cars:    {ar['unique_cars']:>8,}")
    print(f"    First order:    {ar['first_order']}")
    print(f"    Last order:     {ar['last_order']}")

    print(f"\n  [MV]")
    print(f"    Orders:         {r['mv']['orders_completed']:>8,}")
    print(f"    Note:           MV uses operational_date (may differ from created_at)")

    print(f"\n  [INGESTION RUNS]")
    print(f"    Total runs:     {ing['total_runs']}")
    print(f"    Completed:      {ing['completed_runs']}")
    print(f"    Stalled:        {ing['stalled_runs']}  <- NOT completed, ingestion interrupted")
    print(f"    Failed:         {ing['failed_runs']}")
    print(f"    Fetched (rpt):  {ing['total_fetched_reported']}")
    print(f"    Inserted (rpt): {ing['total_inserted_reported']}")
    if ing["counter_note"]:
        print(f"    Note:           {ing['counter_note']}")

    print(f"\n  [PAGINATION]")
    print(f"    Batches found:  {pag['batches']}")
    if pag["expected_pages"]:
        print(f"    Expected pages: {pag['expected_pages']} (at {pag['page_size_default']}/page)")
    print(f"    Actual pages:   {pag['actual_pages_ingested']}")
    if pag["batch_details"]:
        print(f"    Batch breakdown:")
        for b in pag["batch_details"]:
            print(f"      {b['count']:>5,} orders  rows {b['row_range']}  {b['time_range']}")
    if pag["gaps"]:
        print(f"\n    ID GAPS (missing segments between batches):")
        for g in pag["gaps"]:
            print(f"      rows {g['from_row']}-{g['to_row']}: {g['missing']:,} missing orders")
        print(f"    Total missing:  {pag['total_missing_between_gaps']:,}")
    else:
        print(f"    No gaps between batches.")

    errs = r["errors"]
    if errs["total_error_types"] > 0:
        print(f"\n  [ERRORS]")
        for e in errs["details"]:
            print(f"    {e['type']}: HTTP {e['status_code']} x{e['count']} retries={e['retries']} ({e['message']})")
    else:
        print(f"\n  [ERRORS]")
        print(f"    No ingestion errors recorded.")

    print(f"\n  {'=' * 72}")
    print(f"  COVERAGE CALCULATION")
    print(f"  {'=' * 72}")

    if cov["coverage_pct"] is not None:
        print(f"  API orders:      {cov['api_unique']:>8,}")
        print(f"  Fleet Room:      {cov['fleet_room']:>8,}")
        print(f"  Coverage:        {cov['coverage_pct']:>9.2f}%")
        print(f"  Missing:         {cov['missing_orders']:>8,}")
        bar = "#" * int(cov["coverage_pct"] / 5)
        print(f"  Bar:             [{bar:<20}] {cov['coverage_pct']:.1f}%")
    else:
        print(f"  Fleet Room data not provided. Cannot calculate coverage.")

    print(f"\n  VERDICT: {r['verdict']}")
    print(f"  {r['verdict_reason']}")

    verdict_map = {"PASS": ">=99% API certified", "WARNING": "95-99%", "FAIL": "<95% API incomplete", "NO_FLEET_ROOM_DATA": "pending"}
    print(f"  Threshold:       {verdict_map.get(r['verdict'], '?')}")


def export_csv(result: Dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cov = result["coverage"]
    ing = result["ingestion"]
    pag = result["pagination"]
    ar = result["api_raw"]
    er = result["errors"]

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["audit_date", "park_id", "target_date",
                     "fleet_room_trips", "api_unique_orders", "api_total_rows",
                     "coverage_pct", "missing_orders", "verdict",
                     "completed_runs", "stalled_runs", "failed_runs",
                     "batches_ingested", "expected_pages", "error_types",
                     "mv_orders", "unique_drivers", "unique_cars"])
        w.writerow([
            result["audit_date"], result["park"]["id"], result["target_date"],
            cov["fleet_room"], ar["unique_orders"], ar["total_rows"],
            cov["coverage_pct"], cov["missing_orders"], result["verdict"],
            ing["completed_runs"], ing["stalled_runs"], ing["failed_runs"],
            pag["batches"], pag["expected_pages"], er["total_error_types"],
            result["mv"]["orders_completed"], ar["unique_drivers"], ar["unique_cars"],
        ])
    print(f"\n[export] CSV: {path}")


def export_json(result: Dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"[export] JSON: {path}")


# ── Main ────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="API Completeness Audit (OV2-B.6A)")
    ap.add_argument("--park-id", default=PARK_ID)
    ap.add_argument(
        "--date", default="2026-06-04",
        help="Date to audit in YYYY-MM-DD format",
    )
    ap.add_argument(
        "--fleet-room", type=int, default=None,
        help="Total orders reported by Fleet Room for this date",
    )
    ap.add_argument(
        "--output-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports", "audits", "api_completeness",
        ),
    )
    args = ap.parse_args()

    result = audit(args.park_id, args.date, args.fleet_room)
    print_report(result)

    base = f"api_completeness_{args.date.replace('-', '')}"
    export_csv(result, os.path.join(args.output_dir, f"{base}.csv"))
    export_json(result, os.path.join(args.output_dir, f"{base}.json"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
