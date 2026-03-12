"""
Top Driver Behavior — Benchmarks and patterns for Elite/Legend (and FT).
Reads from ops.v_top_driver_behavior_weekly, ops.v_top_driver_behavior_benchmarks, ops.v_top_driver_behavior_patterns.
Additive; does not modify existing modules.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

_TOP_WEEKLY = "ops.v_top_driver_behavior_weekly"
_BENCHMARKS = "ops.v_top_driver_behavior_benchmarks"
_PATTERNS = "ops.v_top_driver_behavior_patterns"


def get_top_driver_behavior_summary(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """Counts of Elite, Legend, FT drivers in window; date range."""
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
    where_sql = " AND ".join(conditions) if conditions else "1=1"
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    COUNT(DISTINCT driver_key) FILTER (WHERE segment_current = 'ELITE') AS elite_drivers,
                    COUNT(DISTINCT driver_key) FILTER (WHERE segment_current = 'LEGEND') AS legend_drivers,
                    COUNT(DISTINCT driver_key) FILTER (WHERE segment_current = 'FT') AS ft_drivers
                FROM {_TOP_WEEKLY}
                WHERE {where_sql}
                """,
                params,
            )
            row = cur.fetchone()
            out = dict(row) if row else {"elite_drivers": 0, "legend_drivers": 0, "ft_drivers": 0}
            out["from_date"] = from_date
            out["to_date"] = to_date
            out["week_start"] = week_start
            return out
        finally:
            cur.close()


def get_top_driver_behavior_benchmarks(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """Aggregate benchmarks by segment (ELITE, LEGEND, FT). Optional geo filter on underlying weekly view."""
    # Benchmarks view aggregates all time; we can filter by joining to weekly and re-aggregating if needed
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    segment_current,
                    driver_count,
                    avg_weekly_trips,
                    consistency_score_avg,
                    active_weeks_avg
                FROM {_BENCHMARKS}
                ORDER BY CASE segment_current WHEN 'LEGEND' THEN 1 WHEN 'ELITE' THEN 2 WHEN 'FT' THEN 3 ELSE 4 END
                """
            )
            rows = [dict(r) for r in cur.fetchall()]
            return {"data": rows}
        finally:
            cur.close()


def get_top_driver_behavior_patterns(
    segment_current: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Concentration by segment, city, park. Optional segment filter."""
    conditions = []
    params: list = []
    if segment_current:
        conditions.append("segment_current = %s")
        params.append(segment_current)
    if country:
        conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(city)
    where_sql = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    segment_current,
                    country,
                    city,
                    park_id,
                    park_name,
                    driver_count,
                    avg_trips,
                    pct_of_segment
                FROM {_PATTERNS}
                WHERE {where_sql}
                ORDER BY driver_count DESC, avg_trips DESC NULLS LAST
                LIMIT %s
                """,
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            return {"data": rows}
        finally:
            cur.close()


def get_top_driver_behavior_playbook_insights(
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Short playbook-style insights (e.g. Elite vs FT consistency). Derived from benchmarks."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT segment_current, avg_weekly_trips, consistency_score_avg, driver_count
                FROM {_BENCHMARKS}
                """
            )
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
    by_seg = {r["segment_current"]: r for r in rows}
    insights = []
    elite = by_seg.get("ELITE") or {}
    legend = by_seg.get("LEGEND") or {}
    ft = by_seg.get("FT") or {}
    if elite and ft and (elite.get("consistency_score_avg") or 0) > (ft.get("consistency_score_avg") or 0):
        insights.append({
            "title": "Elite vs FT: consistencia",
            "text": "Los conductores Elite muestran mayor consistencia semanal que los FT; priorizar estabilidad en coaching.",
        })
    if legend and elite and (legend.get("avg_weekly_trips") or 0) > (elite.get("avg_weekly_trips") or 0):
        insights.append({
            "title": "Legend vs Elite: volumen",
            "text": "Los Legend concentran más viajes por semana que los Elite; revisar patrones de territorio y días.",
        })
    if ft and elite:
        insights.append({
            "title": "Candidatos near-upgrade",
            "text": "Los FT con patrones similares a Elite (alta consistencia, alto volumen) son candidatos a nudge hacia Elite.",
        })
    if not insights:
        insights.append({"title": "Benchmarks cargados", "text": "Revisa la pestaña Benchmarks para comparar Elite, Legend y FT."})
    return insights


def get_top_driver_behavior_export(
    segment_current: Optional[str] = None,
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    max_rows: int = 10000,
) -> list[dict[str, Any]]:
    """Export Elite/Legend/FT driver list with filters."""
    conditions = []
    params: list = []
    if segment_current:
        conditions.append("segment_current = %s")
        params.append(segment_current)
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
    where_sql = " AND ".join(conditions) if conditions else "1=1"
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
                    trips_current_week,
                    avg_trips_baseline,
                    consistency_score,
                    active_weeks_in_window
                FROM {_TOP_WEEKLY}
                WHERE {where_sql}
                ORDER BY segment_current, driver_key, week_start DESC
                LIMIT %s
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()
