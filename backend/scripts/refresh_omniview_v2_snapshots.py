#!/usr/bin/env python3
"""
Refresh Omniview V2 Serving Snapshots.

Usage:
  cd backend
  python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --confirm
  python -m scripts.refresh_omniview_v2_snapshots --date 2026-06-05 --payload-type matrix --confirm
  python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date as dt_date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from app.services.omniview_v2_snapshot_service import (
    build_and_store_matrix_snapshot,
    build_and_store_shell_snapshot,
    get_snapshot_health,
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "omniview_v2_snapshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _get_latest_closed_date(source_system: str) -> str:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if source_system == "CT_TRIPS_2026":
                cur.execute(
                    "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact "
                    "WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'"
                )
            elif source_system == "YANGO_API_RAW":
                cur.execute(
                    "SELECT MAX(order_date) FROM raw_yango.mv_orders_day "
                    "WHERE park_id='08e20910d81d42658d4334d3f6d10ac0'"
                )
            else:
                cur.close()
                return dt_date.today().isoformat()
            row = cur.fetchone()
            cur.close()
            if row and row[0]:
                return row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
    except Exception:
        pass
    return dt_date.today().isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh OV2 serving snapshots")
    ap.add_argument("--source-system", default="CT_TRIPS_2026")
    ap.add_argument("--grain", default="day")
    ap.add_argument("--date", default=None)
    ap.add_argument("--payload-type", default="all", choices=["all", "shell", "matrix"])
    ap.add_argument("--use-latest-closed-date", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    operating_date = args.date
    if args.use_latest_closed_date or not operating_date:
        operating_date = _get_latest_closed_date(args.source_system)

    print(f"[snapshot] source={args.source_system} grain={args.grain} date={operating_date}")
    print(f"[snapshot] type={args.payload_type} dry_run={args.dry_run}")

    if args.dry_run:
        print(f"[snapshot] DRY-RUN: would generate snapshots for {operating_date}")
        health = get_snapshot_health()
        print(f"[snapshot] Current health: {health}")
        return 0

    if not args.confirm:
        print("[snapshot] Use --confirm to actually generate snapshots.")
        return 0

    filters = None
    if args.source_system == "CT_TRIPS_2026":
        filters = {"country": "peru", "city": "lima"}
    elif args.source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}

    results = []

    if args.payload_type in ("all", "shell"):
        print("[snapshot] Building shell...")
        r = build_and_store_shell_snapshot(args.source_system, args.grain, operating_date, filters)
        results.append(r)
        status = "OK" if r.get("ok") else "FAIL"
        print(f"  shell: {status} ({r.get('ms', '?')}ms)")

    if args.payload_type in ("all", "matrix"):
        print("[snapshot] Building matrix...")
        r = build_and_store_matrix_snapshot(args.source_system, args.grain, operating_date, filters)
        results.append(r)
        status = "OK" if r.get("ok") else "FAIL"
        print(f"  matrix: {status} ({r.get('ms', '?')}ms)")

    health = get_snapshot_health()

    # Write summary
    md = [
        "# OV2 Snapshot Refresh Report",
        "",
        f"**Generated:** {datetime.now().isoformat()}",
        f"**Source:** {args.source_system}",
        f"**Grain:** {args.grain}",
        f"**Date:** {operating_date}",
        "",
        "| Type | Status | Build (ms) |",
        "|------|--------|------------|",
    ]
    for r in results:
        md.append(f"| {r.get('type','?')} | {'OK' if r.get('ok') else 'FAIL'} | {r.get('ms','?')} |")

    md += [
        "",
        "## Snapshot Health",
        "",
        f"| Total | Ready | Stale | Failed |",
        f"|-------|-------|-------|--------|",
        f"| {health['total']} | {health['ready']} | {health['stale']} | {health['failed']} |",
    ]

    summary_path = os.path.join(OUTPUT_DIR, "refresh_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n[snapshot] Report: {summary_path}")
    print(f"[snapshot] Health: {health}")
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
