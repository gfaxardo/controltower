"""
Auditoría de consistencia de la cadena hourly-first.
Verifica: SUM(hourly) == SUM(day), SUM(day) == SUM(week), SUM(week) == SUM(month)
para requested_trips, completed_trips, cancelled_trips, revenue, margin, duration.

Uso: cd backend && python -m scripts.audit_hourly_chain_consistency
Tolerancia: 0.01 (redondeo). Si diferencia > tolerancia → exit 1.
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

MV_HOUR = "ops.mv_real_lob_hour_v2"
MV_DAY = "ops.mv_real_lob_day_v2"
MV_WEEK = "ops.mv_real_lob_week_v3"
MV_MONTH = "ops.mv_real_lob_month_v3"
TIMEOUT_MS = 60000
TOLERANCE = 0.01


def _float(v):
    if v is None:
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def run():
    init_db_pool()
    today = date.today()
    day_check = today - timedelta(days=1)
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)
    month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)  # primer día del mes pasado
    next_month = (month_start.replace(day=1) + timedelta(days=32)).replace(day=1)

    errors = []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))

        # 1) hourly vs day (un día)
        cur.execute(
            f"""
            SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_HOUR} WHERE trip_date = %s
            """,
            (day_check,),
        )
        hour_row = cur.fetchone()
        cur.execute(
            f"""
            SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_DAY} WHERE trip_date = %s
            """,
            (day_check,),
        )
        day_row = cur.fetchone()
        for key in ("requested_trips", "completed_trips", "cancelled_trips", "gross_revenue", "margin_total", "duration_total_minutes"):
            h = _float(hour_row.get(key) if hour_row else None)
            d = _float(day_row.get(key) if day_row else None)
            if abs(h - d) > TOLERANCE:
                errors.append(f"day {day_check} {key}: hourly={h} day={d} diff={abs(h - d)}")

        # 2) day vs week (sum(day) en semana vs week_v3)
        cur.execute(
            f"""
            SELECT SUM(requested_trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips, SUM(gross_revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_DAY} WHERE trip_date >= %s AND trip_date <= %s
            """,
            (week_start, week_end),
        )
        day_week = cur.fetchone()
        cur.execute(
            f"""
            SELECT SUM(trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips, SUM(revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_WEEK} WHERE week_start = %s
            """,
            (week_start,),
        )
        week_row = cur.fetchone()
        for key in ("requested_trips", "completed_trips", "cancelled_trips", "gross_revenue", "margin_total", "duration_total_minutes"):
            d = _float(day_week.get(key) if day_week else None)
            w = _float(week_row.get(key) if week_row else None)
            if abs(d - w) > TOLERANCE:
                errors.append(f"week {week_start} {key}: sum(day)={d} week_v3={w} diff={abs(d - w)}")

        # 3) week vs month (sum(week) en mes vs month_v3)
        cur.execute(
            f"""
            SELECT SUM(trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips, SUM(revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_WEEK} WHERE week_start >= %s AND week_start < %s
            """,
            (month_start, next_month),
        )
        week_month = cur.fetchone()
        cur.execute(
            f"""
            SELECT SUM(trips) AS requested_trips, SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips, SUM(revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total, SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_MONTH} WHERE month_start = %s
            """,
            (month_start,),
        )
        month_row = cur.fetchone()
        for key in ("requested_trips", "completed_trips", "cancelled_trips", "gross_revenue", "margin_total", "duration_total_minutes"):
            w = _float(week_month.get(key) if week_month else None)
            m = _float(month_row.get(key) if month_row else None)
            if abs(w - m) > TOLERANCE:
                errors.append(f"month {month_start} {key}: sum(week)={w} month_v3={m} diff={abs(w - m)}")

        cur.close()

    if errors:
        print("INCONSISTENCIAS:")
        for e in errors:
            print(" ", e)
        sys.exit(1)
    print("OK: cadena hourly → day → week → month coherente.")
    sys.exit(0)


if __name__ == "__main__":
    run()
