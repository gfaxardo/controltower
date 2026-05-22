"""
Operational Behavioral Intelligence Service — Fase 2B
Diagnóstico operacional profundo de conductores.

Capas:
  1. Session analytics
  2. Zone behavior analytics
  3. Time behavior analytics
  4. Efficiency analytics (KPIs)
  5. Idle behavior analytics
  6. Pre-churn behavior signals
  7. Operational archetypes (clasificación inicial determinística)

Reglas:
  - NO generar recomendaciones.
  - NO automatizar acciones.
  - NO usar IA/ML.
  - Si no existe la métrica, devolver available=false / null y documentar.
  - Todo determinístico.
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
SESSION_TIMEOUT_MS = 180000  # 3 min para session queries
ENRICHED_VIEW = "ops.v_real_trips_enriched_base"
TRIP_BEHAVIOR_VIEW = "ops.driver_trip_behavior_fact"
SESSION_MVIEW = "ops.driver_session_fact"
ZONE_BEHAVIOR_VIEW = "ops.driver_zone_behavior_fact"
DAILY_FACT = "ops.driver_daily_activity_fact"
RAW_TRIPS = "public.trips_2026"

# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(timeout_ms),))
    return c


def _view_exists(conn, schema_table: str) -> bool:
    parts = schema_table.split(".")
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            ) AS obj_exists""",
            (parts[0], parts[1])
        )
        row = cur.fetchone()
        return bool(row and row.get("obj_exists"))
    except Exception:
        return False
    finally:
        cur.close()


def _resolve_source(conn) -> dict:
    """Resuelve la fuente primaria y devuelve metadata de disponibilidad."""
    available = {
        "trip_behavior_view": _view_exists(conn, TRIP_BEHAVIOR_VIEW),
        "session_mview": _view_exists(conn, SESSION_MVIEW),
        "zone_behavior_view": _view_exists(conn, ZONE_BEHAVIOR_VIEW),
        "daily_fact": _view_exists(conn, DAILY_FACT),
        "enriched_view": _view_exists(conn, ENRICHED_VIEW),
        "raw_trips_2026": _view_exists(conn, "public.trips_2026"),
    }
    return {
        "data_source": TRIP_BEHAVIOR_VIEW if available["trip_behavior_view"] else ENRICHED_VIEW,
        "source_type": "view" if available["trip_behavior_view"] else "enriched_view_fallback",
        "available_objects": available,
        "missing_columns": [
            "destination_zone", "surge", "idle_before_trip_min",
            "online_hours", "acceptance_rate", "origin_lat", "destination_lat",
            "cancellation_reason_code"
        ],
    }


