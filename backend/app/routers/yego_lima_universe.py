"""
YEGO Lima Growth — Universe Governance Router (Fase PP-1).

Audits and exposes all operational universes.
"""

import logging
from datetime import date as date_type, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yego-lima-growth/universe", tags=["yego-lima-growth-universe"])

TABLE_HISTORY_DAILY = "growth.yango_lima_driver_history_daily"
TABLE_HISTORY_WEEKLY = "growth.yango_lima_driver_history_weekly"
TABLE_360 = "growth.yango_lima_driver_360_daily"
TABLE_STATE = "growth.yango_lima_driver_state_snapshot"
TABLE_OPPORTUNITY = "growth.yango_lima_daily_opportunity_list"


def _count_active(cur, table: str, date_col: str, from_date: str, to_date: str, orders_col: str = "completed_orders") -> Dict[str, Any]:
    cur.execute(f"""
        SELECT COUNT(DISTINCT driver_profile_id) AS drivers,
               COALESCE(SUM({orders_col}), 0) AS total_orders,
               ROUND(COALESCE(SUM({orders_col})::numeric / NULLIF(COUNT(DISTINCT driver_profile_id), 0), 0), 1) AS orders_per_driver,
               MIN({date_col}) AS min_date,
               MAX({date_col}) AS max_date
        FROM {table}
        WHERE {date_col} >= %(from_d)s AND {date_col} <= %(to_d)s
          AND {orders_col} > 0
    """, {"from_d": from_date, "to_d": to_date})
    r = cur.fetchone()
    return {
        "drivers_count": r["drivers"],
        "completed_orders": r["total_orders"],
        "trips_per_driver": r["orders_per_driver"],
        "min_date": str(r["min_date"]),
        "max_date": str(r["max_date"]),
    }


def _count_active_with_supply(cur, date_str: str) -> Dict[str, Any]:
    cur.execute(f"""
        SELECT COUNT(DISTINCT driver_profile_id) AS drivers,
               SUM(completed_orders) AS total_orders,
               SUM(supply_hours) AS total_supply,
               ROUND(SUM(completed_orders)::numeric / NULLIF(COUNT(DISTINCT driver_profile_id), 0), 1) AS orders_per_driver,
               ROUND(SUM(completed_orders)::numeric / NULLIF(SUM(supply_hours), 0), 2) AS trips_per_supply_hour
        FROM {TABLE_360}
        WHERE date = %(d)s
    """, {"d": date_str})
    r = cur.fetchone()
    return {
        "active_drivers_day": r["drivers"],
        "completed_orders_day": r["total_orders"] or 0,
        "supply_hours_day": round(float(r["total_supply"] or 0), 2),
        "trips_per_active_driver_day": r["orders_per_driver"],
        "trips_per_supply_hour_day": r["trips_per_supply_hour"],
    }


def _count_weekly_kpis(cur, year: int, week: int) -> Dict[str, Any]:
    cur.execute(f"""
        SELECT EXTRACT(ISOYEAR FROM week_start_date)::int AS iso_year,
               EXTRACT(WEEK FROM week_start_date)::int AS iso_week,
               week_start_date,
               COUNT(DISTINCT driver_profile_id) AS drivers,
               SUM(completed_orders_week) AS orders,
               ROUND(SUM(completed_orders_week)::numeric / NULLIF(COUNT(DISTINCT driver_profile_id), 0), 1) AS orders_per_driver
        FROM {TABLE_HISTORY_WEEKLY}
        WHERE EXTRACT(ISOYEAR FROM week_start_date) = %(yr)s
          AND EXTRACT(WEEK FROM week_start_date) = %(wk)s
        GROUP BY week_start_date
    """, {"yr": year, "wk": week})
    r = cur.fetchone()
    if not r:
        return {"iso_week_key": f"{year}-W{week:02d}", "error": "No data for this week"}

    return {
        "iso_week_key": f"{year}-W{week:02d}",
        "week_start_date": str(r["week_start_date"]),
        "completed_orders_week": r["orders"],
        "active_drivers_week": r["drivers"],
        "trips_per_active_driver_week": r["orders_per_driver"],
    }


