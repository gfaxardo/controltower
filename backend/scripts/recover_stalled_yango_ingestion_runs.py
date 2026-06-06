#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recover stalled Yango ingestion runs.

Detects runs with stale heartbeat, marks them as stalled, and optionally
resumes ingestion for missing pages.

Usage:
  # Diagnose only
  python -m scripts.recover_stalled_yango_ingestion_runs --date 2026-06-04

  # Resume missing pages for a specific run
  python -m scripts.recover_stalled_yango_ingestion_runs --date 2026-06-04 \
    --endpoint-group orders --resume-missing-pages --confirm-live

  # Mark stalled but don't resume
  python -m scripts.recover_stalled_yango_ingestion_runs --date 2026-06-04 \
    --mark-stalled --stale-minutes 15
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PET = timezone(timedelta(hours=-5))

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def _query(sql: str, params: tuple = ()) -> List[Dict]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _write_report(lines: list, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[report] {path}")


def diagnose(park_id: str, date_str: str, stale_min: int) -> Dict[str, Any]:
    """Diagnose all runs for a park/date. Returns structured result."""
    from app.repositories.raw_yango_repository import (
        get_stalled_runs, get_completed_runs, mark_stalled_runs,
    )

    stalled = get_stalled_runs(park_id, stale_min)
    completed = get_completed_runs(park_id, date_str, date_str)

    return {
        "park_id": park_id,
        "date": date_str,
        "stale_threshold_min": stale_min,
        "stalled_runs": len(stalled),
        "completed_runs": len(completed),
        "stalled_details": [
            {
                "run_id": r["run_id"],
                "endpoint": r["endpoint_group"],
                "status": r["status"],
                "current_page": r["current_page"],
                "last_cursor": r["last_cursor"],
                "next_cursor": r["next_cursor"],
                "pages_done": r["pages_completed"],
                "expected": r["expected_pages"],
                "fetched": r["records_fetched"],
                "inserted": r["records_inserted"],
                "errors": r["error_count"],
                "stale_min": round(r["stale_min"], 1) if r.get("stale_min") else None,
                "started": str(r["started_at"])[:19] if r["started_at"] else None,
            }
            for r in stalled
        ],
        "completed_details": [
            {
                "run_id": r["run_id"],
                "endpoint": r["endpoint_group"],
                "fetched": r["records_fetched"],
                "inserted": r["records_inserted"],
                "pages_done": r["pages_completed"],
                "expected": r["expected_pages"],
                "started": str(r["started_at"])[:19] if r["started_at"] else None,
                "finished": str(r["finished_at"])[:19] if r["finished_at"] else None,
            }
            for r in completed
        ],
    }


def mark_and_report(park_id: str, date_str: str, stale_min: int,
                    output_dir: str) -> str:
    """Mark stalled runs and generate report."""
    from app.repositories.raw_yango_repository import mark_stalled_runs, get_stalled_runs

    diag = diagnose(park_id, date_str, stale_min)

    if diag["stalled_runs"] == 0:
        print("No stalled runs detected.")
        return ""

    marked = mark_stalled_runs(park_id, stale_min)

    md = [
        "# Stalled Run Recovery Report",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Park:** {park_id}",
        f"**Date:** {date_str}",
        f"**Stale threshold:** {stale_min} min",
        "",
        f"## Summary",
        f"- Stalled runs detected: {diag['stalled_runs']}",
        f"- Marked as stalled: {marked}",
        f"- Completed runs: {diag['completed_runs']}",
        "",
    ]

    if diag["stalled_details"]:
        md.append("## Stalled Runs")
        md.append("| Run ID | Endpoint | Pages Done | Expected | Fetched | Inserted | Stale (min) |")
        md.append("|--------|----------|-----------|----------|---------|----------|-------------|")
        for s in diag["stalled_details"]:
            md.append(
                f"| {s['run_id'][:24]} | {s['endpoint']} | {s['pages_done'] or '?'} "
                f"| {s['expected'] or '?'} | {s['fetched']} | {s['inserted']} "
                f"| {s['stale_min']} |"
            )

        md.append("")
        md.append("## Recovery Plan")
        md.append("")
        for s in diag["stalled_details"]:
            if s["endpoint"] == "orders":
                md.append(f"### Resume: {s['run_id'][:30]}")
                md.append(f"```bash")
                cmd = [
                    "python -m scripts.recover_stalled_yango_ingestion_runs",
                    f"  --date {date_str}",
                    f"  --endpoint-group orders",
                    f"  --resume-missing-pages",
                    f"  --start-from-cursor \"{s['next_cursor'] or ''}\"",
                    f"  --run-id {s['run_id']}",
                    f"  --expected-total 11085",
                    f"  --confirm-live",
                ]
                md.extend(cmd)
                md.append("```")

    if diag["completed_details"]:
        md.append("## Completed Runs")
        md.append("| Run ID | Endpoint | Fetched | Inserted | Pages | Expected |")
        md.append("|--------|----------|---------|----------|-------|----------|")
        for c in diag["completed_details"]:
            md.append(
                f"| {c['run_id'][:24]} | {c['endpoint']} | {c['fetched']} "
                f"| {c['inserted']} | {c['pages_done'] or '?'} | {c['expected'] or '?'} |"
            )

    path = os.path.join(output_dir, "stalled_run_recovery.md")
    _write_report(md, path)

    csv_path = os.path.join(output_dir, "stalled_runs.csv")
    os.makedirs(output_dir, exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "endpoint", "status", "pages_done", "expected",
                     "fetched", "inserted", "stale_min", "started"])
        for s in diag["stalled_details"]:
            w.writerow([s["run_id"], s["endpoint"], "stalled",
                        s["pages_done"], s["expected"], s["fetched"],
                        s["inserted"], s["stale_min"], s["started"]])
    print(f"[csv] {csv_path}")

    json_path = os.path.join(output_dir, "stalled_runs_diagnostic.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(diag, f, indent=2, default=str)
    print(f"[json] {json_path}")

    return path


def resume_missing_pages(park_id: str, date_str: str, endpoint: str,
                         expected_total: Optional[int] = None,
                         start_cursor: Optional[str] = None,
                         run_id: Optional[str] = None,
                         dry_run: bool = True) -> None:
    """Resume ingestion for missing pages."""
    if dry_run:
        print(f"\n[DRY RUN] Would resume {endpoint} ingestion for {date_str}")
        print(f"  Park: {park_id}")
        print(f"  Expected total: {expected_total}")
        print(f"  Start cursor: {start_cursor or 'from beginning'}")
        print(f"  Run ID: {run_id or 'new run'}")
        print(f"\n  To execute, add --confirm-live flag.")
        return

    # Live execution
    import subprocess

    cmd = [
        sys.executable, "-m", "scripts.ingest_yango_raw_landing",
        "--date", date_str,
        "--endpoint-group", endpoint,
        "--park-id", park_id,
    ]
    if run_id:
        cmd.extend(["--resume-run-id", run_id])
    if start_cursor:
        cmd.extend(["--start-cursor", start_cursor])
    if expected_total:
        cmd.extend(["--expected-total", str(expected_total)])
        cmd.extend(["--fail-on-coverage-below", "0.95"])

    print(f"\n[LIVE] Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"\n[LIVE] Exit code: {result.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover stalled Yango ingestion runs")
    ap.add_argument("--park-id", default=PARK_ID)
    ap.add_argument("--date", default="2026-06-04", help="Target date YYYY-MM-DD")
    ap.add_argument("--endpoint-group", default="orders",
                    choices=["orders", "transactions", "driver_profiles", "all"])
    ap.add_argument("--stale-minutes", type=int, default=30,
                    help="Minutes without heartbeat to consider stalled")
    ap.add_argument("--mark-stalled", action="store_true",
                    help="Mark stalled runs (changes DB)")
    ap.add_argument("--resume-missing-pages", action="store_true",
                    help="Resume ingestion for missing pages")
    ap.add_argument("--start-from-cursor", default=None,
                    help="Start from a specific cursor value")
    ap.add_argument("--run-id", default=None,
                    help="Specific run ID to resume")
    ap.add_argument("--expected-total", type=int, default=None,
                    help="Expected total orders (for coverage validation)")
    ap.add_argument("--confirm-live", action="store_true",
                    help="Actually execute resume (default is dry-run)")
    ap.add_argument("--output-dir",
                    default=os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "exports", "audits", "yango_raw_landing"))
    args = ap.parse_args()

    print("=" * 72)
    print("  STALLED RUN RECOVERY")
    print("=" * 72)
    print(f"  Park:     {args.park_id}")
    print(f"  Date:     {args.date}")
    print(f"  Endpoint: {args.endpoint_group}")
    print(f"  Stale:    {args.stale_minutes} min")
    print()

    if args.mark_stalled or args.resume_missing_pages:
        report_path = mark_and_report(args.park_id, args.date,
                                       args.stale_minutes, args.output_dir)

    if args.resume_missing_pages:
        resume_missing_pages(
            args.park_id, args.date, args.endpoint_group,
            expected_total=args.expected_total,
            start_cursor=args.start_from_cursor,
            run_id=args.run_id,
            dry_run=not args.confirm_live,
        )
    elif not args.mark_stalled:
        diag = diagnose(args.park_id, args.date, args.stale_minutes)
        print(f"  Stalled runs:   {diag['stalled_runs']}")
        print(f"  Completed runs: {diag['completed_runs']}")
        if diag["stalled_runs"] > 0:
            print(f"\n  Run with --mark-stalled to mark them.")
            print(f"  Run with --resume-missing-pages to resume ingestion.")
            print(f"  Always use --confirm-live for actual execution.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
