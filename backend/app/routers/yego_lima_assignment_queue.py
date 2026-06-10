"""
YEGO Lima Growth — Assignment Queue Router (LG-2.5B V1).

Build and query persistent operational queue from worklist.
Export queue to LoopControl.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.services.yego_lima_assignment_queue_service import (
    create_assignment_batch,
    get_assignment_queue,
)
from app.services.yego_lima_loopcontrol_export_service import export_from_contacts
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/assignment-queue",
    tags=["yego-lima-growth-assignment-queue"],
)


class BuildBatchResponse(BaseModel):
    assignment_batch_id: str
    assignment_date: str
    created_count: int
    ready_count: int
    held_count: int
    skipped_duplicates: int
    skipped_invalid: int = 0
    skipped_reasons: dict = Field(default_factory=dict)


class QueueRecord(BaseModel):
    id: str
    assignment_batch_id: str
    driver_id: str
    driver_name: Optional[str] = None
    phone: Optional[str] = None
    program_code: str
    program_name: Optional[str] = None
    priority_rank: Optional[int] = None
    assigned_channel: Optional[str] = None
    opportunity_reason: Optional[str] = None
    last_trip_date: Optional[str] = None
    recent_trips: Optional[int] = None
    country: Optional[str] = None
    city: Optional[str] = None
    park: Optional[str] = None
    queue_status: str


class QueueResponse(BaseModel):
    date: Optional[str] = None
    total_records: int = 0
    ready_count: int = 0
    held_count: int = 0
    records: List[QueueRecord] = []


class ExportRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    program_code: Optional[str] = None
    campaign_name: Optional[str] = None
    created_by: Optional[str] = None
    limit: int = Field(default=500, ge=1, le=500)


@router.post("/build", response_model=BuildBatchResponse)
async def assignment_queue_build(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    program: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    force: bool = Query(False, description="Force full rebuild even if queue already exists"),
):
    import time
    t0 = time.time()

    if not force:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT "
                "COUNT(*) AS total, "
                "SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) AS ready, "
                "SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) AS held, "
                "SUM(CASE WHEN queue_status = 'EXPORTED' THEN 1 ELSE 0 END) AS exported "
                "FROM growth.yego_lima_assignment_queue "
                "WHERE assignment_date = %(d)s",
                {"d": date},
            )
            row = cur.fetchone()
            total = row[0] or 0
            if total > 0:
                return {
                    "assignment_batch_id": "fast-path-" + date,
                    "assignment_date": date,
                    "created_count": 0,
                    "ready_count": row[1] or 0,
                    "held_count": row[2] or 0,
                    "skipped_duplicates": total,
                    "skipped_invalid": 0,
                    "skipped_reasons": {"fast_path": "Queue already exists for this date. Use force=true to rebuild."},
                    "exported_count": row[3] or 0,
                    "duration_ms": round((time.time() - t0) * 1000),
                }

    return create_assignment_batch(
        date_str=date,
        program=program,
        channel=channel,
        city=city,
    )


@router.get("", response_model=QueueResponse)
async def assignment_queue_get(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="READY or HELD"),
    program: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
):
    return get_assignment_queue(
        date_str=date,
        status=status,
        program=program,
        channel=channel,
    )


@router.post("/export")
async def assignment_queue_export(payload: ExportRequest):
    from uuid import uuid4
    TABLE_QUEUE = "growth.yego_lima_assignment_queue"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = ["assignment_date = %(d)s", "queue_status = 'READY'"]
        params = {"d": payload.date}
        if payload.program_code:
            conditions.append("program_code = %(p)s")
            params["p"] = payload.program_code
        where = " AND ".join(conditions)

        cur.execute(
            f"SELECT * FROM {TABLE_QUEUE} WHERE {where} "
            f"ORDER BY priority_rank ASC NULLS LAST LIMIT %(lim)s",
            {**params, "lim": payload.limit},
        )
        rows = cur.fetchall()

    if not rows:
        return {"exported": False, "error": "No READY records in queue for this date", "count": 0}

    contacts = []
    row_ids = []
    for r in rows:
        row_ids.append(str(r["id"]))
        contacts.append({
            "driver_id": r["driver_id"],
            "phone": r["phone"],
            "driver_name": r["driver_name"],
            "assigned_channel": r["assigned_channel"],
            "priority_rank": r["priority_rank"],
        })

    export_batch_id = str(uuid4())
    program_code = payload.program_code or (rows[0]["program_code"] if rows else "UNKNOWN")

    result = export_from_contacts(
        contacts=contacts,
        opportunity_date=payload.date,
        program_code=program_code,
        campaign_name=payload.campaign_name,
        created_by=payload.created_by,
    )

    exported = result.get("export_status") == "exported" or result.get("export_status") == "draft_dry_run"

    if exported:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {TABLE_QUEUE} SET queue_status = 'EXPORTED', exported_at = now(), "
                f"campaign_id_external = %(cid)s, export_batch_id = %(bid)s, updated_at = now() "
                f"WHERE id::text = ANY(%(ids)s)",
                {"cid": result.get("campaign_id_external"), "bid": export_batch_id, "ids": row_ids},
            )
            conn.commit()
        result["queue_exported_count"] = len(row_ids)
        result["export_batch_id"] = export_batch_id

    return result


# ── Build Audit (R2.8G) ──

from psycopg2.extras import RealDictCursor as BuildAuditCursor


@router.get("/build-audit")
async def assignment_queue_build_audit(
    date: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=BuildAuditCursor)
        if date:
            cur.execute(
                "SELECT * FROM growth.yego_lima_queue_build_audit "
                "WHERE assignment_date = %(d)s ORDER BY created_at DESC LIMIT %(lim)s",
                {"d": date, "lim": limit}
            )
        else:
            cur.execute(
                "SELECT * FROM growth.yego_lima_queue_build_audit "
                "ORDER BY created_at DESC LIMIT %(lim)s",
                {"lim": limit}
            )
        rows = cur.fetchall()
        return {"entries": [dict(r) for r in rows], "count": len(rows)}
