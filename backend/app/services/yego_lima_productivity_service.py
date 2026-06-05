"""
YEGO Lima Growth — Productivity Governance Service (Fase 4A).

Reads from:
- growth.yango_lima_driver_360_daily (primary: supply + orders)
- growth.yango_lima_driver_history_daily (fallback: orders)
- growth.yango_lima_driver_history_weekly (fallback: weekly orders)

Writes to:
- growth.yango_lima_productivity_daily
- growth.yango_lima_productivity_weekly
- growth.yango_lima_productivity_monthly

KPIs:
1. Active Drivers (completed_orders > 0)
2. Trips per Active Driver
3. Supply Drivers (supply_hours > 0)
4. Supply Hours
5. Trips per Supply Hour
6. Supply -> Active Conversion
7. Trip Distribution (0-9, 10-19, 20-29, 30-39, 40-49, 50-69, 70-99, 100+)
"""

from __future__ import annotations
import calendar
import logging
from datetime import date as date_type, timedelta
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_360 = "growth.yango_lima_driver_360_daily"
TABLE_HIST_DAILY = "growth.yango_lima_driver_history_daily"
TABLE_HIST_WEEKLY = "growth.yango_lima_driver_history_weekly"
TABLE_PROD_DAILY = "growth.yango_lima_productivity_daily"
TABLE_PROD_WEEKLY = "growth.yango_lima_productivity_weekly"
TABLE_PROD_MONTHLY = "growth.yango_lima_productivity_monthly"

DISTRIBUTION_BUCKETS = [
    ("drivers_0_9", "completed_orders BETWEEN 0 AND 9"),
    ("drivers_10_19", "completed_orders BETWEEN 10 AND 19"),
    ("drivers_20_29", "completed_orders BETWEEN 20 AND 29"),
    ("drivers_30_39", "completed_orders BETWEEN 30 AND 39"),
    ("drivers_40_49", "completed_orders BETWEEN 40 AND 49"),
    ("drivers_50_69", "completed_orders BETWEEN 50 AND 69"),
    ("drivers_70_99", "completed_orders BETWEEN 70 AND 99"),
    ("drivers_100_plus", "completed_orders >= 100"),
]


