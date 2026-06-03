"""
YEGO Lima Fleet Growth Tower — Driver 360 Daily Repository (Fase 2A.2).

Responsabilidades:
- Upsert diario en growth.yango_lima_driver_360_daily (campos ampliados)
- Lectura de summary por fecha
- Lectura de distribucion por driver_state / productivity_band
- Lectura de listas operacionales sanitizadas
- Muestras sanitizadas
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _cursor(conn, timeout_ms: int = 120000):
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SET LOCAL statement_timeout = %s;", (timeout_ms,))
        yield cur
    finally:
        cur.close()


_UPSERT_SQL = """
INSERT INTO growth.yango_lima_driver_360_daily (
    driver_profile_id, date,
    work_status, current_status, work_rule_id, employment_type,
    car_id, car_category, car_status, car_brand, car_model, car_number,
    completed_orders, gross_revenue,
    supply_seconds, supply_hours, trips_per_supply_hour,
    active_flag, driver_state, source,
    productivity_band, eligibility_tier, eligibility_reason,
    supply_fetch_status, supply_fetch_error_type,
    supply_last_attempt_at, orders_last_seen_at
) VALUES (
    %(driver_profile_id)s, %(date)s,
    %(work_status)s, %(current_status)s, %(work_rule_id)s, %(employment_type)s,
    %(car_id)s, %(car_category)s, %(car_status)s, %(car_brand)s, %(car_model)s, %(car_number)s,
    %(completed_orders)s, %(gross_revenue)s,
    %(supply_seconds)s, %(supply_hours)s, %(trips_per_supply_hour)s,
    %(active_flag)s, %(driver_state)s, %(source)s,
    %(productivity_band)s, %(eligibility_tier)s, %(eligibility_reason)s,
    %(supply_fetch_status)s, %(supply_fetch_error_type)s,
    %(supply_last_attempt_at)s, %(orders_last_seen_at)s
)
ON CONFLICT (driver_profile_id, date) DO UPDATE SET
    work_status = EXCLUDED.work_status,
    current_status = EXCLUDED.current_status,
    work_rule_id = EXCLUDED.work_rule_id,
    employment_type = EXCLUDED.employment_type,
    car_id = EXCLUDED.car_id,
    car_category = EXCLUDED.car_category,
    car_status = EXCLUDED.car_status,
    car_brand = EXCLUDED.car_brand,
    car_model = EXCLUDED.car_model,
    car_number = EXCLUDED.car_number,
    completed_orders = EXCLUDED.completed_orders,
    gross_revenue = EXCLUDED.gross_revenue,
    supply_seconds = EXCLUDED.supply_seconds,
    supply_hours = EXCLUDED.supply_hours,
    trips_per_supply_hour = EXCLUDED.trips_per_supply_hour,
    active_flag = EXCLUDED.active_flag,
    driver_state = EXCLUDED.driver_state,
    source = EXCLUDED.source,
    productivity_band = EXCLUDED.productivity_band,
    eligibility_tier = EXCLUDED.eligibility_tier,
    eligibility_reason = EXCLUDED.eligibility_reason,
    supply_fetch_status = EXCLUDED.supply_fetch_status,
    supply_fetch_error_type = EXCLUDED.supply_fetch_error_type,
    supply_last_attempt_at = EXCLUDED.supply_last_attempt_at,
    orders_last_seen_at = EXCLUDED.orders_last_seen_at,
    last_calculated_at = now()
"""


def upsert_driver_360_daily(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    if not rows:
        return 0, 0

    inserted = 0
    updated = 0

    with get_db() as conn:
        with _cursor(conn) as cur:
            for row in rows:
                cur.execute(_UPSERT_SQL, row)
                if cur.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1

    return inserted, updated


def get_driver_360_summary() -> Dict[str, Any]:
    with get_db() as conn:
        with _cursor(conn) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS rows,
                    COUNT(DISTINCT date) AS dates,
                    COUNT(*) FILTER (WHERE driver_state = 'PRODUCTIVE') AS productive,
                    COUNT(*) FILTER (WHERE driver_state = 'ONLINE_NO_ORDERS') AS online_no_orders,
                    COUNT(*) FILTER (WHERE driver_state = 'OFFLINE') AS offline,
                    COUNT(*) FILTER (WHERE driver_state = 'ORDERS_WITHOUT_SUPPLY_ANOMALY') AS orders_without_supply_anomaly,
                    ROUND(AVG(completed_orders::numeric), 2) AS avg_trips_per_driver,
                    ROUND(AVG(supply_hours), 2) AS avg_supply_hours,
                    COALESCE(SUM(completed_orders), 0) AS total_orders,
                    COALESCE(SUM(supply_hours), 0) AS total_supply_hours
                FROM growth.yango_lima_driver_360_daily
            """)
            row = cur.fetchone()
            if not row:
                return _empty_summary()
            return {
                "rows": row["rows"] or 0,
                "dates": row["dates"] or 0,
                "productive": row["productive"] or 0,
                "online_no_orders": row["online_no_orders"] or 0,
                "offline": row["offline"] or 0,
                "orders_without_supply_anomaly": row["orders_without_supply_anomaly"] or 0,
                "avg_trips_per_driver": float(row["avg_trips_per_driver"] or 0),
                "avg_supply_hours": float(row["avg_supply_hours"] or 0),
                "total_orders": int(row["total_orders"] or 0),
                "total_supply_hours": float(row["total_supply_hours"] or 0),
            }


