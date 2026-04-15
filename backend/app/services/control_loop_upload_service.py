"""Orquestación de carga Control Loop (wide → long → staging)."""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.adapters.control_loop_plan_repo import insert_rejects, insert_valid_metric_rows
from app.config.control_loop_lob_mapping import resolve_excel_line_to_canonical
from app.services.control_loop_geo import normalize_city_control_loop, normalize_country_control_loop
from app.services.control_loop_projection_parser import (
    coerce_numeric_value,
    parse_control_loop_csv,
    parse_control_loop_excel,
)

logger = logging.getLogger(__name__)

_PERIOD = re.compile(r"^\d{4}-\d{2}$")


def run_control_loop_upload(
    file_content: bytes,
    filename: str,
    plan_version: Optional[str] = None,
) -> Dict[str, Any]:
    fn = (filename or "").lower()
    if fn.endswith((".xlsx", ".xls")):
        raw_rows, months = parse_control_loop_excel(file_content, filename)
    elif fn.endswith(".csv"):
        raw_rows, months = parse_control_loop_csv(file_content, filename)
    else:
        raise ValueError("Use Excel .xlsx o CSV.")

    pv = plan_version or f"control_loop_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    batch_id = uuid.uuid4()

    valid_payload: List[Dict[str, Any]] = []
    rejects: List[Dict[str, Any]] = []
    seen: set = set()

    rows_read = len(raw_rows)
    unmapped_samples: List[str] = []

    for i, row in enumerate(raw_rows):
        period = str(row.get("period", "")).strip()
        if not _PERIOD.match(period):
            rejects.append(
                {
                    "reject_kind": "STRUCTURE",
                    "reason": "period_invalid",
                    "detail": {"row_index": i, "period": period, "raw": row},
                }
            )
            continue
        try:
            val = coerce_numeric_value(row.get("raw_value"))
        except ValueError as e:
            rejects.append(
                {
                    "reject_kind": "STRUCTURE",
                    "reason": "value_not_numeric",
                    "detail": {"row_index": i, "error": str(e), "raw": row},
                }
            )
            continue

        country = normalize_country_control_loop(row.get("country"))
        city = normalize_city_control_loop(row.get("city"))
        if not country or not city:
            rejects.append(
                {
                    "reject_kind": "STRUCTURE",
                    "reason": "missing_geo",
                    "detail": {"row_index": i, "country": row.get("country"), "city": row.get("city")},
                }
            )
            continue

        lob_raw = row.get("linea_negocio")
        lob_excel = str(lob_raw).strip() if lob_raw is not None else ""
        canonical, alias_key = resolve_excel_line_to_canonical(lob_excel)
        if not canonical:
            rejects.append(
                {
                    "reject_kind": "UNMAPPED_LOB",
                    "reason": "linea_negocio_not_in_catalog",
                    "detail": {"row_index": i, "linea_negocio": lob_excel},
                }
            )
            if lob_excel and lob_excel not in unmapped_samples and len(unmapped_samples) < 30:
                unmapped_samples.append(lob_excel)
            continue

        metric = row.get("metric")
        if metric not in ("trips", "revenue", "active_drivers"):
            rejects.append(
                {
                    "reject_kind": "STRUCTURE",
                    "reason": "invalid_metric",
                    "detail": {"row_index": i, "metric": metric},
                }
            )
            continue

        key = (pv, period, country, city, canonical, metric)
        if key in seen:
            rejects.append(
                {
                    "reject_kind": "DUPLICATE",
                    "reason": "duplicate_in_file_or_existing",
                    "detail": {"key": [pv, period, country, city, canonical, metric]},
                }
            )
            continue
        seen.add(key)

        valid_payload.append(
            {
                "period": period,
                "country": country,
                "city": city,
                "linea_negocio_excel": lob_excel,
                "linea_negocio_canonica": canonical,
                "metric": metric,
                "value_numeric": val,
                "source_sheet": row.get("source_sheet"),
            }
        )

    inserted, dup_db = insert_valid_metric_rows(batch_id, pv, valid_payload)
    rej_count = insert_rejects(batch_id, pv, rejects)

    return {
        "success": True,
        "plan_version": pv,
        "upload_batch_id": str(batch_id),
        "rows_read": rows_read,
        "rows_valid_inserted": inserted,
        "rows_invalid": len(rejects),
        "rows_duplicate_skipped": dup_db + sum(1 for r in rejects if r.get("reject_kind") == "DUPLICATE"),
        "unmapped_lob_lines_sample": unmapped_samples,
        "months_detected": months,
        "reject_rows_logged": rej_count,
        "message": "Carga Control Loop procesada (staging).",
    }
