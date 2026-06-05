#!/usr/bin/env python3
"""
Audit raw_yango materialized views — counts, date ranges, null rates, duplicates.

Usage:
  cd backend
  python -m scripts.audit_raw_yango_mvs
  python -m scripts.audit_raw_yango_mvs --csv
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
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

PET = timezone(timedelta(hours=-5))
ALL_MVS = [
    "mv_orders_day",
    "mv_transactions_day",
    "mv_revenue_day",
    "mv_driver_profiles_snapshot",
    "mv_source_coverage_day",
]


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _query_all(sql: str, params=None) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params or [])
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception:
        return []


def _query_one(sql: str, params=None) -> Dict[str, Any]:
    rows = _query_all(sql, params)
    return rows[0] if rows else {}


def _mv_exists(mv_name: str) -> bool:
    row = _query_one(
        "SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname = 'raw_yango' AND matviewname = %s) AS ok",
        (mv_name,),
    )
    return bool(row.get("ok", False))


def _audit_mv(mv_name: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "mv": mv_name,
        "exists": False,
        "row_count": 0,
        "min_date": None,
        "max_date": None,
        "distinct_days": 0,
        "distinct_parks": 0,
        "null_rate_pct": 0.0,
        "duplicate_keys": 0,
        "refreshed_at": None,
        "error": None,
    }

    if not _mv_exists(mv_name):
        return result

    result["exists"] = True
    full = f"raw_yango.{mv_name}"

    try:
        base = _query_one(f"SELECT COUNT(*) AS cnt FROM {full}")
        result["row_count"] = base.get("cnt", 0)

        date_col = "operational_date"
        if mv_name == "mv_driver_profiles_snapshot":
            date_col = "snapshot_date"

        date_info = _query_one(f"""
            SELECT MIN({date_col}) AS min_d, MAX({date_col}) AS max_d,
                   COUNT(DISTINCT {date_col}) AS distinct_days
            FROM {full}
        """)
        if date_info.get("min_d"):
            d = date_info["min_d"]
            result["min_date"] = d.isoformat() if hasattr(d, "isoformat") else str(d)
        if date_info.get("max_d"):
            d = date_info["max_d"]
            result["max_date"] = d.isoformat() if hasattr(d, "isoformat") else str(d)
        result["distinct_days"] = date_info.get("distinct_days", 0)

        park_info = _query_one(f"SELECT COUNT(DISTINCT park_id) AS parks FROM {full}")
        result["distinct_parks"] = park_info.get("parks", 0)

        refresh_info = _query_one(f"SELECT MAX(refreshed_at) AS refreshed FROM {full}")
        r_at = refresh_info.get("refreshed")
        if r_at:
            result["refreshed_at"] = r_at.isoformat() if hasattr(r_at, "isoformat") else str(r_at)

        if result["row_count"] > 0:
            null_rate = _query_one(f"""
                SELECT ROUND(100.0 * COUNT(*) / NULLIF(SUM(1), 0), 1) AS pct
                FROM {full}
                WHERE {date_col} IS NULL
            """)
            result["null_rate_pct"] = float(null_rate.get("pct", 0) or 0)

        if mv_name == "mv_orders_day":
            dups = _query_one(f"""
                SELECT COUNT(*) AS cnt FROM (
                    SELECT park_id, operational_date, COUNT(*) FROM {full}
                    GROUP BY park_id, operational_date HAVING COUNT(*) > 1
                ) t
            """)
            result["duplicate_keys"] = dups.get("cnt", 0)
        elif mv_name == "mv_transactions_day":
            dups = _query_one(f"""
                SELECT COUNT(*) AS cnt FROM (
                    SELECT park_id, operational_date, category_name, currency_code, COUNT(*) FROM {full}
                    GROUP BY park_id, operational_date, category_name, currency_code HAVING COUNT(*) > 1
                ) t
            """)
            result["duplicate_keys"] = dups.get("cnt", 0)
        elif mv_name == "mv_revenue_day":
            dups = _query_one(f"""
                SELECT COUNT(*) AS cnt FROM (
                    SELECT park_id, operational_date, currency_code, COUNT(*) FROM {full}
                    GROUP BY park_id, operational_date, currency_code HAVING COUNT(*) > 1
                ) t
            """)
            result["duplicate_keys"] = dups.get("cnt", 0)
        elif mv_name == "mv_driver_profiles_snapshot":
            dups = _query_one(f"""
                SELECT COUNT(*) AS cnt FROM (
                    SELECT park_id, driver_profile_id, snapshot_date, COUNT(*) FROM {full}
                    GROUP BY park_id, driver_profile_id, snapshot_date HAVING COUNT(*) > 1
                ) t
            """)
            result["duplicate_keys"] = dups.get("cnt", 0)
        elif mv_name == "mv_source_coverage_day":
            dups = _query_one(f"""
                SELECT COUNT(*) AS cnt FROM (
                    SELECT park_id, operational_date, COUNT(*) FROM {full}
                    GROUP BY park_id, operational_date HAVING COUNT(*) > 1
                ) t
            """)
            result["duplicate_keys"] = dups.get("cnt", 0)

    except Exception as e:
        result["error"] = str(e)

    return result


def _build_md(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# raw_yango MV Audit",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        "",
        "## 1. MV Summary",
        "",
        "| MV | Exists | Rows | Days | Parks | Null% | Dups | Refreshed |",
        "|----|--------|------|------|-------|-------|------|-----------|",
    ]
    for r in results:
        lines.append(
            f"| {r['mv']} | {'YES' if r['exists'] else 'NO'} | {r['row_count']:,} | "
            f"{r['distinct_days']} | {r['distinct_parks']} | {r['null_rate_pct']}% | "
            f"{r['duplicate_keys']} | {r['refreshed_at'] or 'N/A'} |"
        )

    if r["exists"] and r["distinct_days"] > 0:
        lines.extend([
            "",
            "## 2. Date Range",
            "",
            f"- Min date: {r.get('min_date', 'N/A')}",
            f"- Max date: {r.get('max_date', 'N/A')}",
        ])

    errors = [r for r in results if r.get("error")]
    if errors:
        lines.extend(["", "## 3. Errors"])
        for r in errors:
            lines.append(f"- **{r['mv']}**: {r['error']}")

    return "\n".join(lines)


def _build_csv_detail(results: List[Dict[str, Any]]) -> List[List[str]]:
    hdr = ["mv", "exists", "row_count", "min_date", "max_date", "distinct_days",
           "distinct_parks", "null_rate_pct", "duplicate_keys", "refreshed_at"]
    rows = [hdr]
    for r in results:
        rows.append([str(r.get(k, "")) for k in hdr])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit raw_yango materialized views")
    ap.add_argument("--csv", action="store_true")
    ap.add_argument(
        "--output-dir",
        default=os.path.join(_project_root(), "exports", "audits", "yango_raw_landing"),
    )
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print("[mv-audit] Auditing raw_yango MVs...")
    results = [_audit_mv(mv) for mv in ALL_MVS]

    for r in results:
        status = "OK" if r["exists"] else "MISSING"
        print(f"  {r['mv']}: {status} | rows={r['row_count']:,} | days={r['distinct_days']} | dups={r['duplicate_keys']}")

    md_content = _build_md(results)
    summary_path = os.path.join(args.output_dir, "mv_audit_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n[mv-audit] Summary: {summary_path}")

    metrics_path = os.path.join(args.output_dir, "mv_audit_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now(PET).isoformat(), "mvs": results}, f, indent=2, default=str)
    print(f"[mv-audit] Metrics: {metrics_path}")

    if args.csv:
        csv_content = _build_csv_detail(results)
        csv_path = os.path.join(args.output_dir, "mv_audit_detail.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_content)
        print(f"[mv-audit] CSV: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