def _safe_numeric(val, default=0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return float(default)


def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return int(default)


def _round4(val):
    if val is None:
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def _round2(val):
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


def _compute_rates(supply_drivers, supply_hours, active_drivers, completed_orders,
                   supply_active_both):
    supply_to_active = _round4(
        supply_active_both / supply_drivers) if supply_drivers else None
    trips_per_active = _round4(
        completed_orders / active_drivers) if active_drivers else None
    trips_per_supply_driver = _round4(
        completed_orders / supply_drivers) if supply_drivers else None
    trips_per_supply_hour = _round4(
        completed_orders / supply_hours) if supply_hours else None
    return supply_to_active, trips_per_active, trips_per_supply_driver, trips_per_supply_hour


def _iso_day_name(date_str: str) -> str:
    try:
        dt = date_type.fromisoformat(date_str)
        return calendar.day_name[dt.weekday()].upper()[:3]
    except Exception:
        return "UNK"


def _iso_week_key_from_date(date_str: str) -> Tuple[int, int, str]:
    dt = date_type.fromisoformat(date_str)
    iso_year, iso_week, _ = dt.isocalendar()
    return iso_year, iso_week, f"{iso_year}-W{iso_week:02d}"


def _iso_week_bounds(iso_year: int, iso_week: int) -> Tuple[str, str]:
    jan4 = date_type(iso_year, 1, 4)
    start_of_iso = jan4 - timedelta(days=jan4.isoweekday() - 1)
    start_of_target = start_of_iso + timedelta(weeks=iso_week - 1)
    end_of_target = start_of_target + timedelta(days=6)
    return start_of_target.isoformat(), end_of_target.isoformat()


def _get_daily_distribution(cur, source_table: str, date_str: str) -> Dict[str, int]:
    bucket_sql = ", ".join(
        f"COUNT(*) FILTER (WHERE {cond}) AS {name}"
        for name, cond in DISTRIBUTION_BUCKETS
    )
    cur.execute(f"""
        SELECT {bucket_sql}, COUNT(*) AS total_drivers
        FROM {source_table}
        WHERE date = %(d)s
    """, {"d": date_str})
    row = cur.fetchone()
    if not row:
        return {name: 0 for name, _ in DISTRIBUTION_BUCKETS}
    result = {name: _safe_int(row.get(name)) for name, _ in DISTRIBUTION_BUCKETS}
    result["total_drivers"] = _safe_int(row.get("total_drivers"))
    return result


def _get_weekly_distribution(cur, iso_year: int, iso_week: int) -> Dict[str, int]:
    bucket_sql = ", ".join(
        f"COUNT(*) FILTER (WHERE {cond}) AS {name}"
        for name, cond in DISTRIBUTION_BUCKETS
    )
    cur.execute(f"""
        WITH driver_week AS (
            SELECT driver_profile_id,
                   SUM(completed_orders) AS completed_orders
            FROM {TABLE_360}
            WHERE EXTRACT(ISOYEAR FROM date) = %(yr)s
              AND EXTRACT(WEEK FROM date) = %(wk)s
            GROUP BY driver_profile_id
        )
        SELECT {bucket_sql}, COUNT(*) AS total_drivers
        FROM driver_week
    """, {"yr": iso_year, "wk": iso_week})
    row = cur.fetchone()
    if not row:
        return {name: 0 for name, _ in DISTRIBUTION_BUCKETS}
    result = {name: _safe_int(row.get(name)) for name, _ in DISTRIBUTION_BUCKETS}
    result["total_drivers"] = _safe_int(row.get("total_drivers"))
    return result


def _get_monthly_distribution(cur, year: int, month: int) -> Dict[str, int]:
    bucket_sql = ", ".join(
        f"COUNT(*) FILTER (WHERE {cond}) AS {name}"
        for name, cond in DISTRIBUTION_BUCKETS
    )
    cur.execute(f"""
        WITH driver_month AS (
            SELECT driver_profile_id,
                   SUM(completed_orders) AS completed_orders
            FROM {TABLE_360}
            WHERE EXTRACT(YEAR FROM date) = %(yr)s
              AND EXTRACT(MONTH FROM date) = %(mo)s
            GROUP BY driver_profile_id
        )
        SELECT {bucket_sql}, COUNT(*) AS total_drivers
        FROM driver_month
    """, {"yr": year, "mo": month})
    row = cur.fetchone()
    if not row:
        return {name: 0 for name, _ in DISTRIBUTION_BUCKETS}
    result = {name: _safe_int(row.get(name)) for name, _ in DISTRIBUTION_BUCKETS}
    result["total_drivers"] = _safe_int(row.get("total_drivers"))
    return result


def _fallback_daily_orders(cur, date_str: str) -> Dict[str, Any]:
    cur.execute(f"""
        SELECT COUNT(DISTINCT driver_profile_id) AS active_drivers,
               COALESCE(SUM(completed_orders), 0) AS completed_orders,
               COALESCE(SUM(gross_revenue), 0) AS gross_revenue
        FROM {TABLE_HIST_DAILY}
        WHERE date = %(d)s AND completed_orders > 0
    """, {"d": date_str})
    row = cur.fetchone()
    if not row:
        return {"active_drivers": 0, "completed_orders": 0, "gross_revenue": 0}
    return {
        "active_drivers": _safe_int(row.get("active_drivers")),
        "completed_orders": _safe_int(row.get("completed_orders")),
        "gross_revenue": _safe_numeric(row.get("gross_revenue")),
    }


def _fallback_daily_distribution(cur, date_str: str) -> Dict[str, int]:
    return _get_daily_distribution(cur, TABLE_HIST_DAILY, date_str)


def _fallback_weekly_orders(cur, iso_year: int, iso_week: int) -> Dict[str, Any]:
    cur.execute(f"""
        SELECT COUNT(DISTINCT driver_profile_id) AS active_drivers,
               COALESCE(SUM(completed_orders_week), 0) AS completed_orders,
               COALESCE(SUM(gross_revenue_week), 0) AS gross_revenue
        FROM {TABLE_HIST_WEEKLY}
        WHERE EXTRACT(ISOYEAR FROM week_start_date) = %(yr)s
          AND EXTRACT(WEEK FROM week_start_date) = %(wk)s
    """, {"yr": iso_year, "wk": iso_week})
    row = cur.fetchone()
    if not row:
        return {"active_drivers": 0, "completed_orders": 0, "gross_revenue": 0}
    return {
        "active_drivers": _safe_int(row.get("active_drivers")),
        "completed_orders": _safe_int(row.get("completed_orders")),
        "gross_revenue": _safe_numeric(row.get("gross_revenue")),
    }


def _fallback_weekly_distribution(cur, iso_year: int, iso_week: int) -> Dict[str, int]:
    bucket_sql = ", ".join(
        f"COUNT(*) FILTER (WHERE {cond.replace('completed_orders', 'completed_orders_week')}) AS {name}"
        for name, cond in DISTRIBUTION_BUCKETS
    )
    cur.execute(f"""
        SELECT {bucket_sql}, COUNT(*) AS total_drivers
        FROM {TABLE_HIST_WEEKLY}
        WHERE EXTRACT(ISOYEAR FROM week_start_date) = %(yr)s
          AND EXTRACT(WEEK FROM week_start_date) = %(wk)s
    """, {"yr": iso_year, "wk": iso_week})
    row = cur.fetchone()
    if not row:
        return {name: 0 for name, _ in DISTRIBUTION_BUCKETS}
    result = {name: _safe_int(row.get(name)) for name, _ in DISTRIBUTION_BUCKETS}
    result["total_drivers"] = _safe_int(row.get("total_drivers"))
    return result


# ==============================================================
# GET Functions (read on-the-fly from source tables)
# ==============================================================

def get_daily_productivity(date_str: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE supply_hours > 0) AS supply_drivers,
                COALESCE(SUM(supply_hours), 0) AS supply_hours,
                COUNT(*) FILTER (WHERE completed_orders > 0) AS active_drivers,
                COALESCE(SUM(completed_orders), 0) AS completed_orders,
                COALESCE(SUM(gross_revenue), 0) AS gross_revenue,
                COUNT(*) FILTER (WHERE supply_hours > 0 AND completed_orders > 0) AS supply_active_both
            FROM {TABLE_360}
            WHERE date = %(d)s
        """, {"d": date_str})
        row = cur.fetchone()

        if not row:
            supply_drivers = 0
            supply_hours = 0.0
            active_drivers = 0
            completed_orders = 0
            gross_revenue = 0.0
            supply_active_both = 0
        else:
            supply_drivers = _safe_int(row.get("supply_drivers"))
            supply_hours = _safe_numeric(row.get("supply_hours"))
            active_drivers = _safe_int(row.get("active_drivers"))
            completed_orders = _safe_int(row.get("completed_orders"))
            gross_revenue = _safe_numeric(row.get("gross_revenue"))
            supply_active_both = _safe_int(row.get("supply_active_both"))

        use_fallback_orders = completed_orders == 0
        use_fallback_dist = completed_orders == 0

        if use_fallback_orders:
            fb = _fallback_daily_orders(cur, date_str)
            active_drivers = fb["active_drivers"]
            completed_orders = fb["completed_orders"]
            gross_revenue = fb["gross_revenue"]

        distribution = (_get_daily_distribution(cur, TABLE_360, date_str)
                        if not use_fallback_dist
                        else _fallback_daily_distribution(cur, date_str))

        supply_to_active, trips_per_active, trips_per_supply_driver, trips_per_supply_hour = \
            _compute_rates(supply_drivers, supply_hours, active_drivers, completed_orders,
                           supply_active_both)

        iso_year, iso_week, iso_week_key = _iso_week_key_from_date(date_str)
        dt = date_type.fromisoformat(date_str)

    return {
        "date": date_str,
        "iso_year": iso_year,
        "iso_week": iso_week,
        "iso_week_key": iso_week_key,
        "iso_day_of_week": dt.isoweekday(),
        "iso_day_name": calendar.day_name[dt.weekday()].upper()[:3],
        "supply_drivers": supply_drivers,
        "supply_hours": _round2(supply_hours),
        "active_drivers": active_drivers,
        "completed_orders": completed_orders,
        "gross_revenue": _round2(gross_revenue),
        "supply_to_active_driver_rate": supply_to_active,
        "trips_per_active_driver": trips_per_active,
        "trips_per_supply_driver": trips_per_supply_driver,
        "trips_per_supply_hour": trips_per_supply_hour,
        **distribution,
        "source_supply": TABLE_360,
        "source_orders": TABLE_HIST_DAILY if use_fallback_orders else TABLE_360,
    }


def get_weekly_productivity(iso_year: int, iso_week: int) -> Dict[str, Any]:
    week_key = f"{iso_year}-W{iso_week:02d}"
    week_start, week_end = _iso_week_bounds(iso_year, iso_week)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            WITH driver_week AS (
                SELECT
                    driver_profile_id,
                    SUM(supply_hours) AS supply_hours,
                    SUM(completed_orders) AS completed_orders,
                    SUM(gross_revenue) AS gross_revenue
                FROM {TABLE_360}
                WHERE EXTRACT(ISOYEAR FROM date) = %(yr)s
                  AND EXTRACT(WEEK FROM date) = %(wk)s
                GROUP BY driver_profile_id
            )
            SELECT
                COUNT(*) FILTER (WHERE supply_hours > 0) AS supply_drivers,
                COALESCE(SUM(supply_hours), 0) AS supply_hours,
                COUNT(*) FILTER (WHERE completed_orders > 0) AS active_drivers,
                COALESCE(SUM(completed_orders), 0) AS completed_orders,
                COALESCE(SUM(gross_revenue), 0) AS gross_revenue,
                COUNT(*) FILTER (WHERE supply_hours > 0 AND completed_orders > 0) AS supply_active_both
            FROM driver_week
        """, {"yr": iso_year, "wk": iso_week})
        row = cur.fetchone()

        if not row:
            supply_drivers = 0
            supply_hours = 0.0
            active_drivers = 0
            completed_orders = 0
            gross_revenue = 0.0
            supply_active_both = 0
        else:
            supply_drivers = _safe_int(row.get("supply_drivers"))
            supply_hours = _safe_numeric(row.get("supply_hours"))
            active_drivers = _safe_int(row.get("active_drivers"))
            completed_orders = _safe_int(row.get("completed_orders"))
            gross_revenue = _safe_numeric(row.get("gross_revenue"))
            supply_active_both = _safe_int(row.get("supply_active_both"))

        use_fallback_orders = completed_orders == 0
        use_fallback_dist = completed_orders == 0

        if use_fallback_orders:
            fb = _fallback_weekly_orders(cur, iso_year, iso_week)
            active_drivers = fb["active_drivers"]
            completed_orders = fb["completed_orders"]
            gross_revenue = fb["gross_revenue"]

        distribution = (_get_weekly_distribution(cur, iso_year, iso_week)
                        if not use_fallback_dist
                        else _fallback_weekly_distribution(cur, iso_year, iso_week))

        supply_to_active, trips_per_active, trips_per_supply_driver, trips_per_supply_hour = \
            _compute_rates(supply_drivers, supply_hours, active_drivers, completed_orders,
                           supply_active_both)

    return {
        "iso_year": iso_year,
        "iso_week": iso_week,
        "iso_week_key": week_key,
        "iso_week_start_date": week_start,
        "iso_week_end_date": week_end,
        "supply_drivers": supply_drivers,
        "supply_hours": _round2(supply_hours),
        "active_drivers": active_drivers,
        "completed_orders": completed_orders,
        "gross_revenue": _round2(gross_revenue),
        "supply_to_active_driver_rate": supply_to_active,
        "trips_per_active_driver": trips_per_active,
        "trips_per_supply_driver": trips_per_supply_driver,
        "trips_per_supply_hour": trips_per_supply_hour,
        **distribution,
        "source_supply": TABLE_360,
        "source_orders": TABLE_HIST_WEEKLY if use_fallback_orders else TABLE_360,
    }


