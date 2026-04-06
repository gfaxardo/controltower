"""
BUSINESS_SLICE — lecturas REAL desde vistas/MV ops (sin mezclar Plan).
"""
from __future__ import annotations

import logging
import math
import numbers
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db, get_db_drill

logger = logging.getLogger(__name__)

# Tabla canónica mensual (carga incremental). La vista homónima sigue existiendo por compat.
FACT_MONTHLY = "ops.real_business_slice_month_fact"
MV_MONTHLY = FACT_MONTHLY
FACT_DAILY = "ops.real_business_slice_day_fact"
FACT_WEEKLY = "ops.real_business_slice_week_fact"
V_RESOLVED = "ops.v_real_trips_business_slice_resolved"
V_COVERAGE = "ops.v_business_slice_coverage_month"
V_UNMATCHED = "ops.v_business_slice_unmatched_trips"
V_CONFLICTS = "ops.v_business_slice_conflict_trips"
V_STUB = "ops.v_plan_business_slice_join_stub"
COMPARE_DIM_FIELDS = (
    "country",
    "city",
    "business_slice_name",
    "fleet_display_name",
    "is_subfleet",
    "subfleet_name",
)

_RESOLVED_METRIC_SELECT = """
    COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
    COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
    COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
    AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS avg_ticket,
    SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net,
    CASE
        WHEN SUM(total_fare) FILTER (
            WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
        ) > 0
        THEN SUM(revenue_yego_net) FILTER (
            WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
        ) / SUM(total_fare) FILTER (
            WHERE completed_flag AND total_fare IS NOT NULL AND total_fare > 0
        )
        ELSE NULL
    END AS commission_pct,
    CASE
        WHEN COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) > 0
        THEN COUNT(*) FILTER (WHERE completed_flag)::numeric
            / COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)
        ELSE NULL
    END AS trips_per_driver,
    CASE
        WHEN (COUNT(*) FILTER (WHERE completed_flag) + COUNT(*) FILTER (WHERE cancelled_flag)) > 0
        THEN COUNT(*) FILTER (WHERE cancelled_flag)::numeric
            / (COUNT(*) FILTER (WHERE completed_flag) + COUNT(*) FILTER (WHERE cancelled_flag))
        ELSE NULL
    END AS cancel_rate_pct
"""


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


def _json_safe_scalar(v: Any) -> Any:
    """Evita NaN/inf y Decimal no finitos: json.dumps de Starlette no los admite.

    psycopg2/pandas pueden devolver numpy.float64 (no es isinstance(..., float)).
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, Decimal):
        if not v.is_finite():
            return None
        return float(v)
    if isinstance(v, numbers.Integral):
        return int(v)
    if isinstance(v, numbers.Real):
        x = float(v)
        return None if not math.isfinite(x) else x
    return v


def _serialize_row(row: dict) -> dict:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat") and getattr(v, "day", None):
            out[k] = v.isoformat()[:10]
        else:
            out[k] = _json_safe_scalar(v)
    return out


def _dim_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row.get(k) for k in COMPARE_DIM_FIELDS)


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _month_end(d: date) -> date:
    return date(d.year, d.month, monthrange(d.year, d.month)[1])


def _previous_month_start(d: date) -> date:
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _iso_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _resolved_filter_clauses(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> tuple[list[str], list[Any]]:
    w: list[str] = ["resolution_status = 'resolved'", "trip_date IS NOT NULL"]
    p: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append(
            "business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(business_slice).strip())
    if fleet and str(fleet).strip():
        w.append(
            "fleet_display_name IS NOT NULL AND LOWER(TRIM(fleet_display_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(fleet).strip())
    if subfleet and str(subfleet).strip():
        w.append(
            "subfleet_name IS NOT NULL AND LOWER(TRIM(subfleet_name::text)) = LOWER(TRIM(%s))"
        )
        p.append(str(subfleet).strip())
    return w, p


def _get_latest_available_trip_date(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> Optional[date]:
    w, p = _resolved_filter_clauses(country, city, business_slice, fleet, subfleet)
    if period_start is not None:
        w.append("trip_date >= %s")
        p.append(period_start)
    if period_end is not None:
        w.append("trip_date <= %s")
        p.append(period_end)
    with get_db_drill() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT MAX(trip_date) FROM {V_RESOLVED} WHERE {' AND '.join(w)}",
            p,
        )
        row = cur.fetchone()
        cur.close()
    return row[0] if row and row[0] is not None else None


def _fetch_resolved_metrics_by_dims_for_range(
    start_date: date,
    end_date: date,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    w, p = _resolved_filter_clauses(country, city, business_slice, fleet, subfleet)
    w.extend(["trip_date >= %s", "trip_date <= %s"])
    p.extend([start_date, end_date])
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                country, city, business_slice_name, fleet_display_name,
                is_subfleet, subfleet_name,
                {_RESOLVED_METRIC_SELECT}
            FROM {V_RESOLVED}
            WHERE {' AND '.join(w)}
            GROUP BY country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
            """,
            p,
        )
        rows = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return {_dim_key(r): r for r in rows}


