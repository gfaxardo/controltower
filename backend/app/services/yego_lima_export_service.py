"""
LG-EXP-1A — Export Service
Reads serving facts / certified endpoints. Generates CSV. Registers audit log.
NO recalculation. NO runtime heavy. NO monstrous joins.
"""
from __future__ import annotations
import csv
import io
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_EXPORT = "growth.yego_lima_export_audit"
TABLE_DS = "growth.yango_lima_driver_state_snapshot"
TABLE_LC = "growth.yego_lima_driver_lifecycle_daily"
TABLE_TAX = "growth.yego_lima_driver_taxonomy_v2_daily"
TABLE_PR = "growth.yango_lima_program_eligibility_daily"

MAX_ROWS = 10000
SAFE_COLUMNS = [
    "driver_id", "driver_name", "phone", "city", "park",
    "lifecycle", "segment", "activity_status", "value_tier", "momentum",
    "program", "movement_status", "rna_status", "contactability",
    "last_activity", "trips_7d", "trips_30d",
    "explanation_summary",
]

SOURCE_SQL = {
    "driver_explorer": f"""
        SELECT DISTINCT
            ds.driver_profile_id AS driver_id,
            ds.driver_name,
            ds.phone,
            ds.city,
            ds.park_id AS park,
            COALESCE(lc.lifecycle_status, ds.lifecycle_status) AS lifecycle,
            COALESCE(tx.operational_status, ds.segment) AS segment,
            tx.activity_status,
            tx.value_tier,
            tx.momentum_state AS momentum,
            pr.program_code AS program,
            ds.movement_status,
            ds.is_rna AS rna_status,
            ds.contactability,
            COALESCE(ds.last_trip_date::text, ds.last_activity_date::text) AS last_activity,
            lc.completed_trips_7d AS trips_7d,
            lc.completed_trips_30d AS trips_30d,
            lc.lifecycle_reason AS explanation_summary
        FROM {TABLE_DS} ds
        LEFT JOIN {TABLE_LC} lc ON ds.driver_profile_id = lc.driver_profile_id
        LEFT JOIN {TABLE_TAX} tx ON ds.driver_profile_id = tx.driver_profile_id
        LEFT JOIN {TABLE_PR} pr ON ds.driver_profile_id = pr.driver_profile_id
        WHERE ds.snapshot_date = (SELECT MAX(snapshot_date) FROM {TABLE_DS})
    """,
}


def _build_query(source: str, filters: Dict[str, Any]) -> tuple:
    base = SOURCE_SQL.get(source, SOURCE_SQL["driver_explorer"])
    conditions = []
    params = {}

    if filters.get("program"):
        conditions.append("pr.program_code = %(program)s")
        params["program"] = filters["program"]
    if filters.get("lifecycle"):
        conditions.append("COALESCE(lc.lifecycle_status, ds.lifecycle_status) = %(lifecycle)s")
        params["lifecycle"] = filters["lifecycle"]
    if filters.get("segment"):
        conditions.append("COALESCE(tx.operational_status, ds.segment) = %(segment)s")
        params["segment"] = filters["segment"]
    if filters.get("rna") is not None:
        val = filters["rna"]
        if isinstance(val, bool):
            conditions.append("ds.is_rna = %(rna)s")
            params["rna"] = val
    if filters.get("search"):
        conditions.append("(ds.driver_profile_id ILIKE %(search)s OR ds.driver_name ILIKE %(search)s)")
        params["search"] = f"%{filters['search']}%"

    sql = base
    if conditions:
        sql = f"SELECT * FROM ({base}) _filtered WHERE " + " AND ".join(conditions)

    max_rows = min(int(filters.get("max_rows", MAX_ROWS)), MAX_ROWS)
    sql += f" LIMIT {max_rows}"

    return sql, params


def create_export(source: str, filters: Dict[str, Any], columns: Optional[List[str]] = None,
                  requested_by: Optional[str] = None, export_reason: Optional[str] = None) -> Dict[str, Any]:
    export_id = f"LG-EXP-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    selected_columns = columns or SAFE_COLUMNS
    selected_columns = [c for c in selected_columns if c in SAFE_COLUMNS]
    if not selected_columns:
        selected_columns = SAFE_COLUMNS[:12]

    sql, params = _build_query(source, filters)
    warnings = []

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description] if cur.description else []

    if len(rows) >= MAX_ROWS:
        warnings.append(f"Export truncated at {MAX_ROWS} rows. Results may exceed limit.")

    output = io.StringIO()
    writer = csv.writer(output)
    header = [c for c in selected_columns if c in col_names]
    writer.writerow(header)
    col_indices = [col_names.index(c) for c in header]

    for row in rows:
        writer.writerow([row[i] for i in col_indices])

    csv_content = output.getvalue()
    output.close()
    file_size = len(csv_content.encode("utf-8"))

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_EXPORT} (export_id, source, filters_json, selected_columns_json,
                                        rows_count, generated_at, generated_by, status, warnings_json, file_size_bytes)
            VALUES (%(eid)s, %(src)s, %(filt)s, %(cols)s, %(rows)s, %(gen)s, %(by)s, %(status)s, %(warn)s, %(size)s)
        """, {
            "eid": export_id, "src": source, "filt": json.dumps(filters),
            "cols": json.dumps(selected_columns), "rows": len(rows),
            "gen": now, "by": requested_by, "status": "COMPLETED",
            "warn": json.dumps(warnings), "size": file_size,
        })

    return {
        "export_id": export_id,
        "status": "COMPLETED",
        "source": source,
        "columns": selected_columns,
        "rows_count": len(rows),
        "generated_at": now.isoformat(),
        "warnings": warnings,
        "csv_content": csv_content,
        "file_size_bytes": file_size,
    }


def get_export_status(export_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT export_id, source, rows_count, generated_at, status, warnings_json, file_size_bytes FROM {TABLE_EXPORT} WHERE export_id = %(eid)s", {"eid": export_id})
        row = cur.fetchone()
        if not row:
            return {"export_id": export_id, "found": False}
        return {
            "export_id": row[0], "source": row[1], "rows_count": row[2],
            "generated_at": str(row[3]) if row[3] else None, "status": row[4],
            "warnings": json.loads(row[5]) if row[5] else [],
            "file_size_bytes": row[6],
        }


def get_export_options() -> Dict[str, Any]:
    return {
        "sources": ["driver_explorer", "programs", "segments", "movement", "rna"],
        "safe_columns": SAFE_COLUMNS,
        "max_rows": MAX_ROWS,
    }
