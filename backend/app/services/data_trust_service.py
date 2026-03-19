"""
Capa mínima de confianza de data (Data Trust Layer).
Evalúa por vista: OK | WARNING | BLOCKED.
Delega en el Confidence Engine central; resiliente: si falla → WARNING.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.config.source_of_truth_registry import DATA_TRUST_VIEWS

logger = logging.getLogger(__name__)

VALID_VIEWS = DATA_TRUST_VIEWS


def get_data_trust_status(view_name: str, _filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Devuelve { status: "ok" | "warning" | "blocked", message: str, last_update: str | null }.
    Delega en el Confidence Engine; contrato existente para UI (DataTrustBadge).
    Si falla → status "warning", message "Estado de data no disponible".
    """
    view_name = (view_name or "").strip().lower()
    if view_name not in VALID_VIEWS:
        return {"status": "warning", "message": "Vista no reconocida", "last_update": None}

    try:
        from app.services.confidence_engine import get_confidence_status

        conf = get_confidence_status(view_name, _filters)
        trust = conf.get("trust_status") or "warning"
        return {
            "status": trust,
            "message": conf.get("message") or "Estado de data no disponible",
            "last_update": conf.get("last_update"),
        }
    except Exception as e:
        logger.debug("data_trust %s: %s", view_name, e)
        return {"status": "warning", "message": "Estado de data no disponible", "last_update": None}
