"""
BUSINESS_SLICE — lecturas REAL desde vistas/MV ops (sin mezclar Plan).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

# Tabla canónica mensual (carga incremental). La vista homónima sigue existiendo por compat.
FACT_MONTHLY = "ops.real_business_slice_month_fact"
MV_MONTHLY = FACT_MONTHLY
V_RESOLVED = "ops.v_real_trips_business_slice_resolved"
V_COVERAGE = "ops.v_business_slice_coverage_month"
V_UNMATCHED = "ops.v_business_slice_unmatched_trips"
V_CONFLICTS = "ops.v_business_slice_conflict_trips"
V_STUB = "ops.v_plan_business_slice_join_stub"


def _where_clauses(
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    year: Optional[int],
    month: Optional[int],
    prefix: str = "",
) -> tuple[list[str], list[Any]]:
    w: list[str] = []
    p: list[Any] = []
    if country and str(country).strip():
        w.append(f"{prefix}country IS NOT NULL AND LOWER(TRIM({prefix}country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append(f"{prefix}city IS NOT NULL AND LOWER(TRIM({prefix}city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append(
            f"{prefix}business_slice_name IS NOT NULL AND LOWER(TRIM({prefix}business_slice_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(business_slice).strip())
    if fleet and str(fleet).strip():
        w.append(
            f"{prefix}fleet_display_name IS NOT NULL AND LOWER(TRIM({prefix}fleet_display_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(fleet).strip())
    if subfleet and str(subfleet).strip():
        w.append(
            f"{prefix}subfleet_name IS NOT NULL AND LOWER(TRIM({prefix}subfleet_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(subfleet).strip())
    if year is not None:
        w.append(f"EXTRACT(YEAR FROM {prefix}month)::int = %s")
        p.append(int(year))
    if month is not None:
        w.append(f"EXTRACT(MONTH FROM {prefix}month)::int = %s")
        p.append(int(month))
    return w, p


def _serialize_row(row: dict) -> dict:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat") and getattr(v, "day", None):
            out[k] = v.isoformat()[:10]
        else:
            out[k] = v
    return out


def get_business_slice_filters() -> dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT DISTINCT country, city, business_slice_name, fleet_display_name,
                   is_subfleet, subfleet_name
            FROM {MV_MONTHLY}
            WHERE country IS NOT NULL AND city IS NOT NULL
            ORDER BY country, city, business_slice_name, fleet_display_name
            """
        )
        rows = cur.fetchall()
        cur.close()
    countries = sorted({r["country"] for r in rows if r.get("country")})
    cities = sorted({r["city"] for r in rows if r.get("city")})
    slices = sorted({r["business_slice_name"] for r in rows if r.get("business_slice_name")})
    fleets = sorted({r["fleet_display_name"] for r in rows if r.get("fleet_display_name")})
    subfleets = sorted({r["subfleet_name"] for r in rows if r.get("subfleet_name")})
    return {
        "countries": countries,
        "cities": cities,
        "business_slices": slices,
        "fleets": fleets,
        "subfleets": subfleets,
        "metrics_available": [
            "trips_completed",
            "trips_cancelled",
            "active_drivers",
            "avg_ticket",
            "commission_pct",
            "trips_per_driver",
            "revenue_yego_net",
            "precio_km",
            "tiempo_km",
            "completados_por_hora",
            "cancelados_por_hora",
        ],
    }


