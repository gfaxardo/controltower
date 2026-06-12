"""
YEGO Lima Growth - Driver Taxonomy Router (LG-TAX-1.0B)
Shadow mode: read-only endpoints + POST build (shadow only).
"""
from fastapi import APIRouter, Query
from app.services.yego_lima_taxonomy_service import (
    build_driver_taxonomy,
    get_taxonomy_summary,
    get_driver_taxonomy,
    get_taxonomy_transitions,
    seed_taxonomy_config,
)

router = APIRouter(
    prefix="/yego-lima-growth/taxonomy",
    tags=["yego-lima-growth-taxonomy"],
)


@router.get("/summary")
async def taxonomy_summary(date: str = Query(None, description="Fecha YYYY-MM-DD")):
    return get_taxonomy_summary(date)


@router.get("/driver/{driver_id}")
async def driver_taxonomy(driver_id: str, date: str = Query(None, description="Fecha YYYY-MM-DD")):
    result = get_driver_taxonomy(driver_id, date)
    if result is None:
        return {"error": "Driver not found in taxonomy"}
    return result


@router.get("/transitions")
async def taxonomy_transitions(date: str = Query(None, description="Fecha YYYY-MM-DD"), limit: int = Query(100)):
    return get_taxonomy_transitions(date, limit)


@router.post("/build")
async def build_taxonomy(date: str = Query(..., description="Fecha YYYY-MM-DD"), version: str = Query("v2")):
    result = build_driver_taxonomy(date, version)
    if not result.get("ok"):
        return {"error": result.get("error", "Build failed"), "detail": result}
    return {
        "message": "Taxonomy built (shadow mode - no production impact)",
        "rows_built": result["rows_built"],
        "explanations_built": result["explanations_built"],
        "transitions_built": result["transitions_built"],
        "duration_ms": result["duration_ms"],
        "taxonomy_version": result["taxonomy_version"],
        "match": result["match"],
        "expected_rows": result["expected_rows"],
        "distributions": result["distributions"],
        "top_personas": result["top_personas"][:10],
        "total_personas": result["total_personas"],
        "config": result["config"],
    }


@router.post("/seed-config")
async def seed_config():
    return seed_taxonomy_config()
