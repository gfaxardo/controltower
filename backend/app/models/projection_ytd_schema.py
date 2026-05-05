"""
Contrato tipado para meta.ytd_summary (Omniview proyección).

Valida salida de compute_ytd_summary antes de exponerla en JSON; fallos → payload de error explícito.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


class YtdSummaryErrorPayload(BaseModel):
    """Respuesta cuando YTD falla o no valida."""

    model_config = ConfigDict(extra="forbid")

    error: str
    grain: str


class ProjectionYtdSummary(BaseModel):
    """Cumplimiento YTD agregado (FASE 3.5). Campos alineados con _finalize_ytd_payload."""

    model_config = ConfigDict(extra="allow")

    grain: str
    year: int
    through_period: str
    metric_trace: Dict[str, Any]
    ytd_real_trips: float
    ytd_plan_expected_trips: float
    ytd_gap_trips: float
    ytd_attainment_pct: Optional[float] = None
    ytd_real_revenue: Optional[float] = None
    ytd_plan_expected_revenue: Optional[float] = None
    ytd_gap_revenue: Optional[float] = None
    ytd_avg_active_drivers_real: Optional[float] = None
    ytd_avg_active_drivers_expected: Optional[float] = None
    driver_productivity_ytd_real: Optional[float] = None
    driver_productivity_ytd_expected: Optional[float] = None
    ytd_avg_ticket_real: Optional[float] = None
    ytd_avg_ticket_expected: Optional[float] = None
    pacing_vs_expected: Optional[str] = None
    ytd_trend: str
    ytd_trend_periods: List[Dict[str, Any]] = Field(default_factory=list)
    gap_decomposition: Dict[str, Any]
    active_drivers_note: Optional[str] = None
    ytd_active_drivers_real: Optional[float] = None
    ytd_plan_expected_active_drivers: Optional[float] = None
    ytd_gap_active_drivers: Optional[float] = None


def serialize_ytd_summary_for_api(raw: Optional[Dict[str, Any]], *, grain: str) -> Optional[Dict[str, Any]]:
    """
    Devuelve dict listo para JSON. None si raw es None.
    Si raw trae 'error', valida como YtdSummaryErrorPayload.
    Si validación de éxito falla, log + error tipado (sin dict arbitrario).
    """
    if raw is None:
        return None
    try:
        if raw.get("error"):
            return YtdSummaryErrorPayload.model_validate(raw).model_dump(mode="json")
        return ProjectionYtdSummary.model_validate(raw).model_dump(mode="json")
    except ValidationError as exc:
        logger.error("ProjectionYtdSummary validation failed: %s", exc)
        return YtdSummaryErrorPayload(
            error=f"ytd_schema_validation_failed: {exc!s}",
            grain=str(raw.get("grain") or grain),
        ).model_dump(mode="json")
