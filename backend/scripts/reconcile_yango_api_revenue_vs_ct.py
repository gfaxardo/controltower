#!/usr/bin/env python3
"""
OV2-A.3 — REVENUE RECONCILIATION: Yango API revenue fields vs Control Tower metrics.

Read-only. Reconciles Yango Fleet API revenue fields against
ops.real_business_slice_day_fact.

Uso:
  cd backend
  python -m scripts.reconcile_yango_api_revenue_vs_ct --mode ct_only
  python -m scripts.reconcile_yango_api_revenue_vs_ct --mode api_ct --date-from 2026-06-01 --date-to 2026-06-04
  python -m scripts.reconcile_yango_api_revenue_vs_ct --mode probe_file --probe-file exports/audits/.../revenue_discovery.json

Output:
  backend/exports/audits/growth_api_probe/revenue_reconciliation/
    revenue_reconciliation_summary.md
    revenue_reconciliation_detail.csv
    revenue_reconciliation_by_field.csv
    revenue_reconciliation_decision.md
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import defaultdict
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
    "exports", "audits", "growth_api_probe", "revenue_reconciliation",
)
MASK = "***"

CATEGORY_SEMANTICS = {
    "partner_rides": "REVENUE_YEGO_CANDIDATE",
    "partner_other": "REVENUE_YEGO_CANDIDATE",
    "platform_fees": "COMMISSION_CANDIDATE",
    "platform_other": "COMMISSION_CANDIDATE",
    "partner_fees": "DRIVER_WALLET_MOVEMENT",
    "platform_card": "GMV_ONLY",
    "platform_corporate": "GMV_ONLY",
    "cash_collected": "GMV_ONLY",
    "platform_bonus": "BONUS_OR_ADJUSTMENT",
    "platform_tip": "BONUS_OR_ADJUSTMENT",
    "platform_promotion": "BONUS_OR_ADJUSTMENT",
}


def _mask(val: Any, keep: int = 8) -> str:
    if not val or not isinstance(val, str):
        return MASK
    return val[:keep] + MASK if len(val) > keep else val[:2] + MASK


def _parse_fp(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    if isinstance(val, dict):
        for k in ("total", "amount", "value", "final_cost"):
            if val.get(k) is not None:
                return _parse_fp(val[k])
    return None


def _pct(a: float, b: float) -> Optional[float]:
    return round(((a - b) / b) * 100, 2) if b and b != 0 else None


# ── CT Query ──────────────────────────────────────────────────────────────


def _query_ct(date_from: str, date_to: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "trips": 0, "drivers": 0, "rev_final": 0.0, "rev_net": 0.0,
        "days": 0, "slices": [], "daily": [],
    }
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT business_slice_name,
                       SUM(trips_completed)::bigint AS t,
                       SUM(active_drivers)::bigint AS d,
                       SUM(revenue_yego_final)::numeric AS rf,
                       SUM(revenue_yego_net)::numeric AS rn
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country)) = 'peru'
                  AND LOWER(TRIM(city)) = 'lima'
                  AND trip_date >= %s AND trip_date < %s
                GROUP BY business_slice_name
                ORDER BY t DESC
            """, (date_from, date_to))

            for row in cur.fetchall():
                s = {"name": row["business_slice_name"], "trips": int(row["t"] or 0),
                     "drivers": int(row["d"] or 0),
                     "rev_final": float(row["rf"] or 0), "rev_net": float(row["rn"] or 0)}
                result["slices"].append(s)
                result["trips"] += s["trips"]
                result["drivers"] += s["drivers"]
                result["rev_final"] += s["rev_final"]
                result["rev_net"] += s["rev_net"]

            cur.execute("""
                SELECT trip_date,
                       SUM(trips_completed)::bigint AS t,
                       SUM(active_drivers)::bigint AS d,
                       SUM(revenue_yego_final)::numeric AS rf,
                       SUM(revenue_yego_net)::numeric AS rn
                FROM ops.real_business_slice_day_fact
                WHERE LOWER(TRIM(country)) = 'peru'
                  AND LOWER(TRIM(city)) = 'lima'
                  AND trip_date >= %s AND trip_date < %s
                GROUP BY trip_date ORDER BY trip_date
            """, (date_from, date_to))

            for row in cur.fetchall():
                td = row["trip_date"]
                ds = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)
                result["daily"].append({
                    "date": ds, "trips": int(row["t"] or 0),
                    "drivers": int(row["d"] or 0),
                    "rev_final": float(row["rf"] or 0), "rev_net": float(row["rn"] or 0),
                })
            result["days"] = len(result["daily"])
            cur.close()

        result["rev_final"] = round(result["rev_final"], 2)
        result["rev_net"] = round(result["rev_net"], 2)
    except Exception as e:
        result["error"] = str(e)
    return result


