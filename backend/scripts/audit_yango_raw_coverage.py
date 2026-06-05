#!/usr/bin/env python3
"""
Audit raw_yango coverage — measures API and DB coverage by park and date.

Usage:
  cd backend
  python -m scripts.audit_yango_raw_coverage --park-id ... --date-from 2026-06-01
  python -m scripts.audit_yango_raw_coverage --output-dir exports/audits/yango_raw_landing/
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
from app.settings import settings
from psycopg2.extras import RealDictCursor

PET = timezone(timedelta(hours=-5))


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _query_all(sql: str, params: list | tuple | None = None) -> List[Dict[str, Any]]:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params or [])
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows
    except Exception:
        return []


def _query_one(sql: str, params: list | tuple | None = None) -> Dict[str, Any]:
    rows = _query_all(sql, params)
    return rows[0] if rows else {}


def _table_exists(schema_table: str) -> bool:
    parts = schema_table.split(".", 1)
    if len(parts) != 2:
        return False
    schema, table = parts
    row = _query_one(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = %s AND table_name = %s
        ) AS exists_table
        """,
        (schema, table),
    )
    return bool(row.get("exists_table", False))


def _check_schema_exists() -> bool:
    row = _query_one(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.schemata
            WHERE schema_name = 'raw_yango'
        ) AS exists_schema
        """
    )
    return bool(row.get("exists_schema", False))


def _get_table_coverage(
    table_name: str, park_id: str
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "table": table_name,
        "exists": False,
        "min_date": None,
        "max_date": None,
        "distinct_days": 0,
        "total_rows": 0,
        "error": None,
    }
    full_name = f"raw_yango.{table_name}"
    if not _table_exists(full_name):
        return result
    result["exists"] = True
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                f"""
                SELECT
                    MIN(operational_date) AS min_date,
                    MAX(operational_date) AS max_date,
                    COUNT(DISTINCT operational_date) AS distinct_days,
                    COUNT(*) AS total_rows
                FROM {full_name}
                WHERE park_id = %s
                """,
                (park_id,),
            )
            row = cur.fetchone()
            if row:
                result["min_date"] = (
                    row["min_date"].isoformat()
                    if row["min_date"] and hasattr(row["min_date"], "isoformat")
                    else str(row["min_date"]) if row["min_date"] else None
                )
                result["max_date"] = (
                    row["max_date"].isoformat()
                    if row["max_date"] and hasattr(row["max_date"], "isoformat")
                    else str(row["max_date"]) if row["max_date"] else None
                )
                result["distinct_days"] = int(row["distinct_days"] or 0)
                result["total_rows"] = int(row["total_rows"] or 0)
            cur.close()
    except Exception as e:
        result["error"] = str(e)
    return result


def _get_revenue_candidates(park_id: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "exists": False,
        "count": 0,
        "sum_abs_amount": 0.0,
        "error": None,
    }
    if not _table_exists("raw_yango.transactions_raw"):
        return result
    result["exists"] = True
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT
                    COUNT(*) AS cnt,
                    COALESCE(SUM(ABS(amount)), 0) AS sum_abs
                FROM raw_yango.transactions_raw
                WHERE park_id = %s
                  AND category_name = 'Partner fee for trip'
                """,
                (park_id,),
            )
            row = cur.fetchone()
            if row:
                result["count"] = int(row["cnt"] or 0)
                result["sum_abs_amount"] = float(row["sum_abs"] or 0)
            cur.close()
    except Exception as e:
        result["error"] = str(e)
    return result


def _get_daily_breakdown(
    table_name: str, park_id: str
) -> List[Dict[str, Any]]:
    full_name = f"raw_yango.{table_name}"
    if not _table_exists(full_name):
        return []
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                f"""
                SELECT
                    operational_date AS day,
                    COUNT(*) AS rows
                FROM {full_name}
                WHERE park_id = %s
                GROUP BY operational_date
                ORDER BY day
                """,
                (park_id,),
            )
            rows = []
            for r in cur.fetchall():
                d = r["day"]
                rows.append(
                    {
                        "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
                        "rows": int(r["rows"] or 0),
                    }
                )
            cur.close()
            return rows
    except Exception:
        return []


def _find_missing_days(
    date_from: str, date_to: str, covered_dates: set
) -> List[str]:
    fd = datetime.strptime(date_from, "%Y-%m-%d").date()
    td = datetime.strptime(date_to, "%Y-%m-%d").date()
    all_dates = {
        (fd + timedelta(days=i)).isoformat() for i in range((td - fd).days + 1)
    }
    return sorted(all_dates - covered_dates)


