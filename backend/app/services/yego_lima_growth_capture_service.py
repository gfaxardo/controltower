"""
YEGO Lima Fleet Growth Tower — Raw Orders Capture Service (Fase 1).

Responsabilidades:
- Recibir rango from/to en America/Lima
- Validar rango (from < to, max 24h, no rangos futuros grandes)
- Llamar API con paginacion cursor
- Limitar maximo de paginas por request
- Hacer upsert por pagina
- Acumular stats
- Devolver resumen sanitizado
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from app.settings import settings
from app.integrations.yango_api_client import list_completed_orders
from app.repositories.yego_lima_growth_repository import upsert_raw_orders

logger = logging.getLogger(__name__)

PET = timezone(timedelta(hours=-5))
_MAX_RANGE_HOURS = 24
_MAX_PAGES_DEFAULT = 20
_MAX_PAGES_HARD_LIMIT = 50


def _parse_dt(val: str) -> Optional[datetime]:
    if not val:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S-05:00",
        "%Y-%m-%dT%H:%M:%S.%f-05:00",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(val, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=PET)
            return dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=PET)
        return dt
    except ValueError:
        return None


async def capture_orders_range(
    from_str: str,
    to_str: str,
    max_pages: int = _MAX_PAGES_DEFAULT,
) -> Dict[str, Any]:
    """
    Captura ordenes completadas de Lima en un rango temporal.

    - Valida rango
    - Pagina con cursor hasta max_pages
    - Upsert por pagina
    - Devuelve resumen sanitizado
    """
    start_time = time.perf_counter()
    errors: list = []

    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "from": from_str,
            "to": to_str,
            "pages_fetched": 0,
            "orders_seen": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "min_ended_at": None,
            "max_ended_at": None,
            "duration_ms": 0,
            "stopped_reason": "disabled",
            "errors": ["YANGO_API_ENABLED is false"],
        }

    from_dt = _parse_dt(from_str)
    to_dt = _parse_dt(to_str)

    if not from_dt:
        return {
            "ok": False,
            "from": from_str,
            "to": to_str,
            "pages_fetched": 0,
            "orders_seen": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "min_ended_at": None,
            "max_ended_at": None,
            "duration_ms": round((time.perf_counter() - start_time) * 1000),
            "stopped_reason": "invalid_range",
            "errors": ["Invalid 'from' datetime"],
        }

    if not to_dt:
        return {
            "ok": False,
            "from": from_str,
            "to": to_str,
            "pages_fetched": 0,
            "orders_seen": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "min_ended_at": None,
            "max_ended_at": None,
            "duration_ms": round((time.perf_counter() - start_time) * 1000),
            "stopped_reason": "invalid_range",
            "errors": ["Invalid 'to' datetime"],
        }

    if from_dt >= to_dt:
        return {
            "ok": False,
            "from": from_str,
            "to": to_str,
            "pages_fetched": 0,
            "orders_seen": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "min_ended_at": None,
            "max_ended_at": None,
            "duration_ms": round((time.perf_counter() - start_time) * 1000),
            "stopped_reason": "invalid_range",
            "errors": ["'from' must be before 'to'"],
        }

    range_hours = (to_dt - from_dt).total_seconds() / 3600
    if range_hours > _MAX_RANGE_HOURS:
        return {
            "ok": False,
            "from": from_str,
            "to": to_str,
            "pages_fetched": 0,
            "orders_seen": 0,
            "inserted_count": 0,
            "updated_count": 0,
            "min_ended_at": None,
            "max_ended_at": None,
            "duration_ms": round((time.perf_counter() - start_time) * 1000),
            "stopped_reason": "range_too_large",
            "errors": [f"Range exceeds {_MAX_RANGE_HOURS}h limit (got {range_hours:.1f}h)"],
        }

    max_pages = max(1, min(max_pages, _MAX_PAGES_HARD_LIMIT))

    pages_fetched = 0
    total_seen = 0
    total_inserted = 0
    total_updated = 0
    global_min_ended: Optional[str] = None
    global_max_ended: Optional[str] = None
    cursor: Optional[str] = None
    stopped_reason = "no_cursor"

    try:
        while pages_fetched < max_pages:
            api_result = await list_completed_orders(
                from_dt=from_dt,
                to_dt=to_dt,
                cursor=cursor,
            )

            if not api_result.get("ok"):
                err_info = {
                    "page": pages_fetched + 1,
                    "error_type": api_result.get("error_type"),
                    "error_code": api_result.get("error_code"),
                    "error_message": api_result.get("error_message"),
                }
                errors.append(err_info)
                stopped_reason = "api_error"
                break

            orders = api_result.get("orders") or []
            pages_fetched += 1
            total_seen += len(orders)

            if orders:
                ins, upd, min_e, max_e = upsert_raw_orders(orders)
                total_inserted += ins
                total_updated += upd

                if min_e:
                    if global_min_ended is None or min_e < global_min_ended:
                        global_min_ended = min_e
                if max_e:
                    if global_max_ended is None or max_e > global_max_ended:
                        global_max_ended = max_e

            cursor = api_result.get("cursor")

            if not cursor:
                stopped_reason = "no_cursor"
                break

            if len(orders) == 0:
                stopped_reason = "empty_page"
                break

            logger.info(
                "Capture page %s/%s: seen=%s inserted=%s updated=%s cursor=%s",
                pages_fetched,
                max_pages,
                len(orders),
                ins,
                upd,
                bool(cursor),
            )

        if pages_fetched >= max_pages and cursor:
            stopped_reason = "max_pages_reached"

    except Exception as e:
        logger.exception("Capture orders range error: %s", e)
        errors.append({
            "page": pages_fetched,
            "error_type": "unexpected",
            "error_message": str(e)[:300],
        })
        stopped_reason = "exception"

    duration_ms = round((time.perf_counter() - start_time) * 1000)

    ok = len(errors) == 0 or total_seen > 0

    return {
        "ok": ok,
        "from": from_str,
        "to": to_str,
        "pages_fetched": pages_fetched,
        "orders_seen": total_seen,
        "inserted_count": total_inserted,
        "updated_count": total_updated,
        "min_ended_at": global_min_ended,
        "max_ended_at": global_max_ended,
        "duration_ms": duration_ms,
        "stopped_reason": stopped_reason,
        "errors": errors,
    }
