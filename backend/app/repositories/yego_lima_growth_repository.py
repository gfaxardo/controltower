"""
YEGO Lima Fleet Growth Tower — Raw Orders Repository (Fase 1).

Responsabilidades:
- Insertar/upsert ordenes en growth.yango_lima_orders_raw
- Mapear campos desde JSON Yango a columnas normalizadas
- Convertir fechas ISO a timestamptz
- Convertir price/mileage a numeric
- Tolerar campos faltantes
- Devolver estadisticas de operacion
"""

from __future__ import annotations

import logging
import json
import contextlib
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _cursor(conn, timeout_ms: int = 30000):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SET LOCAL statement_timeout = %s;", (timeout_ms,))
        yield cur
    finally:
        cur.close()


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_text(val) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, str):
        return val[:500]
    try:
        return str(val)[:500]
    except Exception:
        return None


def _to_utc_datetime(val) -> Optional[str]:
    if not val:
        return None
    try:
        if isinstance(val, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S+00:00",
                "%Y-%m-%dT%H:%M:%S.%f+00:00",
            ):
                try:
                    return datetime.strptime(val, fmt).isoformat()
                except ValueError:
                    continue
            try:
                dt = datetime.fromisoformat(val)
                return dt.isoformat()
            except ValueError:
                return None
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)
    except Exception:
        return None


_UPSERT_SQL = """
INSERT INTO growth.yango_lima_orders_raw (
    order_id, order_short_id, status,
    created_at, booked_at, ended_at,
    provider, category, payment_method,
    price, mileage,
    driver_profile_id, driver_profile_name,
    car_id, car_callsign, car_brand_model, car_license_number,
    driver_work_rule_id, driver_work_rule_name,
    raw_payload, source
) VALUES (
    %(order_id)s, %(order_short_id)s, %(status)s,
    %(created_at)s, %(booked_at)s, %(ended_at)s,
    %(provider)s, %(category)s, %(payment_method)s,
    %(price)s, %(mileage)s,
    %(driver_profile_id)s, %(driver_profile_name)s,
    %(car_id)s, %(car_callsign)s, %(car_brand_model)s, %(car_license_number)s,
    %(driver_work_rule_id)s, %(driver_work_rule_name)s,
    %(raw_payload)s, %(source)s
)
ON CONFLICT (order_id) DO UPDATE SET
    order_short_id = EXCLUDED.order_short_id,
    status = EXCLUDED.status,
    created_at = EXCLUDED.created_at,
    booked_at = EXCLUDED.booked_at,
    ended_at = EXCLUDED.ended_at,
    provider = EXCLUDED.provider,
    category = EXCLUDED.category,
    payment_method = EXCLUDED.payment_method,
    price = EXCLUDED.price,
    mileage = EXCLUDED.mileage,
    driver_profile_id = EXCLUDED.driver_profile_id,
    driver_profile_name = EXCLUDED.driver_profile_name,
    car_id = EXCLUDED.car_id,
    car_callsign = EXCLUDED.car_callsign,
    car_brand_model = EXCLUDED.car_brand_model,
    car_license_number = EXCLUDED.car_license_number,
    driver_work_rule_id = EXCLUDED.driver_work_rule_id,
    driver_work_rule_name = EXCLUDED.driver_work_rule_name,
    raw_payload = EXCLUDED.raw_payload,
    last_fetched_at = now(),
    fetch_count = growth.yango_lima_orders_raw.fetch_count + 1
"""


def _ensure_dict(val) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        return {"id": val}
    return {}


def _extract_order_params(order) -> Optional[Dict[str, Any]]:
    if not isinstance(order, dict):
        return None

    order_id = _safe_text(order.get("id"))
    if not order_id:
        return None

    dr = _ensure_dict(order.get("driver_profile"))
    car = _ensure_dict(order.get("car"))
    price_info = _ensure_dict(order.get("price"))
    rule = _ensure_dict(order.get("driver_work_rule"))

    return {
        "order_id": order_id,
        "order_short_id": _safe_int(order.get("short_id")),
        "status": _safe_text(order.get("status")) or "unknown",
        "created_at": _to_utc_datetime(order.get("created_at")),
        "booked_at": _to_utc_datetime(order.get("booked_at")),
        "ended_at": _to_utc_datetime(order.get("ended_at")),
        "provider": _safe_text(order.get("provider")),
        "category": _safe_text(order.get("category")),
        "payment_method": _safe_text(order.get("payment_method")),
        "price": _safe_float(price_info.get("final_cost")),
        "mileage": _safe_float(order.get("mileage")),
        "driver_profile_id": _safe_text(dr.get("id")),
        "driver_profile_name": (
            _safe_text(dr.get("first_name"))
            if dr.get("first_name")
            else _safe_text(dr.get("name"))
        ),
        "car_id": _safe_text(car.get("id")),
        "car_callsign": _safe_text(car.get("callsign")),
        "car_brand_model": _safe_text(
            f"{car.get('brand', '')} {car.get('model', '')}".strip()
            if (car.get("brand") or car.get("model"))
            else None
        ),
        "car_license_number": _safe_text(car.get("number")),
        "driver_work_rule_id": _safe_text(rule.get("id")),
        "driver_work_rule_name": _safe_text(rule.get("name")),
        "raw_payload": json.dumps(order, ensure_ascii=False),
        "source": "yango_orders_api_lima",
    }


