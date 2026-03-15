"""
Real Operational: lecturas desde mv_real_lob_day_v2 y mv_real_lob_hour_v2.
Expone: today, yesterday, this_week, day_view, hourly_view, cancellation_view.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

MV_DAY = "ops.mv_real_lob_day_v2"
MV_HOUR = "ops.mv_real_lob_hour_v2"
TIMEOUT_MS = 30000


def _float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _serialize_row(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()[:10] if hasattr(v, "day") else str(v)
        else:
            out[k] = v
    return out


def get_operational_snapshot(
    window: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    window: "today" | "yesterday" | "this_week"
    Agregado de day_v2 para ese periodo. Si no hay datos, devuelve ceros.
    """
    today = date.today()
    if window == "today":
        start_d, end_d = today, today + timedelta(days=1)
    elif window == "yesterday":
        start_d, end_d = today - timedelta(days=1), today
    elif window == "this_week":
        # Lunes a hoy
        start_d = today - timedelta(days=today.weekday())
        end_d = today + timedelta(days=1)
    else:
        return {"error": "window must be today | yesterday | this_week"}

    where_parts = ["trip_date >= %s", "trip_date < %s"]
    params = [start_d, end_d]
    if country and str(country).strip():
        where_parts.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        where_parts.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if park_id and str(park_id).strip():
        where_parts.append("LOWER(TRIM(park_id::text)) = LOWER(TRIM(%s))")
        params.append(str(park_id).strip())

    where_sql = " AND ".join(where_parts)
    sql = f"""
        SELECT
            SUM(requested_trips) AS requested_trips,
            SUM(completed_trips) AS completed_trips,
            SUM(cancelled_trips) AS cancelled_trips,
            SUM(unknown_outcome_trips) AS unknown_outcome_trips,
            SUM(gross_revenue) AS gross_revenue,
            SUM(margin_total) AS margin_total,
            SUM(distance_total_km) AS distance_total_km,
            SUM(duration_total_minutes) AS duration_total_minutes,
            SUM(completed_trips) AS completed_for_avg
        FROM {MV_DAY}
        WHERE {where_sql}
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(sql, params)
            row = cur.fetchone()
            revenue_by_country = []
            if not (country and str(country).strip()):
                sql_by_country = f"""
                    SELECT country, SUM(gross_revenue) AS gross_revenue, SUM(margin_total) AS margin_total
                    FROM {MV_DAY}
                    WHERE {where_sql}
                    GROUP BY country
                    ORDER BY country
                """
                try:
                    cur.execute(sql_by_country, params)
                    for r in cur.fetchall() or []:
                        revenue_by_country.append({
                            "country": r.get("country") or "",
                            "gross_revenue": round(_float(r.get("gross_revenue")) or 0, 4),
                            "margin_total": round(_float(r.get("margin_total")) or 0, 4),
                        })
                except Exception:
                    pass
            cur.close()
        if not row:
            return _empty_snapshot(window, start_d, end_d)

        req = _float(row.get("requested_trips")) or 0
        comp = _float(row.get("completed_trips")) or 0
        canc = _float(row.get("cancelled_trips")) or 0
        comp_for_avg = _float(row.get("completed_for_avg")) or 0
        dur_total = _float(row.get("duration_total_minutes"))

        out = {
            "window": window,
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "requested_trips": int(req),
            "completed_trips": int(comp),
            "cancelled_trips": int(canc),
            "unknown_outcome_trips": int(_float(row.get("unknown_outcome_trips")) or 0),
            "gross_revenue": round(_float(row.get("gross_revenue")) or 0, 4),
            "margin_total": round(_float(row.get("margin_total")) or 0, 4),
            "distance_total_km": round(_float(row.get("distance_total_km")) or 0, 4),
            "duration_total_minutes": round(dur_total, 2) if dur_total is not None else None,
            "duration_avg_minutes": round(dur_total / comp_for_avg, 2) if comp_for_avg and dur_total else None,
            "cancellation_rate": round(canc / req, 4) if req else 0,
            "completion_rate": round(comp / req, 4) if req else 0,
        }
        if revenue_by_country:
            out["gross_revenue_by_country"] = revenue_by_country
        return out
    except Exception as e:
        return {"error": str(e), "window": window}


def _empty_snapshot(window: str, start_d: date, end_d: date) -> dict:
    return {
        "window": window,
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "requested_trips": 0,
        "completed_trips": 0,
        "cancelled_trips": 0,
        "unknown_outcome_trips": 0,
        "gross_revenue": 0,
        "margin_total": 0,
        "distance_total_km": 0,
        "duration_total_minutes": None,
        "duration_avg_minutes": None,
        "cancellation_rate": 0,
        "completion_rate": 0,
        "gross_revenue_by_country": [],
    }


def get_day_view(
    days_back: int = 14,
    country: Optional[str] = None,
    city: Optional[str] = None,
    group_by: str = "day",
) -> dict[str, Any]:
    """
    Desempeño por día (últimos days_back). group_by: "day" | "city" | "park" | "lob" | "service".
    """
    end_d = date.today() + timedelta(days=1)
    start_d = end_d - timedelta(days=max(1, min(365, days_back)))

    where_parts = ["trip_date >= %s", "trip_date < %s"]
    params = [start_d, end_d]
    if country and str(country).strip():
        where_parts.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        where_parts.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    where_sql = " AND ".join(where_parts)

    if group_by == "day":
        gb = "trip_date"
        select_extra = "trip_date AS period_key,"
    elif group_by == "city":
        gb = "country, city"
        select_extra = "country, city, city AS period_key,"
    elif group_by == "park":
        gb = "country, city, park_id, park_name"
        select_extra = "country, city, park_id, park_name, COALESCE(park_name, park_id::text) AS period_key,"
    elif group_by == "lob":
        gb = "lob_group"
        select_extra = "lob_group AS period_key,"
    elif group_by == "service":
        gb = "real_tipo_servicio_norm"
        select_extra = "real_tipo_servicio_norm AS period_key,"
    else:
        gb = "trip_date"
        select_extra = "trip_date AS period_key,"

    sql = f"""
        SELECT
            {select_extra}
            SUM(requested_trips) AS requested_trips,
            SUM(completed_trips) AS completed_trips,
            SUM(cancelled_trips) AS cancelled_trips,
            SUM(gross_revenue) AS gross_revenue,
            SUM(margin_total) AS margin_total,
            SUM(distance_total_km) AS distance_total_km,
            SUM(duration_total_minutes) AS duration_total_minutes,
            CASE WHEN SUM(requested_trips) > 0 THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips), 4) ELSE 0 END AS cancellation_rate,
            CASE WHEN SUM(requested_trips) > 0 THEN ROUND(SUM(completed_trips)::numeric / SUM(requested_trips), 4) ELSE 0 END AS completion_rate
        FROM {MV_DAY}
        WHERE {where_sql}
        GROUP BY {gb}
        ORDER BY period_key
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(sql, params)
            rows = [_serialize_row(dict(r)) for r in cur.fetchall()]
            cur.close()
        return {"group_by": group_by, "start_date": start_d.isoformat(), "end_date": end_d.isoformat(), "rows": rows}
    except Exception as e:
        return {"error": str(e), "group_by": group_by, "rows": []}


