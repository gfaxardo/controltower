"""
YEGO Lima Growth - Driver Lifecycle Foundation Router (LG-ACT-1A)
Shadow mode: read-only endpoints + manual backfill.
"""
from fastapi import APIRouter, Query
from app.services.yego_lima_lifecycle_service import (
    backfill_activity_events_from_trips,
    build_activity_daily,
    build_activity_weekly,
    build_activity_monthly,
    build_lifecycle_daily,
    build_lifecycle_events,
    get_lifecycle_summary,
    get_driver_lifecycle,
    get_lifecycle_events,
)

router = APIRouter(
    prefix="/yego-lima-growth/lifecycle",
    tags=["yego-lima-growth-lifecycle"],
)


@router.post("/backfill")
async def lifecycle_backfill(
    start_date: str = Query(..., description="Start date YYYY-MM-DD"),
    end_date: str = Query(..., description="End date YYYY-MM-DD"),
):
    result = backfill_activity_events_from_trips(start_date, end_date)
    return result


@router.post("/build")
async def lifecycle_build(date: str = Query(..., description="Snapshot date YYYY-MM-DD")):
    daily = build_activity_daily(date, date)
    weekly = build_activity_weekly(date, date)
    monthly = build_activity_monthly(date, date)
    lc = build_lifecycle_daily(date)
    events = build_lifecycle_events(date, date)
    return {
        "activity_daily": daily,
        "activity_weekly": weekly,
        "activity_monthly": monthly,
        "lifecycle": lc,
        "lifecycle_events": events,
    }


@router.get("/summary")
async def lifecycle_summary(date: str = Query(..., description="Snapshot date YYYY-MM-DD")):
    return get_lifecycle_summary(date)


@router.get("/driver/{driver_id}")
async def driver_lifecycle(driver_id: str, date: str = Query(..., description="Snapshot date YYYY-MM-DD")):
    result = get_driver_lifecycle(driver_id, date)
    if result is None:
        return {"error": "Driver not found"}
    return result


@router.get("/events")
async def lifecycle_events(date: str = Query(..., description="Event date YYYY-MM-DD"), limit: int = Query(100)):
    return get_lifecycle_events(date, limit)