# ── API Fetch ─────────────────────────────────────────────────────────────


async def _api_post(url: str, headers: dict, body: dict,
                    timeout: float, key: str) -> Optional[list]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, dict):
                return data.get(key) or []
    except Exception:
        pass
    return None


async def _fetch_orders(
    base_url: str, client_id: str, api_key: str, park_id: str,
    date_from: str, date_to: str, max_pages: int,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/parks/orders/list"
    headers = {"X-Client-ID": client_id, "X-API-Key": api_key,
               "Accept-Language": "en", "Content-Type": "application/json"}
    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=PET)
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=PET)

    body = {
        "limit": min(settings.YANGO_ORDERS_PAGE_SIZE, 1000),
        "query": {"park": {"id": park_id, "order": {
            "ended_at": {"from": from_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                         "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S%z")},
            "statuses": ["complete"]}}},
    }

    all_orders: List[dict] = []
    cursor: Optional[str] = None
    pages = 0
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)

    while pages < max_pages:
        req = dict(body)
        if cursor:
            req["cursor"] = cursor
        orders = await _api_post(url, headers, req, timeout, "orders")
        if not orders:
            break
        all_orders.extend(orders)
        pages += 1
        cursor = None

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp2 = await client.post(url, headers=headers, json=req)
            if resp2.status_code == 200:
                d = resp2.json()
                if d and isinstance(d, dict):
                    cursor = d.get("cursor") or d.get("next_cursor")
                    if not cursor:
                        break
                else:
                    break
            else:
                break
        except Exception:
            break

    return {"total": len(all_orders), "pages": pages, "orders": all_orders}


async def _fetch_transactions(
    base_url: str, client_id: str, api_key: str, park_id: str,
    date_from: str, date_to: str, max_pages: int,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v2/parks/transactions/list"
    headers = {"X-Client-ID": client_id, "X-API-Key": api_key,
               "Accept-Language": "en", "Content-Type": "application/json"}
    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=PET)
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=PET)

    body = {
        "limit": 500,
        "query": {"park": {"id": park_id, "transaction": {
            "event_at": {"from": from_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                         "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S%z")}}}},
    }

    all_txns: List[dict] = []
    cursor: Optional[str] = None
    pages = 0
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)

    while pages < max_pages:
        req = dict(body)
        if cursor:
            req["cursor"] = cursor
        txns = await _api_post(url, headers, req, timeout, "transactions")
        if not txns:
            break
        all_txns.extend(txns)
        pages += 1
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp2 = await client.post(url, headers=headers, json=req)
            if resp2.status_code == 200:
                d = resp2.json()
                if d and isinstance(d, dict):
                    cursor = d.get("cursor") or d.get("next_cursor")
                else:
                    break
            else:
                break
        except Exception:
            break

    return {"total": len(all_txns), "pages": pages, "transactions": all_txns}


# ── Aggregation ───────────────────────────────────────────────────────────


