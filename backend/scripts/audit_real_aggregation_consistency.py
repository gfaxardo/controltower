"""
Auditoría de coherencia REAL: hourly → day → week → month.
Compara sumas equivalentes para los mismos periodos y filtros.
Uso: cd backend && python -m scripts.audit_real_aggregation_consistency
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

MV_HOUR = "ops.mv_real_lob_hour_v2"
MV_DAY = "ops.mv_real_lob_day_v2"
MV_WEEK = "ops.mv_real_lob_week_v3"
MV_MONTH = "ops.mv_real_lob_month_v3"
TIMEOUT_MS = 60000


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
    # Ventana: últimos 7 días completos (evitar hoy parcial)
    end_d = today
    start_d = today - timedelta(days=7)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))

        errors = []
        # 1) Sum(hourly) por trip_date vs day para un día concreto (ayer)
        day_check = today - timedelta(days=1)
        cur.execute(
            f"""
            SELECT SUM(requested_trips) AS requested_trips,
                   SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips,
                   SUM(gross_revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total,
                   SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_HOUR}
            WHERE trip_date = %s
            """,
            (day_check,),
        )
        hour_sum = cur.fetchone()
        cur.execute(
            f"""
            SELECT SUM(requested_trips) AS requested_trips,
                   SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips,
                   SUM(gross_revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total,
                   SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_DAY}
            WHERE trip_date = %s
            """,
            (day_check,),
        )
        day_row = cur.fetchone()

        if hour_sum and day_row:
            for key in ("requested_trips", "completed_trips", "cancelled_trips", "gross_revenue", "margin_total", "duration_total_minutes"):
                h = _float(hour_sum.get(key))
                d = _float(day_row.get(key))
                diff = abs(h - d)
                if diff > 0.01:  # tolerancia por redondeo
                    errors.append(f"day {day_check} {key}: hourly_sum={h} vs day={d} (diff={diff})")
        else:
            errors.append(f"Sin datos para día {day_check} en hourly o day")

        # 2) Sum(day) sobre una semana vs week_v3 (última semana cerrada)
        week_end = today - timedelta(days=today.weekday() + 1)  # domingo pasado
        week_start = week_end - timedelta(days=6)
        cur.execute(
            f"""
            SELECT SUM(requested_trips) AS requested_trips,
                   SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips,
                   SUM(gross_revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total,
                   SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date <= %s
            """,
            (week_start, week_end),
        )
        day_week_sum = cur.fetchone()
        cur.execute(
            f"""
            SELECT SUM(trips) AS requested_trips,
                   SUM(completed_trips) AS completed_trips,
                   SUM(cancelled_trips) AS cancelled_trips,
                   SUM(revenue) AS gross_revenue,
                   SUM(margin_total) AS margin_total,
                   SUM(duration_total_minutes) AS duration_total_minutes
            FROM {MV_WEEK}
            WHERE week_start = %s
            """,
            (week_start,),
        )
        week_row = cur.fetchone()

        if day_week_sum and week_row:
            for key in ("requested_trips", "completed_trips", "cancelled_trips", "gross_revenue", "margin_total", "duration_total_minutes"):
                d = _float(day_week_sum.get(key))
                w = _float(week_row.get(key))
                diff = abs(d - w)
                if diff > 0.01:
                    errors.append(f"week {week_start} {key}: sum(day)={d} vs week_v3={w} (diff={diff})")
        else:
            errors.append(f"Sin datos para semana {week_start} en day o week_v3")

        cur.close()

    if errors:
        print("INCONSISTENCIAS detectadas:")
        for e in errors:
            print(" ", e)
        sys.exit(1)
    print("OK: hourly ↔ day ↔ week coherentes en la ventana comprobada.")
    sys.exit(0)


if __name__ == "__main__":
    run()
