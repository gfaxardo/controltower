"""
YEGO Lima Growth — Risk Panel Service (LG-2.6 V1).

Deterministic risk calculation from existing operational data.
NO predicciones. NO impacto. NO revenue. NO atribucion.
"""

from __future__ import annotations

import logging
from datetime import date as date_type, datetime, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

from app.config.yego_lima_risk_registry import (
    CAPACITY_RISK,
    QUEUE_RISK,
    EXPORT_RISK,
    SYNC_RISK,
    DATA_QUALITY_RISK,
    RISK_THRESHOLDS,
    evaluate_level,
    evaluate_score,
)

logger = logging.getLogger(__name__)

TABLE_CAPACITY = "growth.yego_lima_capacity_config"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"
TABLE_RESULT = "growth.yego_lima_loopcontrol_result_sync"


def _calculate_capacity_risk(date_str: str, conn) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        f"""
        SELECT COALESCE(SUM(agents * capacity_per_agent), 0) as total_capacity
        FROM {TABLE_CAPACITY}
        WHERE is_active = true AND config_date IS NULL
    """
    )
    total_capacity = int(cur.fetchone()["total_capacity"])

    cur.execute(
        f"""
        SELECT COUNT(*) as cnt FROM {TABLE_QUEUE}
        WHERE assignment_date = %(d)s
    """,
        {"d": date_str},
    )
    total_opportunities = cur.fetchone()["cnt"]

    if total_opportunities == 0:
        level = "GREEN"
        score = 1.0
        ratio = 1.0
    else:
        ratio = total_capacity / total_opportunities if total_opportunities > 0 else 1.0
        level = evaluate_level(CAPACITY_RISK, ratio)
        score = evaluate_score(CAPACITY_RISK, ratio)

    return {
        "risk_code": CAPACITY_RISK,
        "risk_level": level,
        "risk_score": score,
        "explanation": f"Capacity {total_capacity} vs Opportunities {total_opportunities} (ratio {ratio:.2f})",
        "metrics": {
            "total_capacity": total_capacity,
            "total_opportunities": total_opportunities,
            "capacity_ratio": round(ratio, 4),
        },
    }


def _calculate_queue_risk(date_str: str, conn) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready,
            SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held,
            SUM(CASE WHEN queue_status = 'EXPORTED' THEN 1 ELSE 0 END) as exported
        FROM {TABLE_QUEUE}
        WHERE assignment_date = %(d)s
    """,
        {"d": date_str},
    )
    row = cur.fetchone()
    total = row["total"] or 0
    ready = row["ready"] or 0
    held = row["held"] or 0
    exported = row["exported"] or 0

    if total == 0:
        level = "GREEN"
        score = 1.0
        held_rate = 0.0
    else:
        held_rate = held / total
        level = evaluate_level(QUEUE_RISK, held_rate)
        score = evaluate_score(QUEUE_RISK, held_rate)

    return {
        "risk_code": QUEUE_RISK,
        "risk_level": level,
        "risk_score": score,
        "explanation": f"HELD {held}/{total} ({held_rate:.1%})",
        "metrics": {
            "total_in_queue": total,
            "ready_count": ready,
            "held_count": held,
            "held_rate": round(held_rate, 4),
        },
    }


def _calculate_export_risk(date_str: str, conn) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        f"""
        SELECT
            SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready,
            SUM(CASE WHEN queue_status = 'EXPORTED' THEN 1 ELSE 0 END) as exported
        FROM {TABLE_QUEUE}
        WHERE assignment_date = %(d)s
    """,
        {"d": date_str},
    )
    row = cur.fetchone()
    ready = row["ready"] or 0
    exported = row["exported"] or 0
    exportable = ready + exported

    if exportable == 0:
        level = "GREEN"
        score = 1.0
        export_rate = 1.0
    else:
        export_rate = exported / exportable
        level = evaluate_level(EXPORT_RISK, export_rate)
        score = evaluate_score(EXPORT_RISK, export_rate)

    return {
        "risk_code": EXPORT_RISK,
        "risk_level": level,
        "risk_score": score,
        "explanation": f"EXPORTED {exported}/{exportable} exportable ({export_rate:.1%})",
        "metrics": {
            "ready_for_export": ready,
            "already_exported": exported,
            "export_rate": round(export_rate, 4),
        },
    }


def _calculate_sync_risk(date_str: str, conn) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN assignment_queue_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
            SUM(CASE WHEN assignment_queue_id IS NULL THEN 1 ELSE 0 END) as unmatched
        FROM {TABLE_RESULT}
        WHERE last_call_at::date = %(d)s
    """,
        {"d": date_str},
    )
    row = cur.fetchone()
    total = row["total"] or 0
    matched = row["matched"] or 0
    unmatched = row["unmatched"] or 0

    if total == 0:
        level = "GREEN"
        score = 1.0
        unmatched_rate = 0.0
    else:
        unmatched_rate = unmatched / total
        level = evaluate_level(SYNC_RISK, unmatched_rate)
        score = evaluate_score(SYNC_RISK, unmatched_rate)

    return {
        "risk_code": SYNC_RISK,
        "risk_level": level,
        "risk_score": score,
        "explanation": f"Unmatched {unmatched}/{total} results ({unmatched_rate:.1%})",
        "metrics": {
            "total_results": total,
            "matched_queue_count": matched,
            "unmatched_count": unmatched,
            "unmatched_rate": round(unmatched_rate, 4),
        },
    }