def _fetch_resolved_daily_metrics_for_dates(
    target_dates: list[date],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
) -> dict[tuple[str, tuple[Any, ...]], dict[str, Any]]:
    if not target_dates:
        return {}
    w, p = _resolved_filter_clauses(country, city, business_slice, None, None)
    placeholders = ", ".join(["%s"] * len(target_dates))
    w.append(f"trip_date IN ({placeholders})")
    p.extend(target_dates)
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                trip_date,
                country, city, business_slice_name, fleet_display_name,
                is_subfleet, subfleet_name,
                {_RESOLVED_METRIC_SELECT}
            FROM {V_RESOLVED}
            WHERE {' AND '.join(w)}
            GROUP BY trip_date, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
            """,
            p,
        )
        rows = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    out: dict[tuple[str, tuple[Any, ...]], dict[str, Any]] = {}
    for row in rows:
        out[(row["trip_date"], _dim_key(row))] = row
    return out


def _attach_weekly_partial_equivalent_context(
    rows: list[dict[str, Any]],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
) -> list[dict[str, Any]]:
    today = date.today()
    current_week_start = _iso_week_start(today)
    current_week_key = current_week_start.isoformat()
    if not any(str(r.get("week_start")) == current_week_key for r in rows):
        return rows
    current_cutoff = _get_latest_available_trip_date(
        country=country,
        city=city,
        business_slice=business_slice,
        period_start=current_week_start,
        period_end=current_week_start + timedelta(days=6),
    )
    if current_cutoff is None or current_cutoff < current_week_start:
        return rows
    previous_week_start = current_week_start - timedelta(days=7)
    previous_cutoff = previous_week_start + (current_cutoff - current_week_start)
    baseline_by_dim = _fetch_resolved_metrics_by_dims_for_range(
        previous_week_start,
        previous_cutoff,
        country=country,
        city=city,
        business_slice=business_slice,
    )
    enriched: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("week_start")) != current_week_key:
            enriched.append(row)
            continue
        next_row = dict(row)
        next_row["comparison_context"] = {
            "comparison_mode": "weekly_partial_equivalent",
            "is_partial_equivalent": True,
            "is_operationally_aligned": True,
            "is_preliminary": False,
            "period_state": "PARTIAL",
            "current_range_start": current_week_key,
            "current_cutoff_date": current_cutoff.isoformat(),
            "previous_equivalent_range_start": previous_week_start.isoformat(),
            "previous_equivalent_cutoff_date": previous_cutoff.isoformat(),
            "baseline_period_key": previous_week_start.isoformat(),
            "baseline_metrics": baseline_by_dim.get(_dim_key(row)),
        }
        enriched.append(next_row)
    return enriched


def _attach_monthly_partial_equivalent_context(
    rows: list[dict[str, Any]],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> list[dict[str, Any]]:
    today = date.today()
    current_month_start = _month_start(today)
    current_month_key = current_month_start.isoformat()
    if not any(str(r.get("month")) == current_month_key for r in rows):
        return rows
    current_cutoff = _get_latest_available_trip_date(
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
        period_start=current_month_start,
        period_end=_month_end(today),
    )
    if current_cutoff is None or current_cutoff < current_month_start:
        return rows
    previous_month_start = _previous_month_start(current_month_start)
    previous_month_end = _month_end(previous_month_start)
    previous_cutoff = date(
        previous_month_start.year,
        previous_month_start.month,
        min(current_cutoff.day, previous_month_end.day),
    )
    baseline_by_dim = _fetch_resolved_metrics_by_dims_for_range(
        previous_month_start,
        previous_cutoff,
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
    )
    enriched: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("month")) != current_month_key:
            enriched.append(row)
            continue
        next_row = dict(row)
        next_row["comparison_context"] = {
            "comparison_mode": "monthly_partial_equivalent",
            "is_partial_equivalent": True,
            "is_operationally_aligned": True,
            "is_preliminary": False,
            "period_state": "PARTIAL",
            "current_range_start": current_month_key,
            "current_cutoff_date": current_cutoff.isoformat(),
            "previous_equivalent_range_start": previous_month_start.isoformat(),
            "previous_equivalent_cutoff_date": previous_cutoff.isoformat(),
            "baseline_period_key": previous_month_start.isoformat(),
            "baseline_metrics": baseline_by_dim.get(_dim_key(row)),
        }
        enriched.append(next_row)
    return enriched


def _attach_daily_same_weekday_context(
    rows: list[dict[str, Any]],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
) -> list[dict[str, Any]]:
    today = date.today()
    parsed_dates: dict[str, date] = {}
    target_dates: list[date] = []
    for row in rows:
        trip_date = row.get("trip_date")
        if not trip_date:
            continue
        d = date.fromisoformat(str(trip_date))
        parsed_dates[str(trip_date)] = d
        target_dates.append(d - timedelta(days=7))
    unique_targets = sorted(set(target_dates))
    baseline_by_date_dim = _fetch_resolved_daily_metrics_for_dates(
        unique_targets,
        country=country,
        city=city,
        business_slice=business_slice,
    )
    enriched: list[dict[str, Any]] = []
    for row in rows:
        trip_date = row.get("trip_date")
        if not trip_date:
            enriched.append(row)
            continue
        d = parsed_dates[str(trip_date)]
        target = d - timedelta(days=7)
        next_row = dict(row)
        next_row["comparison_context"] = {
            "comparison_mode": "daily_same_weekday",
            "is_partial_equivalent": False,
            "is_operationally_aligned": True,
            "is_preliminary": d == today,
            "period_state": "CURRENT_DAY" if d == today else "CLOSED",
            "current_range_start": d.isoformat(),
            "current_cutoff_date": d.isoformat(),
            "previous_equivalent_range_start": target.isoformat(),
            "previous_equivalent_cutoff_date": target.isoformat(),
            "baseline_period_key": target.isoformat(),
            "baseline_metrics": baseline_by_date_dim.get((target.isoformat(), _dim_key(row))),
        }
        enriched.append(next_row)
    return enriched


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
    return _attach_monthly_partial_equivalent_context(
        data,
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
    )


def get_business_slice_coverage(
    year: Optional[int] = None,
    limit_months: int = 36,
) -> dict[str, Any]:
    w, params = [], []
    if year is not None:
        w.append("EXTRACT(YEAR FROM month)::int = %s")
        params.append(int(year))
    where_cov = ("WHERE " + " AND ".join(w)) if w else ""
    # Misma estrategia que real-lob drill: conexión dedicada con statement_timeout=0
    # (el pool/rol a menudo corta ~15s y SET LOCAL no siempre puede subirlo).
    with get_db_drill() as conn:
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
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data


def get_business_slice_coverage_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, Any]:
    """Lightweight coverage summary for Matrix context bar."""
    w: list[str] = ["trip_date IS NOT NULL"]
    params: list[Any] = []
    if year is not None:
        w.append("EXTRACT(YEAR FROM trip_date)::int = %s")
        params.append(int(year))
    if month is not None:
        w.append("EXTRACT(MONTH FROM trip_date)::int = %s")
        params.append(int(month))
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    where_sql = " AND ".join(w)
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT resolution_status, COUNT(*)::bigint AS cnt
                FROM {V_RESOLVED}
                WHERE {where_sql}
                GROUP BY resolution_status
                """,
                params,
            )
            status_counts = {r["resolution_status"]: r["cnt"] for r in cur.fetchall()}
        finally:
            cur.close()
    resolved = status_counts.get("resolved", 0)
    unmatched = status_counts.get("unmatched", 0)
    conflict = status_counts.get("conflict", 0)
    total = sum(int(v or 0) for v in status_counts.values())
    mapped = resolved
    unmapped = unmatched + conflict
    other_status = total - mapped - unmapped
    if total != mapped + unmapped:
        logger.warning(
            "business_slice_coverage_summary_inconsistent total=%s mapped=%s unmapped=%s other_status=%s statuses=%s",
            total, mapped, unmapped, other_status, status_counts,
        )
    return {
        "total_trips": total,
        "mapped_trips": mapped,
        "unmapped_trips": unmapped,
        "other_status_trips": other_status,
        "coverage_pct": round(mapped / total * 100, 1) if total > 0 else None,
        "by_status": status_counts,
    }


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
    with get_db_drill() as conn:
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


