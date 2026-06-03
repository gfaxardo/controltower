"""
YEGO Lima Fleet Growth Tower — Driver 360 Daily Service (Fase 2A.2).

Responsabilidades:
- Construir Driver 360 para una fecha usando eligible universe ya poblado
- NO consultar driver-profiles/list si eligible_universe ya existe
- Procesar supply solo para HOT (y WARM si include_warm=true)
- COLD/DORMANT: completed_orders desde raw, supply_seconds = 0
- Calcular driver_state, productivity_band, active_flag
- Manejar rate_limited con backoff, no bloquear toda la corrida
- Persistir en growth.yango_lima_driver_360_daily con campos ampliados
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

from app.settings import settings
from app.integrations.yango_api_client import get_supply_hours
from app.repositories.yego_lima_driver_360_repository import upsert_driver_360_daily

logger = logging.getLogger(__name__)

PET = timezone(timedelta(hours=-5))


def _classify_driver_state(supply_seconds: int, completed_orders: int) -> str:
    has_supply = supply_seconds > 0
    has_orders = completed_orders > 0

    if has_supply and has_orders:
        return "PRODUCTIVE"
    if has_supply and not has_orders:
        return "ONLINE_NO_ORDERS"
    if not has_supply and not has_orders:
        return "OFFLINE"
    if not has_supply and has_orders:
        return "ORDERS_WITHOUT_SUPPLY_ANOMALY"
    return "OFFLINE"


def _classify_productivity_band(
    driver_state: str,
    supply_hours_val: float,
    completed_orders: int,
) -> str:
    if driver_state != "PRODUCTIVE":
        return "NOT_APPLICABLE"

    if supply_hours_val <= 0 or completed_orders <= 0:
        return "NOT_APPLICABLE"

    tph = completed_orders / supply_hours_val
    low = settings.YANGO_LOW_PRODUCTIVITY_TPH_THRESHOLD
    high = settings.YANGO_HIGH_PRODUCTIVITY_TPH_THRESHOLD

    if tph < low:
        return "LOW_PRODUCTIVITY"
    if tph >= high:
        return "HIGH_PRODUCTIVITY"
    return "NORMAL_PRODUCTIVITY"


def _parse_date_to_lima_range(date_str: str) -> Tuple[date, str, str]:
    target_date = date.fromisoformat(date_str)
    lima_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=PET)
    lima_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=PET)
    return (
        target_date,
        lima_start.strftime("%Y-%m-%dT%H:%M:%S%z"),
        lima_end.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )


def _get_orders_for_date(target_date: date) -> Dict[str, Dict[str, Any]]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    result: Dict[str, Dict[str, Any]] = {}
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        driver_profile_id,
                        COUNT(*) AS cnt,
                        COALESCE(SUM(price), 0) AS total_revenue,
                        MAX(ended_at) AS last_order_ts
                    FROM growth.yango_lima_orders_raw
                    WHERE ended_at >= %(start)s::timestamptz
                      AND ended_at < %(end)s::timestamptz
                      AND driver_profile_id IS NOT NULL
                      AND status = 'complete'
                    GROUP BY driver_profile_id
                """, {
                    "start": target_date.isoformat(),
                    "end": (target_date + timedelta(days=1)).isoformat(),
                })
                for row in cur.fetchall():
                    did = str(row.get("driver_profile_id", ""))
                    if did:
                        result[did] = {
                            "completed_orders": int(row.get("cnt", 0)),
                            "gross_revenue": float(row.get("total_revenue", 0) or 0),
                            "last_order_ts": row.get("last_order_ts"),
                        }
    except Exception as e:
        logger.warning("Failed to query orders for date %s: %s", target_date, e)
    return result