def get_hourly_view(
    days_back: int = 7,
    country: Optional[str] = None,
    city: Optional[str] = None,
    group_by: str = "hour",
) -> dict[str, Any]:
    """
    Desempeño por hora del día (0-23). days_back: ventana para agregar.
    group_by: "hour" | "city" | "park" | "lob" | "service".
    """
    end_d = date.today() + timedelta(days=1)
    start_d = end_d - timedelta(days=max(1, min(90, days_back)))

    where_parts = ["trip_date >= %s", "trip_date < %s"]
    params = [start_d, end_d]
    if country and str(country).strip():
        where_parts.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        where_parts.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    where_sql = " AND ".join(where_parts)

    if group_by == "hour":
        gb = "trip_hour"
        select_extra = "trip_hour AS period_key,"
    elif group_by == "city":
        gb = "trip_hour, country, city"
        select_extra = "trip_hour, country, city, city AS period_key,"
    elif group_by == "park":
        gb = "trip_hour, country, city, park_id, park_name"
        select_extra = "trip_hour, country, city, park_id, park_name, COALESCE(park_name, park_id::text) AS period_key,"
    elif group_by == "lob":
        gb = "trip_hour, lob_group"
        select_extra = "trip_hour, lob_group AS period_key,"
    elif group_by == "service":
        gb = "trip_hour, real_tipo_servicio_norm"
        select_extra = "trip_hour, real_tipo_servicio_norm AS period_key,"
    else:
        gb = "trip_hour"
        select_extra = "trip_hour AS period_key,"

    sql = f"""
        SELECT
            {select_extra}
            SUM(requested_trips) AS requested_trips,
            SUM(completed_trips) AS completed_trips,
            SUM(cancelled_trips) AS cancelled_trips,
            SUM(gross_revenue) AS gross_revenue,
            SUM(margin_total) AS margin_total,
            SUM(duration_total_minutes) AS duration_total_minutes,
            CASE WHEN SUM(requested_trips) > 0 THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips), 4) ELSE 0 END AS cancellation_rate,
            CASE WHEN SUM(requested_trips) > 0 THEN ROUND(SUM(completed_trips)::numeric / SUM(requested_trips), 4) ELSE 0 END AS completion_rate
        FROM {MV_HOUR}
        WHERE {where_sql}
        GROUP BY {gb}
        ORDER BY trip_hour NULLS LAST, period_key
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(sql, params)
            rows = [_serialize_row(dict(r)) for r in cur.fetchall()]
            cur.close()
        return {"group_by": group_by, "start_date": start_d.isoformat(), "end_date": end_d.isoformat(), "rows": rows}
    except Exception as e:
        return {"error": str(e), "group_by": group_by, "rows": []}


def get_cancellation_view(
    days_back: int = 14,
    country: Optional[str] = None,
    limit: int = 20,
    by: str = "reason",
) -> dict[str, Any]:
    """
    Top motivos de cancelación. by: "reason" | "reason_group" | "hour" | "city" | "park" | "service".
    """
    end_d = date.today() + timedelta(days=1)
    start_d = end_d - timedelta(days=max(1, min(90, days_back)))

    where_parts = ["trip_date >= %s", "trip_date < %s", "cancelled_trips > 0"]
    params = [start_d, end_d]
    if country and str(country).strip():
        where_parts.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    where_sql = " AND ".join(where_parts)
    params.append(min(100, max(5, limit)))

    if by == "reason":
        gb = "cancel_reason_norm"
        order = "cancelled_trips DESC"
        select_key = "COALESCE(cancel_reason_norm, 'sin_motivo') AS reason_key"
    elif by == "reason_group":
        gb = "cancel_reason_group"
        order = "cancelled_trips DESC"
        select_key = "COALESCE(cancel_reason_group, 'otro') AS reason_key"
    elif by == "hour":
        gb = "trip_hour, cancel_reason_group"
        order = "trip_hour, cancelled_trips DESC"
        select_key = "trip_hour, COALESCE(cancel_reason_group, 'otro') AS reason_key"
    elif by == "city":
        gb = "country, city, cancel_reason_group"
        order = "cancelled_trips DESC"
        select_key = "country, city, COALESCE(cancel_reason_group, 'otro') AS reason_key"
    elif by == "park":
        gb = "country, city, park_id, park_name, cancel_reason_group"
        order = "cancelled_trips DESC"
        select_key = "country, city, park_id, COALESCE(park_name, park_id::text), COALESCE(cancel_reason_group, 'otro') AS reason_key"
    elif by == "service":
        gb = "real_tipo_servicio_norm, cancel_reason_group"
        order = "cancelled_trips DESC"
        select_key = "real_tipo_servicio_norm, COALESCE(cancel_reason_group, 'otro') AS reason_key"
    else:
        gb = "cancel_reason_norm"
        order = "cancelled_trips DESC"
        select_key = "COALESCE(cancel_reason_norm, 'sin_motivo') AS reason_key"

    sql = f"""
        SELECT
            {select_key},
            SUM(cancelled_trips) AS cancelled_trips,
            SUM(requested_trips) AS requested_trips,
            CASE WHEN SUM(requested_trips) > 0 THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips), 4) ELSE 0 END AS cancellation_rate
        FROM {MV_HOUR}
        WHERE {where_sql}
        GROUP BY {gb}
        ORDER BY {order}
        LIMIT %s
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(sql, params)
            rows = [_serialize_row(dict(r)) for r in cur.fetchall()]
            cur.close()
        return {"by": by, "start_date": start_d.isoformat(), "end_date": end_d.isoformat(), "rows": rows}
    except Exception as e:
        return {"error": str(e), "by": by, "rows": []}