def _build_coverage_summary_md(
    park_id: str,
    date_from: str,
    date_to: str,
    orders_cov: Dict[str, Any],
    transactions_cov: Dict[str, Any],
    drivers_cov: Dict[str, Any],
    revenue_candidates: Dict[str, Any],
    missing_orders: List[str],
    missing_transactions: List[str],
    missing_drivers: List[str],
    is_empty: bool,
) -> str:
    lines = [
        "# raw_yango Coverage Audit",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Date Range:** {date_from} -> {date_to}",
        f"**Park ID (masked):** {park_id[:8] if park_id else 'N/A'}***",
        "",
    ]

    if is_empty:
        lines.extend([
            "> **NO RAW DATA — run ingest_yango_raw_landing.py first**",
            "",
            "All raw_yango tables are empty or do not exist for this park.",
            "Run the ingestion script to populate raw_yango tables:",
            "",
            "```",
            "cd backend",
            "python -m scripts.ingest_yango_raw_landing --endpoint-group all --confirm-live",
            "```",
            "",
        ])
        return "\n".join(lines)

    lines.extend([
        "## 1. Table Coverage",
        "",
        "| Table | Exists | Rows | Distinct Days | Min Date | Max Date |",
        "|-------|--------|------|---------------|----------|----------|",
    ])

    for cov in [orders_cov, transactions_cov, drivers_cov]:
        name = cov.get("table", "?")
        exists = "YES" if cov.get("exists") else "NO"
        rows = cov.get("total_rows", 0)
        days = cov.get("distinct_days", 0)
        min_d = cov.get("min_date") or "N/A"
        max_d = cov.get("max_date") or "N/A"
        lines.append(
            f"| {name} | {exists} | {rows:,} | {days} | {min_d} | {max_d} |"
        )

    lines.extend([
        "",
        "## 2. Revenue Candidates",
        "",
        f"- **Partner fee for trip** count: {revenue_candidates.get('count', 0):,}",
        f"- **SUM(ABS(amount))**: {revenue_candidates.get('sum_abs_amount', 0):,.2f}",
        "",
        "## 3. Missing Days",
        "",
    ])

    for label, missing in [
        ("orders_raw", missing_orders),
        ("transactions_raw", missing_transactions),
        ("driver_profiles_raw", missing_drivers),
    ]:
        if missing:
            lines.append(
                f"- **{label}** ({len(missing)} days): {', '.join(missing[:10])}"
                + ("..." if len(missing) > 10 else "")
            )
        else:
            lines.append(f"- **{label}**: none missing")

    lines.extend([
        "",
        "## 4. Coverage Score",
        "",
    ])
    total_days = (
        (datetime.strptime(date_to, "%Y-%m-%d").date()
         - datetime.strptime(date_from, "%Y-%m-%d").date()).days
        + 1
    )
    for cov, label in [
        (orders_cov, "orders_raw"),
        (transactions_cov, "transactions_raw"),
        (drivers_cov, "driver_profiles_raw"),
    ]:
        if cov.get("exists") and total_days > 0:
            pct = round((cov.get("distinct_days", 0) / total_days) * 100, 1)
            lines.append(f"- **{label}** coverage: {pct}% ({cov.get('distinct_days', 0)}/{total_days} days)")
        else:
            lines.append(f"- **{label}** coverage: 0% (table empty or missing)")

    return "\n".join(lines)


def _build_coverage_csv(
    orders_daily: List[Dict],
    transactions_daily: List[Dict],
    drivers_daily: List[Dict],
) -> List[List[str]]:
    all_dates: Dict[str, Dict] = {}
    for row in orders_daily:
        d = row["date"]
        if d not in all_dates:
            all_dates[d] = {"date": d}
        all_dates[d]["orders_rows"] = row.get("rows", 0)
    for row in transactions_daily:
        d = row["date"]
        if d not in all_dates:
            all_dates[d] = {"date": d}
        all_dates[d]["transactions_rows"] = row.get("rows", 0)
    for row in drivers_daily:
        d = row["date"]
        if d not in all_dates:
            all_dates[d] = {"date": d}
        all_dates[d]["drivers_rows"] = row.get("rows", 0)

    rows = [
        [
            "date",
            "orders_rows",
            "transactions_rows",
            "drivers_rows",
        ]
    ]
    for d in sorted(all_dates):
        entry = all_dates[d]
        rows.append(
            [
                d,
                str(entry.get("orders_rows", "")),
                str(entry.get("transactions_rows", "")),
                str(entry.get("drivers_rows", "")),
            ]
        )
    return rows