def _safe_num(val, default=None):
    """Convierte valor a float seguro, retorna default si es None."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _period_filter(period_days: int) -> str:
    return f"trip_date >= CURRENT_DATE - INTERVAL '{period_days} days'"


# ═══════════════════════════════════════════════════════════════════
# 1. SESSION ANALYTICS
# ═══════════════════════════════════════════════════════════════════

def get_operational_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    Resumen operacional: KPIs agregados, fuentes disponibles, metadatos.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)

        # Build WHERE clause
        where_parts = [_period_filter(period_days)]
        params = {}
        if country:
            where_parts.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        # Query desde la vista trip_behavior o enriched
        base = source_meta["data_source"]

        # KPIs agregados
        cur.execute(
            f"""
            SELECT
                COUNT(DISTINCT driver_id) AS total_drivers,
                SUM(completed_trips) AS total_completed_trips,
                COUNT(*) AS total_trips,
                SUM(CASE WHEN cancelled_trips > 0 OR cancelled_trips IS NULL AND trip_status ILIKE '%%cancel%%' THEN 1 ELSE 0 END) AS total_cancelled,
                SUM(revenue) AS total_revenue,
                SUM(distance_km) AS total_distance_km,
                SUM(duration_min) AS total_duration_min,
                AVG(revenue) FILTER (WHERE revenue IS NOT NULL AND revenue > 0) AS avg_revenue_per_trip,
                AVG(distance_km) AS avg_distance_km,
                AVG(duration_min) AS avg_duration_min,
                COUNT(DISTINCT trip_date) AS active_days,
                COUNT(DISTINCT park_id) AS active_zones,
                COUNT(DISTINCT city) AS active_cities
            FROM {base}
            WHERE {where_sql}
            """,
            params
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


# ═══════════════════════════════════════════════════════════════════
# 2. EFFICIENCY ANALYTICS (KPIs)
# ═══════════════════════════════════════════════════════════════════

def get_efficiency_analytics(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    KPIs de eficiencia operacional por conductor.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        base = source_meta["data_source"]

        where_parts = [_period_filter(period_days)]
        params = {}
        if country:
            where_parts.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        # KPIs por driver
        cur.execute(
            f"""
            WITH driver_efficiency AS (
                SELECT
                    driver_id,
                    COUNT(*) FILTER (WHERE completed_trips > 0) AS completed_trips,
                    COUNT(DISTINCT trip_date) AS active_days,
                    SUM(revenue) AS total_revenue,
                    SUM(distance_km) AS total_distance_km,
                    SUM(duration_min) AS total_duration_min,
                    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_hour_trips,
                    COUNT(*) FILTER (WHERE day_of_week IN (0, 6)) AS weekend_trips,
                    COUNT(DISTINCT park_id) AS zones_used
                FROM {base}
                WHERE {where_sql} AND completed_trips > 0
                GROUP BY driver_id
            )
            SELECT
                -- A. Revenue/hour (proxy: revenue / duration_min * 60)
                AVG(CASE WHEN total_duration_min > 0
                    THEN total_revenue / (total_duration_min / 60.0) ELSE NULL END) AS avg_revenue_per_hour,
                -- B. Revenue/km
                AVG(CASE WHEN total_distance_km > 0
                    THEN total_revenue / total_distance_km ELSE NULL END) AS avg_revenue_per_km,
                -- C. Trips/hour
                AVG(CASE WHEN total_duration_min > 0
                    THEN completed_trips / (total_duration_min / 60.0) ELSE NULL END) AS avg_trips_per_hour,
                -- D. Trips/day
                AVG(CASE WHEN active_days > 0
                    THEN completed_trips::numeric / active_days ELSE NULL END) AS avg_trips_per_day,
                -- E. Revenue/day
                AVG(CASE WHEN active_days > 0
                    THEN total_revenue / active_days ELSE NULL END) AS avg_revenue_per_day,
                -- F. Revenue/trip
                AVG(CASE WHEN completed_trips > 0
                    THEN total_revenue / completed_trips ELSE NULL END) AS avg_revenue_per_trip,
                -- G. Peak-hour share
                AVG(CASE WHEN completed_trips > 0
                    THEN peak_hour_trips::numeric / completed_trips ELSE NULL END) AS avg_peak_hour_share,
                -- H. Weekend share
                AVG(CASE WHEN completed_trips > 0
                    THEN weekend_trips::numeric / completed_trips ELSE NULL END) AS avg_weekend_share,
                -- I. Zone concentration (zones_used / active_days)
                AVG(CASE WHEN active_days > 0
                    THEN zones_used::numeric / active_days ELSE NULL END) AS avg_zone_concentration,
                -- J. Distance/trip
                AVG(CASE WHEN completed_trips > 0
                    THEN total_distance_km / completed_trips ELSE NULL END) AS avg_km_per_trip,
                COUNT(*) AS drivers_in_sample
            FROM driver_efficiency
            """,
            params
        )
        kpis = dict(cur.fetchone() or {})

        # Distribución percentil para contexto
        cur.execute(
            f"""
            WITH driver_efficiency AS (
                SELECT
                    driver_id,
                    completed_trips,
                    active_days,
                    total_revenue,
                    total_duration_min,
                    CASE WHEN total_duration_min > 0
                        THEN total_revenue / (total_duration_min / 60.0) ELSE NULL END AS revenue_per_hour
                FROM (
                    SELECT
                        driver_id,
                        COUNT(*) FILTER (WHERE completed_trips > 0) AS completed_trips,
                        COUNT(DISTINCT trip_date) AS active_days,
                        SUM(revenue) AS total_revenue,
                        SUM(duration_min) AS total_duration_min
                    FROM {base}
                    WHERE {where_sql} AND completed_trips > 0
                    GROUP BY driver_id
                ) sub
            )
            SELECT
                PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY revenue_per_hour) AS p10_rev_hour,
                PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY revenue_per_hour) AS p25_rev_hour,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY revenue_per_hour) AS p50_rev_hour,
                PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY revenue_per_hour) AS p75_rev_hour,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY revenue_per_hour) AS p90_rev_hour,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY completed_trips) AS p50_trips,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY active_days) AS p50_active_days
            FROM driver_efficiency
            WHERE revenue_per_hour IS NOT NULL
            """,
            params
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
            "unavailable_kpis": {
                "I. Idle Ratio": "Requiere session_fact con idle_time. Disponible en endpoint /sessions.",
                "J. Session Consistency": "Requiere session_fact. Disponible en endpoint /sessions.",
                "K. Active Blocks per Day": "Requiere session_fact. Disponible en endpoint /sessions.",
            },
            "source": source_meta,
        }


# ═══════════════════════════════════════════════════════════════════
# 3. SESSION ANALYTICS (desde session MVIEW)
# ═══════════════════════════════════════════════════════════════════

def get_session_analytics(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    Analítica de sesiones operacionales.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn, timeout_ms=SESSION_TIMEOUT_MS)

        if not source_meta["available_objects"]["session_mview"]:
            return {
                "sessions": {},
                "available": False,
                "reason": "ops.driver_session_fact no existe. Ejecutar phase2b_operational_intelligence_build.sql primero.",
                "source": source_meta,
            }

        cur.execute(
            f"""
            WITH session_stats AS (
                SELECT
                    driver_id,
                    COUNT(*) AS session_count,
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
                FROM {SESSION_MVIEW}
                WHERE session_date >= CURRENT_DATE - INTERVAL %(period)s days
                GROUP BY driver_id
            )
            SELECT
                COUNT(*) AS drivers_with_sessions,
                AVG(session_count) AS avg_sessions_per_driver,
                AVG(total_trips) AS avg_trips_per_driver,
                AVG(avg_session_duration_min) AS avg_session_duration_min,
                AVG(avg_trips_per_session) AS avg_trips_per_session,
                AVG(CASE WHEN avg_session_duration_min > 0
                    THEN avg_trips_per_session / (avg_session_duration_min / 60.0)
                    ELSE NULL END) AS avg_trips_per_hour_in_session,
                AVG(avg_revenue_per_session) AS avg_revenue_per_session,
                AVG(CASE WHEN avg_session_duration_min > 0 AND avg_revenue_per_session IS NOT NULL
                    THEN avg_revenue_per_session / (avg_session_duration_min / 60.0)
                    ELSE NULL END) AS avg_revenue_per_hour_in_session,
                AVG(avg_idle_per_session) AS avg_idle_time_per_session_min,
                AVG(avg_idle_between_trips) AS avg_idle_between_trips_min,
                AVG(avg_trip_duration_min) AS avg_trip_duration_min,
                AVG(avg_ticket_per_trip) AS avg_ticket_per_trip,
                AVG(stddev_session_trips) AS avg_session_trips_volatility,
                AVG(stddev_session_duration) AS avg_session_duration_volatility
            FROM session_stats
            """,
            {"period": period_days}
        )
        agg = dict(cur.fetchone() or {})

        # Distribución de sessions por driver (para contexto)
        cur.execute(
            f"""
            SELECT
                session_trips AS trips_in_session,
                COUNT(*) AS session_count,
                AVG(session_duration_min) AS avg_duration,
                AVG(session_revenue) AS avg_revenue
            FROM {SESSION_MVIEW}
            WHERE session_date >= CURRENT_DATE - INTERVAL %(period)s days
            GROUP BY session_trips
            ORDER BY session_trips
            """,
            {"period": period_days}
        )
        dist = [dict(r) for r in (cur.fetchall() or [])]

        # Idle ratio: idle_time / session_duration
        cur.execute(
            f"""
            SELECT
                AVG(CASE WHEN session_duration_min > 0 AND total_idle_time_min IS NOT NULL
                    THEN total_idle_time_min / session_duration_min
                    ELSE NULL END) AS avg_idle_ratio,
                PERCENTILE_CONT(0.50) WITHIN GROUP (
                    ORDER BY CASE WHEN session_duration_min > 0 AND total_idle_time_min IS NOT NULL
                    THEN total_idle_time_min / session_duration_min ELSE NULL END
                ) AS p50_idle_ratio
            FROM {SESSION_MVIEW}
            WHERE session_date >= CURRENT_DATE - INTERVAL %(period)s days
              AND session_duration_min > 0
            """,
            {"period": period_days}
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


# ═══════════════════════════════════════════════════════════════════
# 4. ZONE BEHAVIOR ANALYTICS
# ═══════════════════════════════════════════════════════════════════

def get_zone_analytics(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    Comportamiento por zona (park_id = proxy de zona).
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        base = source_meta["data_source"]

        where_parts = [_period_filter(period_days)]
        params = {}
        if country:
            where_parts.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        # Por zona (park)
        cur.execute(
            f"""
            WITH zone_stats AS (
                SELECT
                    park_id,
                    country,
                    city,
                    COUNT(DISTINCT driver_id) AS unique_drivers,
                    SUM(completed_trips) AS total_trips,
                    SUM(revenue) AS total_revenue,
                    AVG(revenue) FILTER (WHERE revenue IS NOT NULL AND revenue > 0) AS avg_ticket,
                    SUM(distance_km) AS total_distance_km,
                    COUNT(DISTINCT trip_date) AS active_days,
                    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_hour_trips,
                    COUNT(*) FILTER (WHERE day_of_week IN (0, 6)) AS weekend_trips
                FROM {base}
                WHERE {where_sql} AND completed_trips > 0
                GROUP BY park_id, country, city
            )
            SELECT
                park_id,
                country,
                city,
                unique_drivers,
                total_trips,
                total_revenue,
                avg_ticket,
                total_distance_km,
                active_days,
                CASE WHEN total_trips > 0
                    THEN peak_hour_trips::numeric / total_trips ELSE NULL END AS peak_hour_share,
                CASE WHEN total_trips > 0
                    THEN weekend_trips::numeric / total_trips ELSE NULL END AS weekend_share,
                CASE WHEN unique_drivers > 0
                    THEN total_trips::numeric / unique_drivers ELSE NULL END AS trips_per_driver,
                CASE WHEN active_days > 0
                    THEN total_trips::numeric / active_days ELSE NULL END AS trips_per_day
            FROM zone_stats
            ORDER BY total_trips DESC
            LIMIT 50
            """,
            params
        )
        zones = [dict(r) for r in (cur.fetchall() or [])]

        # Top zonas por driver (concentración)
        cur.execute(
            f"""
            WITH driver_zone_concentration AS (
                SELECT
                    driver_id,
                    COUNT(DISTINCT park_id) AS zones_used,
                    COUNT(*) AS total_trips,
                    MAX(zone_trips) AS top_zone_trips,
                    MAX(park_id_top) AS top_zone
                FROM (
                    SELECT
                        driver_id,
                        park_id,
                        COUNT(*) AS zone_trips,
                        FIRST_VALUE(park_id) OVER (
                            PARTITION BY driver_id ORDER BY COUNT(*) DESC
                        ) AS park_id_top
                    FROM {base}
                    WHERE {where_sql} AND completed_trips > 0
                    GROUP BY driver_id, park_id
                ) sub
                GROUP BY driver_id
            )
            SELECT
                AVG(zones_used) AS avg_zones_per_driver,
                AVG(CASE WHEN total_trips > 0
                    THEN top_zone_trips::numeric / total_trips ELSE NULL END) AS avg_top_zone_concentration,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY zones_used) AS p50_zones_used,
                COUNT(*) FILTER (WHERE zones_used = 1) AS single_zone_drivers,
                COUNT(*) FILTER (WHERE zones_used >= 5) AS multi_zone_drivers,
                COUNT(*) AS total_drivers
            FROM driver_zone_concentration
            """,
            params
        )
        concentration = dict(cur.fetchone() or {})

        return {
            "zones": zones,
            "concentration": {
                "avg_zones_per_driver": _safe_num(concentration.get("avg_zones_per_driver")),
                "avg_top_zone_concentration": _safe_num(concentration.get("avg_top_zone_concentration")),
                "p50_zones_used": concentration.get("p50_zones_used"),
                "single_zone_drivers": concentration.get("single_zone_drivers", 0),
                "multi_zone_drivers": concentration.get("multi_zone_drivers", 0),
                "total_drivers": concentration.get("total_drivers", 0),
            },
            "note": "zone = park_id (proxy). No hay geozonas reales en los datos de origen.",
            "available": True,
            "source": source_meta,
        }


# ═══════════════════════════════════════════════════════════════════
# 5. TIME BEHAVIOR ANALYTICS
# ═══════════════════════════════════════════════════════════════════

def get_time_patterns(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    Patrones de comportamiento por hora del día y día de la semana.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        base = source_meta["data_source"]

        where_parts = [_period_filter(period_days)]
        params = {}
        if country:
            where_parts.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        # Distribución por hora
        cur.execute(
            f"""
            SELECT
                trip_hour,
                COUNT(*) AS trips,
                AVG(revenue) FILTER (WHERE revenue IS NOT NULL AND revenue > 0) AS avg_revenue,
                AVG(distance_km) AS avg_distance_km,
                AVG(duration_min) AS avg_duration_min,
                COUNT(DISTINCT driver_id) AS unique_drivers
            FROM {base}
            WHERE {where_sql} AND completed_trips > 0
            GROUP BY trip_hour
            ORDER BY trip_hour
            """,
            params
        )
        hourly = [dict(r) for r in (cur.fetchall() or [])]

        # Distribución por día de semana
        cur.execute(
            f"""
            SELECT
                day_of_week,
                CASE day_of_week
                    WHEN 0 THEN 'Domingo'
                    WHEN 1 THEN 'Lunes'
                    WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles'
                    WHEN 4 THEN 'Jueves'
                    WHEN 5 THEN 'Viernes'
                    WHEN 6 THEN 'Sábado'
                END AS day_name,
                COUNT(*) AS trips,
                AVG(revenue) FILTER (WHERE revenue IS NOT NULL AND revenue > 0) AS avg_revenue,
                COUNT(DISTINCT driver_id) AS unique_drivers
            FROM {base}
            WHERE {where_sql} AND completed_trips > 0
            GROUP BY day_of_week
            ORDER BY day_of_week
            """,
            params
        )
        daily = [dict(r) for r in (cur.fetchall() or [])]

        # Peak vs off-peak
        cur.execute(
            f"""
            SELECT
                CASE
                    WHEN trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20 THEN 'peak'
                    ELSE 'off_peak'
                END AS period_type,
                COUNT(*) AS trips,
                AVG(revenue) FILTER (WHERE revenue IS NOT NULL AND revenue > 0) AS avg_revenue,
                AVG(distance_km) AS avg_distance_km,
                COUNT(DISTINCT driver_id) AS unique_drivers
            FROM {base}
            WHERE {where_sql} AND completed_trips > 0
            GROUP BY period_type
            """,
            params
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


# ═══════════════════════════════════════════════════════════════════
# 6. PRE-CHURN BEHAVIOR SIGNALS
# ═══════════════════════════════════════════════════════════════════

def get_pre_churn_signals(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 56,  # ventana más larga para detectar tendencias
) -> dict:
    """
    Señales tempranas de deterioro operacional previo al churn.
    Compara conductores activos recientes vs los que dejaron de operar.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        base = source_meta["data_source"]

        half = period_days // 2
        where_parts1 = [f"trip_date >= CURRENT_DATE - INTERVAL '{period_days} days'",
                        f"trip_date < CURRENT_DATE - INTERVAL '{half} days'"]
        where_parts2 = [f"trip_date >= CURRENT_DATE - INTERVAL '{half} days'"]

        params = {}
        if country:
            where_parts1.append("country = %(country)s")
            where_parts2.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts1.append("city = %(city)s")
            where_parts2.append("city = %(city)s")
            params["city"] = city

        where1 = " AND ".join(where_parts1)
        where2 = " AND ".join(where_parts2)

        # Driver metrics en primera mitad vs segunda mitad
        cur.execute(
            f"""
            WITH first_half AS (
                SELECT
                    driver_id,
                    COUNT(*) FILTER (WHERE completed_trips > 0) AS trips_p1,
                    COUNT(DISTINCT trip_date) AS active_days_p1,
                    SUM(revenue) AS revenue_p1,
                    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_trips_p1,
                    COUNT(*) FILTER (WHERE day_of_week IN (0, 6)) AS weekend_trips_p1,
                    COUNT(DISTINCT park_id) AS zones_p1,
                    SUM(duration_min) AS duration_p1
                FROM {base}
                WHERE {where1} AND completed_trips > 0
                GROUP BY driver_id
            ),
            second_half AS (
                SELECT
                    driver_id,
                    COUNT(*) FILTER (WHERE completed_trips > 0) AS trips_p2,
                    COUNT(DISTINCT trip_date) AS active_days_p2,
                    SUM(revenue) AS revenue_p2,
                    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_trips_p2,
                    SUM(duration_min) AS duration_p2
                FROM {base}
                WHERE {where2} AND completed_trips > 0
                GROUP BY driver_id
            )
            SELECT
                fh.driver_id,
                fh.trips_p1,
                sh.trips_p2,
                fh.active_days_p1,
                sh.active_days_p2,
                fh.revenue_p1,
                sh.revenue_p2,
                CASE WHEN fh.trips_p1 > 0
                    THEN (sh.trips_p2::numeric - fh.trips_p1) / fh.trips_p1 ELSE NULL END AS trips_change_pct,
                CASE WHEN fh.active_days_p1 > 0
                    THEN (sh.active_days_p2::numeric - fh.active_days_p1) / fh.active_days_p1 ELSE NULL END AS active_days_change_pct,
                CASE WHEN fh.revenue_p1 > 0
                    THEN (sh.revenue_p2 - fh.revenue_p1) / fh.revenue_p1 ELSE NULL END AS revenue_change_pct,
                CASE WHEN fh.trips_p1 > 0 AND fh.duration_p1 > 0
                    THEN fh.revenue_p1 / (fh.duration_p1 / 60.0) ELSE NULL END AS rev_per_hour_p1,
                CASE WHEN sh.trips_p2 > 0 AND sh.duration_p2 > 0
                    THEN sh.revenue_p2 / (sh.duration_p2 / 60.0) ELSE NULL END AS rev_per_hour_p2,
                CASE WHEN fh.trips_p1 > 0
                    THEN fh.peak_trips_p1::numeric / fh.trips_p1 ELSE NULL END AS peak_share_p1,
                CASE WHEN sh.trips_p2 > 0
                    THEN sh.peak_trips_p2::numeric / sh.trips_p2 ELSE NULL END AS peak_share_p2
            FROM first_half fh
            LEFT JOIN second_half sh ON fh.driver_id = sh.driver_id
            """,
            params
        )
        driver_changes = [dict(r) for r in (cur.fetchall() or [])]

        # Clasificar señales
        signals = []
        for d in driver_changes:
            driver_signals = []
            driver_id = d.get("driver_id")

            trips_change = d.get("trips_change_pct")
            if trips_change is not None and trips_change < -0.30:
                driver_signals.append({
                    "type": "TRIPS_DECLINE",
                    "change_pct": round(trips_change * 100, 1),
                    "severity": "STRONG_DEGRADATION" if trips_change < -0.50 else "MODERATE_DEGRADATION"
                })
            elif trips_change is not None and trips_change < -0.15:
                driver_signals.append({
                    "type": "TRIPS_DECLINE",
                    "change_pct": round(trips_change * 100, 1),
                    "severity": "EARLY_WARNING"
                })

            active_change = d.get("active_days_change_pct")
            if active_change is not None and active_change < -0.30:
                driver_signals.append({
                    "type": "ACTIVE_DAYS_DECLINE",
                    "change_pct": round(active_change * 100, 1),
                    "severity": "STRONG_DEGRADATION" if active_change < -0.50 else "MODERATE_DEGRADATION"
                })
            elif active_change is not None and active_change < -0.15:
                driver_signals.append({
                    "type": "ACTIVE_DAYS_DECLINE",
                    "change_pct": round(active_change * 100, 1),
                    "severity": "EARLY_WARNING"
                })

            revenue_change = d.get("revenue_change_pct")
            if revenue_change is not None and revenue_change < -0.30:
                driver_signals.append({
                    "type": "REVENUE_DECLINE",
                    "change_pct": round(revenue_change * 100, 1),
                    "severity": "STRONG_DEGRADATION" if revenue_change < -0.50 else "MODERATE_DEGRADATION"
                })

            peak_p1 = d.get("peak_share_p1")
            peak_p2 = d.get("peak_share_p2")
            if peak_p1 is not None and peak_p2 is not None and peak_p1 > 0:
                peak_change = (peak_p2 - peak_p1) / peak_p1
                if peak_change < -0.20:
                    driver_signals.append({
                        "type": "PEAK_HOUR_PARTICIPATION_DECLINE",
                        "change_pct": round(peak_change * 100, 1),
                        "severity": "EARLY_WARNING"
                    })

            rev_h_p1 = d.get("rev_per_hour_p1")
            rev_h_p2 = d.get("rev_per_hour_p2")
            if rev_h_p1 is not None and rev_h_p2 is not None and rev_h_p1 > 0:
                rev_h_change = (rev_h_p2 - rev_h_p1) / rev_h_p1
                if rev_h_change < -0.20:
                    driver_signals.append({
                        "type": "REVENUE_PER_HOUR_DECLINE",
                        "change_pct": round(rev_h_change * 100, 1),
                        "severity": "MODERATE_DEGRADATION"
                    })

            # Churn: driver existía en P1 pero no en P2
            if d.get("trips_p2") is None or d.get("trips_p2") == 0:
                driver_signals.append({
                    "type": "POTENTIAL_CHURN",
                    "change_pct": -100.0,
                    "severity": "STRONG_DEGRADATION"
                })

            if driver_signals:
                signals.append({
                    "driver_id": driver_id,
                    "first_half": {
                        "trips": d.get("trips_p1", 0),
                        "active_days": d.get("active_days_p1", 0),
                        "revenue": _safe_num(d.get("revenue_p1")),
                        "rev_per_hour": _safe_num(rev_h_p1),
                        "peak_share": _safe_num(peak_p1),
                    },
                    "second_half": {
                        "trips": d.get("trips_p2", 0) or 0,
                        "active_days": d.get("active_days_p2", 0) or 0,
                        "revenue": _safe_num(d.get("revenue_p2")),
                        "rev_per_hour": _safe_num(rev_h_p2),
                        "peak_share": _safe_num(peak_p2),
                    },
                    "signals": driver_signals,
                    "max_severity": max(
                        (s["severity"] for s in driver_signals),
                        key=lambda x: {"STRONG_DEGRADATION": 3, "MODERATE_DEGRADATION": 2, "EARLY_WARNING": 1}.get(x, 0)
                    ),
                })

        # Agregados de señales
        severity_counts = {"EARLY_WARNING": 0, "MODERATE_DEGRADATION": 0, "STRONG_DEGRADATION": 0}
        for s in signals:
            sev = s["max_severity"]
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        return {
            "signals": signals[:500],  # top 500 drivers con señales
            "total_drivers_with_signals": len(signals),
            "severity_summary": severity_counts,
            "available": True,
            "note": "Sin recomendaciones. Diagnóstico determinístico solamente.",
            "source": source_meta,
        }