def get_monthly_productivity(year: int, month: int) -> Dict[str, Any]:
    month_key = f"{year}-{month:02d}"

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(f"""
            WITH driver_month AS (
                SELECT
                    driver_profile_id,
                    SUM(supply_hours) AS supply_hours,
                    SUM(completed_orders) AS completed_orders,
                    SUM(gross_revenue) AS gross_revenue
                FROM {TABLE_360}
                WHERE EXTRACT(YEAR FROM date) = %(yr)s
                  AND EXTRACT(MONTH FROM date) = %(mo)s
                GROUP BY driver_profile_id
            )
            SELECT
                COUNT(*) FILTER (WHERE supply_hours > 0) AS supply_drivers,
                COALESCE(SUM(supply_hours), 0) AS supply_hours,
                COUNT(*) FILTER (WHERE completed_orders > 0) AS active_drivers,
                COALESCE(SUM(completed_orders), 0) AS completed_orders,
                COALESCE(SUM(gross_revenue), 0) AS gross_revenue,
                COUNT(*) FILTER (WHERE supply_hours > 0 AND completed_orders > 0) AS supply_active_both
            FROM driver_month
        """, {"yr": year, "mo": month})
        row = cur.fetchone()

        if not row:
            supply_drivers = 0
            supply_hours = 0.0
            active_drivers = 0
            completed_orders = 0
            gross_revenue = 0.0
            supply_active_both = 0
        else:
            supply_drivers = _safe_int(row.get("supply_drivers"))
            supply_hours = _safe_numeric(row.get("supply_hours"))
            active_drivers = _safe_int(row.get("active_drivers"))
            completed_orders = _safe_int(row.get("completed_orders"))
            gross_revenue = _safe_numeric(row.get("gross_revenue"))
            supply_active_both = _safe_int(row.get("supply_active_both"))

        use_fallback_orders = completed_orders == 0
        use_fallback_dist = completed_orders == 0

        if use_fallback_orders:
            cur.execute(f"""
                SELECT COUNT(DISTINCT driver_profile_id) AS active_drivers,
                       COALESCE(SUM(completed_orders), 0) AS completed_orders,
                       COALESCE(SUM(gross_revenue), 0) AS gross_revenue
                FROM {TABLE_HIST_DAILY}
                WHERE EXTRACT(YEAR FROM date) = %(yr)s
                  AND EXTRACT(MONTH FROM date) = %(mo)s
                  AND completed_orders > 0
            """, {"yr": year, "mo": month})
            fb = cur.fetchone()
            if fb:
                active_drivers = _safe_int(fb.get("active_drivers"))
                completed_orders = _safe_int(fb.get("completed_orders"))
                gross_revenue = _safe_numeric(fb.get("gross_revenue"))
            else:
                active_drivers = 0
                completed_orders = 0
                gross_revenue = 0.0

        distribution = (_get_monthly_distribution(cur, year, month)
                        if not use_fallback_dist
                        else _get_daily_distribution(cur, TABLE_HIST_DAILY, None))

        if use_fallback_dist:
            bucket_sql = ", ".join(
                f"COUNT(*) FILTER (WHERE {cond}) AS {name}"
                for name, cond in DISTRIBUTION_BUCKETS
            )
            cur.execute(f"""
                WITH driver_month AS (
                    SELECT driver_profile_id,
                           SUM(completed_orders) AS completed_orders
                    FROM {TABLE_HIST_DAILY}
                    WHERE EXTRACT(YEAR FROM date) = %(yr)s
                      AND EXTRACT(MONTH FROM date) = %(mo)s
                    GROUP BY driver_profile_id
                )
                SELECT {bucket_sql}, COUNT(*) AS total_drivers
                FROM driver_month
            """, {"yr": year, "mo": month})
            fb_dist = cur.fetchone()
            if fb_dist:
                distribution = {name: _safe_int(fb_dist.get(name)) for name, _ in DISTRIBUTION_BUCKETS}
                distribution["total_drivers"] = _safe_int(fb_dist.get("total_drivers"))
            else:
                distribution = {name: 0 for name, _ in DISTRIBUTION_BUCKETS}
                distribution["total_drivers"] = 0

        supply_to_active, trips_per_active, trips_per_supply_driver, trips_per_supply_hour = \
            _compute_rates(supply_drivers, supply_hours, active_drivers, completed_orders,
                           supply_active_both)

    return {
        "year": year,
        "month": month,
        "month_key": month_key,
        "supply_drivers": supply_drivers,
        "supply_hours": _round2(supply_hours),
        "active_drivers": active_drivers,
        "completed_orders": completed_orders,
        "gross_revenue": _round2(gross_revenue),
        "supply_to_active_driver_rate": supply_to_active,
        "trips_per_active_driver": trips_per_active,
        "trips_per_supply_driver": trips_per_supply_driver,
        "trips_per_supply_hour": trips_per_supply_hour,
        **distribution,
        "source_supply": TABLE_360,
        "source_orders": TABLE_HIST_DAILY if use_fallback_orders else TABLE_360,
    }


