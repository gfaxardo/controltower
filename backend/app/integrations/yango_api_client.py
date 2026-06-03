"""
YEGO Lima Fleet Growth Tower — Yango Fleet API Client (Fase 0 — API Lab).

Responsabilidades:
- Leer settings de Yango
- Validar configuracion minima
- Construir headers seguros
- Ejecutar POST /v1/parks/orders/list
- Timeout configurable
- Retries simples para errores transitorios (httpx TransportError)
- Clasificar errores (400, 401, 403, 429, 500, timeout, network)
- Devolver respuesta sanitizada (nunca keys, nunca PII)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, List

import httpx
from datetime import datetime, timezone, timedelta

from app.settings import settings

logger = logging.getLogger(__name__)

PET = timezone(timedelta(hours=-5))

_SAFE_STATUS_KEYS = {"id", "status", "ended_at", "created_at", "started_at", "updated_at", "booked_at", "is_driver_notified"}
_SAFE_DRIVER_KEYS = {"id"}
_SAFE_CAR_KEYS = {"id", "brand", "model", "number"}
_SAFE_PRICE_KEYS = {"final_cost"}
_MAX_SAMPLE_KEYS = 15


def _sanitize_order_keys(order: dict) -> List[str]:
    keys = list(order.keys())
    return [k for k in keys if not k.startswith("_")][:_MAX_SAMPLE_KEYS]


def _check_key_presence(order: dict, *paths: str) -> bool:
    node = order
    for p in paths:
        if not isinstance(node, dict):
            return False
        node = node.get(p)
        if node is None:
            return False
    return True


def _is_transient_error(status_code: int) -> bool:
    return status_code in (429, 502, 503, 504)


def _build_headers() -> Dict[str, str]:
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()

    if not client_id or not api_key:
        raise ValueError("YANGO_CLIENT_ID y YANGO_API_KEY son requeridos")

    return {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }


def _build_order_list_body(park_id: str, from_dt: datetime, to_dt: datetime, limit: int, statuses: List[str]) -> Dict[str, Any]:
    return {
        "limit": limit,
        "query": {
            "park": {
                "id": park_id,
                "order": {
                    "ended_at": {
                        "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    },
                    "statuses": statuses,
                },
            }
        },
    }


async def _execute_with_retries(
    url: str,
    headers: Dict[str, str],
    body: Dict[str, Any],
    timeout_seconds: int,
    max_retries: int,
) -> tuple[int, float, Optional[Dict[str, Any]]]:
    last_error: Optional[str] = None
    last_status: Optional[int] = None

    for attempt in range(max_retries + 1):
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                resp = await client.post(url, headers=headers, json=body)
                elapsed_ms = round((time.perf_counter() - start) * 1000)

                if resp.status_code < 500:
                    try:
                        data = resp.json()
                    except Exception:
                        data = None
                    return resp.status_code, elapsed_ms, data

                if _is_transient_error(resp.status_code) and attempt < max_retries:
                    last_status = resp.status_code
                    last_error = f"server_error_{resp.status_code}"
                    logger.warning(
                        "Yango API retry %s/%s: status=%s",
                        attempt + 1,
                        max_retries,
                        resp.status_code,
                    )
                    await _sleep_backoff(attempt)
                    continue

                try:
                    data = resp.json()
                except Exception:
                    data = None
                return resp.status_code, elapsed_ms, data

        except httpx.TimeoutException:
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            if attempt < max_retries:
                last_status = None
                last_error = "timeout"
                logger.warning(
                    "Yango API timeout retry %s/%s",
                    attempt + 1,
                    max_retries,
                )
                await _sleep_backoff(attempt)
                continue
            return 0, elapsed_ms, None

        except httpx.ConnectError:
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            if attempt < max_retries:
                last_status = None
                last_error = "network_error"
                logger.warning(
                    "Yango API connect error retry %s/%s",
                    attempt + 1,
                    max_retries,
                )
                await _sleep_backoff(attempt)
                continue
            return 0, elapsed_ms, None

        except Exception:
            elapsed_ms = round((time.perf_counter() - start) * 1000)
            if attempt < max_retries:
                last_status = None
                last_error = "unexpected_error"
                logger.warning(
                    "Yango API unexpected error retry %s/%s",
                    attempt + 1,
                    max_retries,
                )
                await _sleep_backoff(attempt)
                continue
            return 0, elapsed_ms, None

    elapsed_ms = 0
    return last_status or 0, elapsed_ms, None


async def _sleep_backoff(attempt: int) -> None:
    import asyncio
    wait = min(0.5 * (2 ** attempt), 4.0)
    await asyncio.sleep(wait)


def _classify_error(status_code: int) -> tuple[str, Optional[str]]:
    if status_code == 0:
        return "network_error", None
    if status_code == 400:
        return "bad_request", "INVALID_REQUEST"
    if status_code == 401:
        return "unauthorized", "INVALID_CREDENTIALS"
    if status_code == 403:
        return "forbidden", "ACCESS_DENIED"
    if status_code == 429:
        return "rate_limited", "TOO_MANY_REQUESTS"
    if 500 <= status_code < 600:
        return "server_error", f"SERVER_ERROR_{status_code}"
    return "unexpected_error", f"HTTP_{status_code}"


def _safe_error_message(data: Optional[Dict[str, Any]]) -> Optional[str]:
    if not data or not isinstance(data, dict):
        return None
    msg = data.get("message") or data.get("error") or data.get("detail")
    if msg and isinstance(msg, str):
        clean = msg[:200]
        for secret in (settings.YANGO_API_KEY, settings.YANGO_CLIENT_ID):
            if secret and len(secret) > 4:
                clean = clean.replace(secret, "***")
        return clean
    return None


def _build_sanitized_response(
    ok: bool,
    enabled: bool,
    status_code: int,
    elapsed_ms: float,
    response_data: Optional[Dict[str, Any]],
    error_type: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "ok": ok,
        "enabled": enabled,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "records_count": 0,
        "has_cursor": False,
        "cursor_present": False,
        "sample_order_keys": [],
        "sample_order_status": None,
        "sample_order_has_driver_profile": False,
        "sample_order_has_car": False,
        "sample_order_has_price": False,
        "error_type": error_type,
        "error_code": error_code,
        "error_message": error_message,
    }

    if not ok or not response_data or not isinstance(response_data, dict):
        return result

    orders = response_data.get("orders")
    if isinstance(orders, list):
        result["records_count"] = len(orders)
        if orders:
            first = orders[0]
            result["sample_order_keys"] = _sanitize_order_keys(first)
            result["sample_order_status"] = first.get("status")
            result["sample_order_has_driver_profile"] = _check_key_presence(first, "driver_profile")
            result["sample_order_has_car"] = _check_key_presence(first, "car")
            result["sample_order_has_price"] = _check_key_presence(first, "price")

    cursor = response_data.get("cursor") or response_data.get("next_cursor")
    result["cursor_present"] = bool(cursor)
    result["has_cursor"] = bool(cursor)

    return result


async def test_orders_connection() -> Dict[str, Any]:
    """
    Prueba de conexion a Yango Fleet API orders/list para la flota Lima.

    Inputs:
    - Lima park id desde settings
    - Rango today 00:00:00 America/Lima hasta now America/Lima
    - limit=1, statuses=["complete"]

    Output sanitizado: nunca expone api_key, client_id completo, headers,
    payload completo, ni PII.
    """
    enabled = bool(settings.YANGO_API_ENABLED)

    if not enabled:
        return _build_sanitized_response(
            ok=False,
            enabled=False,
            status_code=0,
            elapsed_ms=0,
            response_data=None,
            error_type="disabled",
            error_code="MODULE_DISABLED",
            error_message="YANGO_API_ENABLED is false",
        )

    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    missing = []
    if not client_id:
        missing.append("YANGO_CLIENT_ID")
    if not api_key:
        missing.append("YANGO_API_KEY")
    if not park_id:
        missing.append("YANGO_LIMA_PARK_ID")

    if missing:
        return _build_sanitized_response(
            ok=False,
            enabled=True,
            status_code=0,
            elapsed_ms=0,
            response_data=None,
            error_type="missing_config",
            error_code="MISSING_CONFIG",
            error_message=f"Missing: {', '.join(missing)}",
        )

    now_lima = datetime.now(PET)
    today_start = now_lima.replace(hour=0, minute=0, second=0, microsecond=0)

    url = f"{settings.YANGO_API_BASE_URL.rstrip('/')}/v1/parks/orders/list"

    try:
        headers = _build_headers()
    except ValueError as e:
        return _build_sanitized_response(
            ok=False,
            enabled=True,
            status_code=0,
            elapsed_ms=0,
            response_data=None,
            error_type="missing_config",
            error_code="MISSING_CONFIG",
            error_message=str(e),
        )

    body = _build_order_list_body(
        park_id=park_id,
        from_dt=today_start,
        to_dt=now_lima,
        limit=1,
        statuses=["complete"],
    )

    if settings.YANGO_API_DEBUG:
        logger.debug(
            "Yango orders/list: url=%s park=%s limit=%s",
            url,
            park_id,
            1,
        )

    status_code, elapsed_ms, data = await _execute_with_retries(
        url=url,
        headers=headers,
        body=body,
        timeout_seconds=settings.YANGO_API_TIMEOUT_SECONDS,
        max_retries=settings.YANGO_API_MAX_RETRIES,
    )

    if status_code == 200:
        logger.info(
            "Yango orders/list OK: status=%s elapsed=%sms",
            status_code,
            elapsed_ms,
        )
        return _build_sanitized_response(
            ok=True,
            enabled=True,
            status_code=status_code,
            elapsed_ms=elapsed_ms,
            response_data=data,
        )

    error_type, error_code = _classify_error(status_code)
    error_message = _safe_error_message(data)

    logger.info(
        "Yango orders/list error: status=%s type=%s code=%s elapsed=%sms",
        status_code,
        error_type,
        error_code,
        elapsed_ms,
    )

    return _build_sanitized_response(
        ok=False,
        enabled=True,
        status_code=status_code,
        elapsed_ms=elapsed_ms,
        response_data=None,
        error_type=error_type,
        error_code=error_code,
        error_message=error_message or f"Yango API returned status {status_code}",
    )


def _parse_iso_to_datetime(val) -> Optional[datetime]:
    if not val or not isinstance(val, str):
        return None
    val = val.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%Y-%m-%dT%H:%M:%S.%f+00:00",
    ):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    try:
        clean = val
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        if clean.count(":") == 2 and len(clean.split(":")[-1]) == 2 and "+00:00" not in clean and "-" not in clean[10:]:
            clean = clean + "+00:00"
        return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(val)
    except ValueError:
        return None


async def list_completed_orders(
    from_dt: datetime,
    to_dt: datetime,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Lista ordenes completadas de la flota Lima desde Yango Fleet API.

    Inputs:
    - from_dt/to_dt: rango de ended_at en America/Lima
    - limit: tamanio de pagina (default desde settings, max 500)
    - cursor: cursor de paginacion (None para primera pagina)

    Output:
    {
        "ok": true/false,
        "status_code": 200,
        "elapsed_ms": 123,
        "orders": [...],
        "cursor": "abc123" or None,
        "raw_count": 500,
        "error_type": null,
        "error_code": null,
        "error_message": null
    }

    Nunca devuelve secretos, headers completos, ni PII.
    """
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "orders": [],
            "cursor": None,
            "raw_count": 0,
            "error_type": "disabled",
            "error_code": "MODULE_DISABLED",
            "error_message": "YANGO_API_ENABLED is false",
        }

    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    missing = []
    if not client_id:
        missing.append("YANGO_CLIENT_ID")
    if not api_key:
        missing.append("YANGO_API_KEY")
    if not park_id:
        missing.append("YANGO_LIMA_PARK_ID")

    if missing:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "orders": [],
            "cursor": None,
            "raw_count": 0,
            "error_type": "missing_config",
            "error_code": "MISSING_CONFIG",
            "error_message": f"Missing: {', '.join(missing)}",
        }

    page_size = limit if limit is not None else settings.YANGO_ORDERS_PAGE_SIZE
    page_size = min(page_size, 1000)

    url = f"{settings.YANGO_API_BASE_URL.rstrip('/')}/v1/parks/orders/list"

    try:
        headers = _build_headers()
    except ValueError as e:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "orders": [],
            "cursor": None,
            "raw_count": 0,
            "error_type": "missing_config",
            "error_code": "MISSING_CONFIG",
            "error_message": str(e),
        }

    body = _build_order_list_body(
        park_id=park_id,
        from_dt=from_dt,
        to_dt=to_dt,
        limit=page_size,
        statuses=["complete"],
    )

    if cursor:
        body["cursor"] = cursor

    if settings.YANGO_API_DEBUG:
        logger.debug(
            "Yango orders/list page: url=%s park=%s limit=%s has_cursor=%s",
            url,
            park_id,
            page_size,
            bool(cursor),
        )

    status_code, elapsed_ms, data = await _execute_with_retries(
        url=url,
        headers=headers,
        body=body,
        timeout_seconds=settings.YANGO_API_TIMEOUT_SECONDS,
        max_retries=settings.YANGO_API_MAX_RETRIES,
    )

    if status_code == 200 and data and isinstance(data, dict):
        orders = data.get("orders") or []
        next_cursor = data.get("cursor") or data.get("next_cursor")

        logger.info(
            "Yango orders/list page OK: status=%s elapsed=%sms count=%s has_cursor=%s",
            status_code,
            elapsed_ms,
            len(orders),
            bool(next_cursor),
        )

        return {
            "ok": True,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "orders": orders,
            "cursor": next_cursor,
            "raw_count": len(orders),
            "error_type": None,
            "error_code": None,
            "error_message": None,
        }

    error_type, error_code = _classify_error(status_code)
    error_message = _safe_error_message(data)

    logger.info(
        "Yango orders/list error: status=%s type=%s code=%s elapsed=%sms",
        status_code,
        error_type,
        error_code,
        elapsed_ms,
    )

    return {
        "ok": False,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "orders": [],
        "cursor": None,
        "raw_count": 0,
        "error_type": error_type,
        "error_code": error_code,
        "error_message": error_message or f"Yango API returned status {status_code}",
    }


