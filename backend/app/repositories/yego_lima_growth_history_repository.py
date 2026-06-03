"""
YEGO Lima Growth Tower — History Bootstrap Repository.

Responsabilidades:
- Upsert daily driver aggregates into growth.yango_lima_driver_history_daily
- Upsert weekly driver aggregates into growth.yango_lima_driver_history_weekly
- Consultar resumenes de bootstrap historico
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)


def upsert_history_daily(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    from psycopg2.extras import execute_values

    with get_db() as conn:
        cur = conn.cursor()
        execute_values(cur, """
            INSERT INTO growth.yango_lima_driver_history_daily (
                date, driver_profile_id,
                completed_orders, gross_revenue,
                source, last_calculated_at
            ) VALUES %s
            ON CONFLICT (date, driver_profile_id) DO UPDATE SET
                completed_orders = EXCLUDED.completed_orders,
                gross_revenue = EXCLUDED.gross_revenue,
                last_calculated_at = now()
        """, [
            (r["date"], r["driver_profile_id"],
             r["completed_orders"], r["gross_revenue"],
             r.get("source", "trips_bootstrap"))
            for r in rows
        ], template="(%s, %s, %s, %s, %s, now())", page_size=1000)
        conn.commit()
        return cur.rowcount


def upsert_history_weekly(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    from psycopg2.extras import execute_values

    with get_db() as conn:
        cur = conn.cursor()
        execute_values(cur, """
            INSERT INTO growth.yango_lima_driver_history_weekly (
                week_start_date, week_end_date, driver_profile_id,
                completed_orders_week, gross_revenue_week,
                active_days, avg_orders_per_active_day,
                avg_orders_4w, avg_orders_8w, avg_orders_12w,
                best_week_12w, historical_band,
                source, last_calculated_at
            ) VALUES %s
            ON CONFLICT (week_start_date, driver_profile_id) DO UPDATE SET
                week_end_date = EXCLUDED.week_end_date,
                completed_orders_week = EXCLUDED.completed_orders_week,
                gross_revenue_week = EXCLUDED.gross_revenue_week,
                active_days = EXCLUDED.active_days,
                avg_orders_per_active_day = EXCLUDED.avg_orders_per_active_day,
                avg_orders_4w = EXCLUDED.avg_orders_4w,
                avg_orders_8w = EXCLUDED.avg_orders_8w,
                avg_orders_12w = EXCLUDED.avg_orders_12w,
                best_week_12w = EXCLUDED.best_week_12w,
                historical_band = EXCLUDED.historical_band,
                last_calculated_at = now()
        """, [
            (r["week_start_date"], r["week_end_date"], r["driver_profile_id"],
             r["completed_orders_week"], r.get("gross_revenue_week"),
             r["active_days"], r.get("avg_orders_per_active_day"),
             r.get("avg_orders_4w"), r.get("avg_orders_8w"), r.get("avg_orders_12w"),
             r.get("best_week_12w"), r.get("historical_band"),
             r.get("source", "trips_bootstrap"))
            for r in rows
        ], template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())", page_size=1000)
        conn.commit()
        return cur.rowcount


def get_history_summary() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT
                COUNT(*) AS daily_rows,
                MIN(date) AS min_date,
                MAX(date) AS max_date,
                COUNT(DISTINCT driver_profile_id) AS unique_drivers
            FROM growth.yango_lima_driver_history_daily
        """)
        daily_stats = dict(cur.fetchone() or {})

        cur.execute("""
            SELECT
                COUNT(*) AS weekly_rows,
                MIN(week_start_date) AS min_week,
                MAX(week_start_date) AS max_week,
                COUNT(DISTINCT driver_profile_id) AS unique_drivers
            FROM growth.yango_lima_driver_history_weekly
        """)
        weekly_stats = dict(cur.fetchone() or {})

        cur.execute("""
            SELECT
                COALESCE(historical_band, 'NO_HISTORY') AS band,
                COUNT(*) AS driver_count
            FROM growth.yango_lima_driver_history_weekly
            GROUP BY historical_band
            ORDER BY COUNT(*) DESC
        """)
        band_dist = [dict(r) for r in cur.fetchall()]

        return {
            "daily": daily_stats,
            "weekly": weekly_stats,
            "historical_band_distribution": band_dist,
        }


def get_history_sample(limit: int = 20) -> list:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT
                week_start_date,
                driver_profile_id,
                completed_orders_week,
                active_days,
                avg_orders_4w,
                avg_orders_8w,
                avg_orders_12w,
                best_week_12w,
                historical_band
            FROM growth.yango_lima_driver_history_weekly
            ORDER BY week_start_date DESC, completed_orders_week DESC
            LIMIT %(limit)s
        """, {"limit": min(limit, 100)})

        result = []
        for row in cur.fetchall():
            item = dict(row)
            if item.get("week_start_date"):
                item["week_start_date"] = item["week_start_date"].isoformat()
            if item.get("driver_profile_id") and len(item["driver_profile_id"]) > 8:
                item["driver_profile_id"] = item["driver_profile_id"][:4] + "****" + item["driver_profile_id"][-4:]
            result.append(item)
        return result
