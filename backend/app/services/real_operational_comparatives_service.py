"""
Comparativos operativos: hoy vs ayer, vs mismos días de semana, misma hora vs histórico.
Fuente: ops.mv_real_lob_day_v2 y ops.mv_real_lob_hour_v2.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

MV_DAY = "ops.mv_real_lob_day_v2"
MV_HOUR = "ops.mv_real_lob_hour_v2"
TIMEOUT_MS = 45000


def _float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct_change(current: float, baseline: float) -> Optional[float]:
    if baseline is None or baseline == 0:
        return None
    if current is None:
        return None
    return round((current - baseline) / baseline * 100, 2)


def get_today_vs_yesterday(country: Optional[str] = None) -> dict[str, Any]:
    """Hoy vs ayer: pedidos, completados, cancelados, revenue, margin, duración, cancel rate."""
    today = date.today()
    yesterday = today - timedelta(days=1)

    where_today = "trip_date = %s::date"
    params_t = [today]
    if country and str(country).strip():
        where_today += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params_t.append(str(country).strip())

    where_yesterday = "trip_date = %s::date"
    params_y = [yesterday]
    if country and str(country).strip():
        where_yesterday += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params_y.append(str(country).strip())

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes,
                    SUM(completed_trips) AS comp
                FROM {MV_DAY} WHERE {where_today}
                """,
                params_t,
            )
            row_today = cur.fetchone()
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes,
                    SUM(completed_trips) AS comp
                FROM {MV_DAY} WHERE {where_yesterday}
                """,
                params_y,
            )
            row_yesterday = cur.fetchone()
            cur.close()
    except Exception as e:
        return {"error": str(e)}

    def row_vals(r):
        if not r:
            return 0, 0, 0, 0, 0, None, 0, 0
        req = _float(r.get("requested_trips")) or 0
        comp = _float(r.get("completed_trips")) or 0
        canc = _float(r.get("cancelled_trips")) or 0
        rev = _float(r.get("gross_revenue")) or 0
        margin = _float(r.get("margin_total")) or 0
        dur = _float(r.get("duration_total_minutes"))
        comp_sum = _float(r.get("comp")) or 0
        cancel_rate = (canc / req) if req else 0
        return req, comp, canc, rev, margin, dur, comp_sum, cancel_rate

    t_req, t_comp, t_canc, t_rev, t_margin, t_dur, t_comp_sum, t_cr = row_vals(row_today)
    y_req, y_comp, y_canc, y_rev, y_margin, y_dur, y_comp_sum, y_cr = row_vals(row_yesterday)

    t_dur_avg = (t_dur / t_comp_sum) if t_comp_sum and t_dur else None
    y_dur_avg = (y_dur / y_comp_sum) if y_comp_sum and y_dur else None

    return {
        "today": {
            "date": today.isoformat(),
            "requested_trips": int(t_req),
            "completed_trips": int(t_comp),
            "cancelled_trips": int(t_canc),
            "gross_revenue": round(t_rev, 4),
            "margin_total": round(t_margin, 4),
            "duration_avg_minutes": round(t_dur_avg, 2) if t_dur_avg is not None else None,
            "cancellation_rate": round(t_cr, 4),
        },
        "yesterday": {
            "date": yesterday.isoformat(),
            "requested_trips": int(y_req),
            "completed_trips": int(y_comp),
            "cancelled_trips": int(y_canc),
            "gross_revenue": round(y_rev, 4),
            "margin_total": round(y_margin, 4),
            "duration_avg_minutes": round(y_dur_avg, 2) if y_dur_avg is not None else None,
            "cancellation_rate": round(y_cr, 4),
        },
        "comparative": {
            "requested_trips_pct": _pct_change(t_req, y_req),
            "completed_trips_pct": _pct_change(t_comp, y_comp),
            "cancelled_trips_pct": _pct_change(t_canc, y_canc),
            "gross_revenue_pct": _pct_change(t_rev, y_rev),
            "margin_total_pct": _pct_change(t_margin, y_margin),
            "cancellation_rate_pp": round((t_cr - y_cr) * 100, 2) if y_cr is not None else None,
            "duration_avg_pct": _pct_change(t_dur_avg, y_dur_avg),
        },
    }


def get_today_vs_same_weekday_avg(
    n_weeks: int = 4,
    country: Optional[str] = None,
) -> dict[str, Any]:
    """Hoy vs promedio de los últimos n mismos días de semana (ej. últimos 4 lunes)."""
    today = date.today()
    weekday = today.weekday()
    baseline_dates = [today - timedelta(weeks=w) for w in range(1, n_weeks + 1)]
    baseline_dates = [d for d in baseline_dates if d.weekday() == weekday]

    where_today = "trip_date = %s::date"
    params_t = [today]
    if country and str(country).strip():
        where_today += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params_t.append(str(country).strip())

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes,
                    SUM(completed_trips) AS comp
                FROM {MV_DAY} WHERE {where_today}
                """,
                params_t,
            )
            row_today = cur.fetchone()

            if not baseline_dates:
                cur.close()
                return {"error": "no baseline dates", "today": _row_to_snapshot(row_today, today)}

            placeholders = ",".join(["%s::date"] * len(baseline_dates))
            where_baseline = f"trip_date IN ({placeholders})"
            params_b = list(baseline_dates)
            if country and str(country).strip():
                where_baseline += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
                params_b.append(str(country).strip())
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes,
                    SUM(completed_trips) AS comp
                FROM {MV_DAY} WHERE {where_baseline}
                """,
                params_b,
            )
            row_baseline = cur.fetchone()
            cur.close()
    except Exception as e:
        return {"error": str(e)}

    def row_vals(r):
        if not r:
            return 0, 0, 0, 0, 0, None, 0
        req = _float(r.get("requested_trips")) or 0
        comp = _float(r.get("completed_trips")) or 0
        canc = _float(r.get("cancelled_trips")) or 0
        rev = _float(r.get("gross_revenue")) or 0
        margin = _float(r.get("margin_total")) or 0
        dur = _float(r.get("duration_total_minutes"))
        comp_sum = _float(r.get("comp")) or 0
        return req, comp, canc, rev, margin, dur / comp_sum if comp_sum and dur else None, (canc / req if req else 0)

    t_req, t_comp, t_canc, t_rev, t_margin, t_dur_avg, t_cr = row_vals(row_today)
    b_req, b_comp, b_canc, b_rev, b_margin, b_dur_avg, b_cr = row_vals(row_baseline)
    n = len(baseline_dates) or 1
    b_req_avg, b_comp_avg, b_canc_avg = b_req / n, b_comp / n, b_canc / n
    b_rev_avg, b_margin_avg = b_rev / n, b_margin / n

    return {
        "today": {
            "date": today.isoformat(),
            "requested_trips": int(t_req),
            "completed_trips": int(t_comp),
            "cancelled_trips": int(t_canc),
            "gross_revenue": round(t_rev, 4),
            "margin_total": round(t_margin, 4),
            "duration_avg_minutes": round(t_dur_avg, 2) if t_dur_avg is not None else None,
            "cancellation_rate": round(t_cr, 4),
        },
        "baseline": {
            "description": f"promedio últimos {n_weeks} mismos días de semana",
            "dates": [d.isoformat() for d in baseline_dates],
            "requested_trips": round(b_req_avg, 2),
            "completed_trips": round(b_comp_avg, 2),
            "cancelled_trips": round(b_canc_avg, 2),
            "gross_revenue": round(b_rev_avg, 4),
            "margin_total": round(b_margin_avg, 4),
            "duration_avg_minutes": round(b_dur_avg, 2) if b_dur_avg is not None else None,
            "cancellation_rate": round(b_cr, 4),
        },
        "comparative": {
            "requested_trips_pct": _pct_change(t_req, b_req_avg),
            "completed_trips_pct": _pct_change(t_comp, b_comp_avg),
            "cancellation_rate_pp": round((t_cr - b_cr) * 100, 2) if b_cr is not None else None,
            "gross_revenue_pct": _pct_change(t_rev, b_rev_avg),
            "duration_avg_pct": _pct_change(t_dur_avg, b_dur_avg),
        },
    }


def _row_to_snapshot(row, d: date) -> dict:
    if not row:
        return {"date": d.isoformat(), "requested_trips": 0, "completed_trips": 0, "cancelled_trips": 0, "gross_revenue": 0, "margin_total": 0, "duration_avg_minutes": None, "cancellation_rate": 0}
    req = _float(row.get("requested_trips")) or 0
    comp = _float(row.get("completed_trips")) or 0
    canc = _float(row.get("cancelled_trips")) or 0
    comp_sum = _float(row.get("comp")) or 0
    dur = _float(row.get("duration_total_minutes"))
    return {
        "date": d.isoformat(),
        "requested_trips": int(req),
        "completed_trips": int(comp),
        "cancelled_trips": int(canc),
        "gross_revenue": round(_float(row.get("gross_revenue")) or 0, 4),
        "margin_total": round(_float(row.get("margin_total")) or 0, 4),
        "duration_avg_minutes": round(dur / comp_sum, 2) if comp_sum and dur else None,
        "cancellation_rate": round((canc / req), 4) if req else 0,
    }


def get_current_hour_vs_historical(
    country: Optional[str] = None,
    weeks_back: int = 4,
) -> dict[str, Any]:
    """Hora actual vs mismo tramo horario en semanas anteriores (promedio)."""
    from datetime import datetime
    now = datetime.utcnow()
    current_hour = now.hour
    today = date.today()

    where_cur = "trip_date = %s::date AND trip_hour = %s"
    params_cur = [today, current_hour]
    if country and str(country).strip():
        where_cur += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params_cur.append(str(country).strip())

    baseline_dates = [today - timedelta(weeks=w) for w in range(1, weeks_back + 1)]

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total
                FROM {MV_HOUR} WHERE {where_cur}
                """,
                params_cur,
            )
            row_cur = cur.fetchone()

            placeholders = ",".join(["%s::date"] * len(baseline_dates))
            where_hist = f"trip_date IN ({placeholders}) AND trip_hour = %s"
            params_hist = list(baseline_dates) + [current_hour]
            if country and str(country).strip():
                where_hist += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
                params_hist.append(str(country).strip())
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total
                FROM {MV_HOUR} WHERE {where_hist}
                """,
                params_hist,
            )
            row_hist = cur.fetchone()
            cur.close()
    except Exception as e:
        return {"error": str(e)}

    def vals(r):
        if not r:
            return 0, 0, 0, 0, 0, 0
        req = _float(r.get("requested_trips")) or 0
        comp = _float(r.get("completed_trips")) or 0
        canc = _float(r.get("cancelled_trips")) or 0
        rev = _float(r.get("gross_revenue")) or 0
        margin = _float(r.get("margin_total")) or 0
        cr = (canc / req) if req else 0
        return req, comp, canc, rev, margin, cr

    c_req, c_comp, c_canc, c_rev, c_margin, c_cr = vals(row_cur)
    h_req, h_comp, h_canc, h_rev, h_margin, h_cr = vals(row_hist)

    return {
        "current_hour": current_hour,
        "current_date": today.isoformat(),
        "current": {
            "requested_trips": int(c_req),
            "completed_trips": int(c_comp),
            "cancelled_trips": int(c_canc),
            "gross_revenue": round(c_rev, 4),
            "margin_total": round(c_margin, 4),
            "cancellation_rate": round(c_cr, 4),
        },
        "historical_same_hour": {
            "description": f"promedio misma hora, últimas {weeks_back} semanas",
            "requested_trips": round(h_req, 2),
            "completed_trips": round(h_comp, 2),
            "cancelled_trips": round(h_canc, 2),
            "gross_revenue": round(h_rev, 4),
            "margin_total": round(h_margin, 4),
            "cancellation_rate": round(h_cr, 4),
        },
        "comparative": {
            "requested_trips_pct": _pct_change(c_req, h_req),
            "completed_trips_pct": _pct_change(c_comp, h_comp),
            "cancellation_rate_pp": round((c_cr - h_cr) * 100, 2) if h_cr is not None else None,
            "gross_revenue_pct": _pct_change(c_rev, h_rev),
        },
    }


def get_this_week_vs_comparable(
    country: Optional[str] = None,
    weeks_back: int = 4,
) -> dict[str, Any]:
    """Esta semana (lunes a hoy) vs promedio de las últimas n semanas completas."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    baseline_starts = [week_start - timedelta(weeks=w) for w in range(1, weeks_back + 1)]

    where_this = "trip_date >= %s AND trip_date <= %s"
    params_this = [week_start, today]
    if country and str(country).strip():
        where_this += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params_this.append(str(country).strip())

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total, SUM(completed_trips) AS comp
                FROM {MV_DAY} WHERE {where_this}
                """,
                params_this,
            )
            row_this = cur.fetchone()

            all_dates = []
            for ws in baseline_starts:
                for d in range(7):
                    all_dates.append(ws + timedelta(days=d))
            placeholders = ",".join(["%s::date"] * len(all_dates))
            where_b = f"trip_date IN ({placeholders})"
            params_b = all_dates
            if country and str(country).strip():
                where_b += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
                params_b = list(params_b) + [str(country).strip()]
            cur.execute(
                f"""
                SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                    SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                    SUM(margin_total) AS margin_total, SUM(completed_trips) AS comp
                FROM {MV_DAY} WHERE {where_b}
                """,
                params_b,
            )
            row_baseline = cur.fetchone()
            cur.close()
    except Exception as e:
        return {"error": str(e)}

    def vals(r):
        if not r:
            return 0, 0, 0, 0, 0, None, 0
        req = _float(r.get("requested_trips")) or 0
        comp = _float(r.get("completed_trips")) or 0
        canc = _float(r.get("cancelled_trips")) or 0
        rev = _float(r.get("gross_revenue")) or 0
        margin = _float(r.get("margin_total")) or 0
        dur = _float(r.get("duration_total_minutes"))
        comp_sum = _float(r.get("comp")) or 0
        return req, comp, canc, rev, margin, (dur / comp_sum if comp_sum and dur else None), (canc / req if req else 0)

    t_req, t_comp, t_canc, t_rev, t_margin, t_dur, t_cr = vals(row_this)
    b_req, b_comp, b_canc, b_rev, b_margin, b_dur, b_cr = vals(row_baseline)

    return {
        "this_week": {
            "start": week_start.isoformat(),
            "end": today.isoformat(),
            "requested_trips": int(t_req),
            "completed_trips": int(t_comp),
            "cancelled_trips": int(t_canc),
            "gross_revenue": round(t_rev, 4),
            "margin_total": round(t_margin, 4),
            "duration_avg_minutes": round(t_dur, 2) if t_dur is not None else None,
            "cancellation_rate": round(t_cr, 4),
        },
        "baseline": {
            "description": f"promedio {weeks_back} semanas anteriores",
            "requested_trips": round(b_req / weeks_back, 2),
            "completed_trips": round(b_comp / weeks_back, 2),
            "cancelled_trips": round(b_canc / weeks_back, 2),
            "gross_revenue": round(b_rev / weeks_back, 4),
            "margin_total": round(b_margin / weeks_back, 4),
            "duration_avg_minutes": round(b_dur, 2) if b_dur is not None else None,
            "cancellation_rate": round(b_cr, 4),
        },
        "comparative": {
            "requested_trips_pct": _pct_change(t_req, b_req / weeks_back if weeks_back else 0),
            "completed_trips_pct": _pct_change(t_comp, b_comp / weeks_back if weeks_back else 0),
            "cancellation_rate_pp": round((t_cr - b_cr) * 100, 2) if b_cr is not None else None,
            "gross_revenue_pct": _pct_change(t_rev, b_rev / weeks_back if weeks_back else 0),
        },
    }