def get_supply_vs_production(date_str: str) -> Dict[str, Any]:
    day = get_daily_productivity(date_str)

    supply_drivers = day.get("supply_drivers", 0)
    active_drivers = day.get("active_drivers", 0)
    supply_hours = day.get("supply_hours", 0)
    completed_orders = day.get("completed_orders", 0)

    conversion = _round4(active_drivers / supply_drivers) if supply_drivers else None
    trips_per_supply_hour = _round4(
        completed_orders / supply_hours) if supply_hours else None

    supply_side = {
        "supply_drivers": supply_drivers,
        "supply_hours": round(supply_hours, 2),
        "avg_supply_hours_per_driver": _round2(supply_hours / supply_drivers) if supply_drivers else 0,
    }

    production_side = {
        "active_drivers": active_drivers,
        "completed_orders": completed_orders,
        "trips_per_active_driver": day.get("trips_per_active_driver"),
        "trips_per_supply_hour": trips_per_supply_hour,
    }

    return {
        "date": date_str,
        "supply": supply_side,
        "production": production_side,
        "supply_to_production_conversion": conversion,
        "gap_drivers": max(0, supply_drivers - active_drivers),
        "conversion_label": f"{supply_drivers} supply -> {active_drivers} active ({_round2(conversion * 100) if conversion else 0}%)",
    }


