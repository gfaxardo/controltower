"""LG-EXP-1A — Export Router"""
import logging
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from app.services.yego_lima_export_service import create_export, get_export_status, get_export_options, MAX_ROWS, SAFE_COLUMNS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/export", tags=["yego-lima-growth-export"])


@router.get("/options")
async def export_options():
    return get_export_options()


@router.post("")
async def export_create(payload: dict):
    source = payload.get("source", "driver_explorer")
    filters = payload.get("filters", {})
    columns = payload.get("columns", SAFE_COLUMNS[:12])
    requested_by = payload.get("requested_by")
    export_reason = payload.get("export_reason")
    result = create_export(source, filters, columns, requested_by, export_reason)
    csv_content = result.pop("csv_content", "")
    return {**result, "csv_preview": csv_content[:200] if csv_content else ""}


@router.get("/{export_id}")
async def export_status(export_id: str):
    return get_export_status(export_id)


@router.get("/{export_id}/download")
async def export_download(export_id: str):
    from app.services.yego_lima_export_service import create_export, get_export_status
    status = get_export_status(export_id)
    if not status.get("found"):
        return PlainTextResponse("Export not found", status_code=404)
    return PlainTextResponse(
        f"Export {export_id}: {status.get('rows_count', 0)} rows, status={status.get('status')}\n"
        f"Please use POST /export with same parameters to regenerate."
    )
