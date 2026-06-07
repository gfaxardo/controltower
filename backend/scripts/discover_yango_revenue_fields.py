#!/usr/bin/env python3
"""
OV2-A.2 — REVENUE FIELD DISCOVERY: Descubre campos relevantes de revenue en Yango Fleet API.

Read-only. NO modifica tablas. NO toca serving facts. NO modifica UI.

Uso:
  cd backend
  python -m scripts.discover_yango_revenue_fields --date-from 2026-06-01 --date-to 2026-06-03
  python -m scripts.discover_yango_revenue_fields --dry-run
  python -m scripts.discover_yango_revenue_fields --discover-categories --sample-orders 20

Output:
  backend/exports/audits/growth_api_probe/revenue_discovery/
    revenue_field_inventory.json
    revenue_field_candidates.md
    revenue_payload_examples_sanitized.json
    revenue_semantic_hypotheses.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings

import httpx

PET = timezone(timedelta(hours=-5))
EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "growth_api_probe", "revenue_discovery",
)

MASK = "***"

SEMANTIC_LABELS = [
    "GMV_CANDIDATE",
    "REVENUE_YEGO_CANDIDATE",
    "COMMISSION_CANDIDATE",
    "DRIVER_WALLET_MOVEMENT",
    "BONUS_OR_ADJUSTMENT",
    "FEE_CANDIDATE",
    "UNKNOWN",
]

TRANSACTION_CATEGORY_SEMANTICS = {
    "platform_card": "GMV_CANDIDATE",
    "platform_corporate": "GMV_CANDIDATE",
    "partner_rides": "REVENUE_YEGO_CANDIDATE",
    "platform_fees": "COMMISSION_CANDIDATE",
    "partner_fees": "FEE_CANDIDATE",
    "platform_bonus": "BONUS_OR_ADJUSTMENT",
    "platform_tip": "BONUS_OR_ADJUSTMENT",
    "cash_collected": "GMV_CANDIDATE",
    "platform_promotion": "BONUS_OR_ADJUSTMENT",
    "partner_other": "REVENUE_YEGO_CANDIDATE",
    "platform_other": "COMMISSION_CANDIDATE",
}

ORDER_REVENUE_FIELDS = {
    "price": {
        "json_path": "price",
        "label": "GMV_CANDIDATE",
        "grain": "trip",
        "notes": "Per docs: STRING fixed-point like '12345.1434', NOT an object",
    },
    "mileage": {
        "json_path": "mileage",
        "label": "UNKNOWN",
        "grain": "trip",
        "notes": "Trip distance; may be needed for revenue-per-km calculations",
    },
}


def _mask(val: Any, keep: int = 8) -> str:
    if not val or not isinstance(val, str):
        return MASK
    if len(val) <= keep:
        return val[:2] + MASK
    return val[:keep] + MASK


def _infer_schema(obj: Any, max_depth: int = 5, _depth: int = 0) -> Any:
    if _depth >= max_depth:
        return "max_depth_reached"
    if obj is None:
        return "null"
    if isinstance(obj, bool):
        return "boolean"
    if isinstance(obj, int):
        return "integer"
    if isinstance(obj, float):
        return "number"
    if isinstance(obj, str):
        return "string"
    if isinstance(obj, list):
        if not obj:
            return ["empty_list"]
        schemas = []
        for item in obj[:3]:
            schemas.append(_infer_schema(item, max_depth, _depth + 1))
        if all(s == schemas[0] for s in schemas):
            return [schemas[0]]
        return {"list_of": schemas}
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            result[k] = _infer_schema(v, max_depth, _depth + 1)
        return result
    return f"unknown({type(obj).__name__})"


def _parse_fixed_point(val: Any) -> Optional[float]:
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
        for sub_key in ("final_cost", "total", "amount", "value"):
            sub = val.get(sub_key)
            if sub is not None:
                return _parse_fixed_point(sub)
    return None


def _format_currency(val: float) -> str:
    return f"{val:,.2f}"


def _build_headers(client_id: str, api_key: str) -> Dict[str, str]:
    return {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }


async def _fetch_transaction_categories(
    base_url: str,
    headers: Dict[str, str],
    park_id: str,
    timeout: float,
    dry_run: bool = False,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v2/parks/transactions/categories/list"
    body = {
        "query": {
            "park": {"id": park_id},
        },
    }

    if dry_run:
        return {
            "endpoint": url,
            "method": "POST",
            "dry_run": True,
            "body_summary": {"park_id": _mask(park_id)},
        }

    import time as _time
    start = _time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            elapsed_ms = round((_time.perf_counter() - start) * 1000)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = None

            if data and isinstance(data, dict):
                categories = data.get("categories") or []
                category_groups = data.get("category_groups") or data.get("groups") or []

                group_map: Dict[str, str] = {}
                for g in category_groups:
                    if isinstance(g, dict):
                        gid = g.get("id") or g.get("group_id")
                        gname = g.get("name") or g.get("group_name") or ""
                        if gid:
                            group_map[str(gid)] = str(gname)

                for cat in categories:
                    if isinstance(cat, dict):
                        gid = str(cat.get("group_id") or cat.get("group") or "")
                        if gid and gid in group_map:
                            cat["_group_name"] = group_map[gid]

                return {
                    "endpoint": url,
                    "method": "POST",
                    "status_code": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "total_categories": len(categories),
                    "categories": categories,
                    "category_groups": category_groups,
                    "sample_schema": _infer_schema(categories[0]) if categories else None,
                }

        return {
            "endpoint": url,
            "method": "POST",
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "error": f"HTTP {resp.status_code}",
        }

    except httpx.TimeoutException:
        return {"endpoint": url, "method": "POST", "error": "timeout"}
    except Exception as e:
        return {"endpoint": url, "method": "POST", "error": str(e)}


async def _fetch_transactions(
    base_url: str,
    headers: Dict[str, str],
    park_id: str,
    date_from: str,
    date_to: str,
    timeout: float,
    max_samples: int = 50,
    dry_run: bool = False,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v2/parks/transactions/list"

    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=PET)
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=PET
    )

    body = {
        "limit": min(max_samples, 500),
        "query": {
            "park": {
                "id": park_id,
                "transaction": {
                    "event_at": {
                        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    },
                },
            }
        },
    }

    if dry_run:
        return {
            "endpoint": url,
            "method": "POST",
            "dry_run": True,
            "body_summary": {
                "park_id": _mask(park_id),
                "date_from": date_from,
                "date_to": date_to,
                "limit": body["limit"],
            },
        }

    all_transactions: List[dict] = []
    cursor: Optional[str] = None
    pages_fetched = 0
    max_pages = 5
    errors: List[dict] = []
    timings: List[float] = []

    import time as _time
    while pages_fetched < max_pages and len(all_transactions) < max_samples * 3:
        req_body = dict(body)
        if cursor:
            req_body["cursor"] = cursor

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                start = _time.perf_counter()
                resp = await client.post(url, headers=headers, json=req_body)
                elapsed_ms = round((_time.perf_counter() - start) * 1000)
                timings.append(elapsed_ms)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None

                if data and isinstance(data, dict):
                    transactions = data.get("transactions") or []
                    all_transactions.extend(transactions)
                    next_cursor = data.get("cursor") or data.get("next_cursor")
                    pages_fetched += 1
                    if not next_cursor or not transactions:
                        cursor = None
                        break
                    cursor = next_cursor
                else:
                    break
            else:
                errors.append({
                    "page": pages_fetched + 1,
                    "status_code": resp.status_code,
                    "cursor": bool(cursor),
                })
                if resp.status_code == 429:
                    await asyncio.sleep(2.0)
                    continue
                break

        except httpx.TimeoutException:
            errors.append({"page": pages_fetched + 1, "error": "timeout"})
            break
        except Exception as e:
            errors.append({"page": pages_fetched + 1, "error": str(e)})
            break

    sample_schema = None
    if all_transactions:
        sample_schema = _infer_schema(all_transactions[0])

    return {
        "endpoint": url,
        "method": "POST",
        "date_range": {"from": date_from, "to": date_to},
        "park_id_masked": _mask(park_id),
        "total_transactions_fetched": len(all_transactions),
        "pages_fetched": pages_fetched,
        "has_more_pages": cursor is not None,
        "last_cursor_masked": _mask(cursor) if cursor else None,
        "errors": errors,
        "avg_elapsed_ms": round(sum(timings) / len(timings), 1) if timings else 0,
        "sample_schema": sample_schema,
        "sample_transactions": all_transactions[:max_samples],
        "sample_transaction_count": len(all_transactions[:max_samples]),
    }


async def _fetch_orders(
    base_url: str,
    headers: Dict[str, str],
    park_id: str,
    date_from: str,
    date_to: str,
    timeout: float,
    max_samples: int = 10,
    dry_run: bool = False,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/parks/orders/list"

    from_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=PET)
    to_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, tzinfo=PET
    )

    body = {
        "limit": min(max_samples, 500),
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

    if dry_run:
        return {
            "endpoint": url,
            "method": "POST",
            "dry_run": True,
            "body_summary": {
                "park_id": _mask(park_id),
                "date_from": date_from,
                "date_to": date_to,
                "limit": body["limit"],
                "statuses": ["complete"],
            },
        }

    import time as _time
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            start = _time.perf_counter()
            resp = await client.post(url, headers=headers, json=body)
            elapsed_ms = round((_time.perf_counter() - start) * 1000)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = None

            if data and isinstance(data, dict):
                orders = data.get("orders") or []

                sample_schema = None
                if orders:
                    sample_schema = _infer_schema(orders[0])

                return {
                    "endpoint": url,
                    "method": "POST",
                    "date_range": {"from": date_from, "to": date_to},
                    "park_id_masked": _mask(park_id),
                    "total_orders_fetched": len(orders),
                    "elapsed_ms": elapsed_ms,
                    "sample_schema": sample_schema,
                    "sample_orders": orders[:max_samples],
                    "sample_order_count": len(orders[:max_samples]),
                }

        return {
            "endpoint": url,
            "method": "POST",
            "status_code": resp.status_code,
            "elapsed_ms": elapsed_ms,
            "error": f"HTTP {resp.status_code}",
        }

    except httpx.TimeoutException:
        return {"endpoint": url, "method": "POST", "error": "timeout"}
    except Exception as e:
        return {"endpoint": url, "method": "POST", "error": str(e)}


def _analyze_price_field(orders: List[dict]) -> Dict[str, Any]:
    price_types: Dict[str, int] = {}
    string_examples: List[str] = []
    object_examples: List[dict] = []
    null_count = 0
    values: List[float] = []

    for order in orders:
        price = order.get("price")
        if price is None:
            null_count += 1
            continue
        if isinstance(price, str):
            price_types["string"] = price_types.get("string", 0) + 1
            if len(string_examples) < 5:
                string_examples.append(price)
            parsed = _parse_fixed_point(price)
            if parsed is not None:
                values.append(parsed)
        elif isinstance(price, dict):
            price_types["object"] = price_types.get("object", 0) + 1
            if len(object_examples) < 3:
                object_examples.append({k: type(v).__name__ for k, v in price.items()})
            parsed = _parse_fixed_point(price)
            if parsed is not None:
                values.append(parsed)
        elif isinstance(price, (int, float)):
            price_types["number"] = price_types.get("number", 0) + 1
            values.append(float(price))
        else:
            price_types[f"other({type(price).__name__})"] = price_types.get(f"other({type(price).__name__})", 0) + 1

    return {
        "type_distribution": price_types,
        "null_count": null_count,
        "total_checked": len(orders),
        "is_per_docs_string_type": price_types.get("string", 0) > 0 and not price_types.get("object", 0),
        "string_examples": string_examples,
        "object_example_shapes": object_examples,
        "min_value": min(values) if values else None,
        "max_value": max(values) if values else None,
        "avg_value": round(sum(values) / len(values), 4) if values else None,
    }


def _analyze_transactions(transactions: List[dict]) -> Dict[str, Any]:
    category_id_counts: Dict[str, int] = defaultdict(int)
    category_name_counts: Dict[str, int] = defaultdict(int)
    category_group_counts: Dict[str, int] = defaultdict(int)
    amounts_by_category: Dict[str, List[float]] = defaultdict(list)
    currency_counts: Dict[str, int] = defaultdict(int)
    has_event_at: Dict[str, int] = defaultdict(int)
    has_order_id: Dict[str, int] = defaultdict(int)
    driver_balance_ids: set = set()

    for txn in transactions:
        if not isinstance(txn, dict):
            continue

        cat_id = str(txn.get("category_id") or "null")
        cat_name = str(txn.get("category_name") or txn.get("category") or "null")
        cat_group = str(txn.get("category_group") or txn.get("group_id") or "null")

        category_id_counts[cat_id] += 1
        category_name_counts[cat_name] += 1
        category_group_counts[cat_group] += 1

        amount = _parse_fixed_point(txn.get("amount"))
        if amount is not None:
            amounts_by_category[cat_name].append(amount)
            amounts_by_category[f"id:{cat_id}"].append(amount)

        currency = txn.get("currency_code") or txn.get("currency") or "null"
        currency_counts[str(currency)] += 1

        if txn.get("event_at"):
            has_event_at[cat_name] += 1
        if txn.get("order_id"):
            has_order_id[cat_name] += 1

        if txn.get("driver_balance_before") is not None or txn.get("driver_balance_after") is not None:
            driver_balance_ids.add(cat_name)

    category_summaries = []
    for cat_name in sorted(category_name_counts.keys()):
        amts = amounts_by_category.get(cat_name, [])
        summary = {
            "category_name": cat_name,
            "count": category_name_counts[cat_name],
            "has_event_at_count": has_event_at.get(cat_name, 0),
            "has_order_id_count": has_order_id.get(cat_name, 0),
            "affects_driver_balance": cat_name in driver_balance_ids,
            "semantic_hypothesis": TRANSACTION_CATEGORY_SEMANTICS.get(cat_name, "UNKNOWN"),
        }
        if amts:
            summary["amount_min"] = min(amts)
            summary["amount_max"] = max(amts)
            summary["amount_avg"] = round(sum(amts) / len(amts), 4)
            summary["has_negative"] = any(a < 0 for a in amts)
        category_summaries.append(summary)

    return {
        "category_id_distribution": dict(category_id_counts),
        "category_name_distribution": dict(category_name_counts),
        "category_group_distribution": dict(category_group_counts),
        "currency_code_distribution": dict(currency_counts),
        "category_summaries": category_summaries,
        "total_transactions": len(transactions),
    }


def _cross_reference(orders: List[dict], transactions: List[dict]) -> Dict[str, Any]:
    order_by_id: Dict[str, dict] = {}
    for order in orders:
        oid = order.get("id") or order.get("order_id")
        if oid:
            order_by_id[str(oid)] = order

    matched: List[dict] = []
    unmatched_txn = 0

    for txn in transactions:
        order_id = txn.get("order_id") or txn.get("order")
        if not order_id:
            continue
        order = order_by_id.get(str(order_id))
        if order:
            order_price_val = _parse_fixed_point(order.get("price"))
            txn_amount_val = _parse_fixed_point(txn.get("amount"))
            cat_name = txn.get("category_name") or txn.get("category") or "unknown"

            matched.append({
                "order_id_masked": _mask(str(order_id)),
                "transaction_category": cat_name,
                "order_price": order_price_val,
                "transaction_amount": txn_amount_val,
                "transaction_amount_to_price_pct": (
                    round((abs(txn_amount_val) / order_price_val) * 100, 2)
                    if order_price_val and txn_amount_val and order_price_val != 0
                    else None
                ),
            })
        else:
            unmatched_txn += 1

    return {
        "total_orders": len(orders),
        "total_transactions_with_order_id": sum(
            1 for t in transactions if t.get("order_id") or t.get("order")
        ),
        "matched_pairs": len(matched),
        "unmatched_transactions": unmatched_txn,
        "matches": matched,
    }


def _classify_field(
    json_path: str,
    endpoint: str,
    dtype: str,
    currency: Optional[str],
    semantics: str,
    count: int,
    total: int,
    values: Optional[List[float]],
    grain: str,
    confidence: str,
) -> Dict[str, Any]:
    pct = round((count / total) * 100, 1) if total else 0
    entry: Dict[str, Any] = {
        "endpoint_source": endpoint,
        "json_path": json_path,
        "data_type": dtype,
        "currency": currency,
        "semantic_hypothesis": semantics,
        "percentage_of_records_with_value": pct,
        "can_be_negative": False,
        "grain": grain,
        "confidence_level": confidence,
    }
    if values:
        entry["min_value"] = min(values)
        entry["max_value"] = max(values)
        entry["avg_value"] = round(sum(values) / len(values), 4)
        entry["can_be_negative"] = any(v < 0 for v in values)
    return entry


def _build_field_inventory(
    orders_result: Dict[str, Any],
    transactions_result: Dict[str, Any],
    cross_ref: Dict[str, Any],
) -> List[Dict[str, Any]]:
    inventory: List[Dict[str, Any]] = []

    orders = orders_result.get("sample_orders", [])
    transactions = transactions_result.get("sample_transactions", [])

    if orders:
        price_analysis = _analyze_price_field(orders)
        price_values = []
        for o in orders:
            v = _parse_fixed_point(o.get("price"))
            if v is not None:
                price_values.append(v)

        inventory.append(_classify_field(
            json_path="price",
            endpoint="POST /v1/parks/orders/list",
            dtype="string (fixed-point)" if price_analysis.get("is_per_docs_string_type") else "mixed",
            currency=None,
            semantics="GMV_CANDIDATE",
            count=price_analysis["total_checked"] - price_analysis["null_count"],
            total=price_analysis["total_checked"],
            values=price_values if price_values else None,
            grain="trip",
            confidence="HIGH" if price_analysis.get("is_per_docs_string_type") else "HIGH",
        ))

        mileage_values = []
        mileage_count = 0
        for o in orders:
            m = o.get("mileage")
            if m is not None:
                mileage_count += 1
                parsed = _parse_fixed_point(m)
                if parsed is not None:
                    mileage_values.append(parsed)

        if mileage_count > 0:
            inventory.append(_classify_field(
                json_path="mileage",
                endpoint="POST /v1/parks/orders/list",
                dtype="number (km)",
                currency=None,
                semantics="UNKNOWN",
                count=mileage_count,
                total=len(orders),
                values=mileage_values if mileage_values else None,
                grain="trip",
                confidence="MEDIUM",
            ))

        payment_methods: Dict[str, int] = defaultdict(int)
        for o in orders:
            pm = o.get("payment_method") or o.get("payment") or "null"
            payment_methods[str(pm)] += 1
        if payment_methods:
            inventory.append({
                "endpoint_source": "POST /v1/parks/orders/list",
                "json_path": "payment_method",
                "data_type": "string (enum)",
                "semantic_hypothesis": "UNKNOWN",
                "distribution": dict(payment_methods),
                "note": "Payment method may influence revenue recognition",
                "grain": "trip",
                "confidence_level": "LOW",
            })

    if transactions:
        txn_analysis = _analyze_transactions(transactions)
        for summary in txn_analysis.get("category_summaries", []):
            cat_name = summary["category_name"]
            semantics = summary["semantic_hypothesis"]
            inventory.append({
                "endpoint_source": "POST /v2/parks/transactions/list",
                "json_path": f"transactions[category_name={cat_name}].amount",
                "data_type": "string (fixed-point)" if summary.get("has_negative") is not None else "number",
                "currency": txn_analysis.get("currency_code_distribution", {}),
                "semantic_hypothesis": semantics,
                "percentage_of_records_with_value": round(
                    (summary["count"] / txn_analysis["total_transactions"]) * 100, 1
                ),
                "min_value": summary.get("amount_min"),
                "max_value": summary.get("amount_max"),
                "avg_value": summary.get("amount_avg"),
                "can_be_negative": summary.get("has_negative", False),
                "grain": "transaction",
                "confidence_level": "HIGH" if semantics != "UNKNOWN" else "MEDIUM",
                "has_event_at_count": summary.get("has_event_at_count", 0),
                "has_order_id_count": summary.get("has_order_id_count", 0),
                "affects_driver_balance": summary.get("affects_driver_balance", False),
            })

    if cross_ref.get("matches"):
        inventory.append({
            "endpoint_source": "CROSS_REFERENCE: orders.price vs transactions.amount",
            "json_path": "cross-reference",
            "data_type": "relationship",
            "semantic_hypothesis": "GMV vs REVENUE comparison",
            "matched_pairs": cross_ref["matched_pairs"],
            "sample_matches": cross_ref["matches"][:5],
            "note": "order.price / transaction.amount ratio reveals Yango's take rate vs driver earnings",
            "grain": "trip × transaction",
            "confidence_level": "MEDIUM",
        })

    return inventory


def _build_candidates_md(inventory: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
    lines = [
        "# Yango Revenue Field Candidates — Analysis",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Park ID (masked):** {config.get('park_id_masked', MASK)}",
        f"**Date Range:** {config.get('date_from')} -&gt; {config.get('date_to')}",
        f"**Dry Run:** {config.get('dry_run', True)}",
        "",
        "---",
        "",
        "## Field Candidates",
        "",
    ]

    for i, field in enumerate(inventory, 1):
        label = field.get("semantic_hypothesis", "UNKNOWN")
        path = field.get("json_path", "?")
        endpoint = field.get("endpoint_source", "?")
        lines.append(f"### {i}. `{path}`  —  **{label}**")
        lines.append(f"- **Endpoint:** {endpoint}")
        lines.append(f"- **Data type:** {field.get('data_type', '?')}")
        lines.append(f"- **Grain:** {field.get('grain', '?')}")
        lines.append(f"- **Confidence:** {field.get('confidence_level', '?')}")

        if "currency" in field and field["currency"] and isinstance(field["currency"], dict):
            lines.append(f"- **Currency distribution:** {field['currency']}")
        elif field.get("currency"):
            lines.append(f"- **Currency:** {field['currency']}")

        if "min_value" in field:
            lines.append(f"- **Range:** {_format_currency(field['min_value'])} -&gt; {_format_currency(field['max_value'])} (avg: {_format_currency(field['avg_value'])})")
            lines.append(f"- **Can be negative:** {field.get('can_be_negative', '?')}")

        pct = field.get("percentage_of_records_with_value")
        if pct is not None:
            lines.append(f"- **Coverage:** {pct}% of records")

        if field.get("has_event_at_count", 0) > 0:
            lines.append(f"- **Has event_at:** {field.get('has_event_at_count')} transactions")
        if field.get("has_order_id_count", 0) > 0:
            lines.append(f"- **Has order_id:** {field.get('has_order_id_count')} transactions")
        if field.get("affects_driver_balance"):
            lines.append(f"- **Affects driver balance:** YES")

        if field.get("distribution"):
            lines.append(f"- **Value distribution:** {field['distribution']}")

        if field.get("note"):
            lines.append(f"- **Note:** {field['note']}")

        lines.append("")

    return "\n".join(lines)


def _build_semantic_hypotheses_md(inventory: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
    lines = [
        "# Yango Revenue Field — Semantic Hypotheses",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        "",
        "---",
        "",
        "## Overview",
        "",
        "This document captures hypotheses about what each revenue-relevant field semantically represents.",
        "Each hypothesis is classified by confidence level and includes reasoning.",
        "",
        "---",
        "",
    ]

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for field in inventory:
        label = field.get("semantic_hypothesis", "UNKNOWN")
        grouped[label].append(field)

    label_descriptions = {
        "GMV_CANDIDATE": "Gross Merchandise Value — total payment collected from rider (before ANY deductions). This is the top-line trip value.",
        "REVENUE_YEGO_CANDIDATE": "Net revenue that belongs to YEGO (the park/fleet operator). This is what YEGO earns from the trip after platform fees.",
        "COMMISSION_CANDIDATE": "Platform commission — what Yango (the platform) takes as their cut. This is the fee Yango charges for using their platform.",
        "DRIVER_WALLET_MOVEMENT": "Movement in driver wallet/account balance. This is a balance change, not necessarily revenue.",
        "BONUS_OR_ADJUSTMENT": "Bonus, tip, promotion, or adjustment. Non-core revenue that may or may not recur.",
        "FEE_CANDIDATE": "Fee charged to partner/driver. Could be subscription, service, or operational fee.",
        "UNKNOWN": "Unclassified — needs more investigation.",
    }

    for label in SEMANTIC_LABELS:
        fields = grouped.get(label, [])
        if not fields:
            continue
        desc = label_descriptions.get(label, "")
        lines.append(f"## {label}")
        lines.append(f"\n{desc}\n")
        for field in fields:
            path = field.get("json_path", "?")
            endpoint = field.get("endpoint_source", "?")
            conf = field.get("confidence_level", "?")
            lines.append(f"### `{path}`")
            lines.append(f"- **Source endpoint:** {endpoint}")
            lines.append(f"- **Confidence:** {conf}")
            lines.append(f"- **Grain:** {field.get('grain', '?')}")
            if "min_value" in field:
                lines.append(f"- **Value range:** {_format_currency(field['min_value'])} -&gt; {_format_currency(field['max_value'])}")
            if field.get("note"):
                lines.append(f"- **Note:** {field['note']}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Key Discovery: Transaction Categories")
    lines.append("")
    lines.append("Transaction categories with `group_id` reveal revenue semantics directly:")
    lines.append("")
    lines.append("| Category | group_id | Semantic |")
    lines.append("|---|---|---|")
    for cat_name, label in TRANSACTION_CATEGORY_SEMANTICS.items():
        lines.append(f"| `{cat_name}` | (category group) | **{label}** |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Key Discovery: Order `price` Field")
    lines.append("")
    lines.append("Per official API docs (https://fleet.yango.com/docs/api/en/):")
    lines.append("- `price` in orders is a **STRING** type (fixed-point like `\"12345.1434\"`), NOT an object.")
    lines.append("- It does NOT have a `.final_cost` sub-property.")
    lines.append("- Any code treating it as `order[\"price\"][\"final_cost\"]` is INCORRECT per docs.")
    lines.append("")

    return "\n".join(lines)


def _sanitize_examples(
    orders_result: Dict[str, Any],
    transactions_result: Dict[str, Any],
) -> Dict[str, Any]:
    def _sanitize_dict(obj: Any, depth: int = 0) -> Any:
        if depth > 6:
            return "[max_depth]"
        if obj is None:
            return None
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, (int, float)):
            return obj
        if isinstance(obj, str):
            if any(kw in obj.lower() for kw in ("key", "secret", "token", "password", "auth")):
                return MASK
            return obj
        if isinstance(obj, list):
            return [_sanitize_dict(item, depth + 1) for item in obj[:3]]
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                safe_k = k
                if any(s in k.lower() for s in ("key", "secret", "token", "password", "first_name", "last_name", "phone", "license")):
                    safe_k = _mask(k, 4)
                    result[safe_k] = MASK
                else:
                    result[safe_k] = _sanitize_dict(v, depth + 1)
            return result
        return str(obj)[:100]

    examples = {}

    orders = orders_result.get("sample_orders", [])
    examples["orders"] = {
        "count": len(orders),
        "examples": [_sanitize_dict(o) for o in orders[:5]],
        "schema": _infer_schema(orders[0]) if orders else None,
        "price_analysis": _analyze_price_field(orders) if orders else None,
    }

    transactions = transactions_result.get("sample_transactions", [])
    examples["transactions"] = {
        "count": len(transactions),
        "examples": [_sanitize_dict(t) for t in transactions[:10]],
        "schema": _infer_schema(transactions[0]) if transactions else None,
    }

    return examples


async def run_discovery(
    park_id: str,
    date_from: str,
    date_to: str,
    sample_orders: int,
    sample_transactions: int,
    discover_categories: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    base_url = (settings.YANGO_API_BASE_URL or "").strip()
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    enabled = bool(settings.YANGO_API_ENABLED)

    report: Dict[str, Any] = {
        "discovery_id": f"revenue_discovery_{date_from}_{date_to}",
        "generated_at": datetime.now(PET).isoformat(),
        "config": {
            "enabled": enabled,
            "base_url": base_url,
            "park_id_masked": _mask(park_id),
            "date_from": date_from,
            "date_to": date_to,
            "sample_orders": sample_orders,
            "sample_transactions": sample_transactions,
            "discover_categories": discover_categories,
            "dry_run": dry_run,
            "timezone": "America/Lima (UTC-5)",
        },
        "endpoints": {},
        "analysis": {},
    }

    if not enabled:
        report["error"] = "YANGO_API_ENABLED is false — discovery requires enabled API"
        return report

    if not client_id or not api_key or not park_id:
        report["error"] = "Missing YANGO_CLIENT_ID, YANGO_API_KEY, or YANGO_LIMA_PARK_ID"
        return report

    headers = _build_headers(client_id, api_key)
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)

    if discover_categories and not dry_run:
        print("[discovery] Fetching transaction categories ...")
        categories_result = await _fetch_transaction_categories(
            base_url, headers, park_id, timeout, dry_run=False,
        )
        report["endpoints"]["transaction_categories"] = categories_result
    elif discover_categories:
        categories_result = await _fetch_transaction_categories(
            base_url, headers, park_id, timeout, dry_run=True,
        )
        report["endpoints"]["transaction_categories"] = categories_result

    print(f"[discovery] Fetching transactions: {date_from} -> {date_to} ...")
    transactions_result = await _fetch_transactions(
        base_url, headers, park_id,
        date_from=date_from, date_to=date_to,
        timeout=timeout, max_samples=sample_transactions, dry_run=dry_run,
    )
    report["endpoints"]["transactions"] = transactions_result

    print(f"[discovery] Fetching orders: {date_from} -&gt; {date_to} ...")
    orders_result = await _fetch_orders(
        base_url, headers, park_id,
        date_from=date_from, date_to=date_to,
        timeout=timeout, max_samples=sample_orders, dry_run=dry_run,
    )
    report["endpoints"]["orders"] = orders_result

    if not dry_run:
        orders = orders_result.get("sample_orders", [])
        transactions = transactions_result.get("sample_transactions", [])

        if orders and transactions:
            print("[discovery] Cross-referencing orders &lt;-&gt; transactions ...")
            cross_ref = _cross_reference(orders, transactions)
            report["analysis"]["cross_reference"] = cross_ref
        else:
            report["analysis"]["cross_reference"] = {
                "note": "Not enough data for cross-reference",
                "orders_count": len(orders),
                "transactions_count": len(transactions),
            }

        inventory = _build_field_inventory(orders_result, transactions_result, cross_ref if orders and transactions else {})
        report["analysis"]["field_inventory"] = inventory
    else:
        report["analysis"]["field_inventory"] = []
        report["analysis"]["cross_reference"] = {"note": "dry_run"}

    return report


def main() -> int:
    p = argparse.ArgumentParser(
        description="OV2-A.2 — Discover revenue-relevant fields in Yango Fleet API"
    )
    p.add_argument(
        "--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip() or "08e20910d81d42658d4334d3f6d10ac0",
        help="Park ID (default: YANGO_LIMA_PARK_ID from settings)",
    )
    p.add_argument(
        "--date-from",
        default="2026-06-01",
        help="Start date YYYY-MM-DD (default: 2026-06-01)",
    )
    p.add_argument(
        "--date-to",
        default="2026-06-03",
        help="End date YYYY-MM-DD (default: 2026-06-03)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be queried without making API calls",
    )
    p.add_argument(
        "--output-dir",
        default=EXPORT_DIR,
        help=f"Output directory (default: {EXPORT_DIR})",
    )
    p.add_argument(
        "--sample-orders",
        type=int,
        default=10,
        help="Max orders to inspect (default: 10)",
    )
    p.add_argument(
        "--sample-transactions",
        type=int,
        default=50,
        help="Max transactions to inspect (default: 50)",
    )
    p.add_argument(
        "--discover-categories",
        action="store_true",
        help="Fetch transaction categories list from API",
    )
    args = p.parse_args()

    date_from = args.date_from
    date_to = args.date_to

    try:
        from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        to_dt = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        print("ERROR: dates must be YYYY-MM-DD", file=sys.stderr)
        return 1

    if (to_dt - from_dt).days > 7:
        print(
            f"ERROR: range ({date_from} -&gt; {date_to}) exceeds 7 days. Use a smaller range.",
            file=sys.stderr,
        )
        return 1

    if not settings.YANGO_API_ENABLED and not args.dry_run:
        print("WARNING: YANGO_API_ENABLED=false. Forcing --dry-run.", file=sys.stderr)
        args.dry_run = True

    output_dir = args.output_dir or EXPORT_DIR
    os.makedirs(output_dir, exist_ok=True)

    report = asyncio.run(
        run_discovery(
            park_id=args.park_id,
            date_from=date_from,
            date_to=date_to,
            sample_orders=args.sample_orders,
            sample_transactions=args.sample_transactions,
            discover_categories=args.discover_categories,
            dry_run=args.dry_run,
        )
    )

    if report.get("error"):
        print(f"ERROR: {report['error']}", file=sys.stderr)
        return 1

    inventory = report.get("analysis", {}).get("field_inventory", [])
    config = report.get("config", {})

    candidates_md = _build_candidates_md(inventory, config)
    hypotheses_md = _build_semantic_hypotheses_md(inventory, config)
    examples = _sanitize_examples(
        report.get("endpoints", {}).get("orders", {}),
        report.get("endpoints", {}).get("transactions", {}),
    )

    inventory_path = os.path.join(output_dir, "revenue_field_inventory.json")
    candidates_path = os.path.join(output_dir, "revenue_field_candidates.md")
    examples_path = os.path.join(output_dir, "revenue_payload_examples_sanitized.json")
    hypotheses_path = os.path.join(output_dir, "revenue_semantic_hypotheses.md")

    with open(inventory_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, default=str, ensure_ascii=False)

    with open(candidates_path, "w", encoding="utf-8") as f:
        f.write(candidates_md)

    with open(examples_path, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2, default=str, ensure_ascii=False)

    with open(hypotheses_path, "w", encoding="utf-8") as f:
        f.write(hypotheses_md)

    print(f"[discovery] Field inventory:  {inventory_path}")
    print(f"[discovery] Candidates MD:    {candidates_path}")
    print(f"[discovery] Examples JSON:    {examples_path}")
    print(f"[discovery] Hypotheses MD:    {hypotheses_path}")

    if args.dry_run:
        print("\n[discovery] DRY RUN — no API calls were made.")
        orders_dr = report.get("endpoints", {}).get("orders", {})
        txns_dr = report.get("endpoints", {}).get("transactions", {})
        print(f"  Orders endpoint:          {orders_dr.get('endpoint', '?')}")
        print(f"  Transactions endpoint:    {txns_dr.get('endpoint', '?')}")
        if report.get("endpoints", {}).get("transaction_categories"):
            cats_dr = report["endpoints"]["transaction_categories"]
            print(f"  Categories endpoint:      {cats_dr.get('endpoint', '?')}")
    else:
        orders_count = report.get("endpoints", {}).get("orders", {}).get("total_orders_fetched", 0)
        txns_count = report.get("endpoints", {}).get("transactions", {}).get("total_transactions_fetched", 0)
        print(f"\n[discovery] Orders fetched: {orders_count} | Transactions: {txns_count}")

        if report.get("endpoints", {}).get("transaction_categories"):
            cats_count = report["endpoints"]["transaction_categories"].get("total_categories", 0)
            print(f"[discovery] Transaction categories discovered: {cats_count}")

        if inventory:
            for field in inventory:
                label = field.get("semantic_hypothesis", "?")
                path = field.get("json_path", "?")
                conf = field.get("confidence_level", "?")
                print(f"  {label:30s} | {path:45s} | {conf}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