def _fact_table_has_data(conn, table: str, date_col: str = "trip_date",
                         year: int | None = None, month: int | None = None) -> bool:
    """Comprueba si la tabla fact tiene filas relevantes para el rango solicitado.

    Si year/month se pasan, verifica que haya datos en ese periodo concreto.
    Si no, basta con que haya alguna fila.
    """
    try:
        cur = conn.cursor()
        clauses = []
        params: list = []
        if year is not None:
            clauses.append(f"EXTRACT(YEAR FROM {date_col})::int = %s")
            params.append(int(year))
        if month is not None:
            clauses.append(f"EXTRACT(MONTH FROM {date_col})::int = %s")
            params.append(int(month))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        cur.execute(f"SELECT 1 FROM {table} {where} LIMIT 1", params)
        has = cur.fetchone() is not None
        cur.close()
        return has
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False


def get_business_slice_weekly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 1500,
) -> list[dict[str, Any]]:
    """Agregado semanal desde fact table pre-calculada (rápido) con fallback a vista resolved."""
    with get_db() as conn:
        if _fact_table_has_data(conn, FACT_WEEKLY, date_col="week_start", year=year):
            logger.info("weekly: usando week_fact (year=%s)", year)
            data = _weekly_from_fact(conn, country, city, business_slice, year, limit)
            return _attach_weekly_partial_equivalent_context(
                data,
                country=country,
                city=city,
                business_slice=business_slice,
            )
    logger.warning(
        "week_fact sin datos para year=%s — fallback a vista resolved (lento)", year,
    )
    data = _weekly_from_resolved(country, city, business_slice, year, limit)
    return _attach_weekly_partial_equivalent_context(
        data,
        country=country,
        city=city,
        business_slice=business_slice,
    )