def upsert_raw_orders(orders: list) -> Tuple[int, int, Optional[str], Optional[str]]:
    """
    Upsert raw orders into growth.yango_lima_orders_raw.

    Returns (inserted_count, updated_count, min_ended_at, max_ended_at).
    """
    if not orders:
        return 0, 0, None, None

    inserted = 0
    updated = 0
    min_ended = None
    max_ended = None

    with get_db() as conn:
        with _cursor(conn) as cur:
            for order in orders:
                if not isinstance(order, dict):
                    logger.warning("Skipping non-dict order: %s", type(order).__name__)
                    continue

                params = _extract_order_params(order)
                if not params:
                    continue

                ended_iso = params.get("ended_at")
                if ended_iso:
                    if min_ended is None or ended_iso < min_ended:
                        min_ended = ended_iso
                    if max_ended is None or ended_iso > max_ended:
                        max_ended = ended_iso

                cur.execute(_UPSERT_SQL, params)

                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

    return inserted, updated, min_ended, max_ended


def get_raw_orders_summary() -> Dict[str, Any]:
    """Devuelve resumen de la tabla raw."""
    with get_db() as conn:
        with _cursor(conn) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_orders,
                    MIN(ended_at) as min_ended_at,
                    MAX(ended_at) as max_ended_at,
                    COUNT(DISTINCT driver_profile_id) as unique_drivers,
                    COUNT(DISTINCT car_id) as unique_cars,
                    MAX(last_fetched_at) as last_fetched_at,
                    COUNT(*) FILTER (WHERE ended_at >= CURRENT_DATE AT TIME ZONE 'America/Lima') as orders_today,
                    COUNT(*) FILTER (WHERE last_fetched_at >= now() - INTERVAL '1 hour') as orders_last_hour
                FROM growth.yango_lima_orders_raw
            """)
            row = cur.fetchone()
            if not row:
                return {
                    "total_orders": 0,
                    "min_ended_at": None,
                    "max_ended_at": None,
                    "unique_drivers": 0,
                    "unique_cars": 0,
                    "last_fetched_at": None,
                    "orders_today": 0,
                    "orders_last_hour": 0,
                }
            return {
                "total_orders": row["total_orders"] or 0,
                "min_ended_at": row["min_ended_at"].isoformat() if row["min_ended_at"] else None,
                "max_ended_at": row["max_ended_at"].isoformat() if row["max_ended_at"] else None,
                "unique_drivers": row["unique_drivers"] or 0,
                "unique_cars": row["unique_cars"] or 0,
                "last_fetched_at": row["last_fetched_at"].isoformat() if row["last_fetched_at"] else None,
                "orders_today": row["orders_today"] or 0,
                "orders_last_hour": row["orders_last_hour"] or 0,
            }


def get_recent_raw_orders(limit: int = 20) -> list:
    """Devuelve muestra sanitizada de ordenes recientes."""
    with get_db() as conn:
        with _cursor(conn) as cur:
            cur.execute("""
                SELECT
                    order_id,
                    ended_at,
                    status,
                    category,
                    payment_method,
                    price,
                    driver_profile_id,
                    car_id,
                    last_fetched_at
                FROM growth.yango_lima_orders_raw
                ORDER BY ended_at DESC
                LIMIT %(limit)s
            """, {"limit": min(limit, 100)})
            rows = cur.fetchall()
            result = []
            for row in rows:
                item = {
                    "order_id": row["order_id"][:12] if row["order_id"] else None,
                    "ended_at": row["ended_at"].isoformat() if row["ended_at"] else None,
                    "status": row["status"],
                    "category": row["category"],
                    "payment_method": row["payment_method"],
                    "price": float(row["price"]) if row["price"] is not None else None,
                    "driver_profile_id": (
                        row["driver_profile_id"][:12]
                        if row["driver_profile_id"]
                        else None
                    ),
                    "car_id": row["car_id"][:12] if row["car_id"] else None,
                    "last_fetched_at": (
                        row["last_fetched_at"].isoformat()
                        if row["last_fetched_at"]
                        else None
                    ),
                }
                result.append(item)
            return result
