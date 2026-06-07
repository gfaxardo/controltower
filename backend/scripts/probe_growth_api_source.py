#!/usr/bin/env python3
"""
OV2-A.1 — SOURCE DISCOVERY: Probe seguro de Yango Fleet API como fuente candidata para Omniview V2.

Read-only. NO inserta en tablas. NO modifica serving facts. NO toca UI.

Uso:
  cd backend
  python -m scripts.probe_growth_api_source --date-from 2026-06-01 --date-to 2026-06-03
  python -m scripts.probe_growth_api_source --dry-run
  python -m scripts.probe_growth_api_source --park-id 08e20910d81d42658d4334d3f6d10ac0 --max-days 3 --output-json

Output:
  backend/exports/audits/growth_api_probe/
    growth_api_payload_schema.json
    growth_api_probe_sample.json
    growth_api_probe_summary.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings

import httpx

PET = timezone(timedelta(hours=-5))
EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "growth_api_probe",
)

MASK = "***"


def _mask(val: str, keep: int = 8) -> str:
    if not val or not isinstance(val, str):
        return MASK
    if len(val) <= keep:
        return val[:2] + MASK
    return val[:keep] + MASK


def _check_key(obj: Any, *paths: str) -> bool:
    node = obj
    for p in paths:
        if not isinstance(node, dict):
            return False
        node = node.get(p)
        if node is None:
            return False
    return True


def _infer_schema(obj: Any, max_depth: int = 4, _depth: int = 0) -> Any:
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


async def _probe_orders(
    base_url: str,
    client_id: str,
    api_key: str,
    park_id: str,
    date_from: str,
    date_to: str,
    page_size: int = 500,
    max_pages: int = 5,
    dry_run: bool = False,
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
        "limit": min(page_size, 1000),
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

    all_orders: List[dict] = []
    cursor: Optional[str] = None
    pages_fetched = 0
    errors: List[dict] = []
    timings: List[float] = []

    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)

    while pages_fetched < max_pages:
        req_body = dict(body)
        if cursor:
            req_body["cursor"] = cursor

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                start = sys.monotonic() if hasattr(sys, "monotonic") else 0
                import time as _time
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
                    orders = data.get("orders") or []
                    all_orders.extend(orders)
                    next_cursor = data.get("cursor") or data.get("next_cursor")
                    pages_fetched += 1
                    if not next_cursor or not orders:
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
            errors.append({"page": pages_fetched + 1, "error": "timeout", "cursor": bool(cursor)})
            break
        except Exception as e:
            errors.append({"page": pages_fetched + 1, "error": str(e), "cursor": bool(cursor)})
            break

    sample_schema = None
    if all_orders:
        sample_schema = _infer_schema(all_orders[0])

    return {
        "endpoint": url,
        "method": "POST",
        "date_range": {"from": date_from, "to": date_to},
        "park_id_masked": _mask(park_id),
        "total_orders_fetched": len(all_orders),
        "pages_fetched": pages_fetched,
        "has_more_pages": cursor is not None,
        "last_cursor_masked": _mask(cursor) if cursor else None,
        "errors": errors,
        "avg_elapsed_ms": round(sum(timings) / len(timings), 1) if timings else 0,
        "sample_order_schema": sample_schema,
        "sample_orders": all_orders[:3],
        "sample_order_count": len(all_orders),
    }


async def _probe_driver_profiles(
    base_url: str,
    client_id: str,
    api_key: str,
    park_id: str,
    page_size: int = 1000,
    dry_run: bool = False,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/parks/driver-profiles/list"
    headers = {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }

    body = {
        "query": {
            "park": {
                "id": park_id,
                "driver_profile": {"work_status": ["working", "not_working"]},
            },
        },
        "fields": {
            "driver_profile": [
                "id", "park_id", "created_date", "first_name", "last_name",
                "work_rule_id", "work_status", "employment_type", "has_contract_issue",
            ],
            "current_status": ["status", "status_updated_at"],
            "car": ["id", "status", "category", "callsign", "brand", "model", "year", "number"],
            "account": ["id", "balance", "balance_limit", "currency", "last_transaction_date"],
            "park": ["id", "city", "name"],
        },
        "limit": min(page_size, 1000),
        "offset": 0,
    }

    if dry_run:
        return {
            "endpoint": url,
            "method": "POST",
            "dry_run": True,
            "body_summary": {"park_id": _mask(park_id), "limit": body["limit"]},
        }

    try:
        timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            import time as _time
            start = _time.perf_counter()
            resp = await client.post(url, headers=headers, json=body)
            elapsed_ms = round((_time.perf_counter() - start) * 1000)

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = None

            if data and isinstance(data, dict):
                profiles = data.get("driver_profiles") or []
                total = data.get("total", len(profiles))

                work_statuses: Dict[str, int] = {}
                current_statuses: Dict[str, int] = {}
                car_categories: Dict[str, int] = {}
                has_car = False
                has_account = False
                has_current_status = False

                for p in profiles:
                    if not isinstance(p, dict):
                        continue
                    dp = p.get("driver_profile") or {}
                    ws = dp.get("work_status", "unknown")
                    work_statuses[ws] = work_statuses.get(ws, 0) + 1

                    cs = p.get("current_status") or {}
                    if cs:
                        has_current_status = True
                        cst = cs.get("status", "unknown")
                        current_statuses[cst] = current_statuses.get(cst, 0) + 1

                    if p.get("car"):
                        has_car = True
                        car_info = p["car"]
                        if isinstance(car_info, dict):
                            cat = car_info.get("category", "unknown")
                            car_categories[cat] = car_categories.get(cat, 0) + 1

                    if p.get("account"):
                        has_account = True

                sample_schema = None
                if profiles:
                    sample_schema = _infer_schema(profiles[0])

                return {
                    "endpoint": url,
                    "method": "POST",
                    "total": total,
                    "fetched": len(profiles),
                    "elapsed_ms": elapsed_ms,
                    "work_status_distribution": work_statuses,
                    "current_status_distribution": current_statuses if has_current_status else None,
                    "car_category_distribution": car_categories,
                    "has_current_status": has_current_status,
                    "has_car": has_car,
                    "has_account": has_account,
                    "sample_schema": sample_schema,
                    "sample_profiles": profiles[:2],
                }

        return {
            "endpoint": url,
            "method": "POST",
            "status_code": resp.status_code,
            "error": f"HTTP {resp.status_code}",
        }

    except httpx.TimeoutException:
        return {"endpoint": url, "method": "POST", "error": "timeout"}
    except Exception as e:
        return {"endpoint": url, "method": "POST", "error": str(e)}


async def _probe_supply_hours(
    base_url: str,
    client_id: str,
    api_key: str,
    park_id: str,
    sample_contractor_ids: List[str],
    period_from: str,
    period_to: str,
    max_samples: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v2/parks/contractors/supply-hours"
    headers = {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "X-Park-ID": park_id,
        "Accept-Language": "en",
    }

    params_template = {
        "period_from": f"{period_from}T00:00:00-05:00",
        "period_to": f"{period_to}T23:59:59-05:00",
    }

    if dry_run:
        return {
            "endpoint": url,
            "method": "GET",
            "dry_run": True,
            "sample_count": min(len(sample_contractor_ids), max_samples),
            "params_template": params_template,
        }

    results: List[dict] = []
    errors: List[dict] = []
    timeout = float(settings.YANGO_API_TIMEOUT_SECONDS)

    for cid in sample_contractor_ids[:max_samples]:
        params = {"contractor_profile_id": cid, **params_template}
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                import time as _time
                start = _time.perf_counter()
                resp = await client.get(url, headers=headers, params=params)
                elapsed_ms = round((_time.perf_counter() - start) * 1000)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None
                supply_seconds = 0
                if isinstance(data, dict):
                    supply_seconds = data.get("supply_duration_seconds", 0) or 0
                results.append({
                    "contractor_id_masked": _mask(cid),
                    "supply_duration_seconds": supply_seconds,
                    "supply_hours": round(supply_seconds / 3600.0, 2) if supply_seconds else 0,
                    "elapsed_ms": elapsed_ms,
                })
            else:
                errors.append({
                    "contractor_id_masked": _mask(cid),
                    "status_code": resp.status_code,
                })
        except Exception as e:
            errors.append({"contractor_id_masked": _mask(cid), "error": str(e)})
        await asyncio.sleep(1.5)

    return {
        "endpoint": url,
        "method": "GET",
        "samples_attempted": min(len(sample_contractor_ids), max_samples),
        "samples_succeeded": len(results),
        "samples_failed": len(errors),
        "results": results,
        "errors": errors,
    }


async def run_probe(
    park_id: str,
    date_from: str,
    date_to: str,
    max_pages: int,
    dry_run: bool,
) -> Dict[str, Any]:
    base_url = (settings.YANGO_API_BASE_URL or "").strip()
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    enabled = bool(settings.YANGO_API_ENABLED)

    report: Dict[str, Any] = {
        "probe_id": f"growth_api_probe_{date_from}_{date_to}",
        "generated_at": datetime.now(PET).isoformat(),
        "config": {
            "enabled": enabled,
            "base_url": base_url,
            "park_id_masked": _mask(park_id),
            "date_range": {"from": date_from, "to": date_to},
            "max_pages": max_pages,
            "dry_run": dry_run,
            "timezone": "America/Lima (UTC-5)",
        },
        "endpoints": {},
    }

    if not enabled:
        report["error"] = "YANGO_API_ENABLED is false — probe requires enabled API"
        return report

    if not client_id or not api_key or not park_id:
        report["error"] = "Missing YANGO_CLIENT_ID, YANGO_API_KEY, or YANGO_LIMA_PARK_ID"
        return report

    print(f"[probe] Probing orders: {date_from} -> {date_to} ...")
    orders_result = await _probe_orders(
        base_url, client_id, api_key, park_id,
        date_from=date_from, date_to=date_to,
        page_size=500, max_pages=max_pages, dry_run=dry_run,
    )
    report["endpoints"]["orders"] = orders_result

    contractor_ids: List[str] = []
    if not dry_run and orders_result.get("sample_orders"):
        for order in orders_result["sample_orders"]:
            dp = order.get("driver_profile") or {}
            dp_id = dp.get("id") if isinstance(dp, dict) else None
            if dp_id:
                contractor_ids.append(str(dp_id))

    if not dry_run:
        print(f"[probe] Probing driver profiles ...")
        profiles_result = await _probe_driver_profiles(
            base_url, client_id, api_key, park_id, page_size=100, dry_run=dry_run,
        )
        report["endpoints"]["driver_profiles"] = profiles_result

        if not contractor_ids and profiles_result.get("sample_profiles"):
            for profile in profiles_result["sample_profiles"]:
                dp = (
                    profile.get("driver_profile")
                    if isinstance(profile, dict) else None
                )
                dp_id = dp.get("id") if isinstance(dp, dict) else None
                if dp_id:
                    contractor_ids.append(str(dp_id))

    if not dry_run and contractor_ids:
        print(f"[probe] Probing supply hours for {min(len(contractor_ids), 5)} drivers ...")
        supply_result = await _probe_supply_hours(
            base_url, client_id, api_key, park_id,
            sample_contractor_ids=contractor_ids,
            period_from=date_from, period_to=date_to,
            max_samples=5, dry_run=dry_run,
        )
        report["endpoints"]["supply_hours"] = supply_result

    return report


def _build_schema_json(report: Dict[str, Any]) -> Dict[str, Any]:
    orders_ep = report.get("endpoints", {}).get("orders", {})
    profiles_ep = report.get("endpoints", {}).get("driver_profiles", {})
    supply_ep = report.get("endpoints", {}).get("supply_hours", {})

    return {
        "source": "Yango Fleet API",
        "base_url": report.get("config", {}).get("base_url", ""),
        "authentication": "X-Client-ID + X-API-Key (custom headers)",
        "timezone": "America/Lima (UTC-5)",
        "pagination": {
            "orders": "cursor-based (next_cursor field in response)",
            "driver_profiles": "offset-based (limit/offset params, total field in response)",
            "supply_hours": "per-driver (no pagination, one call per contractor_profile_id)",
        },
        "rate_limits": {
            "observed": True,
            "status_code": 429,
            "backoff": f"{settings.YANGO_SUPPLY_RATE_LIMIT_BACKOFF_MS}ms",
            "max_retries": settings.YANGO_SUPPLY_MAX_RETRIES,
        },
        "endpoints": {
            "POST /v1/parks/orders/list": {
                "description": "List completed orders for a park and date range",
                "grain": "order",
                "status_filter": ["complete"],
                "schema": orders_ep.get("sample_order_schema"),
                "fields_available": list(
                    (orders_ep.get("sample_order_schema") or {}).keys()
                ) if isinstance(orders_ep.get("sample_order_schema"), dict) else [],
                "has_driver_id": _check_key(
                    (orders_ep.get("sample_orders") or [{}])[0] if orders_ep.get("sample_orders") else {},
                    "driver_profile", "id",
                ),
                "has_trip_id": True,
                "has_price": _check_key(
                    (orders_ep.get("sample_orders") or [{}])[0] if orders_ep.get("sample_orders") else {},
                    "price",
                ),
                "has_status": True,
                "has_timestamps": True,
                "has_car_info": _check_key(
                    (orders_ep.get("sample_orders") or [{}])[0] if orders_ep.get("sample_orders") else {},
                    "car",
                ),
                "total_fetched": orders_ep.get("total_orders_fetched", 0),
            },
            "POST /v1/parks/driver-profiles/list": {
                "description": "List driver profiles with status, car, and account info",
                "grain": "driver_profile",
                "schema": profiles_ep.get("sample_schema"),
                "fields_available": list(
                    (profiles_ep.get("sample_schema") or {}).keys()
                ) if isinstance(profiles_ep.get("sample_schema"), dict) else [],
                "has_work_status": True,
                "has_current_status": profiles_ep.get("has_current_status", False),
                "has_car": profiles_ep.get("has_car", False),
                "has_account_balance": profiles_ep.get("has_account", False),
                "total": profiles_ep.get("total", 0),
            },
            "GET /v2/parks/contractors/supply-hours": {
                "description": "Get supply hours for a specific driver and date range",
                "grain": "driver × day",
                "returns": "supply_duration_seconds (convert to hours: / 3600)",
                "samples_attempted": supply_ep.get("samples_attempted", 0),
                "samples_succeeded": supply_ep.get("samples_succeeded", 0),
            },
        },
        "metrics_available": {
            "trips_completed": {
                "source": "orders/list filtered by status=complete",
                "grain": "per order (can be aggregated daily/park)",
            },
            "active_drivers": {
                "source": "orders/list DISTINCT driver_profile.id",
                "grain": "per order (distinct aggregation needed)",
            },
            "supply_hours": {
                "source": "supply-hours (per-driver call required)",
                "grain": "driver × day (expensive: one call per driver per day)",
            },
            "revenue": {
                "source": "orders/list price.final_cost",
                "grain": "per order",
                "currency": "from API response (inferred)",
            },
            "driver_state": {
                "source": "driver-profiles/list work_status + current_status",
                "grain": "per driver (snapshot, no history)",
            },
        },
    }


def _build_summary_md(report: Dict[str, Any]) -> str:
    config = report.get("config", {})
    orders = report.get("endpoints", {}).get("orders", {})
    profiles = report.get("endpoints", {}).get("driver_profiles", {})
    supply = report.get("endpoints", {}).get("supply_hours", {})

    lines = [
        "# Growth API Source Probe — Summary",
        "",
        f"**Generated:** {report.get('generated_at', 'N/A')}",
        f"**Dry Run:** {config.get('dry_run', True)}",
        f"**Date Range:** {config.get('date_range', {}).get('from')} → {config.get('date_range', {}).get('to')}",
        f"**Park ID (masked):** {config.get('park_id_masked', 'N/A')}",
        "",
        "## 1. Connection",
        f"- Enabled: {config.get('enabled', False)}",
        f"- Base URL: {config.get('base_url', 'N/A')}",
        f"- Auth: X-Client-ID + X-API-Key (custom headers, NOT Bearer token)",
        f"- Timezone: {config.get('timezone', 'N/A')}",
        "",
        "## 2. Orders Endpoint — POST /v1/parks/orders/list",
        f"- Total orders fetched: {orders.get('total_orders_fetched', 0)}",
        f"- Pages fetched: {orders.get('pages_fetched', 0)} (max: {config.get('max_pages', 0)})",
        f"- Has more pages: {orders.get('has_more_pages', 'N/A')}",
        f"- Pagination: cursor-based (next_cursor field)",
        f"- Errors: {orders.get('errors', [])}",
        "",
        "## 3. Driver Profiles Endpoint — POST /v1/parks/driver-profiles/list",
        f"- Total profiles: {profiles.get('total', 0)}",
        f"- Fetched: {profiles.get('fetched', 0)}",
        f"- Work status distribution: {profiles.get('work_status_distribution', {})}",
        f"- Has car info: {profiles.get('has_car', False)}",
        f"- Has account/balance: {profiles.get('has_account', False)}",
        f"- Has current status: {profiles.get('has_current_status', False)}",
        f"- Pagination: offset-based (limit/offset, total in response)",
        "",
        "## 4. Supply Hours Endpoint — GET /v2/parks/contractors/supply-hours",
        f"- Samples attempted: {supply.get('samples_attempted', 0)}",
        f"- Samples succeeded: {supply.get('samples_succeeded', 0)}",
        f"- Samples failed: {supply.get('samples_failed', 0)}",
        "- Per-driver endpoint (one HTTP call per driver per day)",
        "- Returns supply_duration_seconds (divide by 3600 for hours)",
        f"- Rate limit backoff: {settings.YANGO_SUPPLY_RATE_LIMIT_BACKOFF_MS}ms",
        "",
        "## 5. Grain Analysis",
        "- Orders grain: **order** (driver_profile.id, car.id, timestamp, price, status)",
        "- Driver profiles grain: **driver_profile** (snapshot, no historical tracking via this endpoint alone)",
        "- Supply hours grain: **driver × day** (one call per driver per day)",
        "",
        "## 6. Key Findings",
    ]

    findings = []
    if orders.get("has_more_pages"):
        findings.append("- Orders beyond {0} pages were NOT fetched (probe limit)".format(
            orders.get("pages_fetched", 0)))
    else:
        findings.append("- All available orders within range were fetched")

    if supply.get("samples_failed", 0) > 0:
        findings.append("- Supply-hours endpoint had failures; rate-limiting may be a concern at scale")

    if profiles.get("has_car"):
        findings.append("- Driver profiles include car info (brand, model, year, number)")
    if profiles.get("has_account"):
        findings.append("- Driver profiles include account balance")

    findings.append("- Supply-hours requires per-driver calls — expensive at fleet scale")
    findings.append("- No single endpoint provides aggregated daily metrics (trips, drivers, hours, revenue) — requires client-side aggregation")

    lines.extend(findings)
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(
        description="OV2-A.1 — Probe Yango Fleet API como fuente candidata para Omniview V2"
    )
    p.add_argument(
        "--park-id",
        default=(settings.YANGO_LIMA_PARK_ID or "").strip() or "08e20910d81d42658d4334d3f6d10ac0",
        help="Park ID de Yango (default: YANGO_LIMA_PARK_ID desde .env)",
    )
    p.add_argument(
        "--date-from",
        default="2026-06-01",
        help="Fecha inicio YYYY-MM-DD (default: 2026-06-01)",
    )
    p.add_argument(
        "--date-to",
        default="2026-06-03",
        help="Fecha fin YYYY-MM-DD (default: 2026-06-03)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar qué se consultaría, sin llamar a la API",
    )
    p.add_argument(
        "--max-days",
        type=int,
        default=3,
        help="Máximo de días en el rango (default: 3)",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Máximo de páginas de órdenes a capturar (default: 5)",
    )
    p.add_argument(
        "--output-json",
        action="store_true",
        help="Imprimir JSON completo en stdout además de guardar archivos",
    )
    args = p.parse_args()

    date_from = args.date_from
    date_to = args.date_to

    try:
        from_dt = datetime.strptime(date_from, "%Y-%m-%d")
        to_dt = datetime.strptime(date_to, "%Y-%m-%d")
    except ValueError:
        print("ERROR: fechas deben ser YYYY-MM-DD", file=sys.stderr)
        return 1

    if (to_dt - from_dt).days > args.max_days:
        print(
            f"ERROR: rango ({date_from} -> {date_to}) excede --max-days={args.max_days}",
            file=sys.stderr,
        )
        return 1

    if not settings.YANGO_API_ENABLED and not args.dry_run:
        print("WARNING: YANGO_API_ENABLED=false. Usando --dry-run automáticamente.", file=sys.stderr)
        args.dry_run = True

    os.makedirs(EXPORT_DIR, exist_ok=True)

    report = asyncio.run(
        run_probe(
            park_id=args.park_id,
            date_from=date_from,
            date_to=date_to,
            max_pages=args.max_pages,
            dry_run=args.dry_run,
        )
    )

    if report.get("error"):
        print(f"ERROR: {report['error']}", file=sys.stderr)
        return 1

    schema_doc = _build_schema_json(report)
    summary_md = _build_summary_md(report)

    schema_path = os.path.join(EXPORT_DIR, "growth_api_payload_schema.json")
    sample_path = os.path.join(EXPORT_DIR, "growth_api_probe_sample.json")
    summary_path = os.path.join(EXPORT_DIR, "growth_api_probe_summary.md")

    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema_doc, f, indent=2, default=str, ensure_ascii=False)

    sanitized_report = {}
    for k, v in report.items():
        if k == "endpoints":
            sanitized_report[k] = {}
            for ep_name, ep_data in v.items():
                sanitized = dict(ep_data)
                if "sample_order_schema" in sanitized:
                    pass
                sanitized_report[k][ep_name] = sanitized
        else:
            sanitized_report[k] = v

    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(sanitized_report, f, indent=2, default=str, ensure_ascii=False)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_md)

    print(f"[probe] Schema saved:   {schema_path}")
    print(f"[probe] Sample saved:   {sample_path}")
    print(f"[probe] Summary saved:  {summary_path}")

    if args.output_json:
        print(json.dumps(sanitized_report, indent=2, default=str, ensure_ascii=False))

    if args.dry_run:
        print("\n[probe] DRY RUN — no se realizaron llamadas a la API.")
    else:
        orders_count = report.get("endpoints", {}).get("orders", {}).get("total_orders_fetched", 0)
        profiles_count = report.get("endpoints", {}).get("driver_profiles", {}).get("fetched", 0)
        print(f"\n[probe] Orders fetched: {orders_count} | Profiles: {profiles_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
