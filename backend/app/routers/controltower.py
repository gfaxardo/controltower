"""
Control Tower — Alias router for /controltower/behavior-alerts/* (same as /ops/behavior-alerts/*).
Additive; delegates to the same behavior_alerts_service.
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import Response
from typing import Optional
from app.services.behavior_alerts_service import (
    get_behavior_alerts_summary,
    get_behavior_alerts_drivers,
    get_behavior_alerts_driver_detail,
    get_behavior_alerts_export,
    get_behavior_alerts_insight,
)
from app.routers.ops import _to_csv
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/controltower", tags=["controltower"])


@router.get("/behavior-alerts/summary")
async def get_behavior_alerts_summary_ct(
    week_start: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    segment_current: Optional[str] = Query(None),
    movement_type: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    risk_band: Optional[str] = Query(None),
):
    try:
        return get_behavior_alerts_summary(
            week_start=week_start, from_date=from_, to_date=to,
            country=country, city=city, park_id=park_id,
            segment_current=segment_current, movement_type=movement_type,
            alert_type=alert_type, severity=severity, risk_band=risk_band,
        )
    except Exception as e:
        logger.error("GET /controltower/behavior-alerts/summary: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/behavior-alerts/insight")
async def get_behavior_alerts_insight_ct(
    week_start: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    segment_current: Optional[str] = Query(None),
    movement_type: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    risk_band: Optional[str] = Query(None),
):
    try:
        return get_behavior_alerts_insight(
            week_start=week_start, from_date=from_, to_date=to,
            country=country, city=city, park_id=park_id,
            segment_current=segment_current, movement_type=movement_type,
            alert_type=alert_type, severity=severity, risk_band=risk_band,
        )
    except Exception as e:
        logger.error("GET /controltower/behavior-alerts/insight: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/behavior-alerts/drivers")
async def get_behavior_alerts_drivers_ct(
    week_start: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    segment_current: Optional[str] = Query(None),
    movement_type: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    risk_band: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    order_by: str = Query("risk_score"),
    order_dir: str = Query("desc"),
):
    try:
        return get_behavior_alerts_drivers(
            week_start=week_start, from_date=from_, to_date=to,
            country=country, city=city, park_id=park_id,
            segment_current=segment_current, movement_type=movement_type,
            alert_type=alert_type, severity=severity, risk_band=risk_band,
            limit=limit, offset=offset, order_by=order_by, order_dir=order_dir,
        )
    except Exception as e:
        logger.error("GET /controltower/behavior-alerts/drivers: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/behavior-alerts/driver-detail")
async def get_behavior_alerts_driver_detail_ct(
    driver_key: str = Query(...),
    week_start: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    weeks: int = Query(8, ge=1, le=24),
):
    try:
        return get_behavior_alerts_driver_detail(
            driver_key=driver_key, week_start=week_start, from_date=from_, to_date=to, weeks=weeks,
        )
    except Exception as e:
        logger.error("GET /controltower/behavior-alerts/driver-detail: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/behavior-alerts/export")
async def get_behavior_alerts_export_ct(
    week_start: Optional[str] = Query(None),
    from_: Optional[str] = Query(None, alias="from"),
    to: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    segment_current: Optional[str] = Query(None),
    movement_type: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    risk_band: Optional[str] = Query(None),
    format: Optional[str] = Query("csv"),
    max_rows: int = Query(10000, ge=1, le=50000),
):
    try:
        rows = get_behavior_alerts_export(
            week_start=week_start, from_date=from_, to_date=to,
            country=country, city=city, park_id=park_id,
            segment_current=segment_current, movement_type=movement_type,
            alert_type=alert_type, severity=severity, risk_band=risk_band,
            max_rows=max_rows,
        )
        cols = ["driver_key", "driver_name", "country", "city", "park_name", "week_label", "segment_current", "movement_type", "trips_current_week", "avg_trips_baseline", "delta_abs", "delta_pct", "alert_type", "alert_severity", "risk_score", "risk_band"]
        if (format or "csv").lower() == "excel":
            try:
                import openpyxl
                from io import BytesIO
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Behavioral Alerts"
                ws.append(cols)
                for r in rows:
                    ws.append([r.get(c) for c in cols])
                buf = BytesIO()
                wb.save(buf)
                buf.seek(0)
                return Response(
                    content=buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=behavior_alerts.xlsx"},
                )
            except ImportError:
                body = _to_csv(rows, cols)
                return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=behavior_alerts.csv"})
        body = _to_csv(rows, cols)
        return Response(content=body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=behavior_alerts.csv"})
    except Exception as e:
        logger.error("GET /controltower/behavior-alerts/export: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
