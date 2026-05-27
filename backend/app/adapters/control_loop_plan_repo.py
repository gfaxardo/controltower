"""Persistencia staging Control Loop (proyección agregada)."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Tuple

from psycopg2.extras import execute_values

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
    Inserta filas válidas con ON CONFLICT DO NOTHING usando batch insert
    (psycopg2.extras.execute_values) para performance con CSVs grandes.

    Fase 0.0: persiste columnas ownership (jefe_producto, producto, estado)
    si están presentes en los rows.
    Fase 1.0.2: batch insert vía execute_values (true multi-row INSERT).

    Retorna (filas_insertadas, duplicados_omitidos).
    """
    if not rows:
        return 0, 0

    # Build VALUES tuples as list
    values = []
    for r in rows:
        values.append((
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
            r.get("jefe_producto"),
            r.get("producto"),
            r.get("estado"),
        ))

    with get_db() as conn:
        cur = conn.cursor()
        
        # Count before
        cur.execute(
            "SELECT COUNT(*) FROM staging.control_loop_plan_metric_long WHERE plan_version = %s",
            (plan_version,),
        )
        count_before = cur.fetchone()[0]
        
        execute_values(
            cur,
            """
            INSERT INTO staging.control_loop_plan_metric_long (
                upload_batch_id, plan_version, period, country, city,
                linea_negocio_excel, linea_negocio_canonica, metric, value_numeric, source_sheet,
                jefe_producto, producto, estado
            ) VALUES %s
            ON CONFLICT (plan_version, period, country, city, linea_negocio_canonica, metric)
            DO NOTHING
            """,
            values,
            template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            page_size=1000,
        )
        conn.commit()
        
        # Count after
        cur.execute(
            "SELECT COUNT(*) FROM staging.control_loop_plan_metric_long WHERE plan_version = %s",
            (plan_version,),
        )
        count_after = cur.fetchone()[0]
        cur.close()

    inserted = count_after - count_before
    duplicates = len(rows) - inserted
    return inserted, duplicates
