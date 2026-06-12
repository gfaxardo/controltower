"""LG-UI-1B — Explainability Router"""
import logging
from fastapi import APIRouter
from app.services.yego_lima_explainability_service import get_driver_explainability, get_explainability_by_domain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/yego-lima-growth/explainability", tags=["yego-lima-growth-explainability"])


@router.get("/{driver_id}")
async def explainability_full(driver_id: str):
    return get_driver_explainability(driver_id)


@router.get("/{driver_id}/{domain}")
async def explainability_domain(driver_id: str, domain: str):
    valid = {"lifecycle", "segment", "program", "movement", "rna"}
    if domain not in valid:
        return {"driver_id": driver_id, "found": False, "domain": domain, "error": f"Invalid domain. Valid: {valid}"}
    return get_explainability_by_domain(driver_id, domain)