def main() -> int:
    yesterday = (datetime.now(PET) - timedelta(days=1)).strftime("%Y-%m-%d")

    ap = argparse.ArgumentParser(
        description="Audit raw_yango coverage by park and date"
    )
    ap.add_argument(
        "--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip()
        or "08e20910d81d42658d4334d3f6d10ac0",
    )
    ap.add_argument("--date-from", default=yesterday)
    ap.add_argument("--date-to", default=yesterday)
    ap.add_argument(
        "--output-dir",
        default=os.path.join(
            _project_root(), "exports", "audits", "yango_raw_landing"
        ),
    )
    ap.add_argument("--csv", action="store_true")
    args = ap.parse_args()

    try:
        datetime.strptime(args.date_from, "%Y-%m-%d")
        datetime.strptime(args.date_to, "%Y-%m-%d")
    except ValueError:
        print("ERROR: dates must be YYYY-MM-DD", file=sys.stderr)
        return 1

    park_id = args.park_id
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    if not _check_schema_exists():
        print("[audit] Schema raw_yango does not exist.")
        print("[audit] NO RAW DATA — run ingest_yango_raw_landing.py first")
        is_empty = True
    else:
        is_empty = False

    print(f"[audit] Checking raw_yango coverage for park {park_id[:8]}***")
    print(f"  Range: {args.date_from} -> {args.date_to}")

    orders_cov = _get_table_coverage("orders_raw", park_id)
    transactions_cov = _get_table_coverage("transactions_raw", park_id)
    drivers_cov = _get_table_coverage("driver_profiles_raw", park_id)
    revenue_candidates = _get_revenue_candidates(park_id)

    total_rows = (
        orders_cov.get("total_rows", 0)
        + transactions_cov.get("total_rows", 0)
        + drivers_cov.get("total_rows", 0)
    )

    if not is_empty and total_rows == 0:
        is_empty = True

    orders_daily = _get_daily_breakdown("orders_raw", park_id)
    transactions_daily = _get_daily_breakdown("transactions_raw", park_id)
    drivers_daily = _get_daily_breakdown("driver_profiles_raw", park_id)

    covered_orders = {r["date"] for r in orders_daily}
    covered_transactions = {r["date"] for r in transactions_daily}
    covered_drivers = {r["date"] for r in drivers_daily}

    missing_orders = _find_missing_days(args.date_from, args.date_to, covered_orders)
    missing_transactions = _find_missing_days(
        args.date_from, args.date_to, covered_transactions
    )
    missing_drivers = _find_missing_days(args.date_from, args.date_to, covered_drivers)

    md_content = _build_coverage_summary_md(
        park_id,
        args.date_from,
        args.date_to,
        orders_cov,
        transactions_cov,
        drivers_cov,
        revenue_candidates,
        missing_orders,
        missing_transactions,
        missing_drivers,
        is_empty,
    )

    summary_path = os.path.join(output_dir, "coverage_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[audit] Summary saved: {summary_path}")

    metrics_json = {
        "generated_at": datetime.now(PET).isoformat(),
        "park_id": park_id[:8] + "***" if park_id else "N/A",
        "date_from": args.date_from,
        "date_to": args.date_to,
        "is_empty": is_empty,
        "orders_raw": orders_cov,
        "transactions_raw": transactions_cov,
        "driver_profiles_raw": drivers_cov,
        "revenue_candidates": revenue_candidates,
        "missing_days": {
            "orders_raw": missing_orders,
            "transactions_raw": missing_transactions,
            "driver_profiles_raw": missing_drivers,
        },
    }
    metrics_path = os.path.join(output_dir, "coverage_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_json, f, indent=2, default=str, ensure_ascii=False)
    print(f"[audit] Metrics saved: {metrics_path}")

    if args.csv:
        csv_content = _build_coverage_csv(orders_daily, transactions_daily, drivers_daily)
        csv_path = os.path.join(output_dir, "coverage_by_park_day.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_content)
        print(f"[audit] CSV saved: {csv_path}")

    print(f"\n[audit] Summary:")
    print(f"  orders_raw: {orders_cov.get('total_rows', 0):,} rows, {orders_cov.get('distinct_days', 0)} days")
    print(f"  transactions_raw: {transactions_cov.get('total_rows', 0):,} rows, {transactions_cov.get('distinct_days', 0)} days")
    print(f"  driver_profiles_raw: {drivers_cov.get('total_rows', 0):,} rows, {drivers_cov.get('distinct_days', 0)} days")
    print(f"  Partner fee for trip: {revenue_candidates.get('count', 0):,} txns, {revenue_candidates.get('sum_abs_amount', 0):,.2f} sum ABS")

    if is_empty:
        print("\n  [WARNING] NO RAW DATA — run ingest_yango_raw_landing.py first")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
