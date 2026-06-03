"""
YEGO Lima Fleet Growth Tower — Supply Batch Runner (Fase 2A.1).

Responsabilidades:
- Ejecutar supply-hours para universo elegible (HOT + WARM)
- Respetar rate limiting con delay configurable
- Manejar 429 con backoff adaptativo
- No persistir resultados finales (solo validar arquitectura)
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date
from typing import Any, Dict, List, Optional

from app.settings import settings
from app.integrations.yango_api_client import get_supply_hours

logger = logging.getLogger(__name__)


def _get_eligible_drivers(
    target_date: date,
    tier: str,
    max_drivers: int,
) -> List[Dict[str, Any]]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    drivers: List[Dict[str, Any]] = []
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT driver_profile_id, priority_tier, eligibility_reason, current_status
                    FROM growth.yango_lima_eligible_universe_daily
                    WHERE date = %(date)s
                      AND priority_tier = %(tier)s
                    ORDER BY driver_profile_id
                    LIMIT %(limit)s
                """, {
                    "date": target_date.isoformat(),
                    "tier": tier.upper(),
                    "limit": max_drivers,
                })
                for row in cur.fetchall():
                    drivers.append({
                        "driver_profile_id": row["driver_profile_id"],
                        "priority_tier": row["priority_tier"],
                        "eligibility_reason": row["eligibility_reason"],
                        "current_status": row["current_status"],
                    })
    except Exception as e:
        logger.warning("Failed to query eligible drivers: %s", e)

    return drivers


def _get_period_for_date(target_date: date) -> Tuple[str, str]:
    from datetime import datetime, timezone, timedelta

    PET = timezone(timedelta(hours=-5))
    lima_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=PET)
    lima_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=PET)
    return (
        lima_start.strftime("%Y-%m-%dT%H:%M:%S%z"),
        lima_end.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )


async def run_supply_batch(
    date_str: str,
    tier: str = "HOT",
    max_drivers: int = 0,
) -> Dict[str, Any]:
    enabled = bool(settings.YANGO_API_ENABLED)
    if not enabled:
        return {
            "ok": False,
            "date": date_str,
            "drivers_attempted": 0,
            "success": 0,
            "rate_limited": 0,
            "other_errors": 0,
            "duration_ms": 0,
            "error_message": "YANGO_API_ENABLED is false",
        }

    start_time = time.perf_counter()
    target_date = date.fromisoformat(date_str)
    tier_upper = tier.upper()
    limit = max_drivers if max_drivers > 0 else settings.YANGO_SUPPLY_MAX_DRIVERS_PER_RUN
    batch_size = settings.YANGO_SUPPLY_BATCH_SIZE
    base_delay_ms = settings.YANGO_SUPPLY_REQUEST_DELAY_MS

    period_from, period_to = _get_period_for_date(target_date)

    drivers = _get_eligible_drivers(target_date, tier_upper, limit)
    if not drivers:
        return {
            "ok": False,
            "date": date_str,
            "tier": tier_upper,
            "drivers_attempted": 0,
            "success": 0,
            "rate_limited": 0,
            "other_errors": 0,
            "total_supply_seconds": 0,
            "total_supply_hours": 0,
            "duration_ms": round((time.perf_counter() - start_time) * 1000),
            "error_message": f"No eligible drivers found for tier={tier_upper} on {date_str}",
        }

    drivers_attempted = 0
    success = 0
    rate_limited = 0
    other_errors = 0
    total_supply_seconds = 0
    current_delay_ms = base_delay_ms
    error_log: List[Dict[str, Any]] = []

    for driver in drivers:
        did = driver["driver_profile_id"]
        drivers_attempted += 1

        result = await get_supply_hours(
            contractor_profile_id=did,
            period_from=period_from,
            period_to=period_to,
        )

        if result.get("ok"):
            success += 1
            supply_seconds = result.get("supply_duration_seconds", 0) or 0
            total_supply_seconds += supply_seconds
            current_delay_ms = base_delay_ms
        elif result.get("error_type") == "rate_limited":
            rate_limited += 1
            current_delay_ms = min(current_delay_ms * 2, 5000)
            error_log.append({
                "driver_profile_id_masked": did[:8] + "..." if len(did) > 8 else did,
                "error": "rate_limited",
                "delay_after_ms": current_delay_ms,
            })
        else:
            other_errors += 1
            error_log.append({
                "driver_profile_id_masked": did[:8] + "..." if len(did) > 8 else did,
                "error": result.get("error_type", "unknown"),
            })

        await asyncio.sleep(current_delay_ms / 1000.0)

        if drivers_attempted % batch_size == 0:
            logger.info(
                "Supply batch progress: %s/%s success=%s rate_limited=%s delay_ms=%s",
                drivers_attempted, len(drivers), success, rate_limited, current_delay_ms,
            )

    duration_ms = round((time.perf_counter() - start_time) * 1000)
    total_supply_hours = round(total_supply_seconds / 3600.0, 2)

    logger.info(
        "Supply batch complete: tier=%s attempted=%s success=%s rate_limited=%s supply_h=%s",
        tier_upper, drivers_attempted, success, rate_limited, total_supply_hours,
    )

    return {
        "ok": True,
        "date": date_str,
        "tier": tier_upper,
        "drivers_attempted": drivers_attempted,
        "success": success,
        "rate_limited": rate_limited,
        "other_errors": other_errors,
        "total_supply_seconds": total_supply_seconds,
        "total_supply_hours": total_supply_hours,
        "avg_delay_ms": base_delay_ms,
        "max_delay_reached_ms": current_delay_ms,
        "duration_ms": duration_ms,
        "error_log": error_log[:20],
    }
