"""
Operational Behavioral Intelligence Service - Fase 2B.2
Diagnostico operacional profundo de conductores.
Optimized: usa facts materializadas (309K-2M filas, no VIEWs 64M+).

Capas:
  1. Session analytics (MVIEW)
  2. Zone behavior analytics (zone_daily_fact)
  3. Time behavior analytics (hourly_fact)
  4. Efficiency analytics (trip_daily_fact)
  5. Idle behavior analytics
  6. Pre-churn behavior signals (trip_daily_fact)
  7. Operational archetypes (trip_daily_fact)
  8. Top vs churned (trip_daily_fact)

Reglas:
  - NO generar recomendaciones.
  - NO automatizar acciones.
  - NO usar IA/ML.
  - Todo deterministico.
  - No romper lifecycle, benchmarking, pattern diagnosis, Omniview, Plan vs Real.
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import date, datetime, timedelta
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

TIMEOUT_MS = 120000
SESSION_TIMEOUT_MS = 180000

# Materialized facts (2B.2) - fast, pre-aggregated
FACT_TRIP_DAILY = "ops.driver_trip_behavior_daily_fact"
FACT_ZONE_DAILY = "ops.driver_zone_behavior_daily_fact"
FACT_HOURLY = "ops.driver_time_behavior_hourly_fact"
FACT_SESSION = "ops.driver_session_fact"

# ========== HELPERS ==========

def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(timeout_ms),))
    return c


def _resolve_source(conn) -> dict:
    """Metadata de fuentes disponibles."""
    available = {}
    for name, table in [
        ("trip_daily_fact", FACT_TRIP_DAILY),
        ("zone_daily_fact", FACT_ZONE_DAILY),
        ("hourly_fact", FACT_HOURLY),
        ("session_mview", FACT_SESSION),
    ]:
        parts = table.split(".")
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s) AS ok",
                (parts[0], parts[1]),
            )
            row = cur.fetchone()
            available[name] = bool(row and row.get("ok"))
        except Exception:
            available[name] = False
        finally:
            cur.close()

    # Get refresh max date from trip_daily_fact
    refresh_max_date = None
    if available.get("trip_daily_fact"):
        cur2 = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur2.execute(f"SELECT MAX(activity_date) FROM {FACT_TRIP_DAILY}")
            r = cur2.fetchone()
            if r and r.get("max"):
                refresh_max_date = str(r["max"])
        except Exception:
            pass
        finally:
            cur2.close()

    return {
        "data_source": FACT_TRIP_DAILY,
        "source_type": "materialized_facts_2b2",
        "optimized_source": True,
        "available_objects": available,
        "facts_used": [FACT_TRIP_DAILY, FACT_ZONE_DAILY, FACT_HOURLY, FACT_SESSION],
        "refresh_max_date": refresh_max_date,
        "missing_columns": [],
    }


def _safe_num(val, default=None):
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _where_clause(period_days: int, table_alias: str = "f", country=None, city=None):
    """Build WHERE clause for fact tables with date filter."""
    parts = [f"{table_alias}.activity_date >= CURRENT_DATE - {period_days}"]
    params: dict = {}
    if country:
        parts.append(f"{table_alias}.country = %(country)s")
        params["country"] = country
    if city:
        parts.append(f"{table_alias}.city = %(city)s")
        params["city"] = city
    return " AND ".join(parts), params


# ========== 1. SUMMARY ==========

def get_operational_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        where_sql, params = _where_clause(period_days, "f", country, city)

        cur.execute(
            f"""
            SELECT
                COUNT(DISTINCT f.driver_id) AS total_drivers,
                SUM(f.trips) AS total_completed_trips,
                SUM(f.trips + f.cancelled_trips) AS total_trips,
                SUM(f.cancelled_trips) AS total_cancelled,
                SUM(f.revenue) AS total_revenue,
                SUM(f.distance_km) AS total_distance_km,
                SUM(f.duration_min) AS total_duration_min,
                AVG(f.revenue_per_trip) FILTER (WHERE f.revenue_per_trip IS NOT NULL) AS avg_revenue_per_trip,
                AVG(CASE WHEN f.trips > 0 THEN f.distance_km / f.trips END) AS avg_distance_km,
                AVG(CASE WHEN f.trips > 0 THEN f.duration_min / f.trips END) AS avg_duration_min,
                COUNT(DISTINCT f.activity_date) AS active_days,
                COUNT(DISTINCT f.park_id) AS active_zones,
                COUNT(DISTINCT f.city) AS active_cities
            FROM {FACT_TRIP_DAILY} f
            WHERE {where_sql}
            """,
            params,
        )
        summary = dict(cur.fetchone() or {})

        return {
            "summary": {
                "total_drivers": summary.get("total_drivers", 0),
                "total_completed_trips": summary.get("total_completed_trips", 0),
                "total_trips": summary.get("total_trips", 0),
                "total_cancelled_trips": summary.get("total_cancelled", 0),
                "total_revenue": _safe_num(summary.get("total_revenue")),
                "total_distance_km": _safe_num(summary.get("total_distance_km")),
                "total_duration_min": _safe_num(summary.get("total_duration_min")),
                "avg_revenue_per_trip": _safe_num(summary.get("avg_revenue_per_trip")),
                "avg_distance_km": _safe_num(summary.get("avg_distance_km")),
                "avg_duration_min": _safe_num(summary.get("avg_duration_min")),
                "active_days": summary.get("active_days", 0),
                "active_zones": summary.get("active_zones", 0),
                "active_cities": summary.get("active_cities", 0),
                "period_days": period_days,
            },
            "source": source_meta,
        }


# ========== 2. EFFICIENCY ==========

def get_efficiency_analytics(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        where_sql, params = _where_clause(period_days, "f", country, city)

        # Main KPIs
        cur.execute(
            f"""
            WITH driver_agg AS (
                SELECT
                    f.driver_id,
                    SUM(f.trips) AS completed_trips,
                    COUNT(DISTINCT f.activity_date) AS active_days,
                    SUM(f.revenue) AS total_revenue,
                    SUM(f.distance_km) AS total_distance_km,
                    SUM(f.duration_min) AS total_duration_min,
                    SUM(f.peak_hour_trips) AS peak_hour_trips,
                    SUM(f.weekend_trips) AS weekend_trips,
                    COUNT(DISTINCT f.park_id) AS zones_used
                FROM {FACT_TRIP_DAILY} f
                WHERE {where_sql} AND f.trips > 0
                GROUP BY f.driver_id
            )
            SELECT
                AVG(CASE WHEN total_duration_min > 0 THEN total_revenue / (total_duration_min / 60.0) END) AS avg_revenue_per_hour,
                AVG(CASE WHEN total_distance_km > 0 THEN total_revenue / total_distance_km END) AS avg_revenue_per_km,
                AVG(CASE WHEN total_duration_min > 0 THEN completed_trips / (total_duration_min / 60.0) END) AS avg_trips_per_hour,
                AVG(CASE WHEN active_days > 0 THEN completed_trips::numeric / active_days END) AS avg_trips_per_day,
                AVG(CASE WHEN active_days > 0 THEN total_revenue / active_days END) AS avg_revenue_per_day,
                AVG(CASE WHEN completed_trips > 0 THEN total_revenue / completed_trips END) AS avg_revenue_per_trip,
                AVG(CASE WHEN completed_trips > 0 THEN peak_hour_trips::numeric / completed_trips END) AS avg_peak_hour_share,
                AVG(CASE WHEN completed_trips > 0 THEN weekend_trips::numeric / completed_trips END) AS avg_weekend_share,
                AVG(CASE WHEN active_days > 0 THEN zones_used::numeric / active_days END) AS avg_zone_concentration,
                AVG(CASE WHEN completed_trips > 0 THEN total_distance_km / completed_trips END) AS avg_km_per_trip,
                COUNT(*) AS drivers_in_sample
            FROM driver_agg
            """,
            params,
        )
        kpis = dict(cur.fetchone() or {})

        # Percentiles
        cur.execute(
            f"""
            WITH driver_agg AS (
                SELECT
                    f.driver_id,
                    SUM(f.trips) AS completed_trips,
                    COUNT(DISTINCT f.activity_date) AS active_days,
                    SUM(f.revenue) AS total_revenue,
                    SUM(f.duration_min) AS total_duration_min,
                    CASE WHEN SUM(f.duration_min) > 0 THEN SUM(f.revenue) / (SUM(f.duration_min) / 60.0) END AS revenue_per_hour
                FROM {FACT_TRIP_DAILY} f
                WHERE {where_sql} AND f.trips > 0
                GROUP BY f.driver_id
            )
            SELECT
                PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY revenue_per_hour) AS p10_rev_hour,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY revenue_per_hour) AS p25_rev_hour,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY revenue_per_hour) AS p50_rev_hour,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue_per_hour) AS p75_rev_hour,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY revenue_per_hour) AS p90_rev_hour,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY completed_trips) AS p50_trips,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY active_days) AS p50_active_days
            FROM driver_agg
            WHERE revenue_per_hour IS NOT NULL
            """,
            params,
        )
        percentiles = dict(cur.fetchone() or {})

        return {
            "kpis": {
                "avg_revenue_per_hour": _safe_num(kpis.get("avg_revenue_per_hour")),
                "avg_revenue_per_km": _safe_num(kpis.get("avg_revenue_per_km")),
                "avg_trips_per_hour": _safe_num(kpis.get("avg_trips_per_hour")),
                "avg_trips_per_day": _safe_num(kpis.get("avg_trips_per_day")),
                "avg_revenue_per_day": _safe_num(kpis.get("avg_revenue_per_day")),
                "avg_revenue_per_trip": _safe_num(kpis.get("avg_revenue_per_trip")),
                "avg_peak_hour_share": _safe_num(kpis.get("avg_peak_hour_share")),
                "avg_weekend_share": _safe_num(kpis.get("avg_weekend_share")),
                "avg_zone_concentration": _safe_num(kpis.get("avg_zone_concentration")),
                "avg_km_per_trip": _safe_num(kpis.get("avg_km_per_trip")),
                "drivers_in_sample": kpis.get("drivers_in_sample", 0),
                "available": True,
            },
            "percentiles": {
                "revenue_per_hour": {
                    "p10": _safe_num(percentiles.get("p10_rev_hour")),
                    "p25": _safe_num(percentiles.get("p25_rev_hour")),
                    "p50": _safe_num(percentiles.get("p50_rev_hour")),
                    "p75": _safe_num(percentiles.get("p75_rev_hour")),
                    "p90": _safe_num(percentiles.get("p90_rev_hour")),
                },
                "completed_trips_p50": percentiles.get("p50_trips"),
                "active_days_p50": percentiles.get("p50_active_days"),
            },
            "unavailable_kpis": {},
            "source": source_meta,
        }


# ========== 3. SESSION ANALYTICS (unchanged) ==========

def get_session_analytics(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn, timeout_ms=SESSION_TIMEOUT_MS)

        if not source_meta["available_objects"].get("session_mview"):
            return {
                "sessions": {},
                "available": False,
                "reason": "ops.driver_session_fact no existe.",
                "source": source_meta,
            }

        cur.execute(
            f"""
            WITH session_stats AS (
                SELECT driver_id, COUNT(*) AS session_count,
                    SUM(session_trips) AS total_trips,
                    AVG(session_duration_min) AS avg_session_duration_min,
                    AVG(session_trips) AS avg_trips_per_session,
                    SUM(session_revenue) AS total_session_revenue,
                    AVG(session_revenue) FILTER (WHERE session_revenue IS NOT NULL) AS avg_revenue_per_session,
                    SUM(session_distance_km) AS total_session_distance,
                    AVG(total_idle_time_min) FILTER (WHERE total_idle_time_min IS NOT NULL) AS avg_idle_per_session,
                    AVG(avg_idle_between_trips_min) FILTER (WHERE avg_idle_between_trips_min IS NOT NULL) AS avg_idle_between_trips,
                    AVG(avg_trip_duration_min) AS avg_trip_duration_min,
                    AVG(avg_ticket) AS avg_ticket_per_trip,
                    STDDEV(session_trips) AS stddev_session_trips,
                    STDDEV(session_duration_min) AS stddev_session_duration
                FROM {FACT_SESSION}
                WHERE session_date >= CURRENT_DATE - %(period)s
                GROUP BY driver_id
            )
            SELECT COUNT(*) AS drivers_with_sessions,
                AVG(session_count) AS avg_sessions_per_driver,
                AVG(total_trips) AS avg_trips_per_driver,
                AVG(avg_session_duration_min) AS avg_session_duration_min,
                AVG(avg_trips_per_session) AS avg_trips_per_session,
                AVG(CASE WHEN avg_session_duration_min > 0 THEN avg_trips_per_session / (avg_session_duration_min / 60.0) END) AS avg_trips_per_hour_in_session,
                AVG(avg_revenue_per_session) AS avg_revenue_per_session,
                AVG(CASE WHEN avg_session_duration_min > 0 AND avg_revenue_per_session IS NOT NULL THEN avg_revenue_per_session / (avg_session_duration_min / 60.0) END) AS avg_revenue_per_hour_in_session,
                AVG(avg_idle_per_session) AS avg_idle_time_per_session_min,
                AVG(avg_idle_between_trips) AS avg_idle_between_trips_min,
                AVG(avg_trip_duration_min) AS avg_trip_duration_min,
                AVG(avg_ticket_per_trip) AS avg_ticket_per_trip,
                AVG(stddev_session_trips) AS avg_session_trips_volatility,
                AVG(stddev_session_duration) AS avg_session_duration_volatility
            FROM session_stats
            """,
            {"period": period_days},
        )
        agg = dict(cur.fetchone() or {})

        cur.execute(
            f"""
            SELECT session_trips AS trips_in_session, COUNT(*) AS session_count,
                   AVG(session_duration_min) AS avg_duration, AVG(session_revenue) AS avg_revenue
            FROM {FACT_SESSION}
            WHERE session_date >= CURRENT_DATE - %(period)s
            GROUP BY session_trips ORDER BY session_trips
            """,
            {"period": period_days},
        )
        dist = [dict(r) for r in (cur.fetchall() or [])]

        cur.execute(
            f"""
            SELECT AVG(CASE WHEN session_duration_min > 0 AND total_idle_time_min IS NOT NULL
                THEN total_idle_time_min / session_duration_min END) AS avg_idle_ratio,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY CASE WHEN session_duration_min > 0 AND total_idle_time_min IS NOT NULL
                THEN total_idle_time_min / session_duration_min END) AS p50_idle_ratio
            FROM {FACT_SESSION}
            WHERE session_date >= CURRENT_DATE - %(period)s AND session_duration_min > 0
            """,
            {"period": period_days},
        )
        idle_ratio = dict(cur.fetchone() or {})

        return {
            "sessions": {
                "drivers_with_sessions": agg.get("drivers_with_sessions", 0),
                "avg_sessions_per_driver": _safe_num(agg.get("avg_sessions_per_driver")),
                "avg_trips_per_driver": _safe_num(agg.get("avg_trips_per_driver")),
                "avg_session_duration_min": _safe_num(agg.get("avg_session_duration_min")),
                "avg_trips_per_session": _safe_num(agg.get("avg_trips_per_session")),
                "avg_trips_per_hour_in_session": _safe_num(agg.get("avg_trips_per_hour_in_session")),
                "avg_revenue_per_session": _safe_num(agg.get("avg_revenue_per_session")),
                "avg_revenue_per_hour_in_session": _safe_num(agg.get("avg_revenue_per_hour_in_session")),
                "avg_idle_time_per_session_min": _safe_num(agg.get("avg_idle_time_per_session_min")),
                "avg_idle_between_trips_min": _safe_num(agg.get("avg_idle_between_trips_min")),
                "avg_idle_ratio": _safe_num(idle_ratio.get("avg_idle_ratio")),
                "p50_idle_ratio": _safe_num(idle_ratio.get("p50_idle_ratio")),
                "avg_trip_duration_min": _safe_num(agg.get("avg_trip_duration_min")),
                "avg_ticket_per_trip": _safe_num(agg.get("avg_ticket_per_trip")),
                "session_trips_volatility": _safe_num(agg.get("avg_session_trips_volatility")),
                "session_duration_volatility": _safe_num(agg.get("avg_session_duration_volatility")),
            },
            "distribution_by_trips": dist,
            "available": True,
            "source": source_meta,
        }


# ========== 4. ZONE ANALYTICS ==========

def get_zone_analytics(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        where_sql, params = _where_clause(period_days, "f", country, city)

        # Per-zone stats
        cur.execute(
            f"""
            WITH zone_stats AS (
                SELECT f.zone_key AS park_id, f.country, f.city,
                    COUNT(DISTINCT f.driver_id) AS unique_drivers,
                    SUM(f.trips) AS total_trips,
                    SUM(f.revenue) AS total_revenue,
                    AVG(CASE WHEN f.trips > 0 THEN f.revenue / f.trips END) AS avg_ticket,
                    SUM(f.distance_km) AS total_distance_km,
                    COUNT(DISTINCT f.activity_date) AS active_days,
                    SUM(f.peak_hour_trips) AS peak_hour_trips,
                    SUM(f.weekend_trips) AS weekend_trips
                FROM {FACT_ZONE_DAILY} f
                WHERE {where_sql} AND f.trips > 0
                GROUP BY f.zone_key, f.country, f.city
            )
            SELECT park_id, country, city, unique_drivers, total_trips, total_revenue, avg_ticket,
                   total_distance_km, active_days,
                   CASE WHEN total_trips > 0 THEN peak_hour_trips::numeric / total_trips END AS peak_hour_share,
                   CASE WHEN total_trips > 0 THEN weekend_trips::numeric / total_trips END AS weekend_share,
                   CASE WHEN unique_drivers > 0 THEN total_trips::numeric / unique_drivers END AS trips_per_driver,
                   CASE WHEN active_days > 0 THEN total_trips::numeric / active_days END AS trips_per_day
            FROM zone_stats
            ORDER BY total_trips DESC
            LIMIT 50
            """,
            params,
        )
        zones = [dict(r) for r in (cur.fetchall() or [])]

        # Zone concentration
        cur.execute(
            f"""
            WITH driver_zone_concentration AS (
                SELECT f.driver_id, COUNT(DISTINCT f.zone_key) AS zones_used, SUM(f.trips) AS total_trips
                FROM {FACT_ZONE_DAILY} f
                WHERE {where_sql} AND f.trips > 0
                GROUP BY f.driver_id
            )
            SELECT
                AVG(zones_used) AS avg_zones_per_driver,
                COUNT(*) FILTER (WHERE zones_used = 1) AS single_zone_drivers,
                COUNT(*) FILTER (WHERE zones_used >= 5) AS multi_zone_drivers,
                COUNT(*) AS total_drivers,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY zones_used) AS p50_zones_used
            FROM driver_zone_concentration
            """,
            params,
        )
        concentration = dict(cur.fetchone() or {})

        return {
            "zones": zones,
            "concentration": {
                "avg_zones_per_driver": _safe_num(concentration.get("avg_zones_per_driver")),
                "p50_zones_used": concentration.get("p50_zones_used"),
                "single_zone_drivers": concentration.get("single_zone_drivers", 0),
                "multi_zone_drivers": concentration.get("multi_zone_drivers", 0),
                "total_drivers": concentration.get("total_drivers", 0),
            },
            "note": "zone = park_id (proxy). Source: zone_daily_fact (materialized).",
            "available": True,
            "source": source_meta,
        }


# ========== 5. TIME PATTERNS ==========

def get_time_patterns(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        where_sql, params = _where_clause(period_days, "f", country, city)

        # Hourly distribution
        cur.execute(
            f"""
            SELECT f.trip_hour, SUM(f.trips) AS trips,
                   AVG(CASE WHEN f.trips > 0 THEN f.revenue / f.trips END) AS avg_revenue,
                   AVG(CASE WHEN f.trips > 0 THEN f.distance_km / f.trips END) AS avg_distance_km,
                   AVG(CASE WHEN f.trips > 0 THEN f.duration_min / f.trips END) AS avg_duration_min,
                   COUNT(DISTINCT f.driver_id) AS unique_drivers
            FROM {FACT_HOURLY} f
            WHERE {where_sql} AND f.trips > 0
            GROUP BY f.trip_hour
            ORDER BY f.trip_hour
            """,
            params,
        )
        hourly = [dict(r) for r in (cur.fetchall() or [])]

        # Daily (DOW) distribution
        cur.execute(
            f"""
            SELECT f.day_of_week,
                   CASE f.day_of_week WHEN 0 THEN 'Domingo' WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes'
                       WHEN 3 THEN 'Miercoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes' WHEN 6 THEN 'Sabado' END AS day_name,
                   SUM(f.trips) AS trips,
                   AVG(CASE WHEN f.trips > 0 THEN f.revenue / f.trips END) AS avg_revenue,
                   COUNT(DISTINCT f.driver_id) AS unique_drivers
            FROM {FACT_HOURLY} f
            WHERE {where_sql} AND f.trips > 0
            GROUP BY f.day_of_week
            ORDER BY f.day_of_week
            """,
            params,
        )
        daily = [dict(r) for r in (cur.fetchall() or [])]

        # Peak vs off-peak
        cur.execute(
            f"""
            SELECT CASE WHEN f.is_peak_hour THEN 'peak' ELSE 'off_peak' END AS period_type,
                   SUM(f.trips) AS trips,
                   AVG(CASE WHEN f.trips > 0 THEN f.revenue / f.trips END) AS avg_revenue,
                   AVG(CASE WHEN f.trips > 0 THEN f.distance_km / f.trips END) AS avg_distance_km,
                   COUNT(DISTINCT f.driver_id) AS unique_drivers
            FROM {FACT_HOURLY} f
            WHERE {where_sql} AND f.trips > 0
            GROUP BY f.is_peak_hour
            """,
            params,
        )
        peak_offpeak = [dict(r) for r in (cur.fetchall() or [])]

        return {
            "hourly_distribution": hourly,
            "daily_distribution": daily,
            "peak_vs_offpeak": peak_offpeak,
            "peak_definition": "Peak = 6-9h y 17-20h",
            "available": True,
            "source": source_meta,
        }


# ========== 6. PRE-CHURN SIGNALS ==========

def get_pre_churn_signals(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 56,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        half = period_days // 2

        where1 = [f"f.activity_date >= CURRENT_DATE - {period_days}",
                  f"f.activity_date < CURRENT_DATE - {half}"]
        where2 = [f"f.activity_date >= CURRENT_DATE - {half}"]
        params: dict = {}
        if country:
            where1.append("f.country = %(country)s")
            where2.append("f.country = %(country)s")
            params["country"] = country
        if city:
            where1.append("f.city = %(city)s")
            where2.append("f.city = %(city)s")
            params["city"] = city

        cur.execute(
            f"""
            WITH first_half AS (
                SELECT f.driver_id,
                    SUM(f.trips) AS trips_p1,
                    COUNT(DISTINCT f.activity_date) AS active_days_p1,
                    SUM(f.revenue) AS revenue_p1,
                    SUM(f.peak_hour_trips) AS peak_trips_p1,
                    SUM(f.weekend_trips) AS weekend_trips_p1,
                    COUNT(DISTINCT f.park_id) AS zones_p1,
                    SUM(f.duration_min) AS duration_p1
                FROM {FACT_TRIP_DAILY} f
                WHERE {' AND '.join(where1)} AND f.trips > 0
                GROUP BY f.driver_id
            ),
            second_half AS (
                SELECT f.driver_id,
                    SUM(f.trips) AS trips_p2,
                    COUNT(DISTINCT f.activity_date) AS active_days_p2,
                    SUM(f.revenue) AS revenue_p2,
                    SUM(f.peak_hour_trips) AS peak_trips_p2,
                    SUM(f.duration_min) AS duration_p2
                FROM {FACT_TRIP_DAILY} f
                WHERE {' AND '.join(where2)} AND f.trips > 0
                GROUP BY f.driver_id
            )
            SELECT fh.driver_id, fh.trips_p1, sh.trips_p2, fh.active_days_p1, sh.active_days_p2,
                   fh.revenue_p1, sh.revenue_p2,
                   CASE WHEN fh.trips_p1 > 0 THEN (sh.trips_p2::numeric - fh.trips_p1) / fh.trips_p1 END AS trips_change_pct,
                   CASE WHEN fh.active_days_p1 > 0 THEN (sh.active_days_p2::numeric - fh.active_days_p1) / fh.active_days_p1 END AS active_days_change_pct,
                   CASE WHEN fh.revenue_p1 > 0 THEN (sh.revenue_p2 - fh.revenue_p1) / fh.revenue_p1 END AS revenue_change_pct,
                   CASE WHEN fh.trips_p1 > 0 AND fh.duration_p1 > 0 THEN fh.revenue_p1 / (fh.duration_p1 / 60.0) END AS rev_per_hour_p1,
                   CASE WHEN sh.trips_p2 > 0 AND sh.duration_p2 > 0 THEN sh.revenue_p2 / (sh.duration_p2 / 60.0) END AS rev_per_hour_p2,
                   CASE WHEN fh.trips_p1 > 0 THEN fh.peak_trips_p1::numeric / fh.trips_p1 END AS peak_share_p1,
                   CASE WHEN sh.trips_p2 > 0 THEN sh.peak_trips_p2::numeric / sh.trips_p2 END AS peak_share_p2
            FROM first_half fh
            LEFT JOIN second_half sh ON fh.driver_id = sh.driver_id
            """,
            params,
        )
        driver_changes = [dict(r) for r in (cur.fetchall() or [])]

        signals = []
        for d in driver_changes:
            driver_signals = []
            driver_id = d.get("driver_id")
            trips_change = d.get("trips_change_pct")
            if trips_change is not None and trips_change < -0.30:
                driver_signals.append({"type": "TRIPS_DECLINE", "change_pct": round(trips_change * 100, 1),
                    "severity": "STRONG_DEGRADATION" if trips_change < -0.50 else "MODERATE_DEGRADATION"})
            elif trips_change is not None and trips_change < -0.15:
                driver_signals.append({"type": "TRIPS_DECLINE", "change_pct": round(trips_change * 100, 1),
                    "severity": "EARLY_WARNING"})
            active_change = d.get("active_days_change_pct")
            if active_change is not None and active_change < -0.30:
                driver_signals.append({"type": "ACTIVE_DAYS_DECLINE", "change_pct": round(active_change * 100, 1),
                    "severity": "STRONG_DEGRADATION" if active_change < -0.50 else "MODERATE_DEGRADATION"})
            elif active_change is not None and active_change < -0.15:
                driver_signals.append({"type": "ACTIVE_DAYS_DECLINE", "change_pct": round(active_change * 100, 1),
                    "severity": "EARLY_WARNING"})
            revenue_change = d.get("revenue_change_pct")
            if revenue_change is not None and revenue_change < -0.30:
                driver_signals.append({"type": "REVENUE_DECLINE", "change_pct": round(revenue_change * 100, 1),
                    "severity": "STRONG_DEGRADATION" if revenue_change < -0.50 else "MODERATE_DEGRADATION"})
            peak_p1 = d.get("peak_share_p1")
            peak_p2 = d.get("peak_share_p2")
            if peak_p1 is not None and peak_p2 is not None and peak_p1 > 0:
                peak_change = (peak_p2 - peak_p1) / peak_p1
                if peak_change < -0.20:
                    driver_signals.append({"type": "PEAK_HOUR_PARTICIPATION_DECLINE",
                        "change_pct": round(peak_change * 100, 1), "severity": "EARLY_WARNING"})
            rev_h_p1 = d.get("rev_per_hour_p1")
            rev_h_p2 = d.get("rev_per_hour_p2")
            if rev_h_p1 is not None and rev_h_p2 is not None and rev_h_p1 > 0:
                rev_h_change = (rev_h_p2 - rev_h_p1) / rev_h_p1
                if rev_h_change < -0.20:
                    driver_signals.append({"type": "REVENUE_PER_HOUR_DECLINE",
                        "change_pct": round(rev_h_change * 100, 1), "severity": "MODERATE_DEGRADATION"})
            if d.get("trips_p2") is None or d.get("trips_p2") == 0:
                driver_signals.append({"type": "POTENTIAL_CHURN", "change_pct": -100.0,
                    "severity": "STRONG_DEGRADATION"})
            if driver_signals:
                signals.append({
                    "driver_id": driver_id,
                    "first_half": {"trips": d.get("trips_p1", 0), "active_days": d.get("active_days_p1", 0),
                        "revenue": _safe_num(d.get("revenue_p1")), "rev_per_hour": _safe_num(rev_h_p1),
                        "peak_share": _safe_num(peak_p1)},
                    "second_half": {"trips": d.get("trips_p2", 0) or 0, "active_days": d.get("active_days_p2", 0) or 0,
                        "revenue": _safe_num(d.get("revenue_p2")), "rev_per_hour": _safe_num(rev_h_p2),
                        "peak_share": _safe_num(peak_p2)},
                    "signals": driver_signals,
                    "max_severity": max((s["severity"] for s in driver_signals),
                        key=lambda x: {"STRONG_DEGRADATION": 3, "MODERATE_DEGRADATION": 2, "EARLY_WARNING": 1}.get(x, 0)),
                })

        severity_counts = {"EARLY_WARNING": 0, "MODERATE_DEGRADATION": 0, "STRONG_DEGRADATION": 0}
        for s in signals:
            sev = s["max_severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "signals": signals[:500],
            "total_drivers_with_signals": len(signals),
            "severity_summary": severity_counts,
            "available": True,
            "note": "Sin recomendaciones. Diagnostico deterministico solamente.",
            "source": source_meta,
        }


# ========== 7. OPERATIONAL ARCHETYPES ==========

def get_operational_archetypes(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        where_sql, params = _where_clause(period_days, "f", country, city)

        cur.execute(
            f"""
            WITH driver_metrics AS (
                SELECT f.driver_id,
                    SUM(f.trips)::INTEGER AS total_trips,
                    COUNT(DISTINCT f.activity_date) AS active_days,
                    SUM(f.revenue) AS total_revenue,
                    SUM(f.duration_min) AS total_duration_min,
                    SUM(f.distance_km) AS total_distance_km,
                    SUM(f.peak_hour_trips) AS peak_trips,
                    SUM(f.weekend_trips) AS weekend_trips,
                    SUM(f.weekday_trips) AS weekday_trips,
                    COUNT(DISTINCT f.park_id) AS zones_used
                FROM {FACT_TRIP_DAILY} f
                WHERE {where_sql} AND f.trips > 0
                GROUP BY f.driver_id
            )
            SELECT *,
                CASE WHEN total_duration_min > 0 THEN total_revenue / (total_duration_min / 60.0) END AS revenue_per_hour,
                CASE WHEN total_distance_km > 0 THEN total_revenue / total_distance_km END AS revenue_per_km,
                CASE WHEN total_duration_min > 0 THEN total_trips::numeric / (total_duration_min / 60.0) END AS trips_per_hour,
                CASE WHEN total_trips > 0 THEN peak_trips::numeric / total_trips END AS peak_hour_share,
                CASE WHEN total_trips > 0 THEN weekend_trips::numeric / total_trips END AS weekend_share
            FROM driver_metrics
            """,
            params,
        )
        drivers = [dict(r) for r in (cur.fetchall() or [])]

        if not drivers:
            return {"archetypes": [], "distribution": {}, "available": False,
                    "reason": "No hay conductores con viajes en el periodo.", "source": source_meta}

        trips_list = [d["total_trips"] or 0 for d in drivers]
        active_days_list = [d["active_days"] or 0 for d in drivers]
        rev_per_hour_list = [_safe_num(d.get("revenue_per_hour"), 0) for d in drivers]
        weekend_share_list = [_safe_num(d.get("weekend_share"), 0) for d in drivers]
        peak_share_list = [_safe_num(d.get("peak_hour_share"), 0) for d in drivers]

        def median(lst):
            if not lst: return 0
            s = sorted(lst)
            return s[len(s) // 2]

        p50_trips = median(trips_list)
        p50_active_days = median(active_days_list)
        p50_rev_hour = median(rev_per_hour_list)
        p50_weekend = median(weekend_share_list)
        p50_peak = median(peak_share_list)

        archetype_map = []
        archetype_counts = {}

        for d in drivers:
            trips = d["total_trips"] or 0
            active_days = d["active_days"] or 0
            rev_hour = _safe_num(d.get("revenue_per_hour"), 0)
            weekend_share = _safe_num(d.get("weekend_share"), 0)
            peak_share = _safe_num(d.get("peak_hour_share"), 0)
            trips_per_hour = _safe_num(d.get("trips_per_hour"), 0)
            zones = d.get("zones_used") or 0

            archetypes = []
            if active_days >= 5 and trips >= 40:
                archetypes.append("FULLTIMER")
            if 1 <= active_days <= 4:
                archetypes.append("PART_TIMER")
            if weekend_share > 0.50 and trips >= 10:
                archetypes.append("WEEKEND_SPECIALIST")
            if peak_share > 0.60 and trips >= 10:
                archetypes.append("PEAK_HOUR_SPECIALIST")
            if rev_hour > p50_rev_hour * 1.5 and trips_per_hour > 0:
                archetypes.append("HIGH_EFFICIENCY")
            if trips > p50_trips * 1.5 and rev_hour < p50_rev_hour * 0.7:
                archetypes.append("HIGH_VOLUME_LOW_EFFICIENCY")
            if active_days >= 5 and trips >= p50_trips * 0.8:
                archetypes.append("CONSISTENT_OPERATOR")
            if active_days <= 2 and trips < p50_trips * 0.5:
                archetypes.append("INCONSISTENT_OPERATOR")
            if active_days >= 6 and trips > 0 and (trips / active_days) < (p50_trips / max(p50_active_days, 1)) * 0.5:
                archetypes.append("BURNOUT_PATTERN")

            primary = archetypes[0] if archetypes else "UNCLASSIFIED"
            archetype_map.append({
                "driver_id": d["driver_id"], "primary_archetype": primary, "all_archetypes": archetypes,
                "metrics": {
                    "total_trips": trips, "active_days": active_days,
                    "revenue_per_hour": round(rev_hour, 2),
                    "revenue_per_km": round(_safe_num(d.get("revenue_per_km"), 0), 2),
                    "trips_per_hour": round(trips_per_hour, 2),
                    "peak_hour_share": round(peak_share, 4),
                    "weekend_share": round(weekend_share, 4),
                    "zones_used": zones,
                },
            })
            archetype_counts[primary] = archetype_counts.get(primary, 0) + 1

        distribution = {
            "FULLTIMER": archetype_counts.get("FULLTIMER", 0),
            "PART_TIMER": archetype_counts.get("PART_TIMER", 0),
            "WEEKEND_SPECIALIST": archetype_counts.get("WEEKEND_SPECIALIST", 0),
            "PEAK_HOUR_SPECIALIST": archetype_counts.get("PEAK_HOUR_SPECIALIST", 0),
            "HIGH_EFFICIENCY": archetype_counts.get("HIGH_EFFICIENCY", 0),
            "HIGH_VOLUME_LOW_EFFICIENCY": archetype_counts.get("HIGH_VOLUME_LOW_EFFICIENCY", 0),
            "CONSISTENT_OPERATOR": archetype_counts.get("CONSISTENT_OPERATOR", 0),
            "INCONSISTENT_OPERATOR": archetype_counts.get("INCONSISTENT_OPERATOR", 0),
            "BURNOUT_PATTERN": archetype_counts.get("BURNOUT_PATTERN", 0),
            "UNCLASSIFIED": archetype_counts.get("UNCLASSIFIED", 0),
        }

        return {
            "archetypes": archetype_map[:500],
            "total_drivers_classified": len(drivers),
            "distribution": distribution,
            "classification_rules": {
                "FULLTIMER": "active_days >= 5 AND total_trips >= 40",
                "PART_TIMER": "active_days BETWEEN 1 AND 4",
                "WEEKEND_SPECIALIST": "weekend_share > 0.50 AND total_trips >= 10",
                "PEAK_HOUR_SPECIALIST": "peak_hour_share > 0.60 AND total_trips >= 10",
                "HIGH_EFFICIENCY": "revenue_per_hour > p50 * 1.5",
                "HIGH_VOLUME_LOW_EFFICIENCY": "trips > p50 * 1.5 AND revenue_per_hour < p50 * 0.7",
                "CONSISTENT_OPERATOR": "active_days >= 5 AND trips >= p50 * 0.8",
                "INCONSISTENT_OPERATOR": "active_days <= 2 AND trips < p50 * 0.5",
                "BURNOUT_PATTERN": "active_days >= 6 AND trips_per_active_day < p50 * 0.5",
            },
            "reference_thresholds": {
                "p50_trips": p50_trips, "p50_active_days": p50_active_days,
                "p50_revenue_per_hour": round(p50_rev_hour, 2),
                "p50_weekend_share": round(p50_weekend, 4),
                "p50_peak_share": round(p50_peak, 4),
            },
            "available": True,
            "note": "Clasificacion deterministica sin ML. Un driver puede pertenecer a multiples arquetipos.",
            "source": source_meta,
        }


# ========== 8. TOP VS CHURNED ==========

def get_top_vs_churned(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        where_sql, params = _where_clause(period_days, "f", country, city)

        cur.execute(
            f"""
            WITH driver_metrics AS (
                SELECT f.driver_id,
                    SUM(f.revenue) AS total_revenue,
                    SUM(f.trips) AS total_trips,
                    COUNT(DISTINCT f.activity_date) AS active_days,
                    MAX(f.activity_date) AS last_trip_date,
                    SUM(f.duration_min) AS total_duration_min,
                    SUM(f.distance_km) AS total_distance_km,
                    SUM(f.peak_hour_trips) AS peak_trips,
                    SUM(f.weekend_trips) AS weekend_trips,
                    COUNT(DISTINCT f.park_id) AS zones_used
                FROM {FACT_TRIP_DAILY} f
                WHERE {where_sql} AND f.trips > 0 AND f.revenue IS NOT NULL
                GROUP BY f.driver_id
            ),
            ranked AS (
                SELECT *, NTILE(5) OVER (ORDER BY total_revenue DESC) AS revenue_quintile
                FROM driver_metrics
            ),
            segmented AS (
                SELECT CASE
                           WHEN revenue_quintile = 1 THEN 'TOP_PERFORMER'
                           WHEN last_trip_date < CURRENT_DATE - 14 THEN 'RECENTLY_CHURNED'
                           ELSE 'OTHER' END AS segment,
                       total_revenue, total_trips, active_days, total_duration_min,
                       total_distance_km, peak_trips, weekend_trips, zones_used
                FROM ranked
            )
            SELECT segment,
                   COUNT(*) AS drivers,
                   AVG(total_revenue) AS avg_revenue,
                   AVG(total_trips) AS avg_trips,
                   AVG(active_days) AS avg_active_days,
                   AVG(CASE WHEN total_duration_min > 0 THEN total_revenue / (total_duration_min / 60.0) END) AS avg_revenue_per_hour,
                   AVG(CASE WHEN total_distance_km > 0 THEN total_revenue / total_distance_km END) AS avg_revenue_per_km,
                   AVG(CASE WHEN total_trips > 0 THEN peak_trips::numeric / total_trips END) AS avg_peak_hour_share,
                   AVG(CASE WHEN total_trips > 0 THEN weekend_trips::numeric / total_trips END) AS avg_weekend_share,
                   AVG(zones_used) AS avg_zones_used
            FROM segmented
            WHERE segment IN ('TOP_PERFORMER', 'RECENTLY_CHURNED')
            GROUP BY segment
            """,
            params,
        )
        comparison = [dict(r) for r in (cur.fetchall() or [])]

        return {
            "comparison": comparison,
            "available": True,
            "note": "TOP_PERFORMER = top 20% por revenue. RECENTLY_CHURNED = sin actividad en ultimos 14 dias.",
            "source": source_meta,
        }