def get_business_slice_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    w, params = _where_clauses(country, city, business_slice, fleet, subfleet, year, month, "")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT *
        FROM {MV_MONTHLY}
        {where_sql}
        ORDER BY month DESC, country, city, business_slice_name, fleet_display_name
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_business_slice_coverage(
    year: Optional[int] = None,
    limit_months: int = 36,
) -> dict[str, Any]:
    w, params = [], []
    if year is not None:
        w.append("EXTRACT(YEAR FROM month)::int = %s")
        params.append(int(year))
    where_cov = ("WHERE " + " AND ".join(w)) if w else ""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT * FROM {V_COVERAGE}
            {where_cov}
            ORDER BY month DESC, country, city
            LIMIT %s
            """,
            params + [min(max(limit_months * 50, 1), 5000)],
        )
        by_city = [_serialize_row(dict(r)) for r in cur.fetchall()]

        slice_params: list[Any] = []
        slice_year_clause = ""
        if year is not None:
            slice_year_clause = "AND EXTRACT(YEAR FROM trip_month)::int = %s"
            slice_params.append(int(year))
        cur.execute(
            f"""
            SELECT
                trip_month AS month,
                business_slice_name,
                COUNT(*) FILTER (WHERE resolution_status = 'resolved') AS trips_resolved,
                COUNT(*) FILTER (WHERE resolution_status = 'unmatched') AS trips_unmatched,
                COUNT(*) FILTER (WHERE resolution_status = 'conflict') AS trips_conflict
            FROM {V_RESOLVED}
            WHERE trip_month IS NOT NULL
              {slice_year_clause}
            GROUP BY trip_month, business_slice_name
            ORDER BY trip_month DESC, business_slice_name
            LIMIT %s
            """,
            slice_params + [500],
        )
        by_slice = [_serialize_row(dict(r)) for r in cur.fetchall()]

        rc_params: list[Any] = []
        rc_year_clause = ""
        if year is not None:
            rc_year_clause = "AND EXTRACT(YEAR FROM trip_date)::int = %s"
            rc_params.append(int(year))
        cur.execute(
            f"""
            SELECT resolution_status, COUNT(*)::bigint AS cnt
            FROM {V_RESOLVED}
            WHERE trip_date IS NOT NULL
              {rc_year_clause}
            GROUP BY resolution_status
            """,
            rc_params,
        )
        status_counts = {r["resolution_status"]: r["cnt"] for r in cur.fetchall()}
        cur.close()

    return {
        "by_city_month": by_city,
        "by_slice_month": by_slice,
        "resolution_counts": status_counts,
        "note": "Sin filtro de año la tabla resolution_counts considera todos los viajes con fecha; puede ser costosa.",
    }


def get_business_slice_unmatched(
    country: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    w, params = _where_clauses(country, city, None, None, None, None, None, "")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT trip_id, trip_date, country, city, park_id, park_name, tipo_servicio,
               works_terms, resolution_status
        FROM {V_UNMATCHED}
        {where_sql}
        ORDER BY trip_date DESC NULLS LAST
        LIMIT %s
    """
    params.append(min(max(limit, 1), 500))
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_business_slice_conflicts(
    country: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    w, params = _where_clauses(country, city, None, None, None, None, None, "")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT trip_id, trip_date, country, city, park_id, park_name, tipo_servicio,
               works_terms, resolution_status, conflict_slice_count, conflict_rule_ids,
               conflict_slice_names
        FROM {V_CONFLICTS}
        {where_sql}
        ORDER BY trip_date DESC NULLS LAST
        LIMIT %s
    """
    params.append(min(max(limit, 1), 500))
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_business_slice_subfleets() -> list[dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT DISTINCT country, city, business_slice_name, fleet_display_name,
                   subfleet_name, parent_fleet_name
            FROM {MV_MONTHLY}
            WHERE is_subfleet OR subfleet_name IS NOT NULL
            ORDER BY country, city, business_slice_name, fleet_display_name
            """
        )
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_plan_business_slice_stub(limit: int = 500) -> list[dict[str, Any]]:
    """Contrato futuro de join Plan; sin valores de plan."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT * FROM {V_STUB}
            ORDER BY month DESC, country, city, business_slice_name
            LIMIT %s
            """,
            (min(max(limit, 1), 2000),),
        )
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_business_slice_weekly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 1500,
) -> list[dict[str, Any]]:
    """Agregado semanal desde vista resuelta (puede ser pesado; filtrar por año recomendado)."""
    w: list[str] = ["resolution_status = 'resolved'", "trip_week IS NOT NULL"]
    params: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append(
            "business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))"
        )
        params.append(str(business_slice).strip())
    if year is not None:
        w.append("EXTRACT(YEAR FROM trip_week)::int = %s")
        params.append(int(year))
    where_sql = "WHERE " + " AND ".join(w)
    sql = f"""
        SELECT
            trip_week AS week_start,
            country,
            city,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
            COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
            COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
            AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS avg_ticket,
            SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
        FROM {V_RESOLVED}
        {where_sql}
        GROUP BY trip_week, country, city, business_slice_name, fleet_display_name,
                 is_subfleet, subfleet_name
        ORDER BY week_start DESC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_business_slice_daily(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Agregado diario desde vista resuelta (filtrar año/mes recomendado por coste)."""
    w: list[str] = ["resolution_status = 'resolved'", "trip_date IS NOT NULL"]
    params: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append(
            "business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))"
        )
        params.append(str(business_slice).strip())
    if year is not None:
        w.append("EXTRACT(YEAR FROM trip_date)::int = %s")
        params.append(int(year))
    if month is not None:
        w.append("EXTRACT(MONTH FROM trip_date)::int = %s")
        params.append(int(month))
    where_sql = "WHERE " + " AND ".join(w)
    sql = f"""
        SELECT
            trip_date,
            country,
            city,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
            COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
            COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
            AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS avg_ticket,
            SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
        FROM {V_RESOLVED}
        {where_sql}
        GROUP BY trip_date, country, city, business_slice_name, fleet_display_name,
                 is_subfleet, subfleet_name
        ORDER BY trip_date DESC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data
