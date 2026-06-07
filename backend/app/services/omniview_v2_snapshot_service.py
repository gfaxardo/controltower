"""
Omniview V2 Snapshot Service — builds and stores serving snapshots.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Optional

from app.repositories.omniview_v2_snapshot_repository import (
    get_snapshot,
    get_snapshot_health,
    get_snapshot_payload_fast,
    mark_snapshot_failed,
    snapshot_exists,
    upsert_snapshot,
)

logger = logging.getLogger(__name__)


def build_and_store_shell_snapshot(
    source_system: str = "CT_TRIPS_2026",
    grain: str = "day",
    operating_date: str = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        from app.services.omniview_v2_shell_service import build_shell

        result = build_shell(
            source_system=source_system,
            grain=grain,
            date_from=operating_date,
            date_to=operating_date,
            filters=filters,
        )
        payload = result.to_dict()

        coverage_pct = payload.get("coverage", {}).get("coverage_pct", 0.0) or 0.0
        warnings_list = _extract_warnings(payload)
        source_tables = _extract_source_tables(payload)

        upsert_snapshot(
            source_system=source_system,
            grain=grain,
            operating_date=operating_date,
            payload_type="shell",
            payload=payload,
            status="READY",
            coverage_pct=float(coverage_pct),
            build_ms=int((time.perf_counter() - t0) * 1000),
            source_tables=source_tables,
            warnings=warnings_list,
        )

        return {"ok": True, "type": "shell", "ms": int((time.perf_counter() - t0) * 1000)}

    except Exception as e:
        mark_snapshot_failed(source_system, grain, operating_date, "shell", str(e)[:500])
        logger.error("Shell snapshot failed: %s", str(e)[:200])
        return {"ok": False, "type": "shell", "error": str(e)[:200]}


def build_and_store_matrix_snapshot(
    source_system: str = "CT_TRIPS_2026",
    grain: str = "day",
    operating_date: str = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    try:
        from app.services.omniview_v2_matrix_view_model_service import build_matrix_response

        result = build_matrix_response(
            source_system=source_system,
            grain=grain,
            date_from=operating_date,
            date_to=operating_date,
            filters=filters,
        )
        payload = result.to_dict()

        coverage_pct = payload.get("metadata", {}).get("coverage_pct", 0.0) or 0.0
        warnings_list = payload.get("warnings", [])
        source_tables = [payload.get("metadata", {}).get("source_table", "")] if payload.get("metadata", {}).get("source_table") else []

        upsert_snapshot(
            source_system=source_system,
            grain=grain,
            operating_date=operating_date,
            payload_type="matrix",
            payload=payload,
            status="READY",
            coverage_pct=float(coverage_pct),
            build_ms=int((time.perf_counter() - t0) * 1000),
            source_tables=source_tables,
            warnings=warnings_list,
        )

        return {"ok": True, "type": "matrix", "ms": int((time.perf_counter() - t0) * 1000)}

    except Exception as e:
        mark_snapshot_failed(source_system, grain, operating_date, "matrix", str(e)[:500])
        logger.error("Matrix snapshot failed: %s", str(e)[:200])
        return {"ok": False, "type": "matrix", "error": str(e)[:200]}


def get_served_payload(
    source_system: str,
    grain: str,
    operating_date: str,
    payload_type: str,
) -> Optional[Dict[str, Any]]:
    snap = get_snapshot_payload_fast(source_system, grain, operating_date, payload_type)
    if not snap:
        return None
    payload = snap.get("payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(payload, dict):
        payload["metadata"] = payload.get("metadata", {})
        if isinstance(payload["metadata"], dict):
            payload["metadata"]["served_from_snapshot"] = True
            snapshot_at = snap.get("generated_at")
            payload["metadata"]["snapshot_generated_at"] = snapshot_at
    return payload


def _extract_warnings(payload: dict) -> list:
    warnings_list = []
    for section in payload.get("sections", []):
        for w in section.get("warnings", []):
            if isinstance(w, dict):
                warnings_list.append({"code": w.get("code", "?"), "message": w.get("message", "")[:200]})
    return warnings_list


def _extract_source_tables(payload: dict) -> list:
    tables = set()
    for section in payload.get("sections", []):
        for kpi in section.get("kpis", []):
            lin = kpi.get("lineage", {})
            if isinstance(lin, dict) and lin.get("origin_table"):
                tables.add(lin["origin_table"])
    return sorted(tables)
