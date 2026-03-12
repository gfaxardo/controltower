"""
Fleet Leakage Monitor MVP — summary, drivers list, export.
Reads from ops.v_fleet_leakage_snapshot only. No dependency on Behavioral Alerts.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

_LEAKAGE_VIEW = "ops.v_fleet_leakage_snapshot"
_QUERY_TIMEOUT_MS = 120_000


def _build_where(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    leakage_status: Optional[str] = None,
    recovery_priority: Optional[str] = None,
    top_performers_only: Optional[bool] = None,
) -> tuple[str, list]:
    conditions = []
    params: list = []
    if country:
        conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(city)
    if park_id:
        conditions.append("park_id::text = %s")
        params.append(str(park_id))
    if leakage_status:
        conditions.append("leakage_status = %s")
        params.append(leakage_status)
    if recovery_priority:
        conditions.append("recovery_priority = %s")
        params.append(recovery_priority)
    if top_performers_only:
        conditions.append("top_performer_at_risk = true")
    where_sql = " AND ".join(conditions) if conditions else "1=1"
    return where_sql, params


def get_leakage_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    leakage_status: Optional[str] = None,
    recovery_priority: Optional[str] = None,
    top_performers_only: Optional[bool] = None,
) -> dict[str, Any]:
    """KPIs: drivers_under_watch, progressive_leakage, lost_drivers, top_performers_at_risk, cohort_retention_45d (drivers with days_since_last_trip <= 45)."""
    where_sql, params = _build_where(
        country=country, city=city, park_id=park_id,
        leakage_status=leakage_status, recovery_priority=recovery_priority,
        top_performers_only=top_performers_only,
    )
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SET statement_timeout = %s", (str(_QUERY_TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT
                    COUNT(*)::int AS total_drivers,
                    COUNT(*) FILTER (WHERE leakage_status = 'watchlist')::int AS drivers_under_watch,
                    COUNT(*) FILTER (WHERE leakage_status = 'progressive_leakage')::int AS progressive_leakage,
                    COUNT(*) FILTER (WHERE leakage_status = 'lost_driver')::int AS lost_drivers,
                    COUNT(*) FILTER (WHERE top_performer_at_risk = true)::int AS top_performers_at_risk,
                    COUNT(*) FILTER (WHERE days_since_last_trip IS NOT NULL AND days_since_last_trip <= 45)::int AS cohort_retention_45d
                FROM {_LEAKAGE_VIEW}
                WHERE {where_sql}
                """,
                params,
            )
            row = cur.fetchone()
            return dict(row) if row else {
                "total_drivers": 0,
                "drivers_under_watch": 0,
                "progressive_leakage": 0,
                "lost_drivers": 0,
                "top_performers_at_risk": 0,
                "cohort_retention_45d": 0,
            }
        finally:
            cur.close()


def get_leakage_drivers(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    leakage_status: Optional[str] = None,
    recovery_priority: Optional[str] = None,
    top_performers_only: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    order_by: str = "leakage_score",
    order_dir: str = "desc",
) -> dict[str, Any]:
    """List of drivers from v_fleet_leakage_snapshot with filters and pagination."""
    where_sql, params = _build_where(
        country=country, city=city, park_id=park_id,
        leakage_status=leakage_status, recovery_priority=recovery_priority,
        top_performers_only=top_performers_only,
    )
    order_col = "leakage_score"
    if order_by in ("driver_name", "country", "city", "park_name", "trips_current_week", "baseline_trips_4w_avg",
                    "delta_pct", "last_trip_date", "days_since_last_trip", "leakage_status", "recovery_priority"):
        order_col = order_by
    dir_sql = "DESC" if (order_dir or "desc").lower() == "desc" else "ASC"
    if order_col == "delta_pct":
        dir_sql = "ASC" if (order_dir or "asc").lower() == "asc" else "DESC"
    params.extend([limit, offset])
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SET statement_timeout = %s", (str(_QUERY_TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT
                    driver_key,
                    driver_name,
                    week_start,
                    park_id,
                    park_name,
                    city,
                    country,
                    trips_current_week,
                    baseline_trips_4w_avg,
                    delta_pct,
                    last_trip_date,
                    days_since_last_trip,
                    segment_week,
                    leakage_status,
                    leakage_score,
                    recovery_priority,
                    top_performer_at_risk
                FROM {_LEAKAGE_VIEW}
                WHERE {where_sql}
                ORDER BY {order_col} {dir_sql} NULLS LAST, driver_key
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) AS n FROM {_LEAKAGE_VIEW} WHERE {where_sql}",
                params[:-2],
            )
            total = cur.fetchone()["n"]
            return {"data": rows, "total": total, "limit": limit, "offset": offset}
        finally:
            cur.close()


def get_leakage_export(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    leakage_status: Optional[str] = None,
    recovery_priority: Optional[str] = None,
    top_performers_only: Optional[bool] = None,
    max_rows: int = 10000,
) -> list[dict[str, Any]]:
    """Export rows for Recovery Queue CSV/Excel."""
    where_sql, params = _build_where(
        country=country, city=city, park_id=park_id,
        leakage_status=leakage_status, recovery_priority=recovery_priority,
        top_performers_only=top_performers_only,
    )
    params.append(max_rows)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SET statement_timeout = %s", (str(_QUERY_TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT
                    driver_key,
                    driver_name,
                    country,
                    city,
                    park_name,
                    segment_week,
                    trips_current_week,
                    baseline_trips_4w_avg,
                    delta_pct,
                    last_trip_date,
                    days_since_last_trip,
                    leakage_status,
                    leakage_score,
                    recovery_priority,
                    top_performer_at_risk
                FROM {_LEAKAGE_VIEW}
                WHERE {where_sql}
                ORDER BY leakage_score DESC NULLS LAST, recovery_priority, driver_key
                LIMIT %s
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
