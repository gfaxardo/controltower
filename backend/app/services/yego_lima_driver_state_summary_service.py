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
            "SELECT lifecycle_state, performance_state, retention_state "
            "FROM growth.yango_lima_driver_state_snapshot "
            "WHERE snapshot_date = %(ld)s",
            {"ld": latest},
        )
        rows = cur.fetchall()

        lc_counts: Dict[str, int] = {}
        pf_counts: Dict[str, int] = {}
        rt_counts: Dict[str, int] = {}
        for r in rows:
            lc = r.get("lifecycle_state") or "UNKNOWN"
            pf = r.get("performance_state") or "UNKNOWN"
            rt = r.get("retention_state") or "UNKNOWN"
            lc_counts[lc] = lc_counts.get(lc, 0) + 1
            pf_counts[pf] = pf_counts.get(pf, 0) + 1
            rt_counts[rt] = rt_counts.get(rt, 0) + 1

        by_lifecycle = [
            {"state": k, "count": v}
            for k, v in sorted(lc_counts.items(), key=lambda x: -x[1])
        ]
        by_performance = [
            {"state": k, "count": v}
            for k, v in sorted(pf_counts.items(), key=lambda x: -x[1])
        ]
        by_retention = [
            {"state": k, "count": v}
            for k, v in sorted(rt_counts.items(), key=lambda x: -x[1])
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