def get_trip_distribution(grain: str, **kwargs) -> Dict[str, Any]:
    if grain == "daily":
        date_str = kwargs.get("date", "")
        if not date_str:
            return {"error": "date required for daily grain"}
        day = get_daily_productivity(date_str)
        return _extract_distribution(day, "daily", date_str)

    elif grain == "weekly":
        iso_year = kwargs.get("iso_year")
        iso_week = kwargs.get("iso_week")
        if not iso_year or not iso_week:
            return {"error": "iso_year and iso_week required for weekly grain"}
        week = get_weekly_productivity(int(iso_year), int(iso_week))
        return _extract_distribution(week, "weekly",
                                     f"{iso_year}-W{int(iso_week):02d}")

    elif grain == "monthly":
        year = kwargs.get("year")
        month = kwargs.get("month")
        if not year or not month:
            return {"error": "year and month required for monthly grain"}
        mon = get_monthly_productivity(int(year), int(month))
        return _extract_distribution(mon, "monthly", f"{year}-{int(month):02d}")

    else:
        return {"error": f"Unknown grain: {grain}. Use daily, weekly, or monthly."}


def _extract_distribution(data: Dict[str, Any], grain: str,
                          key: str) -> Dict[str, Any]:
    buckets = []
    total = 0
    for name, _ in DISTRIBUTION_BUCKETS:
        val = data.get(name, 0)
        buckets.append({"bucket": name, "driver_count": val})
        total += val

    return {
        "grain": grain,
        "key": key,
        "distribution": buckets,
        "total_drivers": total,
    }