def _calculate_data_quality_risk(date_str: str, conn) -> Dict[str, Any]:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN phone IS NULL OR phone = '' THEN 1 ELSE 0 END) as missing_phone,
            SUM(CASE WHEN driver_name IS NULL OR driver_name = '' THEN 1 ELSE 0 END) as missing_driver
        FROM {TABLE_QUEUE}
        WHERE assignment_date = %(d)s
    """,
        {"d": date_str},
    )
    row = cur.fetchone()
    total = row["total"] or 0
    missing_phone = row["missing_phone"] or 0
    missing_driver = row["missing_driver"] or 0
    total_missing = missing_phone + missing_driver

    if total == 0:
        level = "GREEN"
        score = 1.0
        missing_rate = 0.0
    else:
        missing_rate = total_missing / (total * 2)
        level = evaluate_level(DATA_QUALITY_RISK, missing_rate)
        score = evaluate_score(DATA_QUALITY_RISK, missing_rate)

    return {
        "risk_code": DATA_QUALITY_RISK,
        "risk_level": level,
        "risk_score": score,
        "explanation": f"Missing phone {missing_phone}, missing driver {missing_driver} of {total} records ({missing_rate:.1%})",
        "metrics": {
            "total_records": total,
            "missing_phone": missing_phone,
            "missing_driver": missing_driver,
            "missing_rate": round(missing_rate, 4),
        },
    }


def get_risk_panel(date_str: str) -> Dict[str, Any]:
    with get_db() as conn:
        risks = [
            _calculate_capacity_risk(date_str, conn),
            _calculate_queue_risk(date_str, conn),
            _calculate_export_risk(date_str, conn),
            _calculate_sync_risk(date_str, conn),
            _calculate_data_quality_risk(date_str, conn),
        ]

    red_count = sum(1 for r in risks if r["risk_level"] == "RED")
    yellow_count = sum(1 for r in risks if r["risk_level"] == "YELLOW")
    green_count = sum(1 for r in risks if r["risk_level"] == "GREEN")

    if red_count > 0:
        overall = "RED"
    elif yellow_count >= 3:
        overall = "RED"
    elif yellow_count >= 2:
        overall = "YELLOW"
    else:
        overall = "GREEN"

    avg_score = round(sum(r["risk_score"] for r in risks) / len(risks), 2)

    return {
        "date": date_str,
        "overall_risk": overall,
        "overall_score": avg_score,
        "summary": f"{green_count} green, {yellow_count} yellow, {red_count} red",
        "risks": risks,
    }
