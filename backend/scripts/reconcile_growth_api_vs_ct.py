#!/usr/bin/env python3
"""
OV2-A.1 — SOURCE DISCOVERY: Reconciliation Growth API vs Control Tower.

Read-only. Compara métricas de Yango Fleet API contra ops.real_business_slice_day_fact.

Uso:
  cd backend
  python -m scripts.reconcile_growth_api_vs_ct --date-from 2026-06-01 --date-to 2026-06-03
  python -m scripts.reconcile_growth_api_vs_ct --date-from 2026-06-01 --date-to 2026-06-03 --mode full
  python -m scripts.reconcile_growth_api_vs_ct --probe-file exports/audits/growth_api_probe/growth_api_probe_sample.json

Output:
  backend/exports/audits/growth_api_probe/reconciliation_YYYYMMDD.md
  backend/exports/audits/growth_api_probe/reconciliation_YYYYMMDD.csv
"""
from __future__ import annotations

import argparse
import asyncio
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

import httpx

PET = timezone(timedelta(hours=-5))
EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "growth_api_probe",
)


async def _list_orders_for_range(
    base_url: str,
    client_id: str,
    api_key: str,
    park_id: str,
    date_from: str,
    date_to: str,
    max_pages: int = 10,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/parks/orders/list"
    headers = {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }

    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=PET)
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=PET
    )

    body = {
        "limit": min(settings.YANGO_ORDERS_PAGE_SIZE, 1000),
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {
                        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    },
                    "statuses": ["complete"],
                },
            }
        },
    }

    all_orders: List[dict] = []
    cursor: Optional[str] = None
    pages = 0
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)

    while pages < max_pages:
        req_body = dict(body)
        if cursor:
            req_body["cursor"] = cursor

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                import time as _time
                resp = await client.post(url, headers=headers, json=req_body)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    break
                if data and isinstance(data, dict):
                    orders = data.get("orders") or []
                    all_orders.extend(orders)
                    next_cursor = data.get("cursor") or data.get("next_cursor")
                    pages += 1
                    if not next_cursor or not orders:
                        break
                    cursor = next_cursor
                else:
                    break
            else:
                break
        except Exception:
            break

    return {
        "total_orders": len(all_orders),
        "pages_fetched": pages,
        "orders": all_orders,
    }


def _aggregate_orders(orders: List[dict], date_from: str, date_to: str) -> Dict[str, Any]:
    trip_count = len(orders)
    driver_ids: set = set()
    revenue_sum = 0.0
    days_with_orders: set = set()
    daily_breakdown: Dict[str, Dict[str, Any]] = {}

    from_dt = datetime.strptime(date_from, "%Y-%m-%d").date()
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").date()

    for order in orders:
        if not isinstance(order, dict):
            continue

        dp = order.get("driver_profile") or {}
        dp_id = dp.get("id") if isinstance(dp, dict) else None
        if dp_id:
            driver_ids.add(str(dp_id))

        price = order.get("price") or {}
        final_cost = (
            price.get("final_cost") if isinstance(price, dict) else None
        )
        if final_cost is not None and isinstance(final_cost, (int, float)):
            revenue_sum += float(final_cost)

        ended = order.get("ended_at")
        order_date = None
        if ended and isinstance(ended, str):
            try:
                clean = ended.replace("Z", "+00:00")
                if "+" in clean[10:] or "-" in clean[10:]:
                    order_dt = datetime.strptime(clean[:19], "%Y-%m-%dT%H:%M:%S")
                    order_date = order_dt.strftime("%Y-%m-%d")
                    days_with_orders.add(order_date)
            except (ValueError, IndexError):
                pass

        if order_date:
            if order_date not in daily_breakdown:
                daily_breakdown[order_date] = {
                    "date": order_date, "trips": 0, "drivers": set(), "revenue": 0.0
                }
            daily_breakdown[order_date]["trips"] += 1
            if dp_id:
                daily_breakdown[order_date]["drivers"].add(str(dp_id))
            if final_cost and isinstance(final_cost, (int, float)):
                daily_breakdown[order_date]["revenue"] += float(final_cost)

    daily_list = []
    for d in sorted(daily_breakdown.keys()):
        entry = daily_breakdown[d]
        daily_list.append({
            "date": d,
            "trips": entry["trips"],
            "active_drivers": len(entry["drivers"]),
            "revenue": round(entry["revenue"], 2),
        })

    return {
        "trips_completed": trip_count,
        "active_drivers": len(driver_ids),
        "revenue": round(revenue_sum, 2),
        "days_with_orders": len(days_with_orders),
        "daily_breakdown": daily_list,
    }