# ═══════════════════════════════════════════════════════════════════
# 7. OPERATIONAL ARCHETYPES
# ═══════════════════════════════════════════════════════════════════

def get_operational_archetypes(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    Clasificación determinística de arquetipos operacionales.
    Reglas auditables, documentadas, sin ML.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        base = source_meta["data_source"]

        where_parts = [_period_filter(period_days)]
        params = {}
        if country:
            where_parts.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        # Métricas por driver
        cur.execute(
            f"""
            WITH driver_metrics AS (
                SELECT
                    driver_id,
                    COUNT(*) FILTER (WHERE completed_trips > 0) AS total_trips,
                    COUNT(DISTINCT trip_date) AS active_days,
                    SUM(revenue) AS total_revenue,
                    SUM(duration_min) AS total_duration_min,
                    SUM(distance_km) AS total_distance_km,
                    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_trips,
                    COUNT(*) FILTER (WHERE day_of_week IN (0, 6)) AS weekend_trips,
                    COUNT(*) FILTER (WHERE day_of_week NOT IN (0, 6)) AS weekday_trips,
                    COUNT(DISTINCT park_id) AS zones_used
                FROM {base}
                WHERE {where_sql} AND completed_trips > 0
                GROUP BY driver_id
            )
            SELECT
                *,
                CASE WHEN total_duration_min > 0
                    THEN total_revenue / (total_duration_min / 60.0) ELSE NULL END AS revenue_per_hour,
                CASE WHEN total_distance_km > 0
                    THEN total_revenue / total_distance_km ELSE NULL END AS revenue_per_km,
                CASE WHEN total_duration_min > 0
                    THEN total_trips::numeric / (total_duration_min / 60.0) ELSE NULL END AS trips_per_hour,
                CASE WHEN total_trips > 0
                    THEN peak_trips::numeric / total_trips ELSE NULL END AS peak_hour_share,
                CASE WHEN total_trips > 0
                    THEN weekend_trips::numeric / total_trips ELSE NULL END AS weekend_share
            FROM driver_metrics
            """,
            params
        )
        drivers = [dict(r) for r in (cur.fetchall() or [])]

        if not drivers:
            return {
                "archetypes": [],
                "distribution": {},
                "available": False,
                "reason": "No hay conductores con viajes en el período.",
                "source": source_meta,
            }

        # Calcular medianas para clasificación
        trips_list = [d["total_trips"] or 0 for d in drivers]
        active_days_list = [d["active_days"] or 0 for d in drivers]
        rev_per_hour_list = [_safe_num(d.get("revenue_per_hour"), 0) for d in drivers]
        weekend_share_list = [_safe_num(d.get("weekend_share"), 0) for d in drivers]
        peak_share_list = [_safe_num(d.get("peak_hour_share"), 0) for d in drivers]

        def median(lst):
            if not lst:
                return 0
            s = sorted(lst)
            n = len(s)
            return s[n // 2]

        p50_trips = median(trips_list)
        p50_active_days = median(active_days_list)
        p50_rev_hour = median(rev_per_hour_list)
        p50_weekend = median(weekend_share_list)
        p50_peak = median(peak_share_list)

        # Clasificación determinística
        archetype_map = []
        archetype_counts = {}

        for d in drivers:
            trips = d["total_trips"] or 0
            active_days = d["active_days"] or 0
            rev_hour = _safe_num(d.get("revenue_per_hour"), 0)
            weekend_share = _safe_num(d.get("weekend_share"), 0)
            peak_share = _safe_num(d.get("peak_hour_share"), 0)
            trips_per_hour = _safe_num(d.get("trips_per_hour"), 0)
            weekday_trips = d.get("weekday_trips") or 0
            zones = d.get("zones_used") or 0

            archetypes = []

            # FULLTIMER: 5+ días activos, 40+ viajes
            if active_days >= 5 and trips >= 40:
                archetypes.append("FULLTIMER")

            # PART_TIMER: 1-4 días activos
            if 1 <= active_days <= 4:
                archetypes.append("PART_TIMER")

            # WEEKEND_SPECIALIST: >50% viajes en fin de semana
            if weekend_share > 0.50 and trips >= 10:
                archetypes.append("WEEKEND_SPECIALIST")

            # PEAK_HOUR_SPECIALIST: >60% viajes en horas pico
            if peak_share > 0.60 and trips >= 10:
                archetypes.append("PEAK_HOUR_SPECIALIST")

            # HIGH_EFFICIENCY: revenue/hour alto, trips/hour alto
            if rev_hour > p50_rev_hour * 1.5 and trips_per_hour > 0:
                archetypes.append("HIGH_EFFICIENCY")

            # HIGH_VOLUME_LOW_EFFICIENCY: muchos viajes, revenue/hour bajo
            if trips > p50_trips * 1.5 and rev_hour < p50_rev_hour * 0.7:
                archetypes.append("HIGH_VOLUME_LOW_EFFICIENCY")

            # CONSISTENT_OPERATOR: activo 5+ días, trips consistentes
            if active_days >= 5 and trips >= p50_trips * 0.8:
                archetypes.append("CONSISTENT_OPERATOR")

            # INCONSISTENT_OPERATOR: pocos días, pocos viajes
            if active_days <= 2 and trips < p50_trips * 0.5:
                archetypes.append("INCONSISTENT_OPERATOR")

            # BURNOUT_PATTERN: activo muchos días pero trips/día bajando
            # (aproximado: muchos días activos, pocos trips por día activo)
            if active_days >= 6 and trips > 0 and (trips / active_days) < (p50_trips / max(p50_active_days, 1)) * 0.5:
                archetypes.append("BURNOUT_PATTERN")

            primary = archetypes[0] if archetypes else "UNCLASSIFIED"

            archetype_map.append({
                "driver_id": d["driver_id"],
                "primary_archetype": primary,
                "all_archetypes": archetypes,
                "metrics": {
                    "total_trips": trips,
                    "active_days": active_days,
                    "revenue_per_hour": round(rev_hour, 2),
                    "revenue_per_km": round(_safe_num(d.get("revenue_per_km"), 0), 2),
                    "trips_per_hour": round(trips_per_hour, 2),
                    "peak_hour_share": round(peak_share, 4),
                    "weekend_share": round(weekend_share, 4),
                    "zones_used": zones,
                },
            })

            archetype_counts[primary] = archetype_counts.get(primary, 0) + 1

        # Distribución agregada
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
                "p50_trips": p50_trips,
                "p50_active_days": p50_active_days,
                "p50_revenue_per_hour": round(p50_rev_hour, 2),
                "p50_weekend_share": round(p50_weekend, 4),
                "p50_peak_share": round(p50_peak, 4),
            },
            "available": True,
            "note": "Clasificación determinística sin ML. Un driver puede pertenecer a múltiples arquetipos.",
            "source": source_meta,
        }


