"""
Omniview V2 Shadow Router — parallel API for raw_yango MVs.
Shadow mode: independent from Omniview V1. canonical_ready always false.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.omniview_v2_shadow_service import build_shadow_response

router = APIRouter(prefix="/ops/omniview-v2-shadow", tags=["omniview_v2_shadow"])


@router.get("/daily")
def shadow_daily(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """KPIs from raw_yango MVs: orders, revenue, coverage per day."""
    return build_shadow_response(park_id=park_id, date_from=date_from, date_to=date_to)


@router.get("/coverage")
def shadow_coverage(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Source coverage by day from raw_yango MVs."""
    from app.repositories.omniview_v2_shadow_repository import (
        get_coverage_by_day,
        get_source_health,
    )
    return {
        "source": "YANGO_API_SHADOW",
        "status": "SHADOW_ONLY",
        "health": get_source_health(park_id),
        "daily": get_coverage_by_day(park_id, date_from, date_to),
    }


@router.get("/reconciliation")
def shadow_reconciliation(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Reconciliation of raw_yango MVs vs CT day_fact."""
    from app.repositories.omniview_v2_shadow_repository import (
        get_reconciliation_vs_ct,
    )
    return {
        "source": "YANGO_API_SHADOW",
        "status": "SHADOW_ONLY",
        "canonical_ready": False,
        "reconciliation": get_reconciliation_vs_ct(park_id, date_from, date_to),
    }


@router.get("/health")
def shadow_health(
    park_id: str = Query(default="08e20910d81d42658d4334d3f6d10ac0"),
):
    """Health check for shadow API — coverage status, warnings."""
    from app.services.omniview_v2_shadow_service import build_shadow_response
    return build_shadow_response(park_id=park_id)