# ==============================================================
# BUILD Functions (compute and store into productivity tables)
# ==============================================================

def build_productivity_daily(date_str: str) -> Dict[str, Any]:
    day = get_daily_productivity(date_str)

    iso_year = day["iso_year"]
    iso_week = day["iso_week"]
    iso_week_key = day["iso_week_key"]
    iso_day_of_week = day["iso_day_of_week"]
    iso_day_name = day["iso_day_name"]

    dist_cols = {name: day.get(name, 0) for name, _ in DISTRIBUTION_BUCKETS}

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_PROD_DAILY} (
                date, iso_year, iso_week, iso_week_key, iso_day_of_week, iso_day_name,
                supply_drivers, supply_hours,
                active_drivers, completed_orders, gross_revenue,
                supply_to_active_driver_rate,
                trips_per_active_driver, trips_per_supply_driver, trips_per_supply_hour,
                drivers_0_9, drivers_10_19, drivers_20_29, drivers_30_39,
                drivers_40_49, drivers_50_69, drivers_70_99, drivers_100_plus,
                last_calculated_at, source
            ) VALUES (
                %(date)s, %(iso_year)s, %(iso_week)s, %(iso_week_key)s,
                %(iso_day_of_week)s, %(iso_day_name)s,
                %(supply_drivers)s, %(supply_hours)s,
                %(active_drivers)s, %(completed_orders)s, %(gross_revenue)s,
                %(supply_to_active_driver_rate)s,
                %(trips_per_active_driver)s, %(trips_per_supply_driver)s,
                %(trips_per_supply_hour)s,
                %(drivers_0_9)s, %(drivers_10_19)s, %(drivers_20_29)s, %(drivers_30_39)s,
                %(drivers_40_49)s, %(drivers_50_69)s, %(drivers_70_99)s, %(drivers_100_plus)s,
                now(), 'productivity_governance'
            )
            ON CONFLICT (date) DO UPDATE SET
                iso_year = EXCLUDED.iso_year,
                iso_week = EXCLUDED.iso_week,
                iso_week_key = EXCLUDED.iso_week_key,
                iso_day_of_week = EXCLUDED.iso_day_of_week,
                iso_day_name = EXCLUDED.iso_day_name,
                supply_drivers = EXCLUDED.supply_drivers,
                supply_hours = EXCLUDED.supply_hours,
                active_drivers = EXCLUDED.active_drivers,
                completed_orders = EXCLUDED.completed_orders,
                gross_revenue = EXCLUDED.gross_revenue,
                supply_to_active_driver_rate = EXCLUDED.supply_to_active_driver_rate,
                trips_per_active_driver = EXCLUDED.trips_per_active_driver,
                trips_per_supply_driver = EXCLUDED.trips_per_supply_driver,
                trips_per_supply_hour = EXCLUDED.trips_per_supply_hour,
                drivers_0_9 = EXCLUDED.drivers_0_9,
                drivers_10_19 = EXCLUDED.drivers_10_19,
                drivers_20_29 = EXCLUDED.drivers_20_29,
                drivers_30_39 = EXCLUDED.drivers_30_39,
                drivers_40_49 = EXCLUDED.drivers_40_49,
                drivers_50_69 = EXCLUDED.drivers_50_69,
                drivers_70_99 = EXCLUDED.drivers_70_99,
                drivers_100_plus = EXCLUDED.drivers_100_plus,
                last_calculated_at = now(),
                source = 'productivity_governance'
        """, {
            "date": date_str,
            "iso_year": iso_year,
            "iso_week": iso_week,
            "iso_week_key": iso_week_key,
            "iso_day_of_week": iso_day_of_week,
            "iso_day_name": iso_day_name,
            "supply_drivers": day["supply_drivers"],
            "supply_hours": day["supply_hours"],
            "active_drivers": day["active_drivers"],
            "completed_orders": day["completed_orders"],
            "gross_revenue": day["gross_revenue"],
            "supply_to_active_driver_rate": day["supply_to_active_driver_rate"],
            "trips_per_active_driver": day["trips_per_active_driver"],
            "trips_per_supply_driver": day["trips_per_supply_driver"],
            "trips_per_supply_hour": day["trips_per_supply_hour"],
            **dist_cols,
        })
    logger.info("Built productivity daily for %s: %s active, %s supply",
                date_str, day["active_drivers"], day["supply_drivers"])
    try:
        from app.services.yego_lima_freshness_service import record_productivity_sync
        record_productivity_sync("daily", date_str, day["active_drivers"], 0)
    except Exception:
        pass
    return day


def build_productivity_weekly(iso_year: int, iso_week: int) -> Dict[str, Any]:
    week = get_weekly_productivity(iso_year, iso_week)

    dist_cols = {name: week.get(name, 0) for name, _ in DISTRIBUTION_BUCKETS}

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_PROD_WEEKLY} (
                iso_year, iso_week, iso_week_key,
                iso_week_start_date, iso_week_end_date,
                supply_drivers, supply_hours,
                active_drivers, completed_orders, gross_revenue,
                supply_to_active_driver_rate,
                trips_per_active_driver, trips_per_supply_driver, trips_per_supply_hour,
                drivers_0_9, drivers_10_19, drivers_20_29, drivers_30_39,
                drivers_40_49, drivers_50_69, drivers_70_99, drivers_100_plus,
                last_calculated_at, source
            ) VALUES (
                %(iso_year)s, %(iso_week)s, %(iso_week_key)s,
                %(iso_week_start_date)s, %(iso_week_end_date)s,
                %(supply_drivers)s, %(supply_hours)s,
                %(active_drivers)s, %(completed_orders)s, %(gross_revenue)s,
                %(supply_to_active_driver_rate)s,
                %(trips_per_active_driver)s, %(trips_per_supply_driver)s,
                %(trips_per_supply_hour)s,
                %(drivers_0_9)s, %(drivers_10_19)s, %(drivers_20_29)s, %(drivers_30_39)s,
                %(drivers_40_49)s, %(drivers_50_69)s, %(drivers_70_99)s, %(drivers_100_plus)s,
                now(), 'productivity_governance'
            )
            ON CONFLICT (iso_year, iso_week) DO UPDATE SET
                iso_week_key = EXCLUDED.iso_week_key,
                iso_week_start_date = EXCLUDED.iso_week_start_date,
                iso_week_end_date = EXCLUDED.iso_week_end_date,
                supply_drivers = EXCLUDED.supply_drivers,
                supply_hours = EXCLUDED.supply_hours,
                active_drivers = EXCLUDED.active_drivers,
                completed_orders = EXCLUDED.completed_orders,
                gross_revenue = EXCLUDED.gross_revenue,
                supply_to_active_driver_rate = EXCLUDED.supply_to_active_driver_rate,
                trips_per_active_driver = EXCLUDED.trips_per_active_driver,
                trips_per_supply_driver = EXCLUDED.trips_per_supply_driver,
                trips_per_supply_hour = EXCLUDED.trips_per_supply_hour,
                drivers_0_9 = EXCLUDED.drivers_0_9,
                drivers_10_19 = EXCLUDED.drivers_10_19,
                drivers_20_29 = EXCLUDED.drivers_20_29,
                drivers_30_39 = EXCLUDED.drivers_30_39,
                drivers_40_49 = EXCLUDED.drivers_40_49,
                drivers_50_69 = EXCLUDED.drivers_50_69,
                drivers_70_99 = EXCLUDED.drivers_70_99,
                drivers_100_plus = EXCLUDED.drivers_100_plus,
                last_calculated_at = now(),
                source = 'productivity_governance'
        """, {
            "iso_year": iso_year,
            "iso_week": iso_week,
            "iso_week_key": week["iso_week_key"],
            "iso_week_start_date": week["iso_week_start_date"],
            "iso_week_end_date": week["iso_week_end_date"],
            "supply_drivers": week["supply_drivers"],
            "supply_hours": week["supply_hours"],
            "active_drivers": week["active_drivers"],
            "completed_orders": week["completed_orders"],
            "gross_revenue": week["gross_revenue"],
            "supply_to_active_driver_rate": week["supply_to_active_driver_rate"],
            "trips_per_active_driver": week["trips_per_active_driver"],
            "trips_per_supply_driver": week["trips_per_supply_driver"],
            "trips_per_supply_hour": week["trips_per_supply_hour"],
            **dist_cols,
        })
    logger.info("Built productivity weekly %s-W%02d: %s active, %s supply",
                iso_year, iso_week, week["active_drivers"], week["supply_drivers"])
    try:
        from app.services.yego_lima_freshness_service import record_productivity_sync
        record_productivity_sync("weekly", week["iso_week_key"], week["active_drivers"], 0)
    except Exception:
        pass
    return week


