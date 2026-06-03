"""
YEGO Lima Fleet Growth Tower — Eligible Universe Service (Fase 2A.1).

Responsabilidades:
- Clasificar conductores en tiers (HOT/WARM/COLD/DORMANT)
- Usar driver_profiles + orders_raw + driver_360_daily histórico
- Persistir en growth.yango_lima_eligible_universe_daily
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.settings import settings
from app.integrations.yango_api_client import list_driver_profiles_raw

logger = logging.getLogger(__name__)


def _get_orders_stats() -> Tuple[
    Dict[str, int],
    Dict[str, int],
    Dict[str, int],
    Dict[str, Optional[str]],
]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    today_orders: Dict[str, int] = {}
    d7_orders: Dict[str, int] = {}
    d30_orders: Dict[str, int] = {}
    last_order: Dict[str, Optional[str]] = {}

    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        driver_profile_id,
                        COUNT(*) FILTER (WHERE ended_at >= CURRENT_DATE AT TIME ZONE 'America/Lima') AS today_cnt,
                        COUNT(*) FILTER (WHERE ended_at >= (CURRENT_DATE - INTERVAL '7 days') AT TIME ZONE 'America/Lima') AS d7_cnt,
                        COUNT(*) FILTER (WHERE ended_at >= (CURRENT_DATE - INTERVAL '30 days') AT TIME ZONE 'America/Lima') AS d30_cnt,
                        MAX(ended_at) AS last_order_ts
                    FROM growth.yango_lima_orders_raw
                    WHERE driver_profile_id IS NOT NULL
                      AND status = 'complete'
                    GROUP BY driver_profile_id
                """)
                for row in cur.fetchall():
                    did = str(row.get("driver_profile_id", ""))
                    if did:
                        today_orders[did] = int(row.get("today_cnt", 0) or 0)
                        d7_orders[did] = int(row.get("d7_cnt", 0) or 0)
                        d30_orders[did] = int(row.get("d30_cnt", 0) or 0)
                        lot = row.get("last_order_ts")
                        last_order[did] = lot.isoformat() if lot else None
    except Exception as e:
        logger.warning("Failed to query orders stats: %s", e)

    return today_orders, d7_orders, d30_orders, last_order


def _classify_driver(
    did: str,
    current_status: str,
    today_orders: Dict[str, int],
    d7_orders: Dict[str, int],
    d30_orders: Dict[str, int],
) -> Tuple[str, str]:
    orders_today = today_orders.get(did, 0)
    orders_7d = d7_orders.get(did, 0)
    orders_30d = d30_orders.get(did, 0)
    is_online = current_status and current_status != "offline"

    if orders_today > 0 or is_online:
        reason = "ORDERS_TODAY" if orders_today > 0 else "CURRENTLY_ONLINE"
        if orders_today > 0 and is_online:
            reason = "ORDERS_TODAY"
        return "HOT", reason

    if orders_7d > 0:
        return "WARM", "RECENT_ACTIVITY_7D"

    if orders_30d > 0:
        return "COLD", "RECENT_ACTIVITY_30D"

    return "DORMANT", "DORMANT"


async def build_eligible_universe(date_str: str) -> Dict[str, Any]:
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "date": date_str,
            "drivers_total": 0,
            "hot": 0,
            "warm": 0,
            "cold": 0,
            "dormant": 0,
            "duration_ms": 0,
            "error_message": "YANGO_API_ENABLED is false",
        }

    start_time = time.perf_counter()
    target_date = date.fromisoformat(date_str)

    today_orders, d7_orders, d30_orders, last_order = _get_orders_stats()

    total_drivers = 0
    hot = 0
    warm = 0
    cold = 0
    dormant = 0
    total_inserted = 0

    page_size = settings.YANGO_DRIVER_PROFILES_PAGE_SIZE
    offset = 0
    more_pages = True

    from app.repositories.yego_lima_driver_360_repository import _cursor
    from app.db.connection import get_db

    _UPSERT_SQL = """
    INSERT INTO growth.yango_lima_eligible_universe_daily (
        date, driver_profile_id,
        eligibility_reason, priority_tier,
        current_status, work_status,
        completed_orders_today, completed_orders_7d, completed_orders_30d,
        last_order_at
    ) VALUES (
        %(date)s, %(driver_profile_id)s,
        %(eligibility_reason)s, %(priority_tier)s,
        %(current_status)s, %(work_status)s,
        %(completed_orders_today)s, %(completed_orders_7d)s, %(completed_orders_30d)s,
        %(last_order_at)s
    )
    ON CONFLICT (date, driver_profile_id) DO UPDATE SET
        eligibility_reason = EXCLUDED.eligibility_reason,
        priority_tier = EXCLUDED.priority_tier,
        current_status = EXCLUDED.current_status,
        work_status = EXCLUDED.work_status,
        completed_orders_today = EXCLUDED.completed_orders_today,
        completed_orders_7d = EXCLUDED.completed_orders_7d,
        completed_orders_30d = EXCLUDED.completed_orders_30d,
        last_order_at = EXCLUDED.last_order_at
    """

    while more_pages:
        profiles_result = await list_driver_profiles_raw(
            limit=page_size,
            offset=offset,
        )

        if not profiles_result.get("ok"):
            logger.warning("Failed to fetch profiles page at offset %s", offset)
            break

        profiles = profiles_result.get("driver_profiles", [])
        if not profiles:
            more_pages = False
            break

        batch_rows: List[Dict[str, Any]] = []

        for profile in profiles:
            dp = profile.get("driver_profile") or {}
            did = dp.get("id")
            if not did:
                continue

            total_drivers += 1
            did_str = str(did)

            cs = profile.get("current_status") or {}
            current_status = cs.get("status", "offline")
            work_status = dp.get("work_status")

            tier, reason = _classify_driver(
                did_str, current_status,
                today_orders, d7_orders, d30_orders,
            )

            if tier == "HOT":
                hot += 1
            elif tier == "WARM":
                warm += 1
            elif tier == "COLD":
                cold += 1
            else:
                dormant += 1

            batch_rows.append({
                "date": target_date.isoformat(),
                "driver_profile_id": did_str,
                "eligibility_reason": reason,
                "priority_tier": tier,
                "current_status": current_status,
                "work_status": work_status,
                "completed_orders_today": today_orders.get(did_str, 0),
                "completed_orders_7d": d7_orders.get(did_str, 0),
                "completed_orders_30d": d30_orders.get(did_str, 0),
                "last_order_at": last_order.get(did_str),
            })

        if batch_rows:
            try:
                with get_db() as conn:
                    with conn.cursor() as cur:
                        for row in batch_rows:
                            cur.execute(_UPSERT_SQL, row)
                        conn.commit()
                    total_inserted += len(batch_rows)
            except Exception as e:
                logger.warning("Failed to upsert eligible universe batch: %s", e)

        logger.info(
            "Eligible universe page offset=%s seen=%s hot=%s warm=%s cold=%s dormant=%s",
            offset, len(batch_rows), hot, warm, cold, dormant,
        )

        offset += page_size
        if len(profiles) < page_size:
            more_pages = False

    duration_ms = round((time.perf_counter() - start_time) * 1000)

    return {
        "ok": True,
        "date": date_str,
        "drivers_total": total_drivers,
        "hot": hot,
        "warm": warm,
        "cold": cold,
        "dormant": dormant,
        "inserted": total_inserted,
        "duration_ms": duration_ms,
    }
