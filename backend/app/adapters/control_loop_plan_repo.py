"""Persistencia staging Control Loop (proyección agregada)."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Tuple

from app.db.connection import get_db

logger = logging.getLogger(__name__)


def insert_rejects(
    upload_batch_id: uuid.UUID,
    plan_version: str,
    rows: List[Dict[str, Any]],
) -> int:
    if not rows:
        return 0
    inserted = 0
    with get_db() as conn:
        cur = conn.cursor()
        for r in rows:
            cur.execute(
                """
                INSERT INTO staging.control_loop_plan_reject
                (upload_batch_id, plan_version, reject_kind, reason, row_detail)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                """,
                (
                    str(upload_batch_id),
                    plan_version,
                    r.get("reject_kind", "UNKNOWN"),
                    r.get("reason", ""),
                    json.dumps(r.get("detail") or {}, default=str),
                ),
            )
            inserted += cur.rowcount
        conn.commit()
        cur.close()
    return inserted


def insert_valid_metric_rows(
    upload_batch_id: uuid.UUID,
    plan_version: str,
    rows: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Inserta filas válidas con ON CONFLICT DO NOTHING.
    Retorna (filas_insertadas, duplicados_omitidos).
    """
    if not rows:
        return 0, 0
    inserted = 0
    with get_db() as conn:
        cur = conn.cursor()
        for r in rows:
            cur.execute(
                """
                INSERT INTO staging.control_loop_plan_metric_long (
                    upload_batch_id, plan_version, period, country, city,
                    linea_negocio_excel, linea_negocio_canonica, metric, value_numeric, source_sheet
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (plan_version, period, country, city, linea_negocio_canonica, metric)
                DO NOTHING
                """,
                (
                    str(upload_batch_id),
                    plan_version,
                    r["period"],
                    r["country"],
                    r["city"],
                    r["linea_negocio_excel"],
                    r["linea_negocio_canonica"],
                    r["metric"],
                    r["value_numeric"],
                    r.get("source_sheet"),
                ),
            )
            if cur.rowcount > 0:
                inserted += 1
        duplicates = len(rows) - inserted
        conn.commit()
        cur.close()
    return inserted, duplicates