def _weekly_from_fact(
    conn,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 1500,
) -> list[dict[str, Any]]:
    w: list[str] = []
    params: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        params.append(str(business_slice).strip())
    if year is not None:
        w.append("EXTRACT(YEAR FROM week_start)::int = %s")
        params.append(int(year))
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT week_start, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, revenue_yego_net, commission_pct, trips_per_driver, cancel_rate_pct
        FROM {FACT_WEEKLY}
        {where_sql}
        ORDER BY week_start DESC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    data = [_serialize_row(dict(r)) for r in cur.fetchall()]
    cur.close()
    return data


def _weekly_from_resolved(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 1500,
) -> list[dict[str, Any]]:
    w: list[str] = ["resolution_status = 'resolved'", "trip_week IS NOT NULL"]
    params: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        params.append(str(business_slice).strip())
    if year is not None:
        w.append("EXTRACT(YEAR FROM trip_week)::int = %s")
        params.append(int(year))
    where_sql = "WHERE " + " AND ".join(w)
    sql = f"""
        SELECT trip_week AS week_start, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
               COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
               COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
               AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS avg_ticket,
               SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
        FROM {V_RESOLVED}
        {where_sql}
        GROUP BY trip_week, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
        ORDER BY week_start DESC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    with get_db_drill() as conn:
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
    """Agregado diario desde fact table pre-calculada (rápido) con fallback a vista resolved."""
    with get_db() as conn:
        if _fact_table_has_data(conn, FACT_DAILY, date_col="trip_date",
                                year=year, month=month):
            logger.info("daily: usando day_fact (year=%s month=%s)", year, month)
            data = _daily_from_fact(conn, country, city, business_slice, year, month, limit)
            return _attach_daily_same_weekday_context(
                data,
                country=country,
                city=city,
                business_slice=business_slice,
            )
    logger.warning(
        "day_fact sin datos para year=%s month=%s — fallback a vista resolved (lento)",
        year, month,
    )
    data = _daily_from_resolved(country, city, business_slice, year, month, limit)
    return _attach_daily_same_weekday_context(
        data,
        country=country,
        city=city,
        business_slice=business_slice,
    )


def _daily_from_fact(
    conn,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    w: list[str] = []
    params: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        params.append(str(business_slice).strip())
    if year is not None:
        w.append("EXTRACT(YEAR FROM trip_date)::int = %s")
        params.append(int(year))
    if month is not None:
        w.append("EXTRACT(MONTH FROM trip_date)::int = %s")
        params.append(int(month))
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT trip_date, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, revenue_yego_net, commission_pct, trips_per_driver, cancel_rate_pct
        FROM {FACT_DAILY}
        {where_sql}
        ORDER BY trip_date DESC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    data = [_serialize_row(dict(r)) for r in cur.fetchall()]
    cur.close()
    return data


def _daily_from_resolved(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    w: list[str] = ["resolution_status = 'resolved'", "trip_date IS NOT NULL"]
    params: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        params.append(str(business_slice).strip())
    if year is not None:
        w.append("EXTRACT(YEAR FROM trip_date)::int = %s")
        params.append(int(year))
    if month is not None:
        w.append("EXTRACT(MONTH FROM trip_date)::int = %s")
        params.append(int(month))
    where_sql = "WHERE " + " AND ".join(w)
    sql = f"""
        SELECT trip_date, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
               COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
               COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
               AVG(ticket) FILTER (WHERE completed_flag AND ticket IS NOT NULL) AS avg_ticket,
               SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
        FROM {V_RESOLVED}
        {where_sql}
        GROUP BY trip_date, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
        ORDER BY trip_date DESC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        data = [_serialize_row(dict(r)) for r in cur.fetchall()]
        cur.close()
    return data
