"""
BUSINESS_SLICE — lecturas REAL desde vistas/MV ops (sin mezclar Plan).
"""
from __future__ import annotations

import logging
import math
import numbers
import threading
import time
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.config.kpi_aggregation_rules import (
    OMNIVIEW_MATRIX_VISIBLE_KPIS,
    get_omniview_kpi_rule,
)
from app.db.connection import get_db, get_db_drill, get_db_quick
from app.services.period_state_engine import build_period_states_payload, extract_period_keys_from_rows

logger = logging.getLogger(__name__)

# Caché coverage-summary (SWR: nunca bloquea la UI; el thread background refresca en caliente).
COVERAGE_SUMMARY_CACHE_TTL_SEC = 45.0
_coverage_summary_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_coverage_summary_lock = threading.Lock()
_coverage_summary_refreshing: set[str] = set()
_coverage_summary_refreshing_lock = threading.Lock()

# Caché de filtros (países/ciudades/slices no cambian en el día; TTL 5 min).
_filters_store: dict[str, Any] = {}
_filters_lock = threading.Lock()
FILTERS_CACHE_TTL_SEC = 300.0

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
# Bucket operativo formal: viajes sin slice resuelto (no oculta volumen).
UNMAPPED_BUCKET_CITY = "UNMAPPED"
UNMAPPED_BUCKET_SLICE_NAME = "UNMAPPED"
UNMAPPED_BUCKET_ENTITY_ID = "OPERATIVE_UNMAPPED_SLICE"
UNMAPPED_BUCKET_KIND = "business_slice_resolution_gap"

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
        y = int(year)
        prev_dec = date(y - 1, 12, 1)
        if month is None:
            # Año completo + diciembre Y-1 para MoM (ej. ene-2026 vs dic-2025).
            w.append(
                f"(EXTRACT(YEAR FROM {prefix}month)::int = %s OR {prefix}month = %s::date)"
            )
            p.append(y)
            p.append(prev_dec)
        elif int(month) == 1:
            # Solo enero: incluir mes anterior civil (diciembre Y-1) sin restringir a MONTH=1.
            cur = date(y, 1, 1)
            w.append(
                f"({prefix}month = %s::date OR {prefix}month = %s::date)"
            )
            p.append(prev_dec)
            p.append(cur)
        else:
            w.append(f"EXTRACT(YEAR FROM {prefix}month)::int = %s")
            p.append(y)
            w.append(f"EXTRACT(MONTH FROM {prefix}month)::int = %s")
            p.append(int(month))
    elif month is not None:
        w.append(f"EXTRACT(MONTH FROM {prefix}month)::int = %s")
        p.append(int(month))
    return w, p


def _where_clauses_trip_date(
    country: Optional[str],
    city: Optional[str],
    business_slice: Optional[str],
    fleet: Optional[str],
    subfleet: Optional[str],
    year: Optional[int],
    month: Optional[int],
    prefix: str = "",
) -> tuple[list[str], list[Any]]:
    """Misma semántica que `_where_clauses` pero sobre columna `trip_date` (facts / RAW)."""
    w: list[str] = []
    p: list[Any] = []
    td = f"{prefix}trip_date" if prefix else "trip_date"
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
        y = int(year)
        prev_dec = date(y - 1, 12, 1)
        if month is None:
            w.append(
                f"(EXTRACT(YEAR FROM {td})::int = %s OR date_trunc('month', {td})::date = %s::date)"
            )
            p.append(y)
            p.append(prev_dec)
        elif int(month) == 1:
            cur = date(y, 1, 1)
            w.append(
                f"(date_trunc('month', {td})::date = %s::date OR date_trunc('month', {td})::date = %s::date)"
            )
            p.append(prev_dec)
            p.append(cur)
        else:
            w.append(f"EXTRACT(YEAR FROM {td})::int = %s")
            p.append(y)
            w.append(f"EXTRACT(MONTH FROM {td})::int = %s")
            p.append(int(month))
    elif month is not None:
        w.append(f"EXTRACT(MONTH FROM {td})::int = %s")
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


_CANONICAL_COMPONENT_SELECT = """
    COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
    COUNT(*) FILTER (WHERE cancelled_flag) AS trips_cancelled,
    COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag) AS active_drivers,
    SUM(ticket) FILTER (
        WHERE completed_flag AND ticket IS NOT NULL
    ) AS ticket_sum_completed,
    COUNT(ticket) FILTER (
        WHERE completed_flag AND ticket IS NOT NULL
    )::bigint AS ticket_count_completed,
    SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net,
    SUM(total_fare) FILTER (
        WHERE completed_flag
          AND total_fare IS NOT NULL
          AND total_fare > 0
    ) AS total_fare_completed_positive_sum
"""


def _num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v) if v.is_finite() else 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def _ratio_or_none(numerator: Any, denominator: Any) -> float | None:
    den = _num(denominator)
    if den <= 0:
        return None
    return _num(numerator) / den


def _canonical_metrics_from_components(row: dict[str, Any]) -> dict[str, Any]:
    trips_completed = int(_num(row.get("trips_completed")))
    trips_cancelled = int(_num(row.get("trips_cancelled")))
    active_drivers = int(_num(row.get("active_drivers")))
    ticket_sum = row.get("ticket_sum_completed")
    ticket_count = row.get("ticket_count_completed")
    revenue_yego_net = row.get("revenue_yego_net")
    total_fare_sum = row.get("total_fare_completed_positive_sum")
    metrics = {
        "trips_completed": trips_completed,
        "trips_cancelled": trips_cancelled,
        "active_drivers": active_drivers,
        "revenue_yego_net": _json_safe_scalar(revenue_yego_net),
        "avg_ticket": _json_safe_scalar(_ratio_or_none(ticket_sum, ticket_count)),
        "commission_pct": _json_safe_scalar(_ratio_or_none(revenue_yego_net, total_fare_sum)),
        "cancel_rate_pct": _json_safe_scalar(
            _ratio_or_none(trips_cancelled, trips_completed + trips_cancelled)
        ),
        "trips_per_driver": _json_safe_scalar(_ratio_or_none(trips_completed, active_drivers)),
    }
    for kpi_key in OMNIVIEW_MATRIX_VISIBLE_KPIS:
        get_omniview_kpi_rule(kpi_key)
    return metrics


def _metrics_dict_from_fact_aggregates(
    trips_completed: int,
    trips_cancelled: int,
    active_drivers: int,
    revenue_yego_net: Any,
    avg_ticket: Any,
    commission_pct: Any,
    trips_per_driver: Any,
) -> dict[str, Any]:
    """Métricas canónicas desde SUM/SUM en day_fact o month_fact (drivers sumados ≈ aproximación vs DISTINCT en crudo)."""
    tc = int(trips_completed)
    tcan = int(trips_cancelled)
    ad = int(active_drivers)
    return {
        "trips_completed": tc,
        "trips_cancelled": tcan,
        "active_drivers": ad,
        "revenue_yego_net": _json_safe_scalar(revenue_yego_net),
        "avg_ticket": _json_safe_scalar(avg_ticket),
        "commission_pct": _json_safe_scalar(commission_pct),
        "cancel_rate_pct": _json_safe_scalar(_ratio_or_none(tcan, tc + tcan)),
        "trips_per_driver": _json_safe_scalar(
            trips_per_driver if trips_per_driver is not None else _ratio_or_none(tc, ad)
        ),
    }


