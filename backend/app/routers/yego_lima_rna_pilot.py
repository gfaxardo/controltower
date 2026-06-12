"""LG-RNA-2B — RNA Pilot Measurement Router"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_rna_pilot_measurement_service import (
    build_pilot_measurement, get_pilot_summary, get_pilot_drivers
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/rna-pilot", tags=["yego-lima-growth-rna-pilot"])


@router.post("/build")
async def pilot_build(cohort_date: str = Query(None)):
    return build_pilot_measurement(cohort_date)


@router.get("/summary")
async def pilot_summary():
    return get_pilot_summary()


@router.get("/drivers")
async def pilot_drivers(band: str = Query(None), limit: int = Query(100), offset: int = Query(0)):
    return get_pilot_drivers(band, limit, offset)


@router.get("/data-quality")
async def pilot_data_quality():
    from app.db.connection import get_db
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM growth.yego_lima_loopcontrol_result_sync")
        lc_total = (cur.fetchone() or [0])[0]
        cur.execute("SELECT COUNT(*) FROM growth.yego_lima_impact_tracking WHERE post_contact_trips > 0")
        imp_with_trips = (cur.fetchone() or [0])[0]
        cur.execute("SELECT COUNT(*) FROM growth.rna_priority_fact")
        rna_total = (cur.fetchone() or [0])[0]
        cur.execute("SELECT COUNT(*) FROM growth.rna_pilot_measurement_fact WHERE data_quality = 'HAS_CONTACT_DATA'")
        measured_with_contact = (cur.fetchone() or [0])[0]

        return {
            "rna_priority_drivers": rna_total,
            "loopcontrol_result_records": lc_total,
            "impact_records_with_trips": imp_with_trips,
            "measured_with_contact": measured_with_contact,
            "ready_for_analysis": lc_total > 0 and measured_with_contact > 0,
        }
