"""
YEGO Lima Fleet Growth Tower — API Lab Router (Fases 0, 1, 2A, 2B, 2B-R0).

Endpoints:
  GET  /yego-lima-growth/lab/health
  POST /yego-lima-growth/lab/test-orders-connection
  POST /yego-lima-growth/lab/capture-orders-range
  GET  /yego-lima-growth/lab/raw-orders-summary
  GET  /yego-lima-growth/lab/recent-raw-orders

  Fase 2A — Driver 360 & Eligible Universe:
  GET  /yego-lima-growth/lab/driver-profiles-discovery
  GET  /yego-lima-growth/lab/supply-hours-discovery
  GET  /yego-lima-growth/lab/balance-discovery
  GET  /yego-lima-growth/lab/driver-360-discovery
  POST /yego-lima-growth/lab/build-driver-360-day
  GET  /yego-lima-growth/lab/driver-360-summary
  GET  /yego-lima-growth/lab/driver-360-sample
  POST /yego-lima-growth/lab/build-eligible-universe
  GET  /yego-lima-growth/lab/eligible-universe-summary
  GET  /yego-lima-growth/lab/eligible-universe-sample
  POST /yego-lima-growth/lab/run-supply-batch
  POST /yego-lima-growth/lab/stabilize-driver-360-day
  GET  /yego-lima-growth/lab/driver-360-day-summary
  GET  /yego-lima-growth/lab/driver-360-operational-lists

  Fase 2B — Loyalty Sub-50:
  POST /yego-lima-growth/lab/build-loyalty-sub50
  GET  /yego-lima-growth/lab/loyalty-sub50-summary
  GET  /yego-lima-growth/lab/loyalty-sub50-top-opportunities
  GET  /yego-lima-growth/lab/loyalty-sub50-supply-opportunities

  Fase 2B-R0 — Historical Bootstrap:
  POST /yego-lima-growth/lab/bootstrap-history
  GET  /yego-lima-growth/lab/history-summary
  GET  /yego-lima-growth/lab/history-sample
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.settings import settings
from app.integrations.yango_api_client import (
    test_orders_connection,
    list_driver_profiles,
    list_driver_profiles_raw,
    get_supply_hours,
    get_blocked_balance,
    _mask_id,
)
from app.services.yego_lima_growth_capture_service import capture_orders_range
from app.services.yego_lima_driver_360_service import stabilize_driver_360_day
from app.services.yego_lima_eligible_universe_service import build_eligible_universe
from app.services.yego_lima_supply_batch_service import run_supply_batch
from app.services.yego_lima_loyalty_sub50_service import (
    build_loyalty_sub50,
    get_sub50_summary,
    get_top_opportunities,
    get_supply_opportunities,
    get_recoverable,
)
from app.services.yego_lima_growth_history_service import (
    bootstrap_history,
    history_summary,
    history_sample,
)
from app.services.yego_lima_driver_segmentation_service import (
    build_driver_segments,
    get_segments_summary,
    get_segments_distribution,
    get_top_opportunities as get_seg_top_opportunities,
    get_recoverable_list,
    get_churn_risk,
    get_14_90,
)
from app.repositories.yego_lima_growth_repository import (
    get_raw_orders_summary,
    get_recent_raw_orders,
)
from app.repositories.yego_lima_driver_360_repository import (
    get_driver_360_summary,
    get_driver_360_sample,
    get_driver_360_day_summary,
    get_driver_360_operational_lists,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/lab",
    tags=["yego-lima-growth-lab"],
)

PET = timezone(timedelta(hours=-5))

# ── Pydantic models ──

class CaptureOrdersRangeRequest(BaseModel):
    from_: str = Field(..., alias="from", description="ISO 8601 start datetime in America/Lima")
    to: str = Field(..., description="ISO 8601 end datetime in America/Lima")
    max_pages: int = Field(20, ge=1, le=50, description="Max pages to fetch")


class BuildDriver360DayRequest(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format (America/Lima)")
    max_drivers: int = Field(0, ge=0, le=100000, description="Max drivers to process (0 = all)")


class BuildEligibleUniverseRequest(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format (America/Lima)")


class RunSupplyBatchRequest(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format (America/Lima)")
    tier: str = Field("HOT", description="Tier: HOT, WARM, COLD")
    max_drivers: int = Field(0, ge=0, le=10000, description="Max drivers (0 = settings default)")


class StabilizeDriver360DayRequest(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format (America/Lima)")
    include_warm: bool = Field(False, description="Include WARM tier drivers in supply fetch")
    max_drivers: int = Field(250, ge=1, le=1000, description="Max drivers to process")


class BuildLoyaltySub50Request(BaseModel):
    week_start_date: str = Field(..., description="Week start date (YYYY-MM-DD), e.g. 2026-06-01")
    target_weekly_trips: Optional[int] = Field(None, ge=1, le=200, description="Optional target override, defaults to LIMA_GROWTH_WEEKLY_TRIPS_TARGET")


class BootstrapHistoryRequest(BaseModel):
    from_date: str = Field(..., description="Start date YYYY-MM-DD")
    to_date: str = Field(..., description="End date YYYY-MM-DD")


class BuildDriverSegmentsRequest(BaseModel):
    snapshot_date: str = Field(..., description="Snapshot date YYYY-MM-DD, e.g. 2026-06-02")


def _get_today_lima_range() -> tuple[str, str]:
    now_lima = datetime.now(PET)
    today_start = now_lima.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        today_start.strftime("%Y-%m-%dT%H:%M:%S%z"),
        now_lima.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )


def _get_today_orders_by_driver() -> Dict[str, int]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    result: Dict[str, int] = {}
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT driver_profile_id, COUNT(*) as cnt
                    FROM growth.yango_lima_orders_raw
                    WHERE ended_at >= CURRENT_DATE AT TIME ZONE 'America/Lima'
                      AND driver_profile_id IS NOT NULL
                    GROUP BY driver_profile_id
                """)
                for row in cur.fetchall():
                    did = row.get("driver_profile_id")
                    if did:
                        result[str(did)] = int(row.get("cnt", 0))
    except Exception as e:
        logger.warning("Failed to query today orders by driver: %s", e)
    return result


