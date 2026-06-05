#!/usr/bin/env python3
"""
Reconcile raw_yango vs Control Tower day_fact.
Read-only comparison. No modifications.

Usage:
  cd backend
  python -m scripts.reconcile_yango_raw_vs_ct --date-from 2026-06-01 --date-to 2026-06-04
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


def _table_exists(schema_table: str) -> bool:
    parts = schema_table.split(".", 1)
    if len(parts) != 2:
        return False
    schema, table = parts
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                ) AS exists_table
                """,
                (schema, table),
            )
            row = cur.fetchone()
            cur.close()
            return bool(row["exists_table"]) if row else False
    except Exception:
        return False


def _check_schema_exists() -> bool:
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = 'raw_yango'
                ) AS exists_schema
                """
            )
            row = cur.fetchone()
            cur.close()
            return bool(row["exists_schema"]) if row else False
    except Exception:
        return False


def _is_raw_yango_empty(park_id: str) -> bool:
    tables = [
        "raw_yango.orders_raw",
        "raw_yango.transactions_raw",
        "raw_yango.driver_profiles_raw",
    ]
    for tbl in tables:
        if _table_exists(tbl):
            row = _query_all(
                f"SELECT COUNT(*) AS cnt FROM {tbl} WHERE park_id = %s LIMIT 1",
                (park_id,),
            )
            if row and row[0].get("cnt", 0) > 0:
                return False
    return True


def _query_raw_orders_daily(park_id: str, date_from: str, date_to: str) -> List[Dict]:
    if not _table_exists("raw_yango.orders_raw"):
        return []
    try:
        return _query_all(
            """
            SELECT
                order_ended_at::date AS trip_date,
                COUNT(*) AS trips
            FROM raw_yango.orders_raw
            WHERE park_id = %s
              AND order_ended_at::date >= %s
              AND order_ended_at::date <= %s
            GROUP BY order_ended_at::date
            ORDER BY order_ended_at::date
            """,
            (park_id, date_from, date_to),
        )
    except Exception:
        return []


def _query_raw_transactions_daily(park_id: str, date_from: str, date_to: str) -> List[Dict]:
    if not _table_exists("raw_yango.transactions_raw"):
        return []
    try:
        return _query_all(
            """
            SELECT
                event_at::date AS trip_date,
                COUNT(*) AS transaction_count,
                COALESCE(SUM(ABS(amount)), 0) AS revenue
            FROM raw_yango.transactions_raw
            WHERE park_id = %s
              AND category_name = 'Partner fee for trip'
              AND event_at::date >= %s
              AND event_at::date <= %s
            GROUP BY event_at::date
            ORDER BY event_at::date
            """,
            (park_id, date_from, date_to),
        )
    except Exception:
        return []


def _query_ct_day_fact(
    date_from: str, date_to: str, country: str, city: str
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "trips": 0,
        "revenue": 0.0,
        "days": 0,
        "daily": [],
        "slices": [],
        "error": None,
    }
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Normalize: strip outer quotes, trim, lower
            norm_country = country.lower().strip().strip("'\"")
            norm_city = city.lower().strip().strip("'\"")

            cur.execute(
                """
                SELECT business_slice_name,
                       SUM(trips_completed)::bigint AS trips,
                       SUM(revenue_yego_final)::numeric AS revenue
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(REPLACE(REPLACE(country, '''', ''), '\"', ''))) = %s
                  AND LOWER(TRIM(REPLACE(REPLACE(city, '''', ''), '\"', ''))) = %s
                  AND trip_date >= %s AND trip_date < %s
                GROUP BY business_slice_name
                ORDER BY trips DESC
                """,
                (norm_country, norm_city, date_from, date_to),
            )

            for row in cur.fetchall():
                result["slices"].append(
                    {
                        "business_slice_name": row["business_slice_name"],
                        "trips": int(row["trips"] or 0),
                        "revenue": float(row["revenue"] or 0),
                    }
                )
                result["trips"] += int(row["trips"] or 0)
                result["revenue"] += float(row["revenue"] or 0)

            cur.execute(
                """
                SELECT trip_date,
                       SUM(trips_completed)::bigint AS trips,
                       SUM(revenue_yego_final)::numeric AS revenue
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(REPLACE(REPLACE(country, '''', ''), '\"', ''))) = %s
                  AND LOWER(TRIM(REPLACE(REPLACE(city, '''', ''), '\"', ''))) = %s
                  AND trip_date >= %s AND trip_date < %s
                GROUP BY trip_date
                ORDER BY trip_date
                """,
                (norm_country, norm_city, date_from, date_to),
            )

            for row in cur.fetchall():
                td = row["trip_date"]
                ds = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)
                result["daily"].append(
                    {
                        "date": ds,
                        "trips": int(row["trips"] or 0),
                        "revenue": float(row["revenue"] or 0),
                    }
                )
            result["days"] = len(result["daily"])
            result["revenue"] = round(result["revenue"], 2)
            cur.close()
    except Exception as e:
        result["error"] = str(e)
    return result


def _pct_delta(raw_val: float, ct_val: float) -> Optional[float]:
    if ct_val and ct_val != 0:
        return round(((raw_val - ct_val) / ct_val) * 100, 2)
    return None


def _classify_delta(raw_val: float, ct_val: float) -> str:
    if raw_val == 0 and ct_val == 0:
        return "MATCH"
    if raw_val > 0 and ct_val == 0:
        return "API_ONLY"
    if raw_val == 0 and ct_val > 0:
        return "CT_ONLY"

    if ct_val == 0:
        return "NEEDS_INVESTIGATION"

    pct = abs(_pct_delta(raw_val, ct_val) or 0)
    if pct < 1:
        return "MATCH"
    elif pct < 5:
        return "MINOR_DELTA"
    elif pct < 20:
        return "MAJOR_DELTA"
    else:
        return "NEEDS_INVESTIGATION"


def _build_reconciliation_daily(
    raw_orders_daily: List[Dict],
    raw_txns_daily: List[Dict],
    ct_daily: List[Dict],
) -> List[Dict]:
    def _norm_date(d: Any) -> str:
        if hasattr(d, "strftime"):
            return d.strftime("%Y-%m-%d")
        return str(d)

    ct_map = {_norm_date(d["date"]): d for d in ct_daily}
    orders_map = {_norm_date(d["trip_date"]): d for d in raw_orders_daily}
    txns_map = {_norm_date(d["trip_date"]): d for d in raw_txns_daily}

    all_dates = sorted(set(list(ct_map.keys()) + list(orders_map.keys()) + list(txns_map.keys())))

    rows = []
    for d in all_dates:
        ct = ct_map.get(d, {})
        ord_ = orders_map.get(d, {})
        txn = txns_map.get(d, {})

        raw_trips = int(ord_.get("trips", 0) or 0)
        ct_trips = int(ct.get("trips", 0) or 0)
        raw_rev = float(txn.get("revenue", 0) or 0)
        ct_rev = float(ct.get("revenue", 0) or 0)

        trips_delta = raw_trips - ct_trips
        trips_class = _classify_delta(raw_trips, ct_trips)
        rev_delta = round(raw_rev - ct_rev, 2)
        rev_class = _classify_delta(raw_rev, ct_rev)

        rows.append(
            {
                "date": d,
                "raw_trips": raw_trips,
                "ct_trips": ct_trips,
                "trips_delta": trips_delta,
                "trips_delta_pct": _pct_delta(raw_trips, ct_trips),
                "trips_classification": trips_class,
                "raw_revenue": round(raw_rev, 2),
                "ct_revenue": round(ct_rev, 2),
                "revenue_delta": rev_delta,
                "revenue_delta_pct": _pct_delta(raw_rev, ct_rev),
                "revenue_classification": rev_class,
            }
        )
    return rows


def _build_summary_md(
    park_id: str,
    date_from: str,
    date_to: str,
    daily_rows: List[Dict],
    is_empty: bool,
) -> str:
    lines = [
        "# raw_yango vs Control Tower — Reconciliation",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Date Range:** {date_from} -> {date_to} (CT exclusive end)",
        f"**Park ID (masked):** {park_id[:8] if park_id else 'N/A'}***",
        f"**CT Country/City:** peru / lima",
        "",
    ]

    if is_empty:
        lines.extend(
            [
                "> **NO RAW DATA — run ingest_yango_raw_landing.py first**",
                "",
                "All raw_yango tables are empty or do not exist for this park.",
                "The following report contains CT data only. Reconciliation is not possible.",
                "",
                "```",
                "cd backend",
                "python -m scripts.ingest_yango_raw_landing --endpoint-group all --confirm-live",
                "```",
                "",
            ]
        )
        if daily_rows:
            lines.extend(
                [
                    "## CT Data (for reference)",
                    "",
                    "| Date | CT Trips | CT Revenue |",
                    "|------|----------|------------|",
                ]
            )
            for r in daily_rows:
                lines.append(
                    f"| {r['date']} | {r['ct_trips']:,} | {r['ct_revenue']:,.2f} |"
                )
        return "\n".join(lines)

    total_raw_trips = sum(r["raw_trips"] for r in daily_rows)
    total_ct_trips = sum(r["ct_trips"] for r in daily_rows)
    total_raw_rev = round(sum(r["raw_revenue"] for r in daily_rows), 2)
    total_ct_rev = round(sum(r["ct_revenue"] for r in daily_rows), 2)

    lines.extend(
        [
            "## 1. Summary Comparison",
            "",
            "| Metric | raw_yango | Control Tower | Delta | Delta % |",
            "|--------|-----------|---------------|-------|---------|",
        ]
    )

    for metric_name, raw_val, ct_val in [
        ("Trips", total_raw_trips, total_ct_trips),
        ("Revenue", total_raw_rev, total_ct_rev),
    ]:
        delta = raw_val - ct_val
        pct = _pct_delta(raw_val, ct_val)
        ds = f"{delta:+,.2f}" if isinstance(delta, float) else f"{delta:+,}"
        ps = f"{pct:+.1f}%" if pct is not None else "N/A"
        raw_fmt = f"{raw_val:,.2f}" if isinstance(raw_val, float) else f"{raw_val:,}"
        ct_fmt = f"{ct_val:,.2f}" if isinstance(ct_val, float) else f"{ct_val:,}"
        lines.append(f"| {metric_name} | {raw_fmt} | {ct_fmt} | {ds} | {ps} |")

    lines.extend(
        [
            "",
            "## 2. Daily Breakdown",
            "",
            "| Date | Raw Trips | CT Trips | Trip Class | Raw Revenue | CT Revenue | Rev Class |",
            "|------|-----------|----------|------------|-------------|------------|-----------|",
        ]
    )
    for r in daily_rows:
        lines.append(
            f"| {r['date']} | {r['raw_trips']:,} | {r['ct_trips']:,} | **{r['trips_classification']}** | "
            f"{r['raw_revenue']:,.2f} | {r['ct_revenue']:,.2f} | **{r['revenue_classification']}** |"
        )

    lines.extend(
        [
            "",
            "## 3. Classification Legend",
            "",
            "| Classification | Criteria |",
            "|----------------|----------|",
            "| MATCH | |delta| < 1% |",
            "| MINOR_DELTA | 1% <= |delta| < 5% |",
            "| MAJOR_DELTA | 5% <= |delta| < 20% |",
            "| CT_ONLY | Data in CT but not in raw |",
            "| API_ONLY | Data in raw but not in CT |",
            "| NEEDS_INVESTIGATION | Any anomaly |",
            "",
            "## 4. Notes",
            "",
            "- Revenue from raw_yango = SUM(ABS(amount)) WHERE category_name = 'Partner fee for trip'",
            "- Revenue from CT = revenue_yego_final (COALESCE(real, proxy))",
            "- CT date range is exclusive-end (trip_date < date_to)",
            "- raw_yango date range is inclusive on fetched_at_date",
            "- Trips from raw_yango = COUNT(*) from orders_raw (status complete)",
            "",
        ]
    )
    return "\n".join(lines)


def _build_reconciliation_csv(daily_rows: List[Dict]) -> List[List[str]]:
    hdr = [
        "date",
        "raw_trips",
        "ct_trips",
        "trips_delta",
        "trips_delta_pct",
        "trips_classification",
        "raw_revenue",
        "ct_revenue",
        "revenue_delta",
        "revenue_delta_pct",
        "revenue_classification",
    ]
    rows = [hdr]
    for r in daily_rows:
        rows.append([str(r.get(k, "")) for k in hdr])
    return rows


def main() -> int:
    yesterday = (datetime.now(PET) - timedelta(days=1)).strftime("%Y-%m-%d")

    ap = argparse.ArgumentParser(
        description="Reconcile raw_yango vs Control Tower day_fact"
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

    is_empty = _is_raw_yango_empty(park_id)

    print(f"[reconcile] Park: {park_id[:8]}***")
    print(f"  Range: {args.date_from} -> {args.date_to}")

    if is_empty:
        print("[reconcile] NO RAW DATA — generating CT-only report")
    else:
        print("[reconcile] Querying raw_yango tables...")

    raw_orders_daily = _query_raw_orders_daily(park_id, args.date_from, args.date_to)
    raw_txns_daily = _query_raw_transactions_daily(park_id, args.date_from, args.date_to)

    if raw_orders_daily:
        print(f"  orders_raw: {len(raw_orders_daily)} days, {sum(r.get('trips', 0) or 0 for r in raw_orders_daily):,} trips")
    if raw_txns_daily:
        rev_sum = sum(r.get("revenue", 0) or 0 for r in raw_txns_daily)
        print(f"  transactions_raw: {len(raw_txns_daily)} days, revenue={rev_sum:,.2f}")

    print("[reconcile] Querying CT day_fact...")
    ct_data = _query_ct_day_fact(args.date_from, args.date_to, "peru", "lima")
    if ct_data.get("error"):
        print(f"ERROR querying CT: {ct_data['error']}", file=sys.stderr)
        return 1

    print(f"  CT: {ct_data['trips']:,} trips, {ct_data['revenue']:,.2f} revenue, {ct_data['days']} days")

    daily_rows = _build_reconciliation_daily(
        raw_orders_daily, raw_txns_daily, ct_data.get("daily", [])
    )

    md_content = _build_summary_md(
        park_id, args.date_from, args.date_to, daily_rows, is_empty
    )

    summary_path = os.path.join(output_dir, "reconciliation_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[reconcile] Summary saved: {summary_path}")

    metrics_json = {
        "generated_at": datetime.now(PET).isoformat(),
        "park_id": park_id[:8] + "***" if park_id else "N/A",
        "date_from": args.date_from,
        "date_to": args.date_to,
        "is_raw_yango_empty": is_empty,
        "daily": daily_rows,
    }
    metrics_path = os.path.join(output_dir, "reconciliation_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_json, f, indent=2, default=str, ensure_ascii=False)
    print(f"[reconcile] Metrics saved: {metrics_path}")

    if args.csv:
        csv_content = _build_reconciliation_csv(daily_rows)
        csv_path = os.path.join(output_dir, "reconciliation_by_day.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_content)
        print(f"[reconcile] CSV saved: {csv_path}")

    print(f"\n[reconcile] Summary:")
    total_raw_t = sum(r["raw_trips"] for r in daily_rows)
    total_ct_t = sum(r["ct_trips"] for r in daily_rows)
    total_raw_r = sum(r["raw_revenue"] for r in daily_rows)
    total_ct_r = sum(r["ct_revenue"] for r in daily_rows)
    print(f"  Trips: raw={total_raw_t:,} vs CT={total_ct_t:,}")
    print(f"  Revenue: raw={total_raw_r:,.2f} vs CT={total_ct_r:,.2f}")

    classifications: Dict[str, int] = {}
    for r in daily_rows:
        for cls_key in ("trips_classification", "revenue_classification"):
            cls = r.get(cls_key, "")
            classifications[cls] = classifications.get(cls, 0) + 1
    for k, v in sorted(classifications.items()):
        print(f"  {k}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