def _period_key_for_row(grain: str, row: dict[str, Any]) -> str | None:
    key_name = "month" if grain == "monthly" else "week_start" if grain == "weekly" else "trip_date"
    value = row.get(key_name)
    return str(value)[:10] if value is not None else None


def _period_expr_for_grain(grain: str, column: str = "trip_date") -> str:
    if grain == "monthly":
        return f"date_trunc('month', {column})::date"
    if grain == "weekly":
        return f"date_trunc('week', {column})::date"
    return f"{column}::date"


def _resolved_period_where_clauses(
    grain: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> tuple[list[str], list[Any]]:
    w, p = _resolved_filter_clauses(
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
    )
    if grain == "monthly":
        date_w, date_p = _where_clauses_trip_date(None, None, None, None, None, year, month, "")
        w.extend(date_w)
        p.extend(date_p)
        if year is None and month is None:
            w.append("trip_date >= (date_trunc('month', CURRENT_DATE)::date - interval '12 months')")
    elif grain == "weekly":
        if year is not None:
            r0, r1 = _calendar_year_week_bounds(int(year))
            w.append("trip_date >= %s AND trip_date < %s")
            p.extend([r0, r1 + timedelta(days=7)])
        else:
            w.append("trip_date >= date_trunc('week', CURRENT_DATE)::date - interval '35 days'")
    else:
        date_w, date_p = _where_clauses_trip_date(None, None, None, None, None, year, month, "")
        w.extend(date_w)
        p.extend(date_p)
        if year is None and month is None:
            w.append("trip_date >= CURRENT_DATE - interval '13 days'")
    return w, p


def _fetch_resolved_metrics_for_range(
    start_date: date,
    end_date: date,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> dict[str, Any]:
    w, p = _trip_fact_filter_clauses(
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
    )
    w.extend(["trip_date >= %s", "trip_date <= %s"])
    p.extend([start_date, end_date])
    try:
        with get_db_quick(60000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                f"""
                SELECT
                    COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
                    COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
                    COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
                    SUM(revenue_yego_net) AS revenue_yego_net,
                    SUM(COALESCE(avg_ticket, 0) * NULLIF(trips_completed, 0)::numeric)
                        / NULLIF(SUM(trips_completed), 0) AS avg_ticket,
                    SUM(COALESCE(commission_pct, 0) * NULLIF(trips_completed, 0)::numeric)
                        / NULLIF(SUM(trips_completed), 0) AS commission_pct,
                    SUM(trips_completed)::numeric / NULLIF(SUM(COALESCE(active_drivers, 0)), 0) AS trips_per_driver
                FROM {FACT_DAILY}
                WHERE {' AND '.join(w)}
                """,
                p,
            )
            row = cur.fetchone()
            cur.close()
        r = dict(row or {})
        return _metrics_dict_from_fact_aggregates(
            int(r.get("trips_completed") or 0),
            int(r.get("trips_cancelled") or 0),
            int(r.get("active_drivers") or 0),
            r.get("revenue_yego_net"),
            r.get("avg_ticket"),
            r.get("commission_pct"),
            r.get("trips_per_driver"),
        )
    except Exception as exc:
        logger.warning("_fetch_resolved_metrics_for_range (day_fact): %s", exc)
        return _metrics_dict_from_fact_aggregates(0, 0, 0, None, None, None, None)


def _fetch_resolved_metrics_by_single_dates_batch(
    dates: list[date],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    """Agrega métricas globales por día en una sola query (evita N round-trips en comparación diaria)."""
    uniq = sorted(set(dates))
    if not uniq:
        return {}
    w, p = _trip_fact_filter_clauses(
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
    )
    placeholders = ", ".join(["%s"] * len(uniq))
    w.append(f"trip_date::date IN ({placeholders})")
    p.extend(uniq)
    with get_db_quick(60000) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                trip_date::date AS d,
                COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
                COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
                COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
                SUM(revenue_yego_net) AS revenue_yego_net,
                SUM(COALESCE(avg_ticket, 0) * NULLIF(trips_completed, 0)::numeric)
                    / NULLIF(SUM(trips_completed), 0) AS avg_ticket,
                SUM(COALESCE(commission_pct, 0) * NULLIF(trips_completed, 0)::numeric)
                    / NULLIF(SUM(trips_completed), 0) AS commission_pct,
                SUM(trips_completed)::numeric / NULLIF(SUM(COALESCE(active_drivers, 0)), 0) AS trips_per_driver
            FROM {FACT_DAILY}
            WHERE {' AND '.join(w)}
            GROUP BY trip_date::date
            ORDER BY trip_date::date ASC
            """,
            p,
        )
        raw = cur.fetchall()
        cur.close()
    out: dict[str, dict[str, Any]] = {}
    for row in raw:
        r = dict(row)
        dval = r.get("d")
        key = dval.isoformat() if hasattr(dval, "isoformat") else str(dval)[:10]
        out[key] = _metrics_dict_from_fact_aggregates(
            int(r.get("trips_completed") or 0),
            int(r.get("trips_cancelled") or 0),
            int(r.get("active_drivers") or 0),
            r.get("revenue_yego_net"),
            r.get("avg_ticket"),
            r.get("commission_pct"),
            r.get("trips_per_driver"),
        )
    return out


def _fetch_month_fact_period_totals(
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, dict[str, Any]]:
    """Totales por mes desde month_fact (índices). Evita escanear V_RESOLVED en /business-slice/monthly."""
    w, params = _where_clauses(country, city, business_slice, fleet, subfleet, year, month, "")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT
            month::date AS period_key,
            COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
            COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
            COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
            SUM(revenue_yego_net) AS revenue_yego_net,
            SUM(COALESCE(avg_ticket, 0) * NULLIF(trips_completed, 0)::numeric)
                / NULLIF(SUM(trips_completed), 0) AS avg_ticket,
            SUM(COALESCE(commission_pct, 0) * NULLIF(trips_completed, 0)::numeric)
                / NULLIF(SUM(trips_completed), 0) AS commission_pct,
            SUM(trips_completed)::numeric / NULLIF(SUM(COALESCE(active_drivers, 0)), 0) AS trips_per_driver
        FROM {FACT_MONTHLY}
        {where_sql}
        GROUP BY month
        ORDER BY month ASC
    """
    try:
        with get_db_quick(60000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            raw = [dict(r) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("_fetch_month_fact_period_totals: %s", exc)
        return {}
    totals: dict[str, dict[str, Any]] = {}
    for row in raw:
        period_key = str(row.get("period_key"))[:10]
        totals[period_key] = _metrics_dict_from_fact_aggregates(
            int(row.get("trips_completed") or 0),
            int(row.get("trips_cancelled") or 0),
            int(row.get("active_drivers") or 0),
            row.get("revenue_yego_net"),
            row.get("avg_ticket"),
            row.get("commission_pct"),
            row.get("trips_per_driver"),
        )
    return totals


def _fetch_week_fact_period_totals(
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, dict[str, Any]]:
    """Totales por semana (lunes) desde week_fact; evita V_RESOLVED en meta Matrix semanal."""
    w: list[str] = []
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
    if year is not None:
        r0, r1 = _calendar_year_week_bounds(int(year))
        w.append("week_start >= %s AND week_start <= %s")
        p.extend([r0, r1])
    else:
        w.append("week_start >= date_trunc('week', CURRENT_DATE)::date - interval '35 days'")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT
            week_start::date AS period_key,
            COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
            COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
            COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
            SUM(revenue_yego_net) AS revenue_yego_net,
            SUM(COALESCE(avg_ticket, 0) * NULLIF(trips_completed, 0)::numeric)
                / NULLIF(SUM(trips_completed), 0) AS avg_ticket,
            SUM(COALESCE(commission_pct, 0) * NULLIF(trips_completed, 0)::numeric)
                / NULLIF(SUM(trips_completed), 0) AS commission_pct,
            SUM(trips_completed)::numeric / NULLIF(SUM(COALESCE(active_drivers, 0)), 0) AS trips_per_driver
        FROM {FACT_WEEKLY}
        {where_sql}
        GROUP BY week_start
        ORDER BY week_start ASC
    """
    try:
        with get_db_quick(60000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, p)
            raw = [dict(r) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("_fetch_week_fact_period_totals: %s", exc)
        return {}
    totals: dict[str, dict[str, Any]] = {}
    for row in raw:
        period_key = str(row.get("period_key"))[:10]
        totals[period_key] = _metrics_dict_from_fact_aggregates(
            int(row.get("trips_completed") or 0),
            int(row.get("trips_cancelled") or 0),
            int(row.get("active_drivers") or 0),
            row.get("revenue_yego_net"),
            row.get("avg_ticket"),
            row.get("commission_pct"),
            row.get("trips_per_driver"),
        )
    return totals


def _fetch_day_fact_period_totals(
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, dict[str, Any]]:
    """Totales por día desde day_fact; evita V_RESOLVED en meta Matrix diaria."""
    w, p = _where_clauses_trip_date(
        country, city, business_slice, fleet, subfleet, year, month, ""
    )
    if year is None and month is None:
        w.append("trip_date >= CURRENT_DATE - interval '13 days'")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT
            trip_date::date AS period_key,
            COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
            COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
            COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
            SUM(revenue_yego_net) AS revenue_yego_net,
            SUM(COALESCE(avg_ticket, 0) * NULLIF(trips_completed, 0)::numeric)
                / NULLIF(SUM(trips_completed), 0) AS avg_ticket,
            SUM(COALESCE(commission_pct, 0) * NULLIF(trips_completed, 0)::numeric)
                / NULLIF(SUM(trips_completed), 0) AS commission_pct,
            SUM(trips_completed)::numeric / NULLIF(SUM(COALESCE(active_drivers, 0)), 0) AS trips_per_driver
        FROM {FACT_DAILY}
        {where_sql}
        GROUP BY trip_date
        ORDER BY trip_date ASC
    """
    try:
        with get_db_quick(60000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, p)
            raw = [dict(r) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("_fetch_day_fact_period_totals: %s", exc)
        return {}
    totals: dict[str, dict[str, Any]] = {}
    for row in raw:
        period_key = str(row.get("period_key"))[:10]
        totals[period_key] = _metrics_dict_from_fact_aggregates(
            int(row.get("trips_completed") or 0),
            int(row.get("trips_cancelled") or 0),
            int(row.get("active_drivers") or 0),
            row.get("revenue_yego_net"),
            row.get("avg_ticket"),
            row.get("commission_pct"),
            row.get("trips_per_driver"),
        )
    return totals


def _fetch_resolved_period_totals(
    grain: str,
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, dict[str, Any]]:
    g = (grain or "monthly").strip().lower()
    if g == "monthly":
        return _fetch_month_fact_period_totals(
            country=country,
            city=city,
            business_slice=business_slice,
            fleet=fleet,
            subfleet=subfleet,
            year=year,
            month=month,
        )
    if g == "weekly":
        return _fetch_week_fact_period_totals(
            country=country,
            city=city,
            business_slice=business_slice,
            fleet=fleet,
            subfleet=subfleet,
            year=year,
            month=month,
        )
    if g == "daily":
        return _fetch_day_fact_period_totals(
            country=country,
            city=city,
            business_slice=business_slice,
            fleet=fleet,
            subfleet=subfleet,
            year=year,
            month=month,
        )
    from app.services.serving_guardrails import (
        ServingPolicy, QueryMode, SourceType,
        assert_serving_source, trace_source_usage,
    )
    _fallback_policy = ServingPolicy(
        feature_name="Omniview period totals (non-standard grain)",
        query_mode=QueryMode.SERVING,
        preferred_source=FACT_MONTHLY,
        preferred_source_type=SourceType.FACT,
        strict_mode=True,
    )
    assert_serving_source(_fallback_policy, V_RESOLVED)
    trace_source_usage(
        _fallback_policy, V_RESOLVED, source_type="resolved",
        fallback_used=True, fallback_reason=f"non-standard grain={grain!r}",
    )
    w, p = _resolved_period_where_clauses(
        grain,
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
        year=year,
        month=month,
    )
    period_expr = _period_expr_for_grain(grain)
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT
                {period_expr} AS period_key,
                {_CANONICAL_COMPONENT_SELECT}
            FROM {V_RESOLVED}
            WHERE {' AND '.join(w)}
            GROUP BY 1
            ORDER BY 1 ASC
            """,
            p,
        )
        raw = [dict(r) for r in cur.fetchall()]
        cur.close()
    totals: dict[str, dict[str, Any]] = {}
    for row in raw:
        period_key = str(row.get("period_key"))[:10]
        totals[period_key] = _canonical_metrics_from_components(row)
    return totals


def _extract_period_comparison_ranges(
    rows: list[dict[str, Any]],
    grain: str,
) -> dict[str, tuple[date, date]]:
    ranges: dict[str, tuple[date, date]] = {}
    for row in rows:
        period_key = _period_key_for_row(grain, row)
        cmp = row.get("comparison_context") or {}
        start = cmp.get("previous_equivalent_range_start")
        end = cmp.get("previous_equivalent_cutoff_date")
        if not period_key or not start or not end or period_key in ranges:
            continue
        try:
            ranges[period_key] = (date.fromisoformat(str(start)), date.fromisoformat(str(end)))
        except Exception:
            continue
    return ranges


def _safe_fetch_matrix_totals_meta(
    grain: str,
    rows: list[dict[str, Any]],
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, Any]:
    try:
        period_totals = _fetch_resolved_period_totals(
            grain,
            country=country,
            city=city,
            business_slice=business_slice,
            fleet=fleet,
            subfleet=subfleet,
            year=year,
            month=month,
        )
        comparison_totals: dict[str, dict[str, Any]] = {}
        ranges = _extract_period_comparison_ranges(rows, grain)
        g = (grain or "").strip().lower()
        if g == "daily" and ranges:
            single_items: list[tuple[str, date, date]] = []
            multi_items: list[tuple[str, date, date]] = []
            for period_key, (sd, ed) in ranges.items():
                if sd == ed:
                    single_items.append((period_key, sd, ed))
                else:
                    multi_items.append((period_key, sd, ed))
            if single_items:
                uniq_dates = sorted({sd for _, sd, _ in single_items})
                by_d: dict[str, dict[str, Any]] | None = None
                try:
                    by_d = _fetch_resolved_metrics_by_single_dates_batch(
                        uniq_dates,
                        country=country,
                        city=city,
                        business_slice=business_slice,
                        fleet=fleet,
                        subfleet=subfleet,
                    )
                except Exception as exc:
                    logger.warning("comparison_totals batch (daily) failed, using per-range: %s", exc)
                empty_cmp = _metrics_dict_from_fact_aggregates(0, 0, 0, None, None, None, None)
                if by_d is not None:
                    for period_key, sd, _ in single_items:
                        comparison_totals[period_key] = by_d.get(sd.isoformat(), empty_cmp)
                else:
                    for period_key, sd, ed in single_items:
                        comparison_totals[period_key] = _fetch_resolved_metrics_for_range(
                            sd,
                            ed,
                            country=country,
                            city=city,
                            business_slice=business_slice,
                            fleet=fleet,
                            subfleet=subfleet,
                        )
            for period_key, sd, ed in multi_items:
                comparison_totals[period_key] = _fetch_resolved_metrics_for_range(
                    sd,
                    ed,
                    country=country,
                    city=city,
                    business_slice=business_slice,
                    fleet=fleet,
                    subfleet=subfleet,
                )
        else:
            for period_key, (start_date, end_date) in ranges.items():
                comparison_totals[period_key] = _fetch_resolved_metrics_for_range(
                    start_date,
                    end_date,
                    country=country,
                    city=city,
                    business_slice=business_slice,
                    fleet=fleet,
                    subfleet=subfleet,
                )
        unmapped_period_totals: dict[str, dict[str, Any]] = {}
        if not business_slice and not fleet and not subfleet:
            unmapped_period_totals = _fetch_resolved_period_totals(
                grain,
                country=country,
                city=city,
                business_slice="UNMAPPED",
                year=year,
                month=month,
            )
        return {
            "period_totals": period_totals,
            "comparison_period_totals": comparison_totals,
            "unmapped_period_totals": unmapped_period_totals,
        }
    except Exception as exc:
        logger.warning("matrix canonical totals unavailable: %s", exc, exc_info=True)
        return {
            "period_totals": {},
            "comparison_period_totals": {},
            "unmapped_period_totals": {},
            "totals_warning": str(exc),
        }


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


def _calendar_year_week_bounds(year: int) -> tuple[date, date]:
    """Incluye semanas cuyo lunes cae finales de dic Y-1 (ISO) necesarias para WoW en enero."""
    y = int(year)
    start = date(y, 1, 1) - timedelta(days=14)
    end = date(y, 12, 31) + timedelta(days=6)
    return start, end


def get_business_slice_matrix_freshness_meta() -> dict[str, Any]:
    """MAX(trip_date) sobre day_fact — referencia global (contexto); el State Engine usa máximos por período."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT MAX(trip_date) FROM {FACT_DAILY}")
                row = cur.fetchone()
                mx = row[0] if row else None
            finally:
                cur.close()
        if mx is None:
            return {"slice_max_trip_date": None}
        if hasattr(mx, "isoformat"):
            return {"slice_max_trip_date": mx.isoformat()[:10]}
        return {"slice_max_trip_date": str(mx)[:10]}
    except Exception:
        logger.warning("get_business_slice_matrix_freshness_meta: falló lectura MAX(trip_date)", exc_info=True)
        return {"slice_max_trip_date": None}


def fetch_slice_max_trip_date_by_period_keys(
    grain: str,
    period_keys: list[str],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, str | None]:
    """
    MAX(trip_date) en day_fact por clave de periodo (mes / semana ISO / día), alineado a filtros Matrix.
    Sin heurística global: cada período usa solo filas cuyo trip_date cae en ese grano.
    """
    g = (grain or "monthly").strip().lower()
    keys = [str(k).strip()[:10] for k in period_keys if k]
    if not keys:
        return {}
    # Weekly + año: misma ventana calendario que week_fact (_calendar_year_week_bounds), no solo EXTRACT(YEAR).
    if g == "weekly" and year is not None:
        w, params = _where_clauses_trip_date(
            country, city, business_slice, fleet, subfleet, None, None, ""
        )
        r0, r1 = _calendar_year_week_bounds(int(year))
        w.append("trip_date >= %s AND trip_date <= %s")
        params.extend([r0, r1])
    else:
        w, params = _where_clauses_trip_date(
            country, city, business_slice, fleet, subfleet, year, month, ""
        )
        if year is None and month is None:
            if g == "monthly":
                w.append(
                    "trip_date >= (date_trunc('month', CURRENT_DATE)::date - interval '12 months')"
                )
            elif g == "weekly":
                w.append(
                    "trip_date >= (date_trunc('week', CURRENT_DATE)::date - interval '35 days')"
                )
            else:
                w.append("trip_date >= CURRENT_DATE - interval '13 days'")
    where_parts = list(w)
    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"
    try:
        parsed_dates: list[date] = []
        for k in keys:
            try:
                y, m, d = int(k[0:4]), int(k[5:7]), int(k[8:10])
                parsed_dates.append(date(y, m, d))
            except (ValueError, TypeError):
                continue
        if not parsed_dates:
            return {}
        with get_db() as conn:
            cur = conn.cursor()
            try:
                if g == "monthly":
                    cur.execute(
                        f"""
                        SELECT date_trunc('month', trip_date)::date AS pk, MAX(trip_date) AS mx
                        FROM {FACT_DAILY}
                        WHERE ({where_sql})
                          AND date_trunc('month', trip_date)::date = ANY(%s)
                        GROUP BY 1
                        """,
                        params + [parsed_dates],
                    )
                elif g == "weekly":
                    cur.execute(
                        f"""
                        SELECT date_trunc('week', trip_date)::date AS pk, MAX(trip_date) AS mx
                        FROM {FACT_DAILY}
                        WHERE ({where_sql})
                          AND date_trunc('week', trip_date)::date = ANY(%s)
                        GROUP BY 1
                        """,
                        params + [parsed_dates],
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT trip_date::date AS pk, MAX(trip_date) AS mx
                        FROM {FACT_DAILY}
                        WHERE ({where_sql})
                          AND trip_date::date = ANY(%s)
                        GROUP BY 1
                        """,
                        params + [parsed_dates],
                    )
                rows = cur.fetchall()
            finally:
                cur.close()
    except Exception:
        logger.warning(
            "fetch_slice_max_trip_date_by_period_keys: falló agregación day_fact",
            exc_info=True,
        )
        return {}
    out: dict[str, str | None] = {}
    for pk, mx in rows:
        if pk is None:
            continue
        pks = pk.isoformat()[:10] if hasattr(pk, "isoformat") else str(pk)[:10]
        if mx is None:
            out[pks] = None
        elif hasattr(mx, "isoformat"):
            out[pks] = mx.isoformat()[:10]
        else:
            out[pks] = str(mx)[:10]
    for k in keys:
        if k not in out:
            out[k] = None
    return out


def enrich_business_slice_matrix_meta(
    meta: dict[str, Any],
    grain: str,
    rows: list[dict[str, Any]],
    *,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    fact_layer: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Añade period_states (State Engine) al meta de Matrix."""
    out = dict(meta or {})
    out["grain"] = (grain or "monthly").strip().lower()
    out["period_max_date_source"] = "ops.real_business_slice_day_fact"
    pkeys = extract_period_keys_from_rows(out["grain"], rows)
    per_period = fetch_slice_max_trip_date_by_period_keys(
        out["grain"],
        pkeys,
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
        year=year,
        month=month,
    )
    out["per_period_max_trip_date"] = per_period
    out["period_states"] = build_period_states_payload(
        out["grain"], rows, out.get("slice_max_trip_date"), per_period_max_dates=per_period
    )
    if fact_layer:
        out["fact_layer"] = fact_layer
    out.update(
        _safe_fetch_matrix_totals_meta(
            out["grain"],
            rows,
            country=country,
            city=city,
            business_slice=business_slice,
            fleet=fleet,
            subfleet=subfleet,
            year=year,
            month=month,
        )
    )
    return out


def _trip_fact_filter_clauses(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> tuple[list[str], list[Any]]:
    """Filtros geo/dimensión sobre `trip_date` en day_fact (sin V_RESOLVED)."""
    w: list[str] = ["trip_date IS NOT NULL"]
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
    # Lee desde FACT_DAILY (indexada) en lugar de V_RESOLVED (sin índice, sin timeout).
    w: list[str] = ["trip_date IS NOT NULL"]
    p: list[Any] = []
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        p.append(str(business_slice).strip())
    if fleet and str(fleet).strip():
        w.append("fleet_display_name IS NOT NULL AND LOWER(TRIM(fleet_display_name::text)) = LOWER(TRIM(%s))")
        p.append(str(fleet).strip())
    if period_start is not None:
        w.append("trip_date >= %s")
        p.append(period_start)
    if period_end is not None:
        w.append("trip_date <= %s")
        p.append(period_end)
    try:
        with get_db_quick(20000) as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT MAX(trip_date) FROM {FACT_DAILY} WHERE {' AND '.join(w)}",
                p,
            )
            row = cur.fetchone()
            cur.close()
        return row[0] if row and row[0] is not None else None
    except Exception as exc:
        logger.warning("_get_latest_available_trip_date timeout/error (fact_daily): %s", exc)
        return None


def _fetch_resolved_metrics_by_dims_for_range(
    start_date: date,
    end_date: date,
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    w, p = _trip_fact_filter_clauses(
        country=country,
        city=city,
        business_slice=business_slice,
        fleet=fleet,
        subfleet=subfleet,
    )
    w.extend(["trip_date >= %s", "trip_date <= %s"])
    p.extend([start_date, end_date])
    try:
        with get_db_quick(60000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                f"""
                SELECT
                    country, city, business_slice_name, fleet_display_name,
                    is_subfleet, subfleet_name,
                    COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
                    COALESCE(SUM(trips_cancelled), 0)::bigint AS trips_cancelled,
                    COALESCE(SUM(active_drivers), 0)::bigint AS active_drivers,
                    SUM(revenue_yego_net) AS revenue_yego_net,
                    SUM(COALESCE(avg_ticket, 0) * NULLIF(trips_completed, 0)::numeric)
                        / NULLIF(SUM(trips_completed), 0) AS avg_ticket,
                    SUM(COALESCE(commission_pct, 0) * NULLIF(trips_completed, 0)::numeric)
                        / NULLIF(SUM(trips_completed), 0) AS commission_pct,
                    SUM(trips_completed)::numeric / NULLIF(SUM(COALESCE(active_drivers, 0)), 0) AS trips_per_driver
                FROM {FACT_DAILY}
                WHERE {' AND '.join(w)}
                GROUP BY country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
                """,
                p,
            )
            rows = []
            for raw in cur.fetchall():
                item = dict(raw)
                m = _metrics_dict_from_fact_aggregates(
                    int(item.get("trips_completed") or 0),
                    int(item.get("trips_cancelled") or 0),
                    int(item.get("active_drivers") or 0),
                    item.get("revenue_yego_net"),
                    item.get("avg_ticket"),
                    item.get("commission_pct"),
                    item.get("trips_per_driver"),
                )
                item.update(m)
                rows.append(_serialize_row(item))
            cur.close()
        return {_dim_key(r): r for r in rows}
    except Exception as exc:
        logger.warning("_fetch_resolved_metrics_by_dims_for_range (day_fact): %s", exc)
        return {}


def _fetch_resolved_daily_metrics_for_dates(
    target_dates: list[date],
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
) -> dict[tuple[str, tuple[Any, ...]], dict[str, Any]]:
    """Devuelve métricas por (trip_date, dimensión) para las fechas indicadas.
    Lee desde FACT_DAILY (pre-agregada, indexed) en lugar de V_RESOLVED sin índice."""
    if not target_dates:
        return {}
    w: list[str] = []
    p: list[Any] = []
    placeholders = ", ".join(["%s"] * len(target_dates))
    w.append(f"trip_date IN ({placeholders})")
    p.extend(target_dates)
    if country and str(country).strip():
        w.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    if business_slice and str(business_slice).strip():
        w.append("business_slice_name IS NOT NULL AND LOWER(TRIM(business_slice_name::text)) = LOWER(TRIM(%s))")
        p.append(str(business_slice).strip())
    try:
        with get_db_quick(20000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                f"""
                SELECT
                    trip_date,
                    country, city, business_slice_name, fleet_display_name,
                    is_subfleet, subfleet_name,
                    SUM(trips_completed)::bigint AS trips_completed,
                    SUM(trips_cancelled)::bigint AS trips_cancelled,
                    SUM(active_drivers)::bigint AS active_drivers,
                    AVG(avg_ticket) AS avg_ticket,
                    SUM(revenue_yego_net) AS revenue_yego_net,
                    AVG(commission_pct) AS commission_pct,
                    AVG(trips_per_driver) AS trips_per_driver,
                    AVG(cancel_rate_pct) AS cancel_rate_pct
                FROM {FACT_DAILY}
                WHERE {' AND '.join(w)}
                GROUP BY trip_date, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
                """,
                p,
            )
            rows = [_serialize_row(dict(r)) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("_fetch_resolved_daily_metrics_for_dates timeout/error (fact_daily): %s", exc)
        return {}
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
    now = time.monotonic()
    with _filters_lock:
        if _filters_store and (now - _filters_store.get("ts", 0.0)) < FILTERS_CACHE_TTL_SEC:
            return _filters_store["data"]
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
    result = {
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
    with _filters_lock:
        _filters_store["ts"] = time.monotonic()
        _filters_store["data"] = result
    return result


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
    if year is None and month is None:
        # Mínimo ~13 meses civiles para serie MoM en Matrix sin filtro año.
        w.append(
            "month >= (date_trunc('month', CURRENT_DATE)::date - interval '12 months')"
        )
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    eff_limit = min(max(limit, 1), 10000)
    if year is not None:
        eff_limit = min(10000, max(eff_limit, 6000))
    # Con filtro de año, orden cronológico para no perder meses iniciales bajo LIMIT.
    order_m = "ASC" if year is not None else "DESC"
    sql = f"""
        SELECT *
        FROM {MV_MONTHLY}
        {where_sql}
        ORDER BY month {order_m}, country, city, business_slice_name, fleet_display_name
        LIMIT %s
    """
    params.append(eff_limit)
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

        # SERVING_DISCIPLINE: These two queries use V_RESOLVED because they need
        # resolution_status (resolved/unmatched/conflict) which is not in fact tables.
        # Classified as drill/audit, not serving normal. Acceptable per architecture doc.
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


def _coverage_summary_cache_key(
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> str:
    return "|".join(
        [
            (country or "").strip().lower(),
            (city or "").strip().lower(),
            str(year) if year is not None else "",
            str(month) if month is not None else "",
        ]
    )


def _compute_coverage_summary_raw(
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> dict[str, Any]:
    """Calcula cobertura desde FACT_DAILY (pre-agregada, sin índice lento de V_RESOLVED).
    'mapped' = trips en slices con nombre real; 'unmapped' = filas con business_slice_name = 'UNMAPPED'.
    Para el total RAW se sigue consultando trips_unified con timeout ajustado."""
    w_fact: list[str] = ["trip_date IS NOT NULL"]
    p_fact: list[Any] = []
    if year is not None:
        w_fact.append("EXTRACT(YEAR FROM trip_date)::int = %s")
        p_fact.append(int(year))
    if month is not None:
        w_fact.append("EXTRACT(MONTH FROM trip_date)::int = %s")
        p_fact.append(int(month))
    if country and str(country).strip():
        w_fact.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        p_fact.append(str(country).strip())
    if city and str(city).strip():
        w_fact.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        p_fact.append(str(city).strip())
    where_fact = " AND ".join(w_fact)

    with get_db_quick(10000) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Cobertura desde FACT_DAILY: trips mapeados vs UNMAPPED
            cur.execute(
                f"""
                SELECT
                    CASE WHEN UPPER(TRIM(business_slice_name)) = 'UNMAPPED' THEN 'unmapped' ELSE 'mapped' END AS bucket,
                    SUM(trips_completed + trips_cancelled)::bigint AS cnt
                FROM {FACT_DAILY}
                WHERE {where_fact}
                GROUP BY bucket
                """,
                p_fact,
            )
            bucket_counts = {r["bucket"]: int(r["cnt"] or 0) for r in cur.fetchall()}
            mapped = bucket_counts.get("mapped", 0)
            unmapped = bucket_counts.get("unmapped", 0)
            total_resolved = mapped + unmapped
            # Usamos el total de FACT_DAILY como denominador (mapped + unmapped)
            total_raw = total_resolved
        finally:
            cur.close()

    identity_raw_vs_resolved_ok = total_raw == total_resolved
    denom = total_raw if total_raw > 0 else (total_resolved if total_resolved > 0 else None)
    cov_ratio = (mapped / float(denom)) if denom else None
    if not identity_raw_vs_resolved_ok:
        logger.warning(
            "business_slice_coverage_summary RAW vs fact: total_raw=%s total_fact=%s (filtro=%s)",
            total_raw, total_resolved,
            {"country": country, "city": city, "year": year, "month": month},
        )
    return {
        "total_trips_real_raw": total_raw,
        "total_trips_real": total_raw,
        "total_trips_in_resolved_view": total_resolved,
        "total_trips": total_raw,
        "mapped_trips": mapped,
        "unmapped_trips": unmapped,
        "coverage_pct": round(cov_ratio * 100, 1) if cov_ratio is not None else None,
        "coverage_ratio": round(cov_ratio, 4) if cov_ratio is not None else None,
        "identity_check_ok": identity_raw_vs_resolved_ok,
        "identity_raw_vs_resolved_ok": identity_raw_vs_resolved_ok,
        "coverage_basis": "fact_daily_mapped_vs_unmapped",
        "by_status": {"resolved": mapped, "unmatched": unmapped},
    }


def _refresh_coverage_summary_background(
    cache_key: str,
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> None:
    """Thread daemon: refresca coverage-summary en segundo plano y actualiza el cache."""
    try:
        result = _compute_coverage_summary_raw(country, city, year, month)
        with _coverage_summary_lock:
            _coverage_summary_cache[cache_key] = (time.monotonic(), result)
        logger.debug("coverage_summary background refresh done: key=%s", cache_key)
    except Exception as exc:
        logger.warning("coverage_summary background refresh failed (key=%s): %s", cache_key, exc)
    finally:
        with _coverage_summary_refreshing_lock:
            _coverage_summary_refreshing.discard(cache_key)


def _coverage_summary_has_scope(
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> bool:
    """True si el agregado está acotado (no escaneo global de toda la fact)."""
    return bool(
        (country and str(country).strip())
        or (city and str(city).strip())
        or year is not None
        or month is not None
    )


def get_business_slice_coverage_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict[str, Any]:
    """Cobertura mapped vs UNMAPPED desde day_fact.

    - Cache fresco (< TTL): respuesta instantánea.
    - Cache stale: devuelve el dato anterior y refresca en background (SWR).
    - Miss sin entrada en cache: si hay scope (país/ciudad/año/mes), **calcula en esta petición**
      para que el cliente no reciba {} sin reintento; sin scope el agregado global es costoso y
      se mantiene refresh en background + {} hasta tener cache.
    """
    cache_key = _coverage_summary_cache_key(country, city, year, month)
    now = time.monotonic()
    with _coverage_summary_lock:
        hit = _coverage_summary_cache.get(cache_key)
        if hit is not None and (now - hit[0]) < COVERAGE_SUMMARY_CACHE_TTL_SEC:
            return hit[1]
        stale = hit[1] if hit else None

    if stale is not None:
        with _coverage_summary_refreshing_lock:
            if cache_key not in _coverage_summary_refreshing:
                _coverage_summary_refreshing.add(cache_key)
                threading.Thread(
                    target=_refresh_coverage_summary_background,
                    args=(cache_key, country, city, year, month),
                    daemon=True,
                ).start()
        return stale

    if _coverage_summary_has_scope(country, city, year, month):
        try:
            result = _compute_coverage_summary_raw(country, city, year, month)
            with _coverage_summary_lock:
                _coverage_summary_cache[cache_key] = (time.monotonic(), result)
            return result
        except Exception as exc:
            logger.warning("coverage_summary sync compute failed (key=%s): %s", cache_key, exc)
            return {}

    with _coverage_summary_refreshing_lock:
        if cache_key not in _coverage_summary_refreshing:
            _coverage_summary_refreshing.add(cache_key)
            threading.Thread(
                target=_refresh_coverage_summary_background,
                args=(cache_key, country, city, year, month),
                daemon=True,
            ).start()

    return {}


def _unmapped_geo_sql(
    country: Optional[str],
    city: Optional[str],
    prefix: str = "",
) -> tuple[str, list[Any]]:
    w: list[str] = []
    p: list[Any] = []
    if country and str(country).strip():
        w.append(f"{prefix}country IS NOT NULL AND LOWER(TRIM({prefix}country::text)) = LOWER(TRIM(%s))")
        p.append(str(country).strip())
    if city and str(city).strip():
        w.append(f"{prefix}city IS NOT NULL AND LOWER(TRIM({prefix}city::text)) = LOWER(TRIM(%s))")
        p.append(str(city).strip())
    return (" AND ".join(w)) if w else "", p


def _unmapped_bucket_monthly_rows(
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for period_key, metrics in _fetch_resolved_period_totals(
        "monthly",
        country=country,
        city=city,
        business_slice="UNMAPPED",
        year=year,
        month=month,
    ).items():
        row = {
            **metrics,
            "month": period_key,
            "country": "—",
            "city": UNMAPPED_BUCKET_CITY,
            "business_slice_name": UNMAPPED_BUCKET_SLICE_NAME,
            "fleet_display_name": "—",
            "is_subfleet": False,
            "subfleet_name": "",
            "is_unmapped_bucket": True,
            "unmapped_entity_id": UNMAPPED_BUCKET_ENTITY_ID,
            "operative_bucket_kind": UNMAPPED_BUCKET_KIND,
        }
        out.append(row)
    return out


def _unmapped_bucket_weekly_rows(
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for period_key, metrics in _fetch_resolved_period_totals(
        "weekly",
        country=country,
        city=city,
        business_slice="UNMAPPED",
        year=year,
        month=None,
    ).items():
        row = {
            **metrics,
            "week_start": period_key,
            "country": "—",
            "city": UNMAPPED_BUCKET_CITY,
            "business_slice_name": UNMAPPED_BUCKET_SLICE_NAME,
            "fleet_display_name": "—",
            "is_subfleet": False,
            "subfleet_name": "",
            "is_unmapped_bucket": True,
            "unmapped_entity_id": UNMAPPED_BUCKET_ENTITY_ID,
            "operative_bucket_kind": UNMAPPED_BUCKET_KIND,
        }
        out.append(row)
    return out


def _unmapped_bucket_daily_rows(
    country: Optional[str],
    city: Optional[str],
    year: Optional[int],
    month: Optional[int],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for period_key, metrics in _fetch_resolved_period_totals(
        "daily",
        country=country,
        city=city,
        business_slice="UNMAPPED",
        year=year,
        month=month,
    ).items():
        row = {
            **metrics,
            "trip_date": period_key,
            "country": "—",
            "city": UNMAPPED_BUCKET_CITY,
            "business_slice_name": UNMAPPED_BUCKET_SLICE_NAME,
            "fleet_display_name": "—",
            "is_subfleet": False,
            "subfleet_name": "",
            "is_unmapped_bucket": True,
            "unmapped_entity_id": UNMAPPED_BUCKET_ENTITY_ID,
            "operative_bucket_kind": UNMAPPED_BUCKET_KIND,
        }
        out.append(row)
    return out


def append_unmapped_bucket_rows(
    rows: list[dict[str, Any]],
    grain: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    business_slice: Optional[str] = None,
    fleet: Optional[str] = None,
    subfleet: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Añade filas agregadas UNMAPPED (viajes sin slice resuelto). No aplica si hay
    filtro de tajada/flota/subflota (el bucket es fuera de dimensión slice).
    """
    if business_slice and str(business_slice).strip():
        return rows
    if fleet and str(fleet).strip():
        return rows
    if subfleet and str(subfleet).strip():
        return rows
    g = (grain or "monthly").strip().lower()
    extra: list[dict[str, Any]] = []
    if g == "monthly":
        extra = _unmapped_bucket_monthly_rows(country, city, year, month)
    elif g == "weekly":
        extra = _unmapped_bucket_weekly_rows(country, city, year)
    else:
        extra = _unmapped_bucket_daily_rows(country, city, year, month)
    if not extra:
        return rows
    return list(rows) + extra


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
            if date_col == "week_start":
                r0, r1 = _calendar_year_week_bounds(year)
                clauses.append(f"{date_col} >= %s AND {date_col} <= %s")
                params.extend([r0, r1])
            elif date_col == "trip_date":
                y = int(year)
                if month is not None:
                    m = int(month)
                    if m == 1:
                        lo = date(y, 1, 1) - timedelta(days=7)
                        hi = date(y, m, monthrange(y, m)[1])
                        clauses.append(f"{date_col} >= %s AND {date_col} <= %s")
                        params.extend([lo, hi])
                    else:
                        clauses.append(f"EXTRACT(YEAR FROM {date_col})::int = %s")
                        params.append(y)
                        clauses.append(f"EXTRACT(MONTH FROM {date_col})::int = %s")
                        params.append(m)
                else:
                    lo = date(y, 1, 1) - timedelta(days=7)
                    hi = date(y, 12, 31)
                    clauses.append(f"{date_col} >= %s AND {date_col} <= %s")
                    params.extend([lo, hi])
            else:
                clauses.append(f"EXTRACT(YEAR FROM {date_col})::int = %s")
                params.append(int(year))
        elif month is not None:
            clauses.append(f"EXTRACT(MONTH FROM {date_col})::int = %s")
            params.append(int(month))
        else:
            if date_col == "week_start":
                clauses.append(
                    f"{date_col} >= date_trunc('week', CURRENT_DATE)::date - interval '35 days'"
                )
            elif date_col == "trip_date":
                clauses.append(f"{date_col} >= CURRENT_DATE - interval '13 days'")
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
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Agregado semanal desde ops.real_business_slice_week_fact; sin datos en fact → vacío (sin escanear V_RESOLVED)."""
    eff_limit = min(max(limit, 1), 10000)
    if year is not None:
        eff_limit = min(10000, max(eff_limit, 7500))
    empty_meta: dict[str, Any] = {
        "grain": "weekly",
        "source_table": FACT_WEEKLY,
        "status": "empty",
        "source": None,
        "code": "FACT_LAYER_EMPTY",
        "message": (
            "No hay datos en ops.real_business_slice_week_fact para el filtro. "
            "Materializá FACT o ejecutá el backfill; la vista resolved no se usa por rendimiento."
        ),
    }
    with get_db() as conn:
        if _fact_table_has_data(
            conn, FACT_WEEKLY, date_col="week_start", year=year, month=None
        ):
            data = _weekly_from_fact(conn, country, city, business_slice, year, eff_limit)
            if not data:
                return [], empty_meta
            meta_ok: dict[str, Any] = {
                "grain": "weekly",
                "source_table": FACT_WEEKLY,
                "status": "ok",
                "source": "week_fact",
            }
            return (
                _attach_weekly_partial_equivalent_context(
                    data,
                    country=country,
                    city=city,
                    business_slice=business_slice,
                ),
                meta_ok,
            )
    return [], empty_meta


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
        r0, r1 = _calendar_year_week_bounds(year)
        w.append("week_start >= %s AND week_start <= %s")
        params.extend([r0, r1])
    else:
        w.append(
            "week_start >= date_trunc('week', CURRENT_DATE)::date - interval '35 days'"
        )
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT week_start, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, revenue_yego_net, commission_pct, trips_per_driver, cancel_rate_pct
        FROM {FACT_WEEKLY}
        {where_sql}
        ORDER BY week_start ASC
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
    w, params = _resolved_filter_clauses(
        country=country,
        city=city,
        business_slice=business_slice,
    )
    if year is not None:
        r0, r1 = _calendar_year_week_bounds(year)
        w.append("trip_date >= %s AND trip_date < %s")
        params.extend([r0, r1 + timedelta(days=7)])
    else:
        w.append("trip_date >= date_trunc('week', CURRENT_DATE)::date - interval '35 days'")
    sql = f"""
        SELECT
            date_trunc('week', trip_date)::date AS week_start,
            country,
            city,
            business_slice_name,
            fleet_display_name,
            is_subfleet,
            subfleet_name,
            {_CANONICAL_COMPONENT_SELECT}
        FROM {V_RESOLVED}
        WHERE {' AND '.join(w)}
        GROUP BY 1, country, city, business_slice_name, fleet_display_name, is_subfleet, subfleet_name
        ORDER BY 1 ASC, country, city, business_slice_name, fleet_display_name
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    with get_db_drill() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        rows: list[dict[str, Any]] = []
        for raw in cur.fetchall():
            item = dict(raw)
            item.update(_canonical_metrics_from_components(item))
            rows.append(_serialize_row(item))
        cur.close()
    return rows


def get_business_slice_daily(
    country: Optional[str] = None,
    city: Optional[str] = None,
    business_slice: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    limit: int = 2000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Agregado diario solo desde ops.real_business_slice_day_fact (sin agregación runtime sobre resolved)."""
    eff_limit = min(max(limit, 1), 10000)
    if year is not None and month is None:
        eff_limit = min(10000, max(eff_limit, 8000))
    empty_meta: dict[str, Any] = {
        "grain": "daily",
        "source_table": FACT_DAILY,
        "status": "empty",
        "source": None,
        "code": "FACT_LAYER_EMPTY",
        "message": (
            "No hay datos operativos en ops.real_business_slice_day_fact para el filtro. "
            "Cargar day_fact / ETL; la agregación en caliente sobre la vista resolved está desactivada."
        ),
    }
    with get_db() as conn:
        if _fact_table_has_data(conn, FACT_DAILY, date_col="trip_date",
                                year=year, month=month):
            logger.info("daily: usando day_fact (year=%s month=%s)", year, month)
            data = _daily_from_fact(conn, country, city, business_slice, year, month, eff_limit)
            meta_ok: dict[str, Any] = {
                "grain": "daily",
                "source_table": FACT_DAILY,
                "status": "ok",
                "source": "day_fact",
            }
            return (
                _attach_daily_same_weekday_context(
                    data,
                    country=country,
                    city=city,
                    business_slice=business_slice,
                ),
                meta_ok,
            )
    logger.error(
        "FACT_LAYER_EMPTY daily: %s sin filas en ventana operativa (year=%s month=%s country=%s city=%s slice=%s). "
        "Fallback a vista resolved deshabilitado por política de rendimiento.",
        FACT_DAILY,
        year,
        month,
        country,
        city,
        business_slice,
    )
    return [], empty_meta


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
        y = int(year)
        if month is not None:
            mo = int(month)
            if mo == 1:
                lo = date(y, 1, 1) - timedelta(days=7)
                hi = date(y, mo, monthrange(y, mo)[1])
                w.append("trip_date >= %s AND trip_date <= %s")
                params.extend([lo, hi])
            else:
                w.append("EXTRACT(YEAR FROM trip_date)::int = %s")
                params.append(y)
                w.append("EXTRACT(MONTH FROM trip_date)::int = %s")
                params.append(mo)
        else:
            lo = date(y, 1, 1) - timedelta(days=7)
            hi = date(y, 12, 31)
            w.append("trip_date >= %s AND trip_date <= %s")
            params.extend([lo, hi])
    elif month is not None:
        w.append("EXTRACT(MONTH FROM trip_date)::int = %s")
        params.append(int(month))
    else:
        w.append("trip_date >= CURRENT_DATE - interval '13 days'")
    where_sql = ("WHERE " + " AND ".join(w)) if w else ""
    sql = f"""
        SELECT trip_date, country, city, business_slice_name, fleet_display_name,
               is_subfleet, subfleet_name,
               trips_completed, trips_cancelled, active_drivers,
               avg_ticket, revenue_yego_net, commission_pct, trips_per_driver, cancel_rate_pct
        FROM {FACT_DAILY}
        {where_sql}
        ORDER BY trip_date ASC
        LIMIT %s
    """
    params.append(min(max(limit, 1), 10000))
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params)
    data = [_serialize_row(dict(r)) for r in cur.fetchall()]
    cur.close()
    return data