def build_productivity_monthly(year: int, month: int) -> Dict[str, Any]:
    mon = get_monthly_productivity(year, month)

    dist_cols = {name: mon.get(name, 0) for name, _ in DISTRIBUTION_BUCKETS}

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_PROD_MONTHLY} (
                year, month, month_key,
                supply_drivers, supply_hours,
                active_drivers, completed_orders, gross_revenue,
                supply_to_active_driver_rate,
                trips_per_active_driver, trips_per_supply_driver, trips_per_supply_hour,
                drivers_0_9, drivers_10_19, drivers_20_29, drivers_30_39,
                drivers_40_49, drivers_50_69, drivers_70_99, drivers_100_plus,
                last_calculated_at, source
            ) VALUES (
                %(year)s, %(month)s, %(month_key)s,
                %(supply_drivers)s, %(supply_hours)s,
                %(active_drivers)s, %(completed_orders)s, %(gross_revenue)s,
                %(supply_to_active_driver_rate)s,
                %(trips_per_active_driver)s, %(trips_per_supply_driver)s,
                %(trips_per_supply_hour)s,
                %(drivers_0_9)s, %(drivers_10_19)s, %(drivers_20_29)s, %(drivers_30_39)s,
                %(drivers_40_49)s, %(drivers_50_69)s, %(drivers_70_99)s, %(drivers_100_plus)s,
                now(), 'productivity_governance'
            )
            ON CONFLICT (year, month) DO UPDATE SET
                month_key = EXCLUDED.month_key,
                supply_drivers = EXCLUDED.supply_drivers,
                supply_hours = EXCLUDED.supply_hours,
                active_drivers = EXCLUDED.active_drivers,
                completed_orders = EXCLUDED.completed_orders,
                gross_revenue = EXCLUDED.gross_revenue,
                supply_to_active_driver_rate = EXCLUDED.supply_to_active_driver_rate,
                trips_per_active_driver = EXCLUDED.trips_per_active_driver,
                trips_per_supply_driver = EXCLUDED.trips_per_supply_driver,
                trips_per_supply_hour = EXCLUDED.trips_per_supply_hour,
                drivers_0_9 = EXCLUDED.drivers_0_9,
                drivers_10_19 = EXCLUDED.drivers_10_19,
                drivers_20_29 = EXCLUDED.drivers_20_29,
                drivers_30_39 = EXCLUDED.drivers_30_39,
                drivers_40_49 = EXCLUDED.drivers_40_49,
                drivers_50_69 = EXCLUDED.drivers_50_69,
                drivers_70_99 = EXCLUDED.drivers_70_99,
                drivers_100_plus = EXCLUDED.drivers_100_plus,
                last_calculated_at = now(),
                source = 'productivity_governance'
        """, {
            "year": year,
            "month": month,
            "month_key": mon["month_key"],
            "supply_drivers": mon["supply_drivers"],
            "supply_hours": mon["supply_hours"],
            "active_drivers": mon["active_drivers"],
            "completed_orders": mon["completed_orders"],
            "gross_revenue": mon["gross_revenue"],
            "supply_to_active_driver_rate": mon["supply_to_active_driver_rate"],
            "trips_per_active_driver": mon["trips_per_active_driver"],
            "trips_per_supply_driver": mon["trips_per_supply_driver"],
            "trips_per_supply_hour": mon["trips_per_supply_hour"],
            **dist_cols,
        })
    logger.info("Built productivity monthly %s-%02d: %s active, %s supply",
                year, month, mon["active_drivers"], mon["supply_drivers"])
    try:
        from app.services.yego_lima_freshness_service import record_productivity_sync
        record_productivity_sync("monthly", mon["month_key"], mon["active_drivers"], 0)
    except Exception:
        pass
    return mon


def build_all_productivity(date_str: str) -> Dict[str, Any]:
    dt = date_type.fromisoformat(date_str)
    iso_year, iso_week, _ = dt.isocalendar()
    year = dt.year
    month = dt.month

    daily = build_productivity_daily(date_str)
    weekly = build_productivity_weekly(iso_year, iso_week)
    monthly = build_productivity_monthly(year, month)

    return {
        "daily": {"date": date_str, "active_drivers": daily["active_drivers"]},
        "weekly": {"iso_week_key": weekly["iso_week_key"],
                    "active_drivers": weekly["active_drivers"]},
        "monthly": {"month_key": monthly["month_key"],
                     "active_drivers": monthly["active_drivers"]},
    }