# ── Endpoints ──

@router.get("/health")
async def health():
    client_id = (settings.YANGO_CLIENT_ID or "").strip()
    api_key = (settings.YANGO_API_KEY or "").strip()
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()

    has_client_id = bool(client_id)
    has_api_key = bool(api_key)
    has_lima_park_id = bool(park_id)
    enabled = bool(settings.YANGO_API_ENABLED)
    ready = enabled and has_client_id and has_api_key and has_lima_park_id

    return {
        "module": "yego_lima_growth_lab",
        "enabled": enabled,
        "base_url": settings.YANGO_API_BASE_URL,
        "has_client_id": has_client_id,
        "has_api_key": has_api_key,
        "has_lima_park_id": has_lima_park_id,
        "ready": ready,
    }


@router.post("/test-orders-connection")
async def test_orders():
    result = await test_orders_connection()
    return result


@router.post("/capture-orders-range")
async def capture_orders(payload: CaptureOrdersRangeRequest):
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )

    result = await capture_orders_range(
        from_str=payload.from_,
        to_str=payload.to,
        max_pages=payload.max_pages,
    )
    return result


@router.get("/raw-orders-summary")
async def raw_orders_summary():
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return get_raw_orders_summary()


@router.get("/recent-raw-orders")
async def recent_raw_orders(limit: int = Query(20, ge=1, le=100)):
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return get_recent_raw_orders(limit=limit)


# ── Fase 2B — Loyalty Sub-50 ──

@router.post("/build-loyalty-sub50")
async def build_loyalty_sub50_endpoint(payload: BuildLoyaltySub50Request):
    result = build_loyalty_sub50(payload.week_start_date, payload.target_weekly_trips)
    return result