def _get_eligible_drivers(target_date: date, include_warm: bool, max_drivers: int) -> List[Dict[str, Any]]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    tiers = "('HOT', 'WARM')" if include_warm else "('HOT')"
    drivers: List[Dict[str, Any]] = []
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT
                        driver_profile_id, priority_tier, eligibility_reason,
                        current_status, work_status,
                        completed_orders_today, completed_orders_7d, completed_orders_30d
                    FROM growth.yango_lima_eligible_universe_daily
                    WHERE date = %(date)s
                      AND priority_tier IN {tiers}
                    ORDER BY
                        CASE priority_tier WHEN 'HOT' THEN 0 WHEN 'WARM' THEN 1 END,
                        driver_profile_id
                    LIMIT %(limit)s
                """, {
                    "date": target_date.isoformat(),
                    "limit": max_drivers if max_drivers > 0 else 999999,
                })
                for row in cur.fetchall():
                    drivers.append({
                        "driver_profile_id": str(row["driver_profile_id"]),
                        "priority_tier": row["priority_tier"],
                        "eligibility_reason": row["eligibility_reason"],
                        "current_status": row["current_status"],
                        "work_status": row["work_status"],
                        "completed_orders_today": int(row["completed_orders_today"] or 0),
                        "completed_orders_7d": int(row["completed_orders_7d"] or 0),
                        "completed_orders_30d": int(row["completed_orders_30d"] or 0),
                    })
    except Exception as e:
        logger.warning("Failed to query eligible drivers: %s", e)
    return drivers


async def _fetch_supply_with_backoff(
    did: str,
    period_from: str,
    period_to: str,
) -> Tuple[int, str, Optional[str]]:
    retries = 0
    max_retries = settings.YANGO_SUPPLY_MAX_RETRIES
    backoff_ms = settings.YANGO_SUPPLY_RATE_LIMIT_BACKOFF_MS

    while True:
        result = await get_supply_hours(
            contractor_profile_id=did,
            period_from=period_from,
            period_to=period_to,
        )

        if result.get("ok"):
            supply_seconds = result.get("supply_duration_seconds", 0) or 0
            return supply_seconds, "success", None

        error_type = result.get("error_type", "unknown")

        if error_type == "rate_limited":
            if retries < max_retries:
                retries += 1
                logger.debug("Driver %s rate limited, retry %s/%s after %sms", did[:8], retries, max_retries, backoff_ms)
                await asyncio.sleep(backoff_ms / 1000.0)
                continue
            return 0, "rate_limited", "rate_limited"

        return 0, "error", error_type


async def stabilize_driver_360_day(
    date_str: str,
    include_warm: bool = False,
    max_drivers: int = 250,
) -> Dict[str, Any]:
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "date": date_str,
            "error_type": "disabled",
            "error_message": "YANGO_API_ENABLED is false",
        }

    start_time = time.perf_counter()
    target_date, period_from, period_to = _parse_date_to_lima_range(date_str)
    delay_ms = settings.YANGO_SUPPLY_REQUEST_DELAY_MS

    eligible_drivers = _get_eligible_drivers(target_date, include_warm, max_drivers)
    if not eligible_drivers:
        return {
            "ok": False,
            "date": date_str,
            "error_type": "eligible_universe_missing",
            "error_message": f"No eligible drivers found for {date_str}. Run build-eligible-universe first.",
            "drivers_processed": 0,
        }

    orders_by_driver = _get_orders_for_date(target_date)

    drivers_processed = 0
    productive = 0
    online_no_orders = 0
    offline = 0
    orders_without_supply_anomaly = 0
    low_productivity = 0
    normal_productivity = 0
    high_productivity = 0
    supply_success = 0
    supply_rate_limited = 0
    supply_errors = 0
    total_inserted = 0
    total_updated = 0
    error_log: List[Dict[str, Any]] = []

    for driver in eligible_drivers:
        did = driver["driver_profile_id"]
        drivers_processed += 1
        tier = driver["priority_tier"]
        reason = driver["eligibility_reason"]
        current_status = driver["current_status"]
        work_status_val = driver["work_status"]

        orders_info = orders_by_driver.get(did, {"completed_orders": 0, "gross_revenue": 0.0, "last_order_ts": None})
        completed_orders = orders_info["completed_orders"]
        gross_revenue = orders_info["gross_revenue"]
        last_order_ts = orders_info.get("last_order_ts")

        orders_last_seen_at = None
        if last_order_ts and hasattr(last_order_ts, 'isoformat'):
            orders_last_seen_at = last_order_ts.isoformat()

        supply_seconds = 0
        supply_hours_val = 0.0
        fetch_status = "not_requested"
        fetch_error = None
        supply_last_attempt = None

        if tier in ("HOT", "WARM"):
            supply_seconds, fetch_status, fetch_error = await _fetch_supply_with_backoff(
                did, period_from, period_to,
            )
            supply_last_attempt = datetime.now(timezone.utc).isoformat()

            if fetch_status == "success":
                supply_success += 1
            elif fetch_status == "rate_limited":
                supply_rate_limited += 1
                error_log.append({
                    "driver_profile_id_masked": did[:8] + "...",
                    "error": "rate_limited",
                })
            else:
                supply_errors += 1
                error_log.append({
                    "driver_profile_id_masked": did[:8] + "...",
                    "error": fetch_error or "unknown",
                })

        supply_hours_val = round(supply_seconds / 3600.0, 4) if supply_seconds else 0.0

        driver_state = _classify_driver_state(supply_seconds, completed_orders)
        active_flag = supply_seconds > 0 or completed_orders > 0

        trips_per_supply_hour = None
        if supply_hours_val > 0 and completed_orders > 0:
            trips_per_supply_hour = round(completed_orders / supply_hours_val, 4)

        productivity_band = _classify_productivity_band(driver_state, supply_hours_val, completed_orders)

        if driver_state == "PRODUCTIVE":
            productive += 1
        elif driver_state == "ONLINE_NO_ORDERS":
            online_no_orders += 1
        elif driver_state == "OFFLINE":
            offline += 1
        elif driver_state == "ORDERS_WITHOUT_SUPPLY_ANOMALY":
            orders_without_supply_anomaly += 1

        if productivity_band == "LOW_PRODUCTIVITY":
            low_productivity += 1
        elif productivity_band == "NORMAL_PRODUCTIVITY":
            normal_productivity += 1
        elif productivity_band == "HIGH_PRODUCTIVITY":
            high_productivity += 1

        upsert_driver_360_daily([{
            "driver_profile_id": did,
            "date": target_date.isoformat(),
            "work_status": work_status_val,
            "current_status": current_status,
            "work_rule_id": None,
            "employment_type": None,
            "car_id": None,
            "car_category": None,
            "car_status": None,
            "car_brand": None,
            "car_model": None,
            "car_number": None,
            "completed_orders": completed_orders,
            "gross_revenue": gross_revenue,
            "supply_seconds": supply_seconds,
            "supply_hours": supply_hours_val,
            "trips_per_supply_hour": trips_per_supply_hour,
            "active_flag": active_flag,
            "driver_state": driver_state,
            "source": "yango_driver_360_daily_v2",
            "productivity_band": productivity_band,
            "eligibility_tier": tier,
            "eligibility_reason": reason,
            "supply_fetch_status": fetch_status,
            "supply_fetch_error_type": fetch_error,
            "supply_last_attempt_at": supply_last_attempt,
            "orders_last_seen_at": orders_last_seen_at,
        }])

        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

        if drivers_processed % 50 == 0:
            logger.info(
                "Driver 360 stabilize: %s/%s prod=%s onln=%s off=%s anom=%s "
                "sh_ok=%s sh_429=%s sh_err=%s",
                drivers_processed, len(eligible_drivers),
                productive, online_no_orders, offline, orders_without_supply_anomaly,
                supply_success, supply_rate_limited, supply_errors,
            )

    duration_ms = round((time.perf_counter() - start_time) * 1000)

    return {
        "ok": True,
        "date": date_str,
        "drivers_processed": drivers_processed,
        "productive": productive,
        "online_no_orders": online_no_orders,
        "offline": offline,
        "orders_without_supply_anomaly": orders_without_supply_anomaly,
        "low_productivity": low_productivity,
        "normal_productivity": normal_productivity,
        "high_productivity": high_productivity,
        "supply_success": supply_success,
        "supply_rate_limited": supply_rate_limited,
        "supply_errors": supply_errors,
        "duration_ms": duration_ms,
        "error_log": error_log[:20],
    }