@router.get("/governance-report")
async def governance_report(date: Optional[str] = Query(None)):
    if not date:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"SELECT MAX(snapshot_date) FROM {TABLE_STATE}")
            date = str(cur.fetchone()["max"])

    target_date = date
    td = date_type.fromisoformat(target_date)
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    cutover = settings.LIMA_GROWTH_API_CUTOVER_DATE

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ── REGISTERED UNIVERSE ──
        cur.execute(f"SELECT COUNT(DISTINCT driver_profile_id) FROM {TABLE_HISTORY_DAILY}")
        registered = cur.fetchone()["count"]

        # ── HISTORICAL UNIVERSE ──
        cur.execute(f"""
            SELECT COUNT(DISTINCT driver_profile_id) AS drivers,
                   COUNT(*) AS rows,
                   MIN(date) AS mi, MAX(date) AS ma
            FROM {TABLE_HISTORY_DAILY}
        """)
        hist = cur.fetchone()
        historical = {
            "drivers_count": hist["drivers"],
            "total_rows": hist["rows"],
            "min_date": str(hist["mi"]),
            "max_date": str(hist["ma"]),
            "source": "trips_2025/trips_2026 backfill (pre-cutover) + API (post-cutover)",
            "filter": f"park_id={park_id[:8]}****, condicion=Completado, conductor_id not null",
        }

        # ── ACTIVE UNIVERSES ──
        active_90d = _count_active(cur, TABLE_HISTORY_DAILY, "date",
                                   str(td - timedelta(days=90)), target_date)
        active_30d = _count_active(cur, TABLE_HISTORY_DAILY, "date",
                                   str(td - timedelta(days=30)), target_date)
        active_7d = _count_active(cur, TABLE_HISTORY_DAILY, "date",
                                  str(td - timedelta(days=6)), target_date)
        active_1d = _count_active(cur, TABLE_HISTORY_DAILY, "date", target_date, target_date)

        api_1d = _count_active_with_supply(cur, target_date)

        cur.execute(f"""
            SELECT opportunity_type, COUNT(DISTINCT driver_profile_id) AS drivers, COUNT(*) AS total
            FROM {TABLE_OPPORTUNITY}
            WHERE opportunity_date = %(d)s
            GROUP BY opportunity_type ORDER BY drivers DESC
        """, {"d": target_date})
        opportunity = {r["opportunity_type"]: {"drivers": r["drivers"], "total_rows": r["total"]}
                       for r in cur.fetchall()}

        warnings = []
        if active_7d["drivers_count"] < 1000:
            warnings.append(f"Weekly active ({active_7d['drivers_count']}) below expected min 1000")
        if active_30d["drivers_count"] < 2000:
            warnings.append(f"Monthly active ({active_30d['drivers_count']}) below expected min 2000")
        if active_1d["drivers_count"] == 0 and target_date >= cutover:
            warnings.append("Post-cutover: no history_daily data. Driver360 API may not be running.")

    return {
        "date": target_date,
        "filter_used": {
            "park_id": park_id[:8] + "****",
            "cutover_date": cutover,
            "note": "Pre-cutover: trips_2025/2026 filtered by park_id + completado. Post-cutover: Yango API Driver360.",
        },
        "registered_universe": {"drivers_count": registered, "source": "history_daily total unique drivers"},
        "historical_universe": historical,
        "active_90d": {**active_90d, "source": TABLE_HISTORY_DAILY},
        "active_30d": {**active_30d, "source": TABLE_HISTORY_DAILY},
        "active_7d": {**active_7d, "source": TABLE_HISTORY_DAILY},
        "active_1d_history": {**active_1d, "source": TABLE_HISTORY_DAILY},
        "active_1d_api360": {**api_1d, "source": TABLE_360},
        "opportunity_universe": {**opportunity, "source": TABLE_OPPORTUNITY},
        "warnings": warnings,
        "confidence": "high" if not warnings else "medium",
    }


@router.get("/daily-kpis")
async def daily_kpis(date: str = Query(..., description="Date YYYY-MM-DD")):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # From history_daily (primary source)
        daily = _count_active(cur, TABLE_HISTORY_DAILY, "date", date, date)

        # From 360_daily (supply data)
        api_daily = _count_active_with_supply(cur, date)

        # Combine: prefer history_daily for orders, 360 for supply
        return {
            "date": date,
            "completed_orders_day": daily.get("completed_orders", 0),
            "active_drivers_day": daily.get("drivers_count", 0),
            "trips_per_active_driver_day": daily.get("trips_per_driver", 0),
            "supply_hours_day": api_daily.get("supply_hours_day", 0),
            "trips_per_supply_hour_day": api_daily.get("trips_per_supply_hour_day"),
            "source_orders": TABLE_HISTORY_DAILY,
            "source_supply": TABLE_360,
        }


@router.get("/weekly-kpis")
async def weekly_kpis(iso_year: int = Query(..., ge=2025, le=2030),
                      iso_week: int = Query(..., ge=1, le=53)):
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        return _count_weekly_kpis(cur, iso_year, iso_week)