def _mask_id(val: str) -> str:
    if not val or not isinstance(val, str):
        return "***"
    return val[:8] + "..." if len(val) > 8 else val


async def list_driver_profiles(
    limit: Optional[int] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Lista driver profiles de la flota Lima desde Yango Fleet API.

    POST /v1/parks/driver-profiles/list

    Devuelve resumen sanitizado: nunca PII, nombres completos, phones, ni licencias.
    """
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "disabled",
            "error_code": "MODULE_DISABLED",
            "error_message": "YANGO_API_ENABLED is false",
        }

    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    missing = []
    if not client_id:
        missing.append("YANGO_CLIENT_ID")
    if not api_key:
        missing.append("YANGO_API_KEY")
    if not park_id:
        missing.append("YANGO_LIMA_PARK_ID")
    if missing:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "missing_config",
            "error_code": "MISSING_CONFIG",
            "error_message": f"Missing: {', '.join(missing)}",
        }

    page_size = limit if limit is not None else settings.YANGO_DRIVER_PROFILES_PAGE_SIZE
    page_size = min(page_size, 1000)

    url = f"{settings.YANGO_API_BASE_URL.rstrip('/')}/v1/parks/driver-profiles/list"

    try:
        headers = _build_headers()
    except ValueError as e:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "missing_config",
            "error_code": "MISSING_CONFIG",
            "error_message": str(e),
        }

    body = {
        "query": {
            "park": {
                "id": park_id,
                "driver_profile": {
                    "work_status": ["working", "not_working"]
                },
            },
        },
        "fields": {
            "driver_profile": [
                "id",
                "park_id",
                "created_date",
                "first_name",
                "last_name",
                "work_rule_id",
                "work_status",
                "employment_type",
                "has_contract_issue",
            ],
            "current_status": [
                "status",
                "status_updated_at",
            ],
            "car": [
                "id",
                "status",
                "category",
                "callsign",
                "brand",
                "model",
                "year",
                "number",
            ],
            "account": [
                "id",
                "balance",
                "balance_limit",
                "currency",
                "last_transaction_date",
            ],
            "park": [
                "id",
                "city",
                "name",
            ],
        },
        "limit": page_size,
        "offset": offset,
    }

    if settings.YANGO_API_DEBUG:
        logger.debug(
            "Yango driver-profiles/list: url=%s park=%s limit=%s offset=%s",
            url,
            park_id,
            page_size,
            offset,
        )

    start = time.perf_counter()
    status_code, elapsed_ms, data = await _execute_with_retries(
        url=url,
        headers=headers,
        body=body,
        timeout_seconds=settings.YANGO_API_TIMEOUT_SECONDS,
        max_retries=settings.YANGO_API_MAX_RETRIES,
    )

    if status_code == 200 and data and isinstance(data, dict):
        profiles = data.get("driver_profiles") or []
        total = data.get("total", len(profiles))
        rlimit = data.get("limit", page_size)
        roffset = data.get("offset", offset)

        work_status_counts: Dict[str, int] = {}
        current_status_counts: Dict[str, int] = {}
        has_current_status = False
        has_car = False
        has_account = False
        sample_profile_keys: List[str] = []

        for p in profiles:
            if not isinstance(p, dict):
                continue
            dp = p.get("driver_profile") or {}
            ws = dp.get("work_status", "unknown")
            work_status_counts[ws] = work_status_counts.get(ws, 0) + 1

            cs = p.get("current_status") or {}
            if cs:
                has_current_status = True
                cst = cs.get("status", "unknown")
                current_status_counts[cst] = current_status_counts.get(cst, 0) + 1

            if p.get("car"):
                has_car = True
            if p.get("account"):
                has_account = True

            if not sample_profile_keys and dp:
                sample_profile_keys = sorted(
                    [k for k in dp.keys() if not k.startswith("_") and k not in ("first_name", "last_name")]
                )[:15]

        logger.info(
            "Yango driver-profiles/list OK: total=%s profiles=%s ws=%s cs=%s",
            total,
            len(profiles),
            work_status_counts,
            current_status_counts,
        )

        return {
            "ok": True,
            "status_code": status_code,
            "elapsed_ms": elapsed_ms,
            "total": total,
            "limit": rlimit,
            "offset": roffset,
            "profiles_count": len(profiles),
            "sample_profile_keys": sample_profile_keys,
            "has_current_status": has_current_status,
            "has_car": has_car,
            "has_account": has_account,
            "work_status_counts": work_status_counts,
            "current_status_counts": current_status_counts,
        }

    error_type, error_code = _classify_error(status_code)
    error_message = _safe_error_message(data)

    logger.info(
        "Yango driver-profiles/list error: status=%s type=%s code=%s",
        status_code,
        error_type,
        error_code,
    )

    return {
        "ok": False,
        "status_code": status_code,
        "elapsed_ms": elapsed_ms,
        "error_type": error_type,
        "error_code": error_code,
        "error_message": error_message or f"Yango API returned status {status_code}",
    }


async def list_driver_profiles_raw(
    limit: Optional[int] = None,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Igual que list_driver_profiles pero retorna los profiles completos (sin sanitizar)
    para uso interno del discovery. NO exponer en endpoint público.
    """
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {"ok": False, "driver_profiles": []}

    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    if not park_id:
        return {"ok": False, "driver_profiles": []}

    page_size = limit if limit is not None else settings.YANGO_DRIVER_PROFILES_PAGE_SIZE
    page_size = min(page_size, 1000)

    url = f"{settings.YANGO_API_BASE_URL.rstrip('/')}/v1/parks/driver-profiles/list"

    try:
        headers = _build_headers()
    except ValueError:
        return {"ok": False, "driver_profiles": []}

    body = {
        "query": {
            "park": {
                "id": park_id,
                "driver_profile": {
                    "work_status": ["working", "not_working"]
                },
            },
        },
        "fields": {
            "driver_profile": [
                "id",
                "park_id",
                "created_date",
                "first_name",
                "last_name",
                "work_rule_id",
                "work_status",
                "employment_type",
                "has_contract_issue",
            ],
            "current_status": [
                "status",
                "status_updated_at",
            ],
            "car": [
                "id",
                "status",
                "category",
                "callsign",
                "brand",
                "model",
                "year",
                "number",
            ],
            "account": [
                "id",
                "balance",
                "balance_limit",
                "currency",
                "last_transaction_date",
            ],
            "park": [
                "id",
                "city",
                "name",
            ],
        },
        "limit": page_size,
        "offset": offset,
    }

    status_code, elapsed_ms, data = await _execute_with_retries(
        url=url,
        headers=headers,
        body=body,
        timeout_seconds=settings.YANGO_API_TIMEOUT_SECONDS,
        max_retries=settings.YANGO_API_MAX_RETRIES,
    )

    if status_code == 200 and data and isinstance(data, dict):
        return {
            "ok": True,
            "driver_profiles": data.get("driver_profiles") or [],
        }

    return {"ok": False, "driver_profiles": []}


async def get_supply_hours(
    contractor_profile_id: str,
    period_from: str,
    period_to: str,
) -> Dict[str, Any]:
    """
    Consulta supply hours para un contractor profile id.

    GET /v2/parks/contractors/supply-hours

    Devuelve resumen sanitizado.
    """
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "disabled",
            "error_code": "MODULE_DISABLED",
        }

    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    if not client_id or not api_key or not park_id:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "missing_config",
            "error_code": "MISSING_CONFIG",
        }

    url = f"{settings.YANGO_API_BASE_URL.rstrip('/')}/v2/parks/contractors/supply-hours"

    headers = {
        "X-Client-ID": client_id,
        "X-API-Key": api_key,
        "X-Park-ID": park_id,
        "Accept-Language": "en",
    }

    params = {
        "contractor_profile_id": contractor_profile_id,
        "period_from": period_from,
        "period_to": period_to,
    }

    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=float(settings.YANGO_API_TIMEOUT_SECONDS)) as client:
            resp = await client.get(url, headers=headers, params=params)
            elapsed_ms = round((time.perf_counter() - start) * 1000)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None

                supply_seconds = 0
                if isinstance(data, dict):
                    supply_seconds = data.get("supply_duration_seconds", 0) or 0
                    if isinstance(supply_seconds, float):
                        supply_seconds = int(supply_seconds)

                supply_hours_val = round(supply_seconds / 3600.0, 2) if supply_seconds else 0

                return {
                    "ok": True,
                    "status_code": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "contractor_profile_id_masked": _mask_id(contractor_profile_id),
                    "supply_duration_seconds": supply_seconds,
                    "supply_hours": supply_hours_val,
                    "total_seconds": supply_seconds,
                    "status_code": resp.status_code,
                    "error_type": None,
                }

            error_type, error_code = _classify_error(resp.status_code)
            try:
                error_data = resp.json()
            except Exception:
                error_data = None
            error_message = _safe_error_message(error_data)

            return {
                "ok": False,
                "status_code": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "contractor_profile_id_masked": _mask_id(contractor_profile_id),
                "supply_duration_seconds": 0,
                "supply_hours": 0,
                "total_seconds": 0,
                "error_type": error_type,
            }

    except httpx.TimeoutException:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "contractor_profile_id_masked": _mask_id(contractor_profile_id),
            "supply_duration_seconds": 0,
            "supply_hours": 0,
            "total_seconds": 0,
            "error_type": "timeout",
        }
    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "contractor_profile_id_masked": _mask_id(contractor_profile_id),
            "supply_duration_seconds": 0,
            "supply_hours": 0,
            "total_seconds": 0,
            "error_type": "network_error",
        }