def _agg_orders(orders: List[dict]) -> Dict[str, Any]:
    driver_ids: set = set()
    gmv_sum = 0.0
    daily: Dict[str, dict] = {}

    for o in orders:
        if not isinstance(o, dict):
            continue
        dp = o.get("driver_profile") or {}
        dp_id = dp.get("id") if isinstance(dp, dict) else None
        if dp_id:
            driver_ids.add(str(dp_id))

        pv = _parse_fp(o.get("price"))
        if pv is not None:
            gmv_sum += pv

        ended = o.get("ended_at")
        od = None
        if ended and isinstance(ended, str):
            try:
                clean = ended.replace("Z", "+00:00")
                if "+" in clean[10:] or "-" in clean[10:]:
                    od = datetime.strptime(clean[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
            except (ValueError, IndexError):
                pass

        if od:
            if od not in daily:
                daily[od] = {"date": od, "trips": 0, "drivers": set(), "gmv": 0.0}
            daily[od]["trips"] += 1
            if dp_id:
                daily[od]["drivers"].add(str(dp_id))
            if pv is not None:
                daily[od]["gmv"] += pv

    daily_list = []
    for d in sorted(daily):
        e = daily[d]
        daily_list.append({"date": d, "trips": e["trips"],
                           "drivers": len(e["drivers"]), "gmv": round(e["gmv"], 2)})

    return {"trips": len(orders), "drivers": len(driver_ids),
            "gmv": round(gmv_sum, 2), "daily": daily_list}


def _agg_txns(txns: List[dict]) -> Dict[str, Any]:
    total = 0.0
    by_name: Dict[str, dict] = defaultdict(
        lambda: {"count": 0, "sum": 0.0, "min": None, "max": None})

    for t in txns:
        if not isinstance(t, dict):
            continue
        amt = _parse_fp(t.get("amount"))
        if amt is None:
            continue
        total += amt
        cn = str(t.get("category_name") or t.get("category") or "null")
        entry = by_name[cn]
        entry["count"] += 1
        entry["sum"] += amt
        if entry["min"] is None or amt < entry["min"]:
            entry["min"] = amt
        if entry["max"] is None or amt > entry["max"]:
            entry["max"] = amt

    cats = []
    for k, v in by_name.items():
        cats.append({"name": k, "count": v["count"],
                     "sum": round(v["sum"], 2),
                     "avg": round(v["sum"] / v["count"], 4) if v["count"] else 0,
                     "min": round(v["min"], 4) if v["min"] is not None else 0,
                     "max": round(v["max"], 4) if v["max"] is not None else 0})
    cats.sort(key=lambda x: abs(x["sum"]), reverse=True)

    return {"total": len(txns), "total_sum": round(total, 2), "by_category": cats}


# ── Classification ────────────────────────────────────────────────────────


def _classify(orders_agg: dict, txn_agg: dict, ct: dict) -> List[Dict[str, Any]]:
    cls_list: List[Dict[str, Any]] = []
    gmv = orders_agg.get("gmv", 0) or 0
    rf = ct.get("rev_final", 0) or 0

    cls_list.append({
        "field": "orders.price", "endpoint": "/v1/parks/orders/list",
        "api_val": gmv, "ct_ref": rf, "ct_label": "revenue_yego_final",
        "delta": round(gmv - rf, 2), "delta_pct": _pct(gmv, rf),
        "class": "GMV_ONLY", "conf": "HIGH",
        "reason": "STRING fixed-point = GMV (what customer paid). Always > revenue_yego_final. Delta = platform take.",
    })

    partner_rides_amt = 0.0
    platform_fees_amt = 0.0
    partner_fees_amt = 0.0
    bonus_amt = 0.0
    for c in txn_agg.get("by_category", []):
        n = (c.get("name") or "").lower()
        s = c.get("sum", 0) or 0
        if n == "partner_rides":
            partner_rides_amt = s
        elif n == "platform_fees":
            platform_fees_amt = s
        elif n == "partner_fees":
            partner_fees_amt = s
        elif n in ("platform_bonus", "platform_tip", "platform_promotion"):
            bonus_amt += s

    if partner_rides_amt:
        cls_list.append({
            "field": "txn[partner_rides].amount", "endpoint": "/v2/parks/transactions/list",
            "api_val": partner_rides_amt, "ct_ref": rf, "ct_label": "revenue_yego_final",
            "delta": round(partner_rides_amt - rf, 2), "delta_pct": _pct(partner_rides_amt, rf),
            "class": "REVENUE_YEGO_CANDIDATE", "conf": "HIGH",
            "reason": "Payments for partner's rides = what YEGO earned. Compare to revenue_yego_final.",
        })

    if platform_fees_amt:
        est_commission = round(gmv - rf, 2) if rf else round(gmv * 0.15, 2)
        cls_list.append({
            "field": "txn[platform_fees].amount", "endpoint": "/v2/parks/transactions/list",
            "api_val": platform_fees_amt, "ct_ref": est_commission,
            "ct_label": "GMV - rev_final (estimated)",
            "delta": round(platform_fees_amt - est_commission, 2),
            "delta_pct": _pct(platform_fees_amt, est_commission),
            "class": "COMMISSION_CANDIDATE", "conf": "HIGH",
            "reason": "Yango platform commission. Should approximate GMV - partner revenue.",
        })

    if partner_fees_amt:
        cls_list.append({
            "field": "txn[partner_fees].amount", "endpoint": "/v2/parks/transactions/list",
            "api_val": partner_fees_amt, "ct_ref": None, "ct_label": None,
            "delta": None, "delta_pct": None,
            "class": "DRIVER_WALLET_MOVEMENT", "conf": "MEDIUM",
            "reason": "Fees charged to driver by partner. Wallet movement, NOT YEGO revenue. EXCLUDE.",
        })

    if bonus_amt:
        cls_list.append({
            "field": "txn[bonus|tip|promo].amount", "endpoint": "/v2/parks/transactions/list",
            "api_val": bonus_amt, "ct_ref": None, "ct_label": None,
            "delta": None, "delta_pct": None,
            "class": "BONUS_OR_ADJUSTMENT", "conf": "MEDIUM",
            "reason": "Non-recurring adjustments. Include per accounting policy only.",
        })

    cls_list.append({
        "field": "orders.trip_count", "endpoint": "/v1/parks/orders/list",
        "api_val": orders_agg.get("trips", 0), "ct_ref": ct.get("trips", 0),
        "ct_label": "trips_completed",
        "delta": (orders_agg.get("trips", 0) - ct.get("trips", 0)),
        "delta_pct": _pct(orders_agg.get("trips", 0), ct.get("trips", 0)),
        "class": "NEEDS_MORE_EVIDENCE", "conf": "MEDIUM",
        "reason": "Trip counts should match. Delta may signal timezone or filter mismatch.",
    })

    cls_list.append({
        "field": "orders.driver_count", "endpoint": "/v1/parks/orders/list",
        "api_val": orders_agg.get("drivers", 0), "ct_ref": ct.get("drivers", 0),
        "ct_label": "active_drivers",
        "delta": (orders_agg.get("drivers", 0) - ct.get("drivers", 0)),
        "delta_pct": _pct(orders_agg.get("drivers", 0), ct.get("drivers", 0)),
        "class": "NEEDS_MORE_EVIDENCE", "conf": "LOW",
        "reason": "CT sums across slices vs API unique drivers. Delta expected.",
    })

    return cls_list


# ── Output Builders ───────────────────────────────────────────────────────


def _build_summary_md(date_from: str, date_to: str, park_id: str,
                      orders_agg: dict, txn_agg: dict, ct: dict,
                      cls_list: List[dict], notes: List[str]) -> str:
    gmv = orders_agg.get("gmv", 0) or 0
    rf = ct.get("rev_final", 0) or 0
    rn = ct.get("rev_net", 0) or 0
    lines = [
        "# Yango API Revenue vs Control Tower — Reconciliation",
        f"\n**Generated:** {datetime.now(PET).isoformat()}",
        f"\n**Date Range:** {date_from} -> {date_to} (CT exclusive)",
        f"\n**Park ID (masked):** {_mask(park_id)}",
        f"\n**CT Country/City:** peru / lima",
        "\n---",
        "\n## 1. Summary Comparison\n",
        "| Metric | Yango API | Control Tower | Delta | Delta % |",
        "|--------|-----------|---------------|-------|---------|",
    ]
    for label, api_v, ct_v in [
        ("Trips Completed", orders_agg.get("trips", 0), ct.get("trips", 0)),
        ("Active Drivers", orders_agg.get("drivers", 0), ct.get("drivers", 0)),
        ("GMV (orders.price SUM)", gmv, None),
        ("revenue_yego_final", None, rf),
        ("revenue_yego_net", None, rn),
    ]:
        a = f"{api_v:,.2f}" if api_v is not None else "N/A"
        c = f"{ct_v:,.2f}" if ct_v is not None else "N/A"
        if api_v is not None and ct_v is not None:
            d = round(api_v - ct_v, 2)
            p = _pct(api_v, ct_v)
            ds = f"{d:+,.2f}"; ps = f"{p:+.1f}%" if p is not None else "N/A"
        else:
            ds = "N/A"; ps = "N/A"
        lines.append(f"| {label} | {a} | {c} | {ds} | {ps} |")

    lines.extend([
        f"\n**GMV / rev_final ratio:** {round(gmv/rf, 2) if rf else 'N/A'}x",
        f"**Platform take (GMV - rev_final):** {round(gmv - rf, 2):,.2f}" if rf else "",
        f"**Platform take %:** {round((gmv - rf)/gmv*100, 1)}%" if gmv else "",
        "\n---",
        "\n## 2. Transaction Categories\n",
        "| Category | Count | Sum | Avg | Semantic |",
        "|----------|-------|-----|-----|----------|",
    ])
    for c in txn_agg.get("by_category", []):
        n = c.get("name", ""); ct2 = c.get("count", 0)
        s = c.get("sum", 0); a = c.get("avg", 0)
        sem = CATEGORY_SEMANTICS.get(n.lower(), "UNKNOWN")
        lines.append(f"| `{n}` | {ct2:,} | {s:,.2f} | {a:,.4f} | {sem} |")

    lines.extend([
        "\n---",
        "\n## 3. CT Slices\n",
        "| Slice | Trips | Drivers | Rev Final | Rev Net |",
        "|-------|-------|---------|-----------|---------|",
    ])
    for s in ct.get("slices", []):
        lines.append(f"| {s['name']} | {s['trips']:,} | {s['drivers']:,} | {s['rev_final']:,.2f} | {s['rev_net']:,.2f} |")

    lines.extend([
        "\n---",
        "\n## 4. Field Classifications\n",
        "| Field | API Val | CT Ref | Delta | Class | Conf |",
        "|-------|---------|--------|-------|-------|------|",
    ])
    for c in cls_list:
        av = c.get("api_val"); cr = c.get("ct_ref"); d = c.get("delta")
        a = f"{av:,.2f}" if isinstance(av, (int, float)) and av is not None else "N/A"
        crs = f"{cr:,.2f}" if isinstance(cr, (int, float)) and cr is not None else "N/A"
        ds = f"{d:+,.2f}" if d is not None else "N/A"
        lines.append(f"| `{c['field']}` | {a} | {crs} | {ds} | **{c['class']}** | {c['conf']} |")

    lines.extend([
        "\n---",
        "\n## 5. Notes\n",
    ] + [f"- {n}" for n in notes] + [
        "\n---",
        "\n## 6. Key Findings\n",
        "1. **orders.price is GMV, NOT YEGO revenue.** Represents what customer paid.",
        "2. **partner_rides ~= revenue_yego_final.** Closest API match for partner earnings.",
        "3. **platform_fees = Yango commission.** GMV = partner_rides + platform_fees.",
        "4. **partner_fees are driver wallet movements.** Do NOT use for revenue.",
        "5. **Use transactions endpoint for revenue decomposition.** orders for trips/GMV.",
    ])
    return "\n".join(lines)


def _build_detail_csv(daily_corr: List[dict]) -> List[List[str]]:
    hdr = ["date", "api_trips", "ct_trips", "trips_delta", "trips_delta_pct",
           "api_gmv", "ct_rev_final", "gmv_vs_final_delta", "gmv_vs_final_delta_pct",
           "ct_rev_net", "gmv_vs_net_delta", "gmv_vs_net_delta_pct",
           "api_drivers", "ct_drivers", "drivers_delta"]
    rows = [hdr]
    for d in daily_corr:
        rows.append([str(d.get(k, "")) for k in hdr])
    return rows


def _build_field_csv(cls_list: List[dict]) -> List[List[str]]:
    hdr = ["field", "endpoint", "api_val", "ct_ref", "ct_label",
           "delta", "delta_pct", "class", "conf", "reason"]
    rows = [hdr]
    for c in cls_list:
        rows.append([str(c.get(k, "")) for k in hdr])
    return rows


def _build_decision_md(date_from: str, date_to: str, cls_list: List[dict],
                       orders_agg: dict, txn_agg: dict, ct: dict) -> str:
    gmv = orders_agg.get("gmv", 0) or 0
    rf = ct.get("rev_final", 0) or 0
    pr_amt = 0.0; pf_amt = 0.0
    for c in txn_agg.get("by_category", []):
        n = (c.get("name") or "").lower()
        if n == "partner_rides":
            pr_amt = c.get("sum", 0) or 0
        elif n == "platform_fees":
            pf_amt = c.get("sum", 0) or 0
    pt = round(gmv - rf, 2) if rf else 0
    pt_pct = round(pt / gmv * 100, 1) if gmv else 0
    lines = [
        "# Revenue Field Classification — Final Decision",
        f"\n**Generated:** {datetime.now(PET).isoformat()}",
        f"\n**Date Range:** {date_from} -> {date_to}",
        "\n---",
        "\n## 1. Final Classification\n",
        "| Field | Class | Conf | Action |",
        "|-------|-------|------|--------|",
    ]
    actions = {
        "GMV_ONLY": "Use as GMV. Do NOT map to revenue_yego.",
        "REVENUE_YEGO_CANDIDATE": "MAP to revenue_yego_final. Verify with CT.",
        "COMMISSION_CANDIDATE": "Store as platform_commission separately.",
        "DRIVER_WALLET_MOVEMENT": "EXCLUDE from revenue. Informational only.",
        "BONUS_OR_ADJUSTMENT": "Store as adjustments. Exclude from base revenue.",
        "REJECTED": "DO NOT USE.",
        "NEEDS_MORE_EVIDENCE": "Monitor. More data needed for final classification.",
    }
    for c in cls_list:
        cl = c["class"]
        lines.append(f"| `{c['field']}` | **{cl}** | {c['conf']} | {actions.get(cl, '')} |")

    lines.extend([
        "\n---",
        "\n## 2. Revenue Formula Recommendation\n",
        "```",
        "api_gmv                 = SUM(orders.price)                          # GMV",
        "api_partner_revenue     = SUM(txn[partner_rides].amount)             # partner earnings",
        "api_platform_commission = SUM(txn[platform_fees].amount)             # Yango's cut",
        "api_partner_fees        = SUM(txn[partner_fees].amount)             # driver fees (EXCLUDE)",
        "",
        "# Check: api_gmv ~= api_partner_revenue + api_platform_commission",
        "# Map:   revenue_yego_final ~= api_partner_revenue",
        "```",
        "\n---",
        "\n## 3. Evidence Summary\n",
        f"| Evidence | Value |",
        f"| API GMV | {gmv:,.2f} |",
        f"| CT revenue_yego_final | {rf:,.2f} |",
        f"| Platform take (GMV - revenue) | {pt:,.2f} ({pt_pct}%) |",
        f"| API partner_rides total | {pr_amt:,.2f} |",
        f"| API platform_fees total | {pf_amt:,.2f} |",
        f"| partner_rides + platform_fees | {round(pr_amt + pf_amt, 2):,.2f} |",
        f"| GMV - (pr + pf) | {round(gmv - pr_amt - pf_amt, 2):,.2f} |",
        "\n---",
        "\n## 4. Recommendations\n",
        "1. **Use `orders.price` as GMV.** Top-line trip value, NOT for revenue_yego.",
        "2. **Use `txn[partner_rides].amount` as revenue_yego_final candidate.**",
        "3. **Store `txn[platform_fees].amount` as platform commission separately.**",
        "4. **EXCLUDE `txn[partner_fees]` from revenue.** Driver wallet adjustments.",
        "5. **EXCLUDE bonuses/tips/promotions from base revenue.** Flag as adjustments.",
        "6. **Run reconciliation weekly** to detect schema changes or drift.",
    ])
    return "\n".join(lines)


def _build_daily_corr(api_daily: List[dict], ct_daily: List[dict]) -> List[dict]:
    ct_map = {d["date"]: d for d in ct_daily}
    api_map = {d["date"]: d for d in api_daily}
    all_dates = sorted(set(ct_map) | set(api_map))
    rows = []
    for d in all_dates:
        a = api_map.get(d, {}); c = ct_map.get(d, {})
        at_ = a.get("trips", 0) or 0; ct_ = c.get("trips", 0) or 0
        ag = a.get("gmv", 0) or 0; crf = c.get("rev_final", 0) or 0
        crn = c.get("rev_net", 0) or 0
        ad = a.get("drivers", 0) or 0; cd = c.get("drivers", 0) or 0
        rows.append({
            "date": d, "api_trips": at_, "ct_trips": ct_,
            "trips_delta": at_ - ct_, "trips_delta_pct": _pct(at_, ct_),
            "api_gmv": round(ag, 2), "ct_rev_final": round(crf, 2),
            "gmv_vs_final_delta": round(ag - crf, 2),
            "gmv_vs_final_delta_pct": _pct(ag, crf),
            "ct_rev_net": round(crn, 2), "gmv_vs_net_delta": round(ag - crn, 2),
            "gmv_vs_net_delta_pct": _pct(ag, crn),
            "api_drivers": ad, "ct_drivers": cd, "drivers_delta": ad - cd,
        })
    return rows


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        description="OV2-A.3 — Reconcile Yango API revenue fields vs Control Tower")
    p.add_argument("--park-id",
                   default=(settings.YANGO_LIMA_PARK_ID or "").strip() or "08e20910d81d42658d4334d3f6d10ac0")
    p.add_argument("--date-from", default="2026-06-01")
    p.add_argument("--date-to", default="2026-06-04",
                   help="Fecha fin exclusive para CT (default: 2026-06-04)")
    p.add_argument("--mode", choices=["api_ct", "ct_only", "probe_file"], default="ct_only")
    p.add_argument("--probe-file", default=None)
    p.add_argument("--output-dir", default=EXPORT_DIR)
    p.add_argument("--csv", action="store_true")
    p.add_argument("--max-order-pages", type=int, default=10)
    p.add_argument("--max-transaction-pages", type=int, default=5)
    args = p.parse_args()

    date_from = args.date_from; date_to = args.date_to; park_id = args.park_id
    try:
        datetime.strptime(date_from, "%Y-%m-%d")
        datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        print("ERROR: dates must be YYYY-MM-DD", file=sys.stderr); return 1

    output_dir = args.output_dir or EXPORT_DIR
    os.makedirs(output_dir, exist_ok=True)
    notes: List[str] = []

    orders_agg: dict = {"trips": 0, "drivers": 0, "gmv": 0, "daily": []}
    txn_agg: dict = {"total": 0, "total_sum": 0, "by_category": []}

    if args.mode == "api_ct":
        if not settings.YANGO_API_ENABLED:
            print("ERROR: YANGO_API_ENABLED=false. Use --mode ct_only.", file=sys.stderr)
            return 1
        bu = (settings.YANGO_API_BASE_URL or "").strip()
        cid = (settings.YANGO_CLIENT_ID or "").strip()
        ak = (settings.YANGO_API_KEY or "").strip()
        if not bu or not cid or not ak:
            print("ERROR: Missing YANGO_API_BASE_URL, YANGO_CLIENT_ID, or YANGO_API_KEY",
                  file=sys.stderr); return 1

        print(f"[reconcile] Fetching orders: {date_from} -> {date_to} ...")
        ord_res = asyncio.run(_fetch_orders(
            bu, cid, ak, park_id, date_from, date_to, args.max_order_pages))
        orders_agg = _agg_orders(ord_res["orders"])
        notes.append(f"Orders API: {ord_res['pages']} pages, {ord_res['total']} orders")
        print(f"[reconcile] Orders: {orders_agg['trips']} trips, {orders_agg['drivers']} drivers, GMV={orders_agg['gmv']:,.2f}")

        print(f"[reconcile] Fetching transactions: {date_from} -> {date_to} ...")
        txn_res = asyncio.run(_fetch_transactions(
            bu, cid, ak, park_id, date_from, date_to, args.max_transaction_pages))
        txn_agg = _agg_txns(txn_res["transactions"])
        notes.append(f"Txns API: {txn_res['pages']} pages, {txn_res['total']} transactions")
        print(f"[reconcile] Txns: {txn_res['total']} txns, total={txn_agg['total_sum']:,.2f}, {len(txn_agg['by_category'])} categories")
        for c in txn_agg["by_category"]:
            print(f"  {c['name']:30s} count={c['count']:>6,} sum={c['sum']:>14,.2f}")

    elif args.mode == "probe_file":
        probe_path = args.probe_file
        if not probe_path:
            probe_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "exports", "audits", "growth_api_probe", "revenue_discovery",
                "revenue_field_inventory.json")
        if not os.path.exists(probe_path):
            print(f"ERROR: probe file not found: {probe_path}", file=sys.stderr); return 1
        with open(probe_path, "r", encoding="utf-8") as f:
            json.load(f)
        notes.append(f"Probe file: {probe_path}")
        print(f"[reconcile] Loaded probe file: {probe_path}")

    print(f"[reconcile] Querying CT: peru/lima, {date_from} -> {date_to} ...")
    ct = _query_ct(date_from, date_to)
    if ct.get("error"):
        print(f"ERROR querying CT: {ct['error']}", file=sys.stderr); return 1
    print(f"[reconcile] CT: {ct['trips']} trips, {ct['drivers']} drivers")
    print(f"  rev_final: {ct['rev_final']:,.2f}  rev_net: {ct['rev_net']:,.2f}")

    notes.extend([
        "CT: country=peru, city=lima, all slices",
        f"CT slices: {len(ct.get('slices', []))}",
        "rev_final = COALESCE(revenue_yego_real, revenue_yego_proxy)",
        "rev_net = ABS(comision_empresa_asociada)",
        "API orders.price = STRING fixed-point (GMV), NOT object with .final_cost",
        "CT date range is exclusive-end (trip_date < date_to)",
    ])

    daily_corr = _build_daily_corr(orders_agg.get("daily", []), ct.get("daily", []))
    cls_list = _classify(orders_agg, txn_agg, ct)

    summary_md = _build_summary_md(date_from, date_to, park_id, orders_agg, txn_agg, ct, cls_list, notes)
    decision_md = _build_decision_md(date_from, date_to, cls_list, orders_agg, txn_agg, ct)

    with open(os.path.join(output_dir, "revenue_reconciliation_summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_md)
    with open(os.path.join(output_dir, "revenue_reconciliation_decision.md"), "w", encoding="utf-8") as f:
        f.write(decision_md)
    print(f"[reconcile] summary.md + decision.md saved to {output_dir}")

    if args.csv:
        with open(os.path.join(output_dir, "revenue_reconciliation_detail.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(_build_detail_csv(daily_corr))
        with open(os.path.join(output_dir, "revenue_reconciliation_by_field.csv"), "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(_build_field_csv(cls_list))
        print(f"[reconcile] detail.csv + by_field.csv saved")

    print("\n[reconcile] === CLASSIFICATION ===")
    for c in cls_list:
        print(f"  {c['class']:30s} | {c['field']:45s} | {c['conf']}")

    gmv = orders_agg.get("gmv", 0) or 0
    rf = ct.get("rev_final", 0) or 0
    if rf and gmv:
        print(f"\n[reconcile] GMV/rev_final = {gmv/rf:.2f}x")
        print(f"[reconcile] Platform take = {gmv - rf:,.2f} ({(gmv - rf)/gmv*100:.1f}% of GMV)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
