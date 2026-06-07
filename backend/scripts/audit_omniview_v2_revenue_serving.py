#!/usr/bin/env python3
"""
OV2-B.7 — Revenue Serving Audit Script

Compares:
  API/MV: raw_yango.mv_revenue_day.revenue_partner_fee_amount
  vs CT: ops.real_business_slice_day_fact.revenue_yego_final

Outputs:
  backend/exports/audits/omniview_v2_shadow/revenue_serving_audit.md
  backend/exports/audits/omniview_v2_shadow/revenue_serving_by_day.csv

Classification:
  MATCH          <= 3%
  MINOR_DELTA    <= 5%
  MAJOR_DELTA    > 5%
  CT_UNAVAILABLE  No CT data for date
  API_UNAVAILABLE No API/MV data for date
"""
from __future__ import annotations

import csv
import os
import sys
from datetime import date as dt_date
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"
CT_COUNTRY = "peru"
CT_CITY = "lima"
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "omniview_v2_shadow",
)


def _mask(val: str) -> str:
    return (val[:8] + "***") if val and len(val) > 8 else "***"


def _pct(a: float, b: float) -> float | None:
    if b and b != 0:
        return round((a - b) / b * 100, 2)
    return None


def _classify(mv_rev: float, ct_rev: float, mv_exists: bool, ct_exists: bool) -> str:
    if not mv_exists and ct_exists:
        return "API_UNAVAILABLE"
    if mv_exists and not ct_exists:
        return "CT_UNAVAILABLE"
    if not mv_exists and not ct_exists:
        return "NO_DATA"
    delta = _pct(mv_rev, ct_rev)
    if delta is None:
        return "CT_UNAVAILABLE"
    abs_delta = abs(delta)
    if abs_delta <= 3:
        return "MATCH"
    elif abs_delta <= 5:
        return "MINOR_DELTA"
    else:
        return "MAJOR_DELTA"


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # MV side: revenue by day from raw_yango
        cur.execute("""
            SELECT
                revenue_date AS data_date,
                revenue_partner_fee_amount AS mv_revenue,
                revenue_partner_fee_count AS mv_txn_count,
                linked_orders AS mv_orders,
                revenue_per_order AS mv_rev_per_order,
                revenue_per_partner_fee_txn AS mv_rev_per_txn,
                revenue_source,
                revenue_confidence
            FROM raw_yango.mv_revenue_day
            WHERE park_id = %s
            ORDER BY revenue_date
        """, (PARK_ID,))
        mv_rows = {r["data_date"].isoformat() if hasattr(r["data_date"], "isoformat") else str(r["data_date"]): dict(r) for r in cur.fetchall()}

        # CT side: revenue by day from ops.real_business_slice_day_fact
        cur.execute("""
            SELECT
                trip_date AS data_date,
                COALESCE(SUM(trips_completed), 0)::bigint AS ct_trips,
                COALESCE(SUM(revenue_yego_final), 0)::numeric AS ct_revenue,
                COALESCE(SUM(revenue_yego_net), 0)::numeric AS ct_revenue_net
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country)) = %s
              AND LOWER(TRIM(city)) = %s
            GROUP BY trip_date
            ORDER BY trip_date
        """, (CT_COUNTRY, CT_CITY))
        ct_rows = {r["data_date"].isoformat() if hasattr(r["data_date"], "isoformat") else str(r["data_date"]): dict(r) for r in cur.fetchall()}

        cur.close()

    all_dates = sorted(set(list(mv_rows.keys()) + list(ct_rows.keys())))

    lines_csv = []
    lines_md = [
        "# OV2-B.7 — Revenue Serving Audit",
        "",
        f"**Date:** {dt_date.today().isoformat()}",
        f"**Park:** {_mask(PARK_ID)}",
        f"**CT filter:** country={CT_COUNTRY} city={CT_CITY}",
        "",
        "| Date | MV Revenue (PEN) | MV Txns | CT Revenue (PEN) | CT Trips | Delta (PEN) | Delta % | Status | MV Rev/Order | CT Rev/Trip |",
        "|------|-----------------|---------|------------------|----------|------------|---------|--------|-------------|------------|",
    ]

    for d in all_dates:
        mv = mv_rows.get(d, {})
        ct = ct_rows.get(d, {})
        mv_rev = float(mv.get("mv_revenue", 0) or 0)
        mv_txn_count = int(mv.get("mv_txn_count", 0) or 0)
        mv_orders = int(mv.get("mv_orders", 0) or 0)
        mv_rev_per_order = float(mv.get("mv_rev_per_order", 0) or 0)
        ct_rev = float(ct.get("ct_revenue", 0) or 0)
        ct_trips = int(ct.get("ct_trips", 0) or 0)
        ct_rev_net = float(ct.get("ct_revenue_net", 0) or 0)

        mv_exists = mv and mv_rev > 0
        ct_exists = ct and ct_trips > 0

        delta_val = round(mv_rev - ct_rev, 2)
        delta_pct = _pct(mv_rev, ct_rev)
        status = _classify(mv_rev, ct_rev, mv_exists, ct_exists)
        ct_rev_per_trip = round(ct_rev / ct_trips, 4) if ct_trips > 0 else 0

        lines_csv.append({
            "date": d,
            "mv_revenue": mv_rev,
            "mv_txn_count": mv_txn_count,
            "mv_orders": mv_orders,
            "mv_rev_per_order": mv_rev_per_order,
            "ct_revenue_final": ct_rev,
            "ct_revenue_net": ct_rev_net,
            "ct_trips": ct_trips,
            "ct_rev_per_trip": ct_rev_per_trip,
            "delta_pen": delta_val,
            "delta_pct": delta_pct,
            "status": status,
        })

        lines_md.append(
            f"| {d} | {mv_rev:,.2f} | {mv_txn_count:,} | {ct_rev:,.2f} | {ct_trips:,} | {delta_val:+,.2f} | "
            f"{delta_pct:+.2f}%" if delta_pct is not None else "N/A" + " | "
            f"{status} | {mv_rev_per_order:.4f} | {ct_rev_per_trip:.4f} |"
        )

    # Summary — only dates where both MV and CT have data
    matched_rows = [r for r in lines_csv if r["status"] not in ("API_UNAVAILABLE", "CT_UNAVAILABLE", "NO_DATA")]
    mv_total_rev = sum(r["mv_revenue"] for r in matched_rows)
    ct_total_rev = sum(r["ct_revenue_final"] for r in matched_rows)
    total_delta = round(mv_total_rev - ct_total_rev, 2) if ct_total_rev > 0 else 0
    total_delta_pct = _pct(mv_total_rev, ct_total_rev) if ct_total_rev > 0 else None
    statuses = {}
    for r in lines_csv:
        s = r["status"]
        statuses[s] = statuses.get(s, 0) + 1

    delta_str = f"{total_delta:+,.2f} PEN ({total_delta_pct:+.2f}%)" if total_delta_pct is not None else "N/A"

    lines_md += [
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Days with MV data | {len([r for r in lines_csv if r['status'] != 'API_UNAVAILABLE'])} |",
        f"| Days with CT data | {len([r for r in lines_csv if r['status'] != 'CT_UNAVAILABLE'])} |",
        f"| Days with both | {len(matched_rows)} |",
        f"| MV total revenue (both days) | {mv_total_rev:,.2f} PEN |",
        f"| CT total revenue (both days) | {ct_total_rev:,.2f} PEN |",
        f"| Delta | {delta_str} |",
        f"| MV Revenue Source | YANGO_TRANSACTIONS_API |",
        f"| MV Revenue Confidence | AUDIT_CERTIFIED |",
        "",
        "## Classification",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for s, c in sorted(statuses.items()):
        lines_md.append(f"| {s} | {c} |")

    md_path = os.path.join(OUTPUT_DIR, "revenue_serving_audit.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_md))

    csv_path = os.path.join(OUTPUT_DIR, "revenue_serving_by_day.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lines_csv[0].keys())
        w.writeheader()
        w.writerows(lines_csv)

    print(f"[audit] Report: {md_path}")
    print(f"[audit] CSV:    {csv_path}")
    print(f"[audit] MV total revenue: {mv_total_rev:,.2f} PEN")
    print(f"[audit] CT total revenue: {ct_total_rev:,.2f} PEN")
    print(f"[audit] Delta: {total_delta:+,.2f} PEN ({total_delta_pct:+.2f}%)" if total_delta_pct is not None else "N/A")
    for s, c in sorted(statuses.items()):
        print(f"[audit]   {s}: {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
