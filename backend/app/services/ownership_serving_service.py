"""
Ownership Serving Service — Fase 0.2

Capa de consulta sobre ops.mv_ownership_serving_fact.
Solo lectura. NO modifica datos. NO expone UI.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.adapters.projection_ownership_repo import query_ownership_serving_fact

logger = logging.getLogger(__name__)


def get_ownership_serving_monthly(
    plan_version_key: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    jefe_producto: Optional[str] = None,
    lob: Optional[str] = None,
    period: Optional[str] = None,
    ownership_assignment: Optional[str] = None,
    limit: int = 2000,
    offset: int = 0,
) -> Dict[str, Any]:
    """Endpoint técnico de consulta al ownership serving fact mensual."""
    return query_ownership_serving_fact(
        plan_version_key=plan_version_key,
        country=country,
        city=city,
        jefe_producto=jefe_producto,
        lob=lob,
        period=period,
        ownership_assignment=ownership_assignment,
        limit=limit,
        offset=offset,
    )
