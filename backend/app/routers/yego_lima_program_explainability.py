"""
YEGO Lima Growth — Program Explainability Router (LG-UX-R3.0)

Read-only. Traces real rules to real data. No AI. No inference.
"""
import logging
from fastapi import APIRouter, Query
from app.services.yego_lima_program_explainability_service import (
    get_driver_program_explainability,
    get_program_rules,
    get_program_coverage,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/yego-lima-growth/explain",
    tags=["yego-lima-growth-explain"],
)


@router.get("/driver/{driver_id}")
async def explain_driver(
    driver_id: str,
    date: str = Query(None, description="Snapshot date (YYYY-MM-DD). Default: latest."),
):
    """
    Explain why a specific driver is in each program.
    Returns real rules evaluated against real data.
    No AI. No inference.
    """
    return get_driver_program_explainability(driver_id, date)


@router.get("/rules")
async def list_rules():
    """List all program rules with descriptions. Read-only reference."""
    return get_program_rules()


@router.get("/coverage")
async def program_coverage(date: str = Query(..., description="Date (YYYY-MM-DD)")):
    """Audit program coverage: which programs have drivers, which are empty."""
    return get_program_coverage(date)