# ═══════════════════════════════════════════════════════════════════
# 8. TOP VS CHURNED COMPARISON
# ═══════════════════════════════════════════════════════════════════

def get_top_vs_churned(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict:
    """
    Comparación operacional entre conductores top y conductores que abandonaron.
    """
    with get_db() as conn:
        source_meta = _resolve_source(conn)
        cur = _cursor(conn)
        base = source_meta["data_source"]

        where_parts = [_period_filter(period_days)]
        params = {}
        if country:
            where_parts.append("country = %(country)s")
            params["country"] = country
        if city:
            where_parts.append("city = %(city)s")
            params["city"] = city
        where_sql = " AND ".join(where_parts)

        # Definir TOP performers (top 20% por revenue) y CHURNED (sin actividad reciente)
        cur.execute(
            f"""
            WITH driver_metrics AS (
                SELECT
                    driver_id,
                    SUM(revenue) AS total_revenue,
                    COUNT(*) FILTER (WHERE completed_trips > 0) AS total_trips,
                    COUNT(DISTINCT trip_date) AS active_days,
                    MAX(trip_date) AS last_trip_date,
                    SUM(duration_min) AS total_duration_min,
                    SUM(distance_km) AS total_distance_km,
                    COUNT(*) FILTER (WHERE trip_hour BETWEEN 6 AND 9 OR trip_hour BETWEEN 17 AND 20) AS peak_trips,
                    COUNT(*) FILTER (WHERE day_of_week IN (0, 6)) AS weekend_trips,
                    COUNT(DISTINCT park_id) AS zones_used
                FROM {base}
                WHERE {where_sql} AND completed_trips > 0 AND revenue IS NOT NULL
                GROUP BY driver_id
            ),
            ranked AS (
                SELECT
                    *,
                    NTILE(5) OVER (ORDER BY total_revenue DESC) AS revenue_quintile
                FROM driver_metrics
            )
            SELECT
                CASE
                    WHEN revenue_quintile = 1 THEN 'TOP_PERFORMER'
                    WHEN last_trip_date < CURRENT_DATE - INTERVAL '14 days' THEN 'RECENTLY_CHURNED'
                    ELSE 'OTHER'
                END AS segment,
                COUNT(*) AS drivers,
                AVG(total_revenue) AS avg_revenue,
                AVG(total_trips) AS avg_trips,
                AVG(active_days) AS avg_active_days,
                AVG(CASE WHEN total_duration_min > 0
                    THEN total_revenue / (total_duration_min / 60.0) ELSE NULL END) AS avg_revenue_per_hour,
                AVG(CASE WHEN total_distance_km > 0
                    THEN total_revenue / total_distance_km ELSE NULL END) AS avg_revenue_per_km,
                AVG(CASE WHEN total_trips > 0
                    THEN peak_trips::numeric / total_trips ELSE NULL END) AS avg_peak_hour_share,
                AVG(CASE WHEN total_trips > 0
                    THEN weekend_trips::numeric / total_trips ELSE NULL END) AS avg_weekend_share,
                AVG(zones_used) AS avg_zones_used,
                AVG(CASE WHEN total_duration_min > 0
                    THEN total_distance_km / (total_duration_min / 60.0) ELSE NULL END) AS avg_km_per_hour
            FROM ranked
            WHERE segment IN ('TOP_PERFORMER', 'RECENTLY_CHURNED')
               OR revenue_quintile IS NOT NULL
            GROUP BY segment
            """,
            params
        )
        comparison = [dict(r) for r in (cur.fetchall() or [])]

        return {
            "comparison": comparison,
            "available": True,
            "note": "TOP_PERFORMER = top 20% por revenue. RECENTLY_CHURNED = sin actividad en últimos 14 días.",
            "source": source_meta,
        }
