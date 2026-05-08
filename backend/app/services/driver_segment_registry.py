"""
Registro oficial de segmentos operativos (FASE 4.2B).

Todas las sugerencias contextualizadas deben referenciar segment_id de este registry.
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class SegmentPayload(TypedDict):
    segment_id: str
    display_name: str
    definition: str
    logic_version: str
    eligibility_notes: str
    data_dependencies: List[str]


# IDs canónicos (no duplicar literales fuera de este módulo)
SID_LOW_ACTIVITY_0_5_7D = "low_activity_0_5_7d"
SID_DORMANT_14D = "dormant_14d"
SID_DORMANT_30D = "dormant_30d"
SID_ELITE_DEGRADED = "elite_degraded"
SID_ONBOARDING_PENDING_FIRST_TRIP = "onboarding_pending_first_trip"
SID_CASUAL_LOW_ENGAGEMENT = "casual_low_engagement"

SEGMENTS: Dict[str, SegmentPayload] = {
    SID_LOW_ACTIVITY_0_5_7D: {
        "segment_id": SID_LOW_ACTIVITY_0_5_7D,
        "display_name": "Baja actividad (0–5 viajes en semana ISO)",
        "definition": "0 a 5 viajes completados en la última semana ISO disponible (mv_driver_weekly_stats).",
        "logic_version": "v1",
        "eligibility_notes": "Un driver-week; no implica ausencia de viajes en ventana calendario 7d distinta.",
        "data_dependencies": ["ops.mv_driver_weekly_stats"],
    },
    SID_DORMANT_14D: {
        "segment_id": SID_DORMANT_14D,
        "display_name": "Dormant 14d+",
        "definition": "Último viaje completado hace más de 14 días calendario (lifecycle).",
        "logic_version": "v1",
        "eligibility_notes": "Incluye conductores con historial de viaje; no cubre nunca activados sin viaje.",
        "data_dependencies": ["ops.mv_driver_lifecycle_base", "public.drivers (park_id)"],
    },
    SID_DORMANT_30D: {
        "segment_id": SID_DORMANT_30D,
        "display_name": "Dormant 30d+",
        "definition": "Sin viaje completado en los últimos 30 días calendario (último viaje anterior o nulo).",
        "logic_version": "v1",
        "eligibility_notes": "Subconjunto operativo más frío; puede solaparse con otros segmentos.",
        "data_dependencies": ["ops.mv_driver_lifecycle_base", "public.drivers (park_id)"],
    },
    SID_ELITE_DEGRADED: {
        "segment_id": SID_ELITE_DEGRADED,
        "display_name": "Elite / alto valor deteriorado",
        "definition": "Cohortes de alto valor con riesgo o deterioro según action engine (si la vista existe).",
        "logic_version": "v1",
        "eligibility_notes": "Requiere ops.v_action_engine_driver_base; si no hay vista, conteo 0.",
        "data_dependencies": ["ops.v_action_engine_driver_base"],
    },
    SID_ONBOARDING_PENDING_FIRST_TRIP: {
        "segment_id": SID_ONBOARDING_PENDING_FIRST_TRIP,
        "display_name": "Onboarding — sin primer viaje",
        "definition": "Registrados con datos en lifecycle sin activación efectiva / sin viajes completados en ventana.",
        "logic_version": "v1",
        "eligibility_notes": "Ventana registros últimos 120 días en consulta lifecycle.",
        "data_dependencies": ["ops.mv_driver_lifecycle_base", "public.drivers (park_id)"],
    },
    SID_CASUAL_LOW_ENGAGEMENT: {
        "segment_id": SID_CASUAL_LOW_ENGAGEMENT,
        "display_name": "Casual / PT — bajo engagement semanal",
        "definition": "Modo trabajo casual o PT en semana ISO y 0–2 viajes en esa semana.",
        "logic_version": "v1",
        "eligibility_notes": "clasificación por work_mode_week en mv_driver_weekly_stats (FT/PT/casual).",
        "data_dependencies": ["ops.mv_driver_weekly_stats"],
    },
}


def segment_public_meta(segment_id: str) -> Dict[str, Any]:
    """Subset seguro para JSON (equivale al contrato solicitado)."""
    s = SEGMENTS.get(segment_id)
    if not s:
        return {
            "segment_id": segment_id,
            "display_name": segment_id,
            "definition": "segmento_no_registrado",
            "logic_version": "unknown",
            "eligibility_notes": "Este segment_id no existe en DRIVER_SEGMENT_REGISTRY",
            "data_dependencies": [],
        }
    return dict(s)


def all_registered_segment_ids() -> List[str]:
    return list(SEGMENTS.keys())
