#!/usr/bin/env python3
"""
Reconcile raw_yango MVs vs Control Tower day_fact.

Usage:
  cd backend
  python -m scripts.reconcile_yango_mv_vs_ct --park-id ... --date-from 2026-06-04 --date-to 2026-06-04
  python -m scripts.reconcile_yango_mv_vs_ct --park-id ... --date-from 2026-06-04 --date-to 2026-06-04 --csv
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


def _query_mv_orders(park_id: str, date_from: str, date_to: str) -> Dict[str, Dict]:
    rows = _query_all(
        """
        SELECT order_date, orders_completed, unique_drivers
        FROM raw_yango.mv_orders_day
        WHERE park_id = %s AND order_date >= %s AND order_date <= %s
        """,
        (park_id, date_from, date_to),
    )
    return {str(r["order_date"]): r for r in rows}


def _query_mv_revenue(park_id: str, date_from: str, date_to: str) -> Dict[str, Dict]:
    rows = _query_all(
        """
        SELECT revenue_date, partner_fee_trip_amount, partner_fee_trip_count,
               revenue_per_order, revenue_per_partner_fee_txn, currency
        FROM raw_yango.mv_revenue_day
        WHERE park_id = %s AND revenue_date >= %s AND revenue_date <= %s
        """,
        (park_id, date_from, date_to),
    )
    return {str(r["revenue_date"]): r for r in rows}


def _query_ct_day_fact(date_from: str, date_to: str) -> Dict[str, Dict]:
    rows = _query_all(
        """
        SELECT trip_date AS d,
               SUM(trips_completed)::bigint AS trips,
               SUM(revenue_yego_final)::numeric AS rev_final,
               SUM(revenue_yego_net)::numeric AS rev_net,
               SUM(active_drivers)::bigint AS drivers
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(REPLACE(REPLACE(country, '''', ''), '\"', ''))) = 'peru'
          AND LOWER(TRIM(REPLACE(REPLACE(city, '''', ''), '\"', ''))) = 'lima'
          AND trip_date >= %s AND trip_date < %s
        GROUP BY trip_date
        """,
        (date_from, date_to),
    )
    return {str(r["d"]): r for r in rows}


def _pct_delta(raw_val: float, ct_val: float) -> Optional[float]:
    if ct_val and ct_val != 0:
        return round(((raw_val - ct_val) / ct_val) * 100, 2)
    return None


def _classify(raw_val: float, ct_val: float) -> str:
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


def _build_daily(
    mv_orders: Dict[str, Dict],
    mv_revenue: Dict[str, Dict],
    ct_data: Dict[str, Dict],
) -> List[Dict]:
    all_dates = sorted(set(list(mv_orders.keys()) + list(mv_revenue.keys()) + list(ct_data.keys())))

    rows = []
    for d in all_dates:
        mo = mv_orders.get(d, {})
        mr = mv_revenue.get(d, {})
        ct = ct_data.get(d, {})

        raw_trips = int(mo.get("orders_completed", 0) or 0)
        ct_trips = int(ct.get("trips", 0) or 0)

        raw_rev = float(mr.get("partner_fee_trip_amount", 0) or 0)
        ct_rev_final = float(ct.get("rev_final", 0) or 0)
        ct_rev_net = float(ct.get("rev_net", 0) or 0)

        raw_drivers = int(mo.get("unique_drivers", 0) or 0)
        ct_drivers = int(ct.get("drivers", 0) or 0)

        rows.append({
            "date": d,
            "mv_trips": raw_trips,
            "ct_trips": ct_trips,
            "trips_delta": raw_trips - ct_trips,
            "trips_delta_pct": _pct_delta(raw_trips, ct_trips),
            "trips_class": _classify(raw_trips, ct_trips),
            "mv_revenue": round(raw_rev, 2),
            "ct_revenue_final": round(ct_rev_final, 2),
            "ct_revenue_net": round(ct_rev_net, 2),
            "revenue_delta_final": round(raw_rev - ct_rev_final, 2),
            "revenue_delta_net": round(raw_rev - ct_rev_net, 2),
            "revenue_class": _classify(raw_rev, ct_rev_final),
            "mv_drivers": raw_drivers,
            "ct_drivers": ct_drivers,
            "drivers_delta": raw_drivers - ct_drivers,
            "drivers_class": _classify(raw_drivers, ct_drivers),
        })
    return rows


def _build_md(park_id: str, date_from: str, date_to: str, daily: List[Dict], has_mv: bool) -> str:
    n_overlap = sum(1 for r in daily if r["mv_trips"] > 0 and r["ct_trips"] > 0)
    lines = [
        "# raw_yango MVs vs Control Tower — Reconciliation",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Date Range:** {date_from} -> {date_to} (CT exclusive end)",
        f"**Park ID (masked):** {park_id[:8] if park_id else 'N/A'}***",
        f"**Days with MV+CT overlap:** {n_overlap} / {len(daily)}",
        "",
    ]

    if not has_mv:
        lines.append("> **MV DATA MISSING — refresh MVs first:** `python -m scripts.refresh_raw_yango_mvs --mv all`")
        return "\n".join(lines)

    if n_overlap == 0:
        lines.append("> **NO OVERLAP** between MV dates and CT dates. Cannot reconcile.")

    totals = {
        "mv_trips": sum(r["mv_trips"] for r in daily),
        "ct_trips": sum(r["ct_trips"] for r in daily),
        "mv_revenue": sum(r["mv_revenue"] for r in daily),
        "ct_rev_final": sum(r["ct_revenue_final"] for r in daily),
        "ct_rev_net": sum(r["ct_revenue_net"] for r in daily),
        "mv_drivers": sum(r["mv_drivers"] for r in daily),
        "ct_drivers": sum(r["ct_drivers"] for r in daily),
    }

    lines.extend([
        "## 1. Summary",
        "",
        "| Metric | MV (raw_yango) | CT (final) | CT (net) |",
        "|--------|----------------|------------|----------|",
        f"| Trips | {totals['mv_trips']:,} | {totals['ct_trips']:,} | — |",
        f"| Revenue | {totals['mv_revenue']:,.2f} | {totals['ct_rev_final']:,.2f} | {totals['ct_rev_net']:,.2f} |",
        f"| Drivers | {totals['mv_drivers']:,} | {totals['ct_drivers']:,} | — |",
        "",
        "## 2. Daily Detail",
        "",
        "| Date | MV Trips | CT Trips | Trip Class | MV Revenue | CT Rev Final | CT Rev Net | Rev Class | MV Drivers | CT Drivers |",
        "|------|----------|----------|------------|------------|-------------|-----------|-----------|------------|------------|",
    ])

    for r in daily:
        lines.append(
            f"| {r['date']} | {r['mv_trips']:,} | {r['ct_trips']:,} | **{r['trips_class']}** | "
            f"{r['mv_revenue']:,.2f} | {r['ct_revenue_final']:,.2f} | {r['ct_revenue_net']:,.2f} | "
            f"**{r['revenue_class']}** | {r['mv_drivers']:,} | {r['ct_drivers']:,} |"
        )

    lines.extend([
        "",
        "## 3. Classification",
        "",
        "| Class | Criteria |",
        "|-------|----------|",
        "| MATCH | delta < 1% |",
        "| MINOR_DELTA | 1% ≤ delta < 5% |",
        "| MAJOR_DELTA | 5% ≤ delta < 20% |",
        "| CT_ONLY | Data in CT but not MV |",
        "| API_ONLY | Data in MV but not CT |",
        "| NO_OVERLAP | No shared dates |",
    ])
    return "\n".join(lines)


def _build_csv(daily: List[Dict]) -> List[List[str]]:
    hdr = ["date", "mv_trips", "ct_trips", "trips_delta", "trips_delta_pct", "trips_class",
           "mv_revenue", "ct_revenue_final", "ct_revenue_net", "revenue_delta_final",
           "revenue_delta_net", "revenue_class", "mv_drivers", "ct_drivers", "drivers_class"]
    return [hdr] + [[str(r.get(k, "")) for k in hdr] for r in daily]


def main() -> int:
    yesterday = (datetime.now(PET) - timedelta(days=1)).strftime("%Y-%m-%d")

    ap = argparse.ArgumentParser(description="Reconcile raw_yango MVs vs CT")
    ap.add_argument(
        "--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip() or "08e20910d81d42658d4334d3f6d10ac0",
    )
    ap.add_argument("--date-from", default=yesterday)
    ap.add_argument("--date-to", default=yesterday)
    ap.add_argument("--csv", action="store_true")
    ap.add_argument(
        "--output-dir",
        default=os.path.join(_project_root(), "exports", "audits", "yango_raw_landing"),
    )
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    park_id = args.park_id
    print(f"[mv-reconcile] Park: {park_id[:8]}***")
    print(f"  Range: {args.date_from} -> {args.date_to}")

    mv_orders = _query_mv_orders(park_id, args.date_from, args.date_to)
    mv_revenue = _query_mv_revenue(park_id, args.date_from, args.date_to)
    has_mv = len(mv_orders) > 0 or len(mv_revenue) > 0

    if not has_mv:
        print("[mv-reconcile] MV DATA MISSING — refresh MVs first")

    ct_exclusive_end = args.date_to
    ct_data = _query_ct_day_fact(args.date_from, ct_exclusive_end)

    print(f"  MV orders: {len(mv_orders)} days | MV revenue: {len(mv_revenue)} days | CT: {len(ct_data)} days")

    daily = _build_daily(mv_orders, mv_revenue, ct_data)

    md_content = _build_md(park_id, args.date_from, args.date_to, daily, has_mv)
    summary_path = os.path.join(args.output_dir, "mv_reconciliation_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[mv-reconcile] Summary: {summary_path}")

    if args.csv:
        csv_content = _build_csv(daily)
        csv_path = os.path.join(args.output_dir, "mv_reconciliation_by_day.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_content)
        print(f"[mv-reconcile] CSV: {csv_path}")

    print(f"\n  Totals: MV trips={sum(r['mv_trips'] for r in daily):,} | "
          f"MV rev={sum(r['mv_revenue'] for r in daily):,.2f} | "
          f"CT trips={sum(r['ct_trips'] for r in daily):,} | "
          f"CT rev={sum(r['ct_revenue_final'] for r in daily):,.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