async def get_blocked_balance(
    contractor_id: str,
) -> Dict[str, Any]:
    """
    Consulta blocked balance para un contractor profile id.

    GET /v1/parks/contractors/blocked-balance

    Devuelve resumen sanitizado: nunca expone datos completos de balance.
    """
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "disabled",
            "error_code": "MODULE_DISABLED",
        }

    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    if not api_key or not park_id:
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": 0,
            "error_type": "missing_config",
            "error_code": "MISSING_CONFIG",
        }

    url = f"{settings.YANGO_API_BASE_URL.rstrip('/')}/v1/parks/contractors/blocked-balance"

    headers = {
        "X-API-Key": api_key,
        "X-Park-ID": park_id,
        "Accept-Language": "en",
    }

    params = {
        "contractor_id": contractor_id,
    }

    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=float(settings.YANGO_API_TIMEOUT_SECONDS)) as client:
            resp = await client.get(url, headers=headers, params=params)
            elapsed_ms = round((time.perf_counter() - start) * 1000)

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = None

                has_balance = False
                has_blocked = False
                balance_val = None
                blocked_val = None
                detail_keys: List[str] = []

                if isinstance(data, dict):
                    if data.get("balance") is not None:
                        has_balance = True
                        balance_val = str(data.get("balance"))[:20]
                    if data.get("blocked_balance") is not None:
                        has_blocked = True
                        blocked_val = str(data.get("blocked_balance"))[:20]
                    detail_keys = sorted([k for k in data.keys() if not k.startswith("_")])[:15]

                return {
                    "ok": True,
                    "status_code": resp.status_code,
                    "elapsed_ms": elapsed_ms,
                    "contractor_id_masked": _mask_id(contractor_id),
                    "has_balance": has_balance,
                    "has_blocked_balance": has_blocked,
                    "balance": balance_val,
                    "blocked_balance": blocked_val,
                    "detail_keys": detail_keys,
                    "error_type": None,
                }

            error_type, error_code = _classify_error(resp.status_code)
            try:
                error_data = resp.json()
            except Exception:
                error_data = None
            error_message = _safe_error_message(error_data)

            return {
                "ok": False,
                "status_code": resp.status_code,
                "elapsed_ms": elapsed_ms,
                "contractor_id_masked": _mask_id(contractor_id),
                "has_balance": False,
                "has_blocked_balance": False,
                "balance": None,
                "blocked_balance": None,
                "detail_keys": [],
                "error_type": error_type,
            }

    except httpx.TimeoutException:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "contractor_id_masked": _mask_id(contractor_id),
            "has_balance": False,
            "has_blocked_balance": False,
            "balance": None,
            "blocked_balance": None,
            "detail_keys": [],
            "error_type": "timeout",
        }
    except Exception:
        elapsed_ms = round((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "contractor_id_masked": _mask_id(contractor_id),
            "has_balance": False,
            "has_blocked_balance": False,
            "balance": None,
            "blocked_balance": None,
            "detail_keys": [],
            "error_type": "network_error",
        }