def _query_ct_day_fact(date_from: str, date_to: str, country: str, city: str, slice_filter: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "trips_completed": 0,
        "active_drivers": 0,
        "revenue_yego_final": 0.0,
        "days_with_data": 0,
        "slices_found": [],
        "daily_breakdown": [],
        "query_params": {"country": country, "city": city, "slice_filter": slice_filter},
    }

    slice_clause = ""
    params = [country, city]
    if slice_filter == "all":
        slice_clause = ""
    elif slice_filter == "auto_regular":
        slice_clause = "AND LOWER(TRIM(business_slice_name)) = 'auto regular'"
    elif slice_filter:
        slice_clause = "AND LOWER(TRIM(business_slice_name)) = LOWER(TRIM(%s))"
        params.append(slice_filter)

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute(f"""
                SELECT business_slice_name,
                       SUM(trips_completed)::bigint AS trips,
                       SUM(active_drivers)::bigint AS drivers,
                       SUM(revenue_yego_final)::numeric AS revenue
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country)) = %s
                  AND LOWER(TRIM(city)) = %s
                  AND trip_date >= %s AND trip_date < %s
                  {slice_clause}
                GROUP BY business_slice_name
                ORDER BY trips DESC
            """, params + [date_from, date_to])

            for row in cur.fetchall():
                bs_name = row["business_slice_name"]
                result["slices_found"].append({
                    "business_slice_name": bs_name,
                    "trips": int(row["trips"] or 0),
                    "active_drivers": int(row["drivers"] or 0),
                    "revenue": float(row["revenue"] or 0),
                })
                result["trips_completed"] += int(row["trips"] or 0)
                result["active_drivers"] += int(row["drivers"] or 0)
                result["revenue_yego_final"] += float(row["revenue"] or 0)

            cur.execute(f"""
                SELECT trip_date,
                       SUM(trips_completed)::bigint AS trips,
                       SUM(active_drivers)::bigint AS drivers,
                       SUM(revenue_yego_final)::numeric AS revenue
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country)) = %s
                  AND LOWER(TRIM(city)) = %s
                  AND trip_date >= %s AND trip_date < %s
                  {slice_clause}
                GROUP BY trip_date
                ORDER BY trip_date
            """, params + [date_from, date_to])

            result["daily_breakdown"] = []
            for row in cur.fetchall():
                td = row["trip_date"]
                date_str = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)
                result["daily_breakdown"].append({
                    "date": date_str,
                    "trips": int(row["trips"] or 0),
                    "active_drivers": int(row["drivers"] or 0),
                    "revenue": float(row["revenue"] or 0),
                })
            result["days_with_data"] = len(result["daily_breakdown"])

            cur.close()

        result["revenue_yego_final"] = round(result["revenue_yego_final"], 2)

    except Exception as e:
        result["error"] = str(e)

    return result


def _compute_comparison(api_agg: Dict[str, Any], ct_agg: Dict[str, Any]) -> Dict[str, Any]:
    def _pct(api_val, ct_val):
        if ct_val and ct_val > 0:
            return round(((api_val - ct_val) / ct_val) * 100, 2)
        return None

    return {
        "trips": {
            "growth_api": api_agg.get("trips_completed", 0),
            "control_tower": ct_agg.get("trips_completed", 0),
            "delta": (api_agg.get("trips_completed", 0) - ct_agg.get("trips_completed", 0)),
            "delta_pct": _pct(api_agg.get("trips_completed", 0), ct_agg.get("trips_completed", 0)),
        },
        "active_drivers": {
            "growth_api": api_agg.get("active_drivers", 0),
            "control_tower": ct_agg.get("active_drivers", 0),
            "delta": (api_agg.get("active_drivers", 0) - ct_agg.get("active_drivers", 0)),
            "delta_pct": _pct(api_agg.get("active_drivers", 0), ct_agg.get("active_drivers", 0)),
        },
        "revenue": {
            "growth_api": api_agg.get("revenue", 0),
            "control_tower": ct_agg.get("revenue_yego_final", 0),
            "delta": round((api_agg.get("revenue", 0) - ct_agg.get("revenue_yego_final", 0)), 2),
            "delta_pct": _pct(api_agg.get("revenue", 0), ct_agg.get("revenue_yego_final", 0)),
        },
        "days_with_data": {
            "growth_api": api_agg.get("days_with_orders", 0),
            "control_tower": ct_agg.get("days_with_data", 0),
        },
    }


