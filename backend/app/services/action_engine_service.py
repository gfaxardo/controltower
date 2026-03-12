"""
Action Engine — Cohorts and recommended actions from Behavioral Alerts signals.
Reads from ops.v_action_engine_driver_base, ops.v_action_engine_cohorts_weekly, ops.v_action_engine_recommendations_weekly.
Additive; does not modify Behavioral Alerts.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

_DRIVER_BASE = "ops.v_action_engine_driver_base"
_COHORTS = "ops.v_action_engine_cohorts_weekly"
_RECOMMENDATIONS = "ops.v_action_engine_recommendations_weekly"


def _build_where(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> tuple[str, list]:
    conditions = []
    params: list = []
    if week_start:
        conditions.append("week_start = %s::date")
        params.append(week_start)
    if from_date:
        conditions.append("week_start >= %s::date")
        params.append(from_date)
    if to_date:
        conditions.append("week_start <= %s::date")
        params.append(to_date)
    if country:
        conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(city)
    if park_id:
        conditions.append("park_id::text = %s")
        params.append(str(park_id))
    if segment_current:
        conditions.append("segment_current = %s")
        params.append(segment_current)
    if cohort_type:
        conditions.append("cohort_type = %s")
        params.append(cohort_type)
    if priority:
        conditions.append("suggested_priority = %s")
        params.append(priority)
    where_sql = " AND ".join(conditions) if conditions else "1=1"
    return where_sql, params


def get_action_engine_summary(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict[str, Any]:
    """KPIs: actionable_drivers, cohorts_detected, high_priority_cohorts, recoverable_drivers, high_value_at_risk, near_upgrade_opportunities."""
    where_sql, params = _build_where(
        week_start=week_start, from_date=from_date, to_date=to_date,
        country=country, city=city, park_id=park_id,
        segment_current=segment_current, cohort_type=cohort_type, priority=priority,
    )
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    COUNT(DISTINCT driver_key) AS actionable_drivers,
                    COUNT(DISTINCT (week_start, cohort_type)) AS cohorts_detected,
                    COUNT(*) FILTER (WHERE cohort_type = 'recoverable_mid_performers') AS recoverable_drivers,
                    COUNT(*) FILTER (WHERE cohort_type IN ('high_value_deteriorating', 'high_value_recovery_candidates')) AS high_value_at_risk,
                    COUNT(*) FILTER (WHERE cohort_type = 'near_upgrade_opportunity') AS near_upgrade_opportunities
                FROM {_DRIVER_BASE}
                WHERE {where_sql}
                """,
                params,
            )
            row = cur.fetchone()
            base = dict(row) if row else {
                "actionable_drivers": 0, "cohorts_detected": 0,
                "recoverable_drivers": 0, "high_value_at_risk": 0, "near_upgrade_opportunities": 0,
            }
            for k in ("recoverable_drivers", "high_value_at_risk", "near_upgrade_opportunities"):
                base[k] = base.get(k) or 0
            # High priority cohorts: count (week_start, cohort_type) with suggested_priority='high' that have drivers in filtered driver_base
            drv_conditions = []
            drv_params = []
            if week_start:
                drv_conditions.append("d.week_start = %s::date")
                drv_params.append(week_start)
            if from_date:
                drv_conditions.append("d.week_start >= %s::date")
                drv_params.append(from_date)
            if to_date:
                drv_conditions.append("d.week_start <= %s::date")
                drv_params.append(to_date)
            if country:
                drv_conditions.append("LOWER(TRIM(d.country)) = LOWER(TRIM(%s))")
                drv_params.append(country)
            if city:
                drv_conditions.append("LOWER(TRIM(d.city)) = LOWER(TRIM(%s))")
                drv_params.append(city)
            if park_id:
                drv_conditions.append("d.park_id::text = %s")
                drv_params.append(str(park_id))
            if segment_current:
                drv_conditions.append("d.segment_current = %s")
                drv_params.append(segment_current)
            if cohort_type:
                drv_conditions.append("d.cohort_type = %s")
                drv_params.append(cohort_type)
            wd = " AND ".join(drv_conditions) if drv_conditions else "1=1"
            cur.execute(
                f"""
                SELECT COUNT(DISTINCT (c.week_start, c.cohort_type)) AS n
                FROM {_COHORTS} c
                WHERE c.suggested_priority = 'high'
                AND EXISTS (SELECT 1 FROM {_DRIVER_BASE} d WHERE d.cohort_type = c.cohort_type AND d.week_start = c.week_start AND {wd})
                """,
                drv_params,
            )
            hp_row = cur.fetchone()
            base["high_priority_cohorts"] = (hp_row["n"] or 0) if hp_row else 0
            return base
        finally:
            cur.close()


