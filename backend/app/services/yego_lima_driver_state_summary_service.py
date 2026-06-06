"""
YEGO Lima Growth — Driver State Summary Service (LG-C1.4-P0).
"""
from __future__ import annotations
import logging
from typing import Any, Dict
from psycopg2.extras import RealDictCursor
from app.db.connection import get_db
from app.services.freshness_service import compute_freshness
from app.services.lima_growth_explainability_service import explain_kpi

logger = logging.getLogger(__name__)


def get_driver_state_summary(date: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            "SELECT MAX(snapshot_date) as latest, COUNT(*) as total "
            "FROM growth.yango_lima_driver_state_snapshot "
            "WHERE snapshot_date <= %(d)s", {"d": date}
        )
        row = cur.fetchone()
        if not row or not row["latest"]:
            return {"error": "No driver state snapshot found", "date": date}

        latest = str(row["latest"])
        total = row["total"]

        cur.execute(
            "SELECT lifecycle_state, COUNT(*) as cnt "
            "FROM growth.yango_lima_driver_state_snapshot "
            "WHERE snapshot_date = %(ld)s "
            "GROUP BY lifecycle_state ORDER BY cnt DESC",
            {"ld": latest},
        )
        by_lifecycle = [
            {"state": r["lifecycle_state"] or "UNKNOWN", "count": r["cnt"]}
            for r in cur.fetchall()
        ]

        cur.execute(
            "SELECT performance_state, COUNT(*) as cnt "
            "FROM growth.yango_lima_driver_state_snapshot "
            "WHERE snapshot_date = %(ld)s "
            "GROUP BY performance_state ORDER BY cnt DESC",
            {"ld": latest},
        )
        by_performance = [
            {"state": r["performance_state"] or "UNKNOWN", "count": r["cnt"]}
            for r in cur.fetchall()
        ]

        cur.execute(
            "SELECT retention_state, COUNT(*) as cnt "
            "FROM growth.yango_lima_driver_state_snapshot "
            "WHERE snapshot_date = %(ld)s "
            "GROUP BY retention_state ORDER BY cnt DESC",
            {"ld": latest},
        )
        by_retention = [
            {"state": r["retention_state"] or "UNKNOWN", "count": r["cnt"]}
            for r in cur.fetchall()
        ]

    return {
        "date": date,
        "total_drivers": total,
        "latest_date": latest,
        "by_lifecycle_state": by_lifecycle,
        "by_performance_state": by_performance,
        "by_retention_state": by_retention,
        "freshness": {
            "driver_snapshot": compute_freshness("driver_snapshot", latest, "growth.yango_lima_driver_state_snapshot"),
        },
        "explainability": {
            "total_drivers": explain_kpi("total_drivers", total, None, {}),
        },
    }