def _build_reconciliation_md(
    date_from: str, date_to: str,
    park_id: str,
    api_agg: Dict[str, Any],
    ct_agg: Dict[str, Any],
    comparison: Dict[str, Any],
    notes: List[str],
) -> str:
    lines = [
        f"# Growth API vs Control Tower — Reconciliation",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Date Range:** {date_from} → {date_to}",
        f"**Park ID (masked):** {park_id[:8]}***",
        f"**CT Country/City:** peru / lima",
        "",
        "## 1. Summary Comparison",
        "",
        "| Metric | Growth API | Control Tower | Delta | Delta % |",
        "|--------|-----------|---------------|-------|---------|",
    ]

    for metric_key, metric_label in [
        ("trips", "Trips Completed"),
        ("active_drivers", "Active Drivers"),
        ("revenue", "Revenue"),
    ]:
        comp = comparison.get(metric_key, {})
        api_val = comp.get("growth_api", 0)
        ct_val = comp.get("control_tower", 0)
        delta = comp.get("delta", 0)
        delta_pct = comp.get("delta_pct")

        delta_str = f"{delta:+,.0f}" if isinstance(delta, (int, float)) and abs(delta) >= 1 else f"{delta:+.2f}"
        pct_str = f"{delta_pct:+.1f}%" if delta_pct is not None else "N/A"

        lines.append(f"| {metric_label} | {api_val:,.2f}" if isinstance(api_val, float) and api_val != int(api_val) else f"| {metric_label} | {api_val:,}")
        lines[-1] += f" | {ct_val:,.2f}" if isinstance(ct_val, float) and ct_val != int(ct_val) else f" | {ct_val:,}"
        lines[-1] += f" | {delta_str} | {pct_str} |"

    lines.extend([
        "",
        f"- Days with data (API): {api_agg.get('days_with_orders', 0)}",
        f"- Days with data (CT): {ct_agg.get('days_with_data', 0)}",
        "",
        "## 2. CT Slices Found",
        "",
        "| Slice | Trips | Drivers | Revenue |",
        "|-------|-------|---------|---------|",
    ])

    for s in ct_agg.get("slices_found", []):
        lines.append(
            f"| {s['business_slice_name']} | {s['trips']:,} | {s['active_drivers']:,} | {s['revenue']:,.2f} |"
        )

    lines.extend([
        "",
        "## 3. Notes & Caveats",
        "",
    ])
    for note in notes:
        lines.append(f"- {note}")

    lines.extend([
        "",
        "## 4. Classification Guidance",
        "",
        "Based on reconciliation results, classify the Growth API per OV2_A1_SOURCE_CERTIFICATION_MATRIX.md.",
        "",
    ])

    return "\n".join(lines)


def _build_reconciliation_csv(
    date_from: str, date_to: str,
    api_agg: Dict[str, Any],
    ct_agg: Dict[str, Any],
    comparison: Dict[str, Any],
) -> List[List[str]]:
    rows = [
        ["metric", "growth_api", "control_tower", "delta", "delta_pct"],
    ]
    for key, label in [
        ("trips", "trips_completed"),
        ("active_drivers", "active_drivers"),
        ("revenue", "revenue"),
    ]:
        comp = comparison.get(key, {})
        rows.append([
            label,
            str(comp.get("growth_api", 0)),
            str(comp.get("control_tower", 0)),
            str(comp.get("delta", 0)),
            str(comp.get("delta_pct", "")),
        ])

    rows.append([])
    rows.append(["days_with_data", str(api_agg.get("days_with_orders", 0)), str(ct_agg.get("days_with_data", 0)), "", ""])

    return rows