def get_action_engine_cohorts(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Cohort list with filters. Joins cohorts to driver_base to apply geo/segment filters."""
    where_driver = []
    params: list = []
    if week_start:
        where_driver.append("d.week_start = %s::date")
        params.append(week_start)
    if from_date:
        where_driver.append("d.week_start >= %s::date")
        params.append(from_date)
    if to_date:
        where_driver.append("d.week_start <= %s::date")
        params.append(to_date)
    if country:
        where_driver.append("LOWER(TRIM(d.country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        where_driver.append("LOWER(TRIM(d.city)) = LOWER(TRIM(%s))")
        params.append(city)
    if park_id:
        where_driver.append("d.park_id::text = %s")
        params.append(str(park_id))
    if segment_current:
        where_driver.append("d.segment_current = %s")
        params.append(segment_current)
    if cohort_type:
        where_driver.append("d.cohort_type = %s")
        params.append(cohort_type)
    wd = " AND ".join(where_driver) if where_driver else "1=1"
    params.extend([limit, offset])
    priority_filter = " AND c.suggested_priority = %s" if priority else ""
    if priority:
        params_priority = params[:-2] + [priority] + params[-2:]
    else:
        params_priority = params
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    c.week_start,
                    c.week_label,
                    c.cohort_type,
                    c.cohort_size,
                    c.avg_risk_score,
                    c.avg_delta_pct,
                    c.avg_baseline_value,
                    c.dominant_segment,
                    c.suggested_priority,
                    c.suggested_channel,
                    c.action_name,
                    c.action_objective
                FROM {_COHORTS} c
                WHERE EXISTS (SELECT 1 FROM {_DRIVER_BASE} d WHERE d.cohort_type = c.cohort_type AND d.week_start = c.week_start AND {wd})
                {priority_filter}
                ORDER BY CASE c.suggested_priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, c.cohort_size DESC, c.week_start DESC
                LIMIT %s OFFSET %s
                """.replace("{wd}", wd),
                params_priority,
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.execute(
                f"""
                SELECT COUNT(*) AS n FROM {_COHORTS} c
                WHERE EXISTS (SELECT 1 FROM {_DRIVER_BASE} d WHERE d.cohort_type = c.cohort_type AND d.week_start = c.week_start AND {wd})
                {priority_filter}
                """.replace("{wd}", wd),
                params_priority[:-2],
            )
            total = cur.fetchone()["n"]
            return {"data": rows, "total": total, "limit": limit, "offset": offset}
        finally:
            cur.close()


def get_action_engine_cohort_detail(
    cohort_type: str,
    week_start: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    """Drivers in a given cohort for the given week. For drilldown and export."""
    conditions = ["cohort_type = %s", "week_start = %s::date"]
    params: list = [cohort_type, week_start]
    if country:
        conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(city)
    if park_id:
        conditions.append("park_id::text = %s")
        params.append(str(park_id))
    where_sql = " AND ".join(conditions)
    params.extend([limit, offset])
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    driver_key,
                    driver_name,
                    week_start,
                    week_label,
                    country,
                    city,
                    park_id,
                    park_name,
                    segment_current,
                    segment_previous,
                    movement_type,
                    trips_current_week,
                    avg_trips_baseline,
                    delta_abs,
                    delta_pct,
                    alert_type,
                    severity,
                    risk_score,
                    risk_band,
                    active_weeks_in_window,
                    weeks_declining_consecutively,
                    weeks_rising_consecutively,
                    cohort_type
                FROM {_DRIVER_BASE}
                WHERE {where_sql}
                ORDER BY risk_score DESC NULLS LAST, delta_pct ASC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) AS n FROM {_DRIVER_BASE} WHERE {where_sql}", params[:-2])
            total = cur.fetchone()["n"]
            return {"cohort_type": cohort_type, "week_start": week_start, "data": rows, "total": total, "limit": limit, "offset": offset}
        finally:
            cur.close()


def get_action_engine_recommendations(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Top N recommended actions (by priority_score) for the panel."""
    where_driver = []
    params: list = []
    if week_start:
        where_driver.append("d.week_start = %s::date")
        params.append(week_start)
    if from_date:
        where_driver.append("d.week_start >= %s::date")
        params.append(from_date)
    if to_date:
        where_driver.append("d.week_start <= %s::date")
        params.append(to_date)
    if country:
        where_driver.append("LOWER(TRIM(d.country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        where_driver.append("LOWER(TRIM(d.city)) = LOWER(TRIM(%s))")
        params.append(city)
    if park_id:
        where_driver.append("d.park_id::text = %s")
        params.append(str(park_id))
    if segment_current:
        where_driver.append("d.segment_current = %s")
        params.append(segment_current)
    wd = " AND ".join(where_driver) if where_driver else "1=1"
    params.append(top_n)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    r.week_start,
                    r.week_label,
                    r.cohort_type,
                    r.cohort_size,
                    r.avg_risk_score,
                    r.avg_delta_pct,
                    r.dominant_segment,
                    r.suggested_priority,
                    r.suggested_channel,
                    r.action_name,
                    r.action_objective,
                    r.priority_score
                FROM {_RECOMMENDATIONS} r
                WHERE EXISTS (SELECT 1 FROM {_DRIVER_BASE} d WHERE d.cohort_type = r.cohort_type AND d.week_start = r.week_start AND {wd})
                ORDER BY r.priority_score DESC NULLS LAST, r.cohort_size DESC
                LIMIT %s
                """,
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            return {"data": rows}
        finally:
            cur.close()


def get_action_engine_export(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
    max_rows: int = 10000,
) -> list[dict[str, Any]]:
    """Export actionable drivers with active filters."""
    where_sql, params = _build_where(
        week_start=week_start, from_date=from_date, to_date=to_date,
        country=country, city=city, park_id=park_id,
        segment_current=segment_current, cohort_type=cohort_type, priority=priority,
    )
    params.append(max_rows)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    driver_key,
                    driver_name,
                    week_start,
                    week_label,
                    country,
                    city,
                    park_id,
                    park_name,
                    segment_current,
                    segment_previous,
                    movement_type,
                    trips_current_week,
                    avg_trips_baseline,
                    delta_abs,
                    delta_pct,
                    alert_type,
                    severity,
                    risk_score,
                    risk_band,
                    active_weeks_in_window,
                    weeks_declining_consecutively,
                    weeks_rising_consecutively,
                    cohort_type
                FROM {_DRIVER_BASE}
                WHERE {where_sql}
                ORDER BY risk_score DESC NULLS LAST, delta_pct ASC NULLS LAST
                LIMIT %s
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