@router.get("/loyalty-sub50-summary")
async def loyalty_sub50_summary(week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD")):
    result = get_sub50_summary(week_start_date)
    return result


@router.get("/loyalty-sub50-top-opportunities")
async def loyalty_sub50_top_opportunities(
    week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_top_opportunities(week_start_date, limit=limit)
    return result


@router.get("/loyalty-sub50-supply-opportunities")
async def loyalty_sub50_supply_opportunities(
    week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_supply_opportunities(week_start_date, limit=limit)
    return result


# ── Fase 2B-R0 — Historical Bootstrap ──

@router.post("/bootstrap-history")
async def bootstrap_history_endpoint(payload: BootstrapHistoryRequest):
    result = bootstrap_history(payload.from_date, payload.to_date)
    return result


@router.get("/history-summary")
async def history_summary_endpoint():
    result = history_summary()
    return result


@router.get("/history-sample")
async def history_sample_endpoint(limit: int = Query(20, ge=1, le=100)):
    result = history_sample(limit=limit)
    return result


@router.get("/loyalty-sub50-recoverable")
async def loyalty_sub50_recoverable(
    week_start_date: Optional[str] = Query(None, description="Week start date YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_recoverable(week_start_date, limit=limit)
    return result


# ── Fase 2B-R2 — Unified Driver Segmentation ──

@router.post("/build-driver-segments")
async def build_driver_segments_endpoint(payload: BuildDriverSegmentsRequest):
    result = build_driver_segments(payload.snapshot_date)
    return result


@router.get("/driver-segments-summary")
async def driver_segments_summary(snapshot_date: Optional[str] = Query(None, description="Snapshot date YYYY-MM-DD")):
    result = get_segments_summary(snapshot_date)
    return result


@router.get("/driver-segments-distribution")
async def driver_segments_distribution(snapshot_date: Optional[str] = Query(None)):
    result = get_segments_distribution(snapshot_date)
    return result


@router.get("/driver-segments-top-opportunities")
async def driver_segments_top_opportunities(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_seg_top_opportunities(snapshot_date, limit)
    return result


@router.get("/driver-segments-recoverable")
async def driver_segments_recoverable(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_recoverable_list(snapshot_date, limit)
    return result


@router.get("/driver-segments-churn-risk")
async def driver_segments_churn_risk(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_churn_risk(snapshot_date, limit)
    return result


@router.get("/driver-segments-14-90")
async def driver_segments_14_90(
    snapshot_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    result = get_14_90(snapshot_date, limit)
    return result
@router.get("/driver-profiles-discovery")
async def driver_profiles_discovery():
    """
    Descubre el universo de driver profiles de la flota Lima.
    Llama POST /v1/parks/driver-profiles/list y devuelve resumen sanitizado.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return await list_driver_profiles(
        limit=settings.YANGO_DRIVER_PROFILES_PAGE_SIZE,
    )


@router.get("/supply-hours-discovery")
async def supply_hours_discovery():
    """
    Descubre supply hours para una muestra de conductores.
    Usa driver_profile_id desde orders_raw o desde driver-profiles/list.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )

    sample_size = settings.YANGO_SUPPLY_HOURS_SAMPLE_SIZE
    period_from, period_to = _get_today_lima_range()

    driver_ids: List[str] = []

    # Try getting driver_ids from orders_raw first
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT driver_profile_id
                    FROM growth.yango_lima_orders_raw
                    WHERE driver_profile_id IS NOT NULL
                    ORDER BY driver_profile_id
                    LIMIT %(limit)s
                """, {"limit": sample_size})
                for row in cur.fetchall():
                    did = row.get("driver_profile_id")
                    if did:
                        driver_ids.append(str(did))
    except Exception as e:
        logger.warning("Failed to get driver ids from orders: %s", e)

    # Fallback: get from driver-profiles/list
    if not driver_ids:
        profiles_result = await list_driver_profiles_raw(limit=sample_size)
        if profiles_result.get("ok"):
            for p in profiles_result.get("driver_profiles", [])[:sample_size]:
                dp = p.get("driver_profile") or {}
                did = dp.get("id")
                if did:
                    driver_ids.append(str(did))

    if not driver_ids:
        return {
            "ok": False,
            "tested_count": 0,
            "ok_count": 0,
            "error_count": 0,
            "total_supply_seconds": 0,
            "drivers_with_supply_seconds_gt_0": 0,
            "drivers_with_zero_supply": 0,
            "sample_results": [],
            "error_message": "No driver IDs available for testing",
        }

    tested_count = 0
    ok_count = 0
    error_count = 0
    total_supply_seconds = 0
    drivers_with_supply_seconds_gt_0 = 0
    drivers_with_zero_supply = 0
    sample_results: List[Dict[str, Any]] = []

    start_time = time.perf_counter()

    for did in driver_ids:
        tested_count += 1
        result = await get_supply_hours(
            contractor_profile_id=did,
            period_from=period_from,
            period_to=period_to,
        )
        if result.get("ok"):
            ok_count += 1
            secs = result.get("supply_duration_seconds", 0) or 0
            total_supply_seconds += secs
            if secs > 0:
                drivers_with_supply_seconds_gt_0 += 1
            else:
                drivers_with_zero_supply += 1
        else:
            error_count += 1

        sample_results.append({
            "contractor_profile_id_masked": result.get("contractor_profile_id_masked", "***"),
            "supply_duration_seconds": result.get("supply_duration_seconds", 0),
            "supply_hours": result.get("supply_hours", 0),
            "ok": result.get("ok", False),
            "error_type": result.get("error_type"),
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000)

    return {
        "ok": True,
        "tested_count": tested_count,
        "ok_count": ok_count,
        "error_count": error_count,
        "total_supply_seconds": total_supply_seconds,
        "drivers_with_supply_seconds_gt_0": drivers_with_supply_seconds_gt_0,
        "drivers_with_zero_supply": drivers_with_zero_supply,
        "period_from": period_from,
        "period_to": period_to,
        "duration_ms": duration_ms,
        "sample_results": sample_results,
    }


@router.get("/balance-discovery")
async def balance_discovery():
    """
    Descubre blocked balance para una muestra de conductores.
    Usa contractor_id (driver_profile_id) como contractor_id.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )

    sample_size = settings.YANGO_BALANCE_SAMPLE_SIZE

    driver_ids: List[str] = []

    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor
    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT DISTINCT driver_profile_id
                    FROM growth.yango_lima_orders_raw
                    WHERE driver_profile_id IS NOT NULL
                    ORDER BY driver_profile_id
                    LIMIT %(limit)s
                """, {"limit": sample_size})
                for row in cur.fetchall():
                    did = row.get("driver_profile_id")
                    if did:
                        driver_ids.append(str(did))
    except Exception as e:
        logger.warning("Failed to get driver ids from orders: %s", e)

    if not driver_ids:
        profiles_result = await list_driver_profiles_raw(limit=sample_size)
        if profiles_result.get("ok"):
            for p in profiles_result.get("driver_profiles", [])[:sample_size]:
                dp = p.get("driver_profile") or {}
                did = dp.get("id")
                if did:
                    driver_ids.append(str(did))

    if not driver_ids:
        return {
            "ok": False,
            "tested_count": 0,
            "ok_count": 0,
            "error_count": 0,
            "drivers_with_balance": 0,
            "drivers_with_blocked_balance": 0,
            "sample_results": [],
            "error_message": "No driver IDs available for testing",
        }

    tested_count = 0
    ok_count = 0
    error_count = 0
    drivers_with_balance = 0
    drivers_with_blocked_balance = 0
    sample_results: List[Dict[str, Any]] = []

    start_time = time.perf_counter()

    for did in driver_ids:
        tested_count += 1
        result = await get_blocked_balance(contractor_id=did)
        if result.get("ok"):
            ok_count += 1
            if result.get("has_balance"):
                drivers_with_balance += 1
            if result.get("has_blocked_balance"):
                drivers_with_blocked_balance += 1
        else:
            error_count += 1

        sample_results.append({
            "contractor_id_masked": result.get("contractor_id_masked", "***"),
            "ok": result.get("ok", False),
            "has_balance": result.get("has_balance", False),
            "has_blocked_balance": result.get("has_blocked_balance", False),
            "balance": result.get("balance"),
            "blocked_balance": result.get("blocked_balance"),
            "detail_keys": result.get("detail_keys", []),
            "error_type": result.get("error_type"),
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000)

    return {
        "ok": True,
        "tested_count": tested_count,
        "ok_count": ok_count,
        "error_count": error_count,
        "drivers_with_balance": drivers_with_balance,
        "drivers_with_blocked_balance": drivers_with_blocked_balance,
        "duration_ms": duration_ms,
        "sample_results": sample_results,
    }


def _classify_driver_state(supply_seconds: float, completed_orders: int) -> str:
    has_supply = supply_seconds > 0
    has_orders = completed_orders > 0

    if has_supply and has_orders:
        return "PRODUCTIVE"
    if has_supply and not has_orders:
        return "ONLINE_NO_ORDERS"
    if not has_supply and not has_orders:
        return "OFFLINE_NO_ORDERS"
    if not has_supply and has_orders:
        return "ORDERS_WITHOUT_SUPPLY_ANOMALY"
    return "UNKNOWN"


@router.get("/driver-360-discovery")
async def driver_360_discovery():
    """
    Conjuga driver profiles + orders hoy + supply hours hoy + balance
    para construir una vista 360 de muestra de conductores Lima.

    No guarda en base de datos. Solo discovery.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )

    sample_size = max(settings.YANGO_SUPPLY_HOURS_SAMPLE_SIZE, settings.YANGO_BALANCE_SAMPLE_SIZE)
    period_from, period_to = _get_today_lima_range()

    # 1. Get driver profiles
    profiles_result = await list_driver_profiles_raw(limit=sample_size)
    if not profiles_result.get("ok") or not profiles_result.get("driver_profiles"):
        return {
            "ok": False,
            "drivers_tested": 0,
            "drivers_with_orders": 0,
            "drivers_with_supply": 0,
            "drivers_with_supply_no_orders": 0,
            "drivers_with_orders_no_supply": 0,
            "drivers_offline_no_orders": 0,
            "sample_matrix": [],
            "error_message": "Failed to fetch driver profiles",
        }

    driver_profiles = profiles_result["driver_profiles"][:sample_size]

    # 2. Get today's orders from raw table
    today_orders = _get_today_orders_by_driver()

    # 3. Query supply hours for each driver
    sample_matrix: List[Dict[str, Any]] = []
    drivers_with_orders = 0
    drivers_with_supply = 0
    drivers_with_supply_no_orders = 0
    drivers_with_orders_no_supply = 0
    drivers_offline_no_orders = 0
    drivers_tested = 0

    start_time = time.perf_counter()

    for profile in driver_profiles:
        dp = profile.get("driver_profile") or {}
        did = dp.get("id")
        if not did:
            continue

        drivers_tested += 1

        cs = profile.get("current_status") or {}
        work_status = dp.get("work_status", "unknown")
        current_status = cs.get("status", "unknown")

        completed_orders_today = today_orders.get(str(did), 0)

        # Get supply hours
        supply_result = await get_supply_hours(
            contractor_profile_id=str(did),
            period_from=period_from,
            period_to=period_to,
        )
        supply_seconds = supply_result.get("supply_duration_seconds", 0) or 0
        supply_hours_val = round(supply_seconds / 3600.0, 2) if supply_seconds else 0

        driver_state = _classify_driver_state(supply_seconds, completed_orders_today)

        if completed_orders_today > 0:
            drivers_with_orders += 1
        if supply_seconds > 0:
            drivers_with_supply += 1
        if supply_seconds > 0 and completed_orders_today == 0:
            drivers_with_supply_no_orders += 1
        if supply_seconds == 0 and completed_orders_today > 0:
            drivers_with_orders_no_supply += 1
        if supply_seconds == 0 and completed_orders_today == 0:
            drivers_offline_no_orders += 1

        sample_matrix.append({
            "driver_profile_id_masked": _mask_id(str(did)),
            "work_status": work_status,
            "current_status": current_status,
            "completed_orders_today": completed_orders_today,
            "supply_seconds_today": supply_seconds,
            "supply_hours_today": supply_hours_val,
            "driver_state": driver_state,
        })

    duration_ms = round((time.perf_counter() - start_time) * 1000)

    return {
        "ok": True,
        "drivers_tested": drivers_tested,
        "drivers_with_orders": drivers_with_orders,
        "drivers_with_supply": drivers_with_supply,
        "drivers_with_supply_no_orders": drivers_with_supply_no_orders,
        "drivers_with_orders_no_supply": drivers_with_orders_no_supply,
        "drivers_offline_no_orders": drivers_offline_no_orders,
        "period_from": period_from,
        "period_to": period_to,
        "duration_ms": duration_ms,
        "sample_matrix": sample_matrix,
    }


@router.post("/build-driver-360-day")
async def build_driver_360_day_endpoint(payload: BuildDriver360DayRequest):
    """
    Construye la fact diaria de Driver 360 para una fecha especifica.

    Itera sobre todos los driver profiles de Lima, consulta supply-hours
    y ordenes completadas, calcula estado y persiste en
    growth.yango_lima_driver_360_daily.

    Operacion manual. Respeta YANGO_SUPPLY_REQUEST_DELAY_MS.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )

    result = await build_driver_360_day(
        date_str=payload.date,
        max_drivers=payload.max_drivers,
    )
    return result


@router.get("/driver-360-summary")
async def driver_360_summary_endpoint():
    """
    Devuelve resumen agregado de la tabla driver_360_daily.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return get_driver_360_summary()


@router.get("/driver-360-sample")
async def driver_360_sample_endpoint(limit: int = Query(20, ge=1, le=100)):
    """
    Devuelve muestra sanitizada de la tabla driver_360_daily.
    Sin PII, sin raw payload.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    return get_driver_360_sample(limit=limit)


@router.post("/build-eligible-universe")
async def build_eligible_universe_endpoint(payload: BuildEligibleUniverseRequest):
    """
    Construye el universo elegible diario clasificando conductores en
    HOT / WARM / COLD / DORMANT usando orders_raw + driver_profiles.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={
                "error_type": "disabled",
                "error_message": "YANGO_API_ENABLED is false",
            },
        )
    result = await build_eligible_universe(date_str=payload.date)
    return result


def _get_eligible_universe_summary() -> Dict[str, Any]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(DISTINCT date) AS dates,
                        COUNT(*) AS total_rows,
                        COUNT(*) FILTER (WHERE priority_tier = 'HOT') AS hot,
                        COUNT(*) FILTER (WHERE priority_tier = 'WARM') AS warm,
                        COUNT(*) FILTER (WHERE priority_tier = 'COLD') AS cold,
                        COUNT(*) FILTER (WHERE priority_tier = 'DORMANT') AS dormant
                    FROM growth.yango_lima_eligible_universe_daily
                """)
                row = cur.fetchone()
                if not row:
                    return {"dates": 0, "total_rows": 0, "hot": 0, "warm": 0, "cold": 0, "dormant": 0}
                return {
                    "dates": row["dates"] or 0,
                    "total_rows": row["total_rows"] or 0,
                    "hot": row["hot"] or 0,
                    "warm": row["warm"] or 0,
                    "cold": row["cold"] or 0,
                    "dormant": row["dormant"] or 0,
                }
    except Exception as e:
        logger.warning("Failed to query eligible universe summary: %s", e)
        return {"dates": 0, "total_rows": 0, "hot": 0, "warm": 0, "cold": 0, "dormant": 0}


def _get_eligible_universe_sample(limit: int = 20, tier: Optional[str] = None) -> List[Dict[str, Any]]:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    try:
        with get_db() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if tier:
                    cur.execute("""
                        SELECT date, driver_profile_id, priority_tier, eligibility_reason,
                               current_status, completed_orders_today, completed_orders_7d, completed_orders_30d
                        FROM growth.yango_lima_eligible_universe_daily
                        WHERE priority_tier = %(tier)s
                        ORDER BY date DESC, driver_profile_id
                        LIMIT %(limit)s
                    """, {"tier": tier.upper(), "limit": min(limit, 100)})
                else:
                    cur.execute("""
                        SELECT date, driver_profile_id, priority_tier, eligibility_reason,
                               current_status, completed_orders_today, completed_orders_7d, completed_orders_30d
                        FROM growth.yango_lima_eligible_universe_daily
                        ORDER BY date DESC, driver_profile_id
                        LIMIT %(limit)s
                    """, {"limit": min(limit, 100)})
                result = []
                for row in cur.fetchall():
                    did = row["driver_profile_id"] or ""
                    result.append({
                        "driver_profile_id_masked": did[:8] + "..." if len(did) > 8 else did,
                        "date": row["date"].isoformat() if row["date"] else None,
                        "priority_tier": row["priority_tier"],
                        "eligibility_reason": row["eligibility_reason"],
                        "current_status": row["current_status"],
                        "completed_orders_today": row["completed_orders_today"] or 0,
                        "completed_orders_7d": row["completed_orders_7d"] or 0,
                        "completed_orders_30d": row["completed_orders_30d"] or 0,
                    })
                return result
    except Exception as e:
        logger.warning("Failed to query eligible universe sample: %s", e)
        return []


@router.get("/eligible-universe-summary")
async def eligible_universe_summary_endpoint():
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={"error_type": "disabled", "error_message": "YANGO_API_ENABLED is false"},
        )
    return _get_eligible_universe_summary()


@router.get("/eligible-universe-sample")
async def eligible_universe_sample_endpoint(
    limit: int = Query(20, ge=1, le=100),
    tier: Optional[str] = Query(None, description="Filter by tier: HOT, WARM, COLD, DORMANT"),
):
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={"error_type": "disabled", "error_message": "YANGO_API_ENABLED is false"},
        )
    return _get_eligible_universe_sample(limit=limit, tier=tier)


@router.post("/run-supply-batch")
async def run_supply_batch_endpoint(payload: RunSupplyBatchRequest):
    """
    Ejecuta supply-hours batch para conductores elegibles.

    Solo para HOT + WARM. Respeta rate limit con backoff adaptativo.
    NO persiste resultados finales (solo valida arquitectura).
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={"error_type": "disabled", "error_message": "YANGO_API_ENABLED is false"},
        )
    result = await run_supply_batch(
        date_str=payload.date,
        tier=payload.tier,
        max_drivers=payload.max_drivers,
    )
    return result


# ── Fase 2A.2: Driver 360 Stabilization endpoints ──

@router.post("/stabilize-driver-360-day")
async def stabilize_driver_360_day_endpoint(payload: StabilizeDriver360DayRequest):
    """
    Construye Driver 360 diario usando eligible_universe como fuente.

    Verifica que eligible_universe este poblado para la fecha.
    Procesa supply solo para HOT (y WARM si include_warm=true).
    COLD/DORMANT no se procesan en esta fase.

    Respeta rate limiting con backoff. No consulta 63k conductores.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={"error_type": "disabled", "error_message": "YANGO_API_ENABLED is false"},
        )

    result = await stabilize_driver_360_day(
        date_str=payload.date,
        include_warm=payload.include_warm,
        max_drivers=payload.max_drivers,
    )
    if not result.get("ok"):
        raise HTTPException(
            status_code=422,
            detail=result,
        )
    return result


@router.get("/driver-360-day-summary")
async def driver_360_day_summary_endpoint(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Summary diario de Driver 360:
    - total drivers, orders, supply hours
    - avg trips per driver, avg trips per supply hour
    - distribucion driver_state
    - distribucion productivity_band
    - distribucion eligibility_tier
    - supply_fetch_status counts
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={"error_type": "disabled", "error_message": "YANGO_API_ENABLED is false"},
        )
    return get_driver_360_day_summary(date_str=date)


@router.get("/driver-360-operational-lists")
async def driver_360_operational_lists_endpoint(date: str = Query(..., description="Date in YYYY-MM-DD format")):
    """
    Listas operacionales sanitizadas para la fecha:
    - online_no_orders
    - low_productivity
    - high_productivity
    - orders_without_supply_anomaly
    - rate_limited_supply

    Sin PII. Sin raw payload. IDs enmascarados.
    """
    if not bool(settings.YANGO_API_ENABLED):
        raise HTTPException(
            status_code=503,
            detail={"error_type": "disabled", "error_message": "YANGO_API_ENABLED is false"},
        )
    return get_driver_360_operational_lists(date_str=date)


# ── Fase 2D-RH — Historical Continuity Hardening ──

class RebuildHistoryRequest(BaseModel):
    cutover_date: str = Field(default="2026-06-01", description="Cutover date YYYY-MM-DD")
    from_date: Optional[str] = Field(None, description="Override start date YYYY-MM-DD")
    dry_run: bool = Field(default=True)


@router.get("/history-source-inspection")
async def history_source_inspection():
    from app.services.yego_lima_growth_history_service import inspect_trips_sources
    return inspect_trips_sources()


@router.post("/rebuild-history-until-cutover")
async def rebuild_history_until_cutover(payload: RebuildHistoryRequest):
    from app.services.yego_lima_growth_history_service import rebuild_history_until_cutover
    return rebuild_history_until_cutover(
        cutover_date=payload.cutover_date,
        from_date=payload.from_date,
        dry_run=payload.dry_run,
    )


@router.get("/history-continuity-check")
async def history_continuity_check():
    from app.services.yego_lima_growth_history_service import continuity_check
    return continuity_check()