def main() -> int:
    p = argparse.ArgumentParser(
        description="OV2-A.1 — Reconcile Growth API vs Control Tower day_fact"
    )
    p.add_argument(
        "--date-from", default="2026-06-01",
        help="Fecha inicio YYYY-MM-DD (default: 2026-06-01)",
    )
    p.add_argument(
        "--date-to", default="2026-06-03",
        help="Fecha fin YYYY-MM-DD (default: 2026-06-03)",
    )
    p.add_argument(
        "--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip() or "08e20910d81d42658d4334d3f6d10ac0",
        help="Park ID de Yango",
    )
    p.add_argument(
        "--slice",
        default="all",
        help="CT business slice filter: 'all', 'auto_regular', o nombre exacto (default: all)",
    )
    p.add_argument(
        "--max-pages", type=int, default=10,
        help="Máximo de páginas de órdenes (default: 10)",
    )
    p.add_argument(
        "--mode", choices=["api_ct", "ct_only", "probe_file"], default="ct_only",
        help="api_ct = call API + compare CT; ct_only = solo CT; probe_file = usar archivo probe previo",
    )
    p.add_argument(
        "--probe-file",
        default=None,
        help="Archivo JSON de probe previo (para --mode probe_file)",
    )
    p.add_argument(
        "--csv", action="store_true",
        help="Generar también CSV",
    )
    args = p.parse_args()

    date_from = args.date_from
    date_to = args.date_to
    park_id = args.park_id
    country = "peru"
    city = "lima"
    slice_filter = args.slice

    os.makedirs(EXPORT_DIR, exist_ok=True)

    date_label = date_from.replace("-", "")
    md_path = os.path.join(EXPORT_DIR, f"reconciliation_{date_label}.md")
    csv_path = os.path.join(EXPORT_DIR, f"reconciliation_{date_label}.csv")

    notes: List[str] = []

    api_agg: Dict[str, Any] = {
        "trips_completed": 0, "active_drivers": 0, "revenue": 0,
        "days_with_orders": 0, "daily_breakdown": [],
    }

    if args.mode == "api_ct":
        if not settings.YANGO_API_ENABLED:
            print("ERROR: YANGO_API_ENABLED=false. Use --mode ct_only o habilita la API.", file=sys.stderr)
            return 1

        base_url = (settings.YANGO_API_BASE_URL or "").strip()
        client_id = (settings.YANGO_CLIENT_ID or "").strip()
        api_key = (settings.YANGO_API_KEY or "").strip()

        if not base_url or not client_id or not api_key:
            print("ERROR: Faltan YANGO_API_BASE_URL, YANGO_CLIENT_ID, o YANGO_API_KEY", file=sys.stderr)
            return 1

        print(f"[reconcile] Fetching orders from Yango API: {date_from} -> {date_to} ...")
        orders_result = asyncio.run(
            _list_orders_for_range(
                base_url, client_id, api_key, park_id,
                date_from=date_from, date_to=date_to,
                max_pages=args.max_pages,
            )
        )
        api_agg = _aggregate_orders(orders_result["orders"], date_from, date_to)
        api_agg["pages_fetched"] = orders_result["pages_fetched"]
        notes.append(f"Growth API: {orders_result['pages_fetched']} pages fetched, {orders_result['total_orders']} orders")
        print(f"[reconcile] API: {api_agg['trips_completed']} trips, {api_agg['active_drivers']} drivers, {api_agg['revenue']} revenue")

    elif args.mode == "probe_file":
        probe_path = args.probe_file
        if not probe_path:
            probe_path = os.path.join(EXPORT_DIR, "growth_api_probe_sample.json")
        if not os.path.exists(probe_path):
            print(f"ERROR: probe file not found: {probe_path}", file=sys.stderr)
            return 1

        with open(probe_path, "r", encoding="utf-8") as f:
            probe_data = json.load(f)

        orders_ep = probe_data.get("endpoints", {}).get("orders", {})
        sample_orders = orders_ep.get("sample_orders", [])
        total_fetched = orders_ep.get("total_orders_fetched", 0)
        notes.append(f"Probe file: {total_fetched} orders (sample from probe)")
        print(f"[reconcile] Probe file: {len(sample_orders)} sample orders, {total_fetched} total")

    print(f"[reconcile] Querying CT day_fact: {country}/{city}, slice={slice_filter} ...")
    ct_agg = _query_ct_day_fact(date_from, date_to, country, city, slice_filter)

    if ct_agg.get("error"):
        print(f"ERROR querying CT: {ct_agg['error']}", file=sys.stderr)
        return 1

    print(f"[reconcile] CT: {ct_agg['trips_completed']} trips, {ct_agg['active_drivers']} drivers, {ct_agg['revenue_yego_final']} revenue")

    notes.append(f"CT filter: country={country}, city={city}, slice={slice_filter}")
    notes.append(f"CT slices found: {len(ct_agg.get('slices_found', []))}")
    notes.append("Revenue in CT is revenue_yego_final (COALESCE(real, proxy))")
    notes.append("Growth API revenue = SUM(price.final_cost) across completed orders")
    notes.append("Active drivers in CT may be summed across slices (possible double-count)")
    notes.append("Date range is exclusive-end in CT queries (trip_date < date_to)")
    notes.append("Growth API orders are filtered by ended_at in PET timezone")

    comparison = _compute_comparison(api_agg, ct_agg)

    md_content = _build_reconciliation_md(
        date_from, date_to, park_id, api_agg, ct_agg, comparison, notes,
    )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"[reconcile] Markdown saved: {md_path}")

    if args.csv:
        csv_content = _build_reconciliation_csv(date_from, date_to, api_agg, ct_agg, comparison)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(csv_content)
        print(f"[reconcile] CSV saved: {csv_path}")

    print(f"\n[reconcile] Comparison:")
    for key, label in [("trips", "Trips"), ("active_drivers", "Drivers"), ("revenue", "Revenue")]:
        comp = comparison.get(key, {})
        api_v = comp.get("growth_api", 0)
        ct_v = comp.get("control_tower", 0)
        delta = comp.get("delta", 0)
        pct = comp.get("delta_pct")
        pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
        print(f"  {label}: API={api_v} vs CT={ct_v} | Delta={delta}{pct_str}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
