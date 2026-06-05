#!/usr/bin/env python3
"""
Refresh raw_yango materialized views.

Usage:
  cd backend
  python -m scripts.refresh_raw_yango_mvs --mv all
  python -m scripts.refresh_raw_yango_mvs --mv orders_day
  python -m scripts.refresh_raw_yango_mvs --mv all --concurrently
  python -m scripts.refresh_raw_yango_mvs --mv source_coverage_day --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

PET = timezone(timedelta(hours=-5))
SCRIPT_VERSION = "2026-06-05"

MV_DEPENDENCIES = {
    "mv_orders_day": [],
    "mv_transactions_day": [],
    "mv_revenue_day": ["mv_transactions_day"],
    "mv_driver_profiles_snapshot": [],
    "mv_source_coverage_day": ["mv_orders_day", "mv_transactions_day", "mv_driver_profiles_snapshot"],
}

ALL_MVS = ["mv_orders_day", "mv_transactions_day", "mv_revenue_day", "mv_driver_profiles_snapshot", "mv_source_coverage_day"]


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mask(val: str) -> str:
    return (val[:8] + "***") if val and len(val) > 8 else "***"


def _mv_exists(mv_name: str) -> bool:
    """Check if MV exists by attempting a lightweight query against it."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT 1 FROM raw_yango.{mv_name} LIMIT 0")
            cur.close()
            return True
    except Exception:
        return False


def _mv_row_count(mv_name: str) -> int:
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM raw_yango.{mv_name}")
            cnt = cur.fetchone()[0]
            cur.close()
            return cnt
    except Exception:
        return -1


def _refresh_mv(mv_name: str, concurrently: bool = False) -> Dict[str, Any]:
    full_name = f"raw_yango.{mv_name}"
    t0 = time.perf_counter()
    result = {"mv": mv_name, "ok": True, "rows": 0, "elapsed_s": 0, "error": None}

    concurrently_clause = "CONCURRENTLY" if concurrently else ""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(f"REFRESH MATERIALIZED VIEW {concurrently_clause} {full_name}")
            cur.close()
        result["rows"] = _mv_row_count(mv_name)
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)[:500]

    result["elapsed_s"] = round(time.perf_counter() - t0, 1)
    return result


def _compute_order(mvs: List[str]) -> List[str]:
    resolved = []
    seen = set()
    for _ in range(len(ALL_MVS)):
        for mv in mvs:
            if mv in seen:
                continue
            deps = MV_DEPENDENCIES.get(mv, [])
            if all(d in resolved for d in deps):
                resolved.append(mv)
                seen.add(mv)
    return resolved


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh raw_yango materialized views")
    ap.add_argument(
        "--mv",
        choices=["all"] + ALL_MVS,
        default="all",
        help="MV to refresh (default: all)",
    )
    ap.add_argument("--concurrently", action="store_true", help="Use REFRESH CONCURRENTLY")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be refreshed")
    ap.add_argument(
        "--output-dir",
        default=os.path.join(_project_root(), "exports", "audits", "yango_raw_landing"),
    )
    args = ap.parse_args()

    mvs = ALL_MVS if args.mv == "all" else [args.mv]
    ordered = _compute_order(mvs)

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[refresh] raw_yango MVs | concurrently={args.concurrently} | dry_run={args.dry_run}")
    print(f"  Order: {' -> '.join(ordered)}")

    if args.dry_run:
        for mv in ordered:
            exists = _mv_exists(mv)
            print(f"  [DRY-RUN] {mv}: exists={exists}")
        return 0

    results = []
    for mv in ordered:
        print(f"[refresh] {mv}...", end=" ", flush=True)
        r = _refresh_mv(mv, concurrently=args.concurrently)
        status = "OK" if r["ok"] else "FAIL"
        if r["ok"]:
            print(f"{status} ({r['rows']:,} rows, {r['elapsed_s']}s)")
        else:
            print(f"{status}: {r['error'][:100]}")
        results.append(r)

    report_time = datetime.now(PET).isoformat()
    md_lines = [
        "# raw_yango MV Refresh Report",
        "",
        f"**Generated:** {report_time}",
        f"**Concurrently:** {args.concurrently}",
        "",
        "| MV | Status | Rows | Elapsed (s) |",
        "|----|--------|------|-------------|",
    ]
    for r in results:
        status = "OK" if r["ok"] else "FAIL"
        rows = f"{r['rows']:,}" if r["rows"] >= 0 else "ERROR"
        md_lines.append(f"| {r['mv']} | {status} | {rows} | {r['elapsed_s']} |")

    if any(not r["ok"] for r in results):
        md_lines.append("")
        md_lines.append("## Errors")
        for r in results:
            if not r["ok"]:
                md_lines.append(f"- **{r['mv']}**: {r['error']}")

    summary_path = os.path.join(args.output_dir, "mv_refresh_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"\n[refresh] Report: {summary_path}")

    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