def get_driver_360_day_summary(date_str: str) -> Dict[str, Any]:
    with get_db() as conn:
        with _cursor(conn) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total_drivers,
                    COALESCE(SUM(completed_orders), 0) AS total_orders,
                    COALESCE(SUM(supply_hours), 0) AS total_supply_hours,
                    ROUND(AVG(completed_orders::numeric), 4) AS avg_trips_per_driver,
                    CASE WHEN SUM(supply_hours) > 0
                         THEN ROUND(SUM(completed_orders)::numeric / SUM(supply_hours), 4)
                         ELSE 0 END AS avg_trips_per_supply_hour,
                    COUNT(*) FILTER (WHERE driver_state = 'PRODUCTIVE') AS productive,
                    COUNT(*) FILTER (WHERE driver_state = 'ONLINE_NO_ORDERS') AS online_no_orders,
                    COUNT(*) FILTER (WHERE driver_state = 'OFFLINE') AS offline,
                    COUNT(*) FILTER (WHERE driver_state = 'ORDERS_WITHOUT_SUPPLY_ANOMALY') AS orders_without_supply_anomaly,
                    COUNT(*) FILTER (WHERE productivity_band = 'LOW_PRODUCTIVITY') AS low_productivity,
                    COUNT(*) FILTER (WHERE productivity_band = 'NORMAL_PRODUCTIVITY') AS normal_productivity,
                    COUNT(*) FILTER (WHERE productivity_band = 'HIGH_PRODUCTIVITY') AS high_productivity,
                    COUNT(*) FILTER (WHERE productivity_band = 'NOT_APPLICABLE') AS not_applicable_pb,
                    COUNT(*) FILTER (WHERE eligibility_tier = 'HOT') AS hot,
                    COUNT(*) FILTER (WHERE eligibility_tier = 'WARM') AS warm,
                    COUNT(*) FILTER (WHERE eligibility_tier = 'COLD') AS cold,
                    COUNT(*) FILTER (WHERE eligibility_tier = 'DORMANT') AS dormant,
                    COUNT(*) FILTER (WHERE supply_fetch_status = 'success') AS supply_success,
                    COUNT(*) FILTER (WHERE supply_fetch_status = 'rate_limited') AS supply_rate_limited,
                    COUNT(*) FILTER (WHERE supply_fetch_status = 'error') AS supply_errors,
                    COUNT(*) FILTER (WHERE supply_fetch_status = 'not_requested') AS supply_not_requested
                FROM growth.yango_lima_driver_360_daily
                WHERE date = %(date)s
            """, {"date": date_str})
            row = cur.fetchone()
            if not row or (row.get("total_drivers") or 0) == 0:
                return {
                    "date": date_str,
                    "total_drivers": 0,
                    "total_orders": 0,
                    "total_supply_hours": 0,
                    "avg_trips_per_driver": 0,
                    "avg_trips_per_supply_hour": 0,
                    "productive": 0,
                    "online_no_orders": 0,
                    "offline": 0,
                    "orders_without_supply_anomaly": 0,
                    "low_productivity": 0,
                    "normal_productivity": 0,
                    "high_productivity": 0,
                    "not_applicable_pb": 0,
                    "hot": 0, "warm": 0, "cold": 0, "dormant": 0,
                    "supply_success": 0,
                    "supply_rate_limited": 0,
                    "supply_errors": 0,
                    "supply_not_requested": 0,
                }
            return {
                "date": date_str,
                "total_drivers": int(row["total_drivers"] or 0),
                "total_orders": int(row["total_orders"] or 0),
                "total_supply_hours": float(row["total_supply_hours"] or 0),
                "avg_trips_per_driver": float(row["avg_trips_per_driver"] or 0),
                "avg_trips_per_supply_hour": float(row["avg_trips_per_supply_hour"] or 0),
                "productive": int(row["productive"] or 0),
                "online_no_orders": int(row["online_no_orders"] or 0),
                "offline": int(row["offline"] or 0),
                "orders_without_supply_anomaly": int(row["orders_without_supply_anomaly"] or 0),
                "low_productivity": int(row["low_productivity"] or 0),
                "normal_productivity": int(row["normal_productivity"] or 0),
                "high_productivity": int(row["high_productivity"] or 0),
                "not_applicable_pb": int(row["not_applicable_pb"] or 0),
                "hot": int(row["hot"] or 0),
                "warm": int(row["warm"] or 0),
                "cold": int(row["cold"] or 0),
                "dormant": int(row["dormant"] or 0),
                "supply_success": int(row["supply_success"] or 0),
                "supply_rate_limited": int(row["supply_rate_limited"] or 0),
                "supply_errors": int(row["supply_errors"] or 0),
                "supply_not_requested": int(row["supply_not_requested"] or 0),
            }


def get_driver_360_operational_lists(date_str: str) -> Dict[str, Any]:
    lists: Dict[str, List[Dict[str, Any]]] = {
        "online_no_orders": [],
        "low_productivity": [],
        "high_productivity": [],
        "orders_without_supply_anomaly": [],
        "rate_limited_supply": [],
    }

    base_cols = """
        driver_profile_id, completed_orders, supply_hours,
        trips_per_supply_hour, driver_state, productivity_band,
        eligibility_tier, current_status, car_brand, car_model
    """

    queries = {
        "online_no_orders": "driver_state = 'ONLINE_NO_ORDERS'",
        "low_productivity": "productivity_band = 'LOW_PRODUCTIVITY'",
        "high_productivity": "productivity_band = 'HIGH_PRODUCTIVITY'",
        "orders_without_supply_anomaly": "driver_state = 'ORDERS_WITHOUT_SUPPLY_ANOMALY'",
        "rate_limited_supply": "supply_fetch_status = 'rate_limited'",
    }

    with get_db() as conn:
        with _cursor(conn) as cur:
            for key, where_clause in queries.items():
                cur.execute(f"""
                    SELECT {base_cols}
                    FROM growth.yango_lima_driver_360_daily
                    WHERE date = %(date)s AND {where_clause}
                    ORDER BY completed_orders DESC
                    LIMIT 200
                """, {"date": date_str})
                for row in cur.fetchall():
                    did = row["driver_profile_id"] or ""
                    lists[key].append({
                        "driver_profile_id_masked": (did[:8] + "..." if len(did) > 8 else did),
                        "completed_orders": int(row["completed_orders"] or 0),
                        "supply_hours": float(row["supply_hours"] or 0),
                        "trips_per_supply_hour": float(row["trips_per_supply_hour"]) if row["trips_per_supply_hour"] is not None else None,
                        "driver_state": row["driver_state"],
                        "productivity_band": row["productivity_band"],
                        "eligibility_tier": row["eligibility_tier"],
                        "current_status": row["current_status"],
                        "car_brand": row["car_brand"],
                        "car_model": row["car_model"],
                    })

    return {
        "date": date_str,
        "online_no_orders": lists["online_no_orders"],
        "online_no_orders_count": len(lists["online_no_orders"]),
        "low_productivity": lists["low_productivity"],
        "low_productivity_count": len(lists["low_productivity"]),
        "high_productivity": lists["high_productivity"],
        "high_productivity_count": len(lists["high_productivity"]),
        "orders_without_supply_anomaly": lists["orders_without_supply_anomaly"],
        "orders_without_supply_anomaly_count": len(lists["orders_without_supply_anomaly"]),
        "rate_limited_supply": lists["rate_limited_supply"],
        "rate_limited_supply_count": len(lists["rate_limited_supply"]),
    }


def get_driver_360_sample(limit: int = 20) -> List[Dict[str, Any]]:
    with get_db() as conn:
        with _cursor(conn) as cur:
            cur.execute("""
                SELECT
                    driver_profile_id,
                    date,
                    completed_orders,
                    supply_hours,
                    trips_per_supply_hour,
                    driver_state,
                    productivity_band,
                    eligibility_tier,
                    supply_fetch_status
                FROM growth.yango_lima_driver_360_daily
                ORDER BY date DESC, completed_orders DESC
                LIMIT %(limit)s
            """, {"limit": min(limit, 100)})
            rows = cur.fetchall()
            result = []
            for row in rows:
                did = row["driver_profile_id"] or ""
                result.append({
                    "driver_profile_id_masked": (did[:8] + "..." if len(did) > 8 else did),
                    "date": row["date"].isoformat() if row["date"] else None,
                    "completed_orders": row["completed_orders"] or 0,
                    "supply_hours": float(row["supply_hours"] or 0),
                    "trips_per_supply_hour": float(row["trips_per_supply_hour"]) if row["trips_per_supply_hour"] is not None else None,
                    "driver_state": row["driver_state"],
                    "productivity_band": row["productivity_band"],
                    "eligibility_tier": row["eligibility_tier"],
                    "supply_fetch_status": row["supply_fetch_status"],
                })
            return result


def _empty_summary():
    return {
        "rows": 0, "dates": 0,
        "productive": 0, "online_no_orders": 0, "offline": 0,
        "orders_without_supply_anomaly": 0,
        "avg_trips_per_driver": 0, "avg_supply_hours": 0,
        "total_orders": 0, "total_supply_hours": 0,
    }
