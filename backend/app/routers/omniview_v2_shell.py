"""
Omniview V2 Shell Router — product shell backend API.

Endpoints:
- GET /ops/omniview-v2/shell               — full shell with all sections
- GET /ops/omniview-v2/shell/sections      — list available sections
- GET /ops/omniview-v2/shell/section/{id}  — single section detail

Rules:
- canonical_ready must be explicit.
- source_system defaults to CT_TRIPS_2026.
- YANGO_API_RAW always canonical_ready=false.
- No UI connection.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.services.omniview_v2_shell_service import (
    build_shell,
    get_shell_section,
    get_shell_sections_list,
)
from app.services.omniview_v2_snapshot_service import get_served_payload

router = APIRouter(prefix="/ops/omniview-v2", tags=["omniview_v2_shell"])


@router.get("/shell")
def get_shell(
    source_system: str = Query(default="CT_TRIPS_2026"),
    grain: str = Query(default="day"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
    allow_runtime: bool = Query(default=False),
):
    """Full product shell with all sections for a source/grain. Reads snapshot if available."""
    # Try snapshot first (single-day queries)
    if date_from and date_from == date_to:
        snap = get_served_payload(source_system, grain, date_from, "shell")
        if snap:
            return snap

    if not allow_runtime:
        return {
            "source_system": source_system,
            "source_status": "SNAPSHOT_MISSING",
            "canonical_ready": source_system != "YANGO_API_RAW",
            "grain": grain,
            "sections": [],
            "warnings": [{"code": "SERVING_SNAPSHOT_MISSING", "message": f"No snapshot for {source_system}/{grain}/{date_from}. Use allow_runtime=true or refresh snapshots.", "severity": "warning"}],
        }

    filters = {"country": country, "city": city}
    if source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}

    response = build_shell(
        source_system=source_system,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
    )
    return response.to_dict()


@router.get("/shell/sections")
def list_sections():
    """List all available shell sections with metadata."""
    return {"sections": get_shell_sections_list()}


@router.get("/shell/section/{section_id}")
def get_section(
    section_id: str,
    source_system: str = Query(default="CT_TRIPS_2026"),
    grain: str = Query(default="day"),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
    country: str = Query(default="peru"),
    city: str = Query(default="lima"),
):
    """Get a single shell section by ID."""
    filters = {"country": country, "city": city}
    if source_system == "YANGO_API_RAW":
        filters = {"park_id": "08e20910d81d42658d4334d3f6d10ac0"}

    section = get_shell_section(
        source_system=source_system,
        grain=grain,
        date_from=date_from,
        date_to=date_to,
        section_id=section_id,
        filters=filters,
    )
    if section:
        from app.contracts.omniview_v2_shell_contract import _serialize_shell
        return _serialize_shell(section)

    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"error": f"Section '{section_id}' not found"})
