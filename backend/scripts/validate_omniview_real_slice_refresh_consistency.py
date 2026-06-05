"""
CF-H1.1 — Anti-Recurrence QA: Omniview Real Slice Refresh Consistency

Validates day_fact, week_fact, and month_fact freshness and cross-grain consistency.
Detects gaps, 0-row anomalies, and cross-grain drift.

Exit codes: 0 = PASS (no blocking FAIL), 1 = FAIL (blocking issue detected)

Usage: cd backend && python -m scripts.validate_omniview_real_slice_refresh_consistency
"""
from __future__ import annotations

import math
import sys
import os
import io
from datetime import date, datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db_audit
from psycopg2.extras import RealDictCursor

RESULTS = []
FAIL_COUNT = 0
WARN_COUNT = 0
PASS_COUNT = 0


def r(label: str, status: str, detail: str = ""):
    global FAIL_COUNT, WARN_COUNT, PASS_COUNT
    s = status.upper()
    if s == "FAIL": FAIL_COUNT += 1
    elif s == "WARNING": WARN_COUNT += 1
    elif s == "PASS": PASS_COUNT += 1
    RESULTS.append({"label": label, "status": s, "detail": detail})
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARNING": "[WARN]"}[s]
    print(f"  {icon} {label}")
    if detail: print(f"       {detail}")


def fmt(v):
    if v is None: return 'NULL'
    return f"{int(v):,}"


def main():
    print("=" * 65)
    print("  OMNIVIEW REAL SLICE REFRESH CONSISTENCY QA")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    with get_db_audit(timeout_ms=300000) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute('SET statement_timeout = 180000')

        def ask(sql, params=None):
            cur.execute(sql, params or ())
            r = cur.fetchone()
            if r is None: return None
            return dict(r)

        today = date.today()

        # 1. DAY_FACT
        print("\n── 1. day_fact Freshness ──")
        df_range = ask("""
            SELECT MIN(trip_date) AS min_d, MAX(trip_date) AS max_d,
                   COUNT(DISTINCT trip_date) AS days, COUNT(1) AS rows
            FROM ops.real_business_slice_day_fact
        """)
        if df_range:
            max_d = df_range['max_d']
            if isinstance(max_d, date):
                days_behind = (today - max_d).days
            elif isinstance(max_d, str):
                days_behind = (today - date.fromisoformat(str(max_d)[:10])).days
            else:
                days_behind = 99
            r("1.1 day_fact max date",
              "FAIL" if days_behind > 3 else ("WARNING" if days_behind > 1 else "PASS"),
              f"Max: {max_d} ({days_behind}d behind today)")
            r("1.2 day_fact coverage", "PASS",
              f"{fmt(df_range['rows'])} rows, {fmt(df_range['days'])} distinct days")
        else:
            r("1.1 day_fact", "FAIL", "day_fact is EMPTY")

        # 2. WEEK_FACT
        print("\n── 2. week_fact Freshness ──")
        wf_range = ask("""
            SELECT MIN(week_start) AS min_w, MAX(week_start) AS max_w,
                   COUNT(DISTINCT week_start) AS weeks, COUNT(1) AS rows
            FROM ops.real_business_slice_week_fact
        """)
        if wf_range:
            max_w = wf_range['max_w']
            iso_today = today - timedelta(days=today.weekday())
            if isinstance(max_w, date):
                weeks_behind = (iso_today - max_w).days // 7
            elif isinstance(max_w, str):
                weeks_behind = (iso_today - date.fromisoformat(str(max_w)[:10])).days // 7
            else:
                weeks_behind = 99
            r("2.1 week_fact max week",
              "FAIL" if weeks_behind > 2 else ("WARNING" if weeks_behind > 1 else "PASS"),
              f"Max: {max_w} ({weeks_behind}w behind current ISO week {iso_today})")
            r("2.2 week_fact coverage", "PASS",
              f"{fmt(wf_range['rows'])} rows, {fmt(wf_range['weeks'])} distinct weeks")
        else:
            r("2.1 week_fact", "FAIL", "week_fact is EMPTY")

        # 3. MONTH_FACT
        print("\n── 3. month_fact Freshness ──")
        mf_range = ask("""
            SELECT MIN(month) AS min_m, MAX(month) AS max_m, COUNT(1) AS rows
            FROM ops.real_business_slice_month_fact
        """)
        if mf_range:
            max_m = mf_range['max_m']
            month_behind = 0
            if isinstance(max_m, date):
                month_behind = (today.year - max_m.year) * 12 + (today.month - max_m.month)
            r("3.1 month_fact max month",
              "FAIL" if month_behind > 1 else ("WARNING" if month_behind > 0 else "PASS"),
              f"Max: {max_m} ({month_behind} months behind)")
            r("3.2 month_fact coverage", "PASS", f"{fmt(mf_range['rows'])} rows")
        else:
            r("3.1 month_fact", "FAIL", "month_fact is EMPTY")

        # 4. CROSS-GRAIN CONSISTENCY (last 3 months)
        print("\n── 4. Cross-Grain Consistency ──")
        has_issues = False
        cur.execute("""
            SELECT month::date AS m, SUM(trips_completed) AS t
            FROM ops.real_business_slice_month_fact
            WHERE month >= date_trunc('month', CURRENT_DATE - INTERVAL '3 months')::date
            GROUP BY month ORDER BY month DESC LIMIT 3
        """)
        month_rows = [dict(r) for r in cur.fetchall()]
        for row in month_rows:
            m = row['m']
            month_trips = int(row['t'] or 0)
            if m.month == 12:
                end = date(m.year + 1, 1, 1)
            else:
                end = date(m.year, m.month + 1, 1)

            cur.execute("""
                SELECT SUM(trips_completed) AS t
                FROM ops.real_business_slice_day_fact
                WHERE trip_date >= %s AND trip_date < %s
            """, (m, end))
            dr = dict(cur.fetchone() or {})
            day_trips = int(dr.get('t') or 0)

            cur.execute("""
                SELECT SUM(trips_completed) AS t
                FROM ops.real_business_slice_week_fact
                WHERE week_start >= %s AND week_start <= %s
            """, (m, end))
            wr = dict(cur.fetchone() or {})
            week_trips = int(wr.get('t') or 0)

            if month_trips > 0 and day_trips == 0:
                r(f"4.x {m} day_fact = 0", "FAIL",
                  f"month={fmt(month_trips)}, day=0. day_fact may be stale!")
                has_issues = True
            elif month_trips > 0 and day_trips > 0:
                diff_pct = abs(month_trips - day_trips) / max(month_trips, day_trips) * 100
                if diff_pct > 1:
                    r(f"4.x {m} month-day drift", "WARNING",
                      f"month={fmt(month_trips)} day={fmt(day_trips)} drift={diff_pct:.2f}%")
                    has_issues = True
            if month_trips > 0 and week_trips == 0:
                r(f"4.x {m} week_fact = 0", "FAIL",
                  f"month={fmt(month_trips)}, week=0. week_fact may be stale!")
                has_issues = True

        if not has_issues:
            r("4.5 Cross-grain consistency", "PASS", "All recent months consistent across grains")

        # 5. RAW vs FACT
        print("\n── 5. RAW vs Fact ──")
        raw_last = ask("""
            SELECT MAX(fecha_inicio_viaje) AS max_d FROM public.trips_2026
        """)
        if raw_last:
            raw_max = raw_last['max_d']
            r("5.1 RAW max date", "PASS", f"Max: {raw_max}")

        # 6. ZERO-ROW ANOMALY DETECTION
        print("\n── 6. Zero-Row / Gap Detection ──")
        cur.execute("""
            SELECT trip_date
            FROM ops.real_business_slice_day_fact
            WHERE trip_date >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY trip_date ORDER BY trip_date
        """)
        days = [r['trip_date'] for r in cur.fetchall()]
        if len(days) < 7:
            r("6.1 day_fact recent coverage",
              "FAIL" if len(days) == 0 else "WARNING",
              f"Only {len(days)} of last 14 days have data")
        else:
            r("6.1 day_fact recent coverage", "PASS", f"{len(days)} of last 14 days covered")

        cur.execute("""
            SELECT week_start
            FROM ops.real_business_slice_week_fact
            WHERE week_start >= CURRENT_DATE - INTERVAL '28 days'
            GROUP BY week_start ORDER BY week_start
        """)
        weeks = [r['week_start'] for r in cur.fetchall()]
        if len(weeks) < 2:
            r("6.2 week_fact recent coverage",
              "FAIL" if len(weeks) == 0 else "WARNING",
              f"Only {len(weeks)} of last 4 weeks have data")
        else:
            r("6.2 week_fact recent coverage", "PASS", f"{len(weeks)} of last 4 weeks covered")

        # 7. MONTH_TRIPS_MISMATCH check
        print("\n── 7. MONTH_TRIPS_MISMATCH May 2026 ──")
        cur.execute("""
            SELECT SUM(trips_completed) AS t
            FROM ops.real_business_slice_month_fact
            WHERE month = '2026-05-01'::date
        """)
        mfr = dict(cur.fetchone() or {})
        mf_trips = int(mfr.get('t') or 0)

        cur.execute("""
            SELECT SUM(trips_completed) AS t
            FROM ops.real_business_slice_day_fact
            WHERE trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
        """)
        dfr = dict(cur.fetchone() or {})
        df_trips = int(dfr.get('t') or 0)

        cur.execute("""
            SELECT SUM(trips_completed) AS t
            FROM ops.real_business_slice_week_fact
            WHERE week_start >= '2026-04-27' AND week_start <= '2026-06-01'
        """)
        wfr = dict(cur.fetchone() or {})
        wf_trips = int(wfr.get('t') or 0)

        if mf_trips > 0 and df_trips == 0:
            r("7.1 MONTH_TRIPS_MISMATCH May 2026", "FAIL",
              f"month_fact={fmt(mf_trips)}, day_fact=0. Refresh gap detected!")
        elif mf_trips > 0 and df_trips > 0:
            drift = abs(mf_trips - df_trips) / max(mf_trips, df_trips) * 100
            s = "PASS" if drift < 1 else "WARNING"
            r("7.1 May 2026 month vs day", s,
              f"month={fmt(mf_trips)} day={fmt(df_trips)} drift={drift:.3f}%")
        else:
            r("7.1 May 2026 month vs day", "WARNING", "No data to compare")

        if wf_trips > 0:
            drift_w = abs(mf_trips - wf_trips) / max(mf_trips, wf_trips) * 100 if mf_trips > 0 else 0
            r("7.2 May 2026 month vs week (ISO spans)", 
              "PASS" if drift_w < 2 else "WARNING",
              f"month={fmt(mf_trips)} week={fmt(wf_trips)} drift={drift_w:.2f}%")
        else:
            r("7.2 May 2026 month vs week", "FAIL" if mf_trips > 0 else "WARNING",
              f"month={fmt(mf_trips)}, week_fact=0")

        cur.close()

    # SUMMARY
    print("\n" + "=" * 65)
    print("  QA SUMMARY")
    print("=" * 65)
    for item in RESULTS:
        icon = {"PASS": "PASS", "FAIL": "FAIL", "WARNING": "WARN"}[item["status"]]
        print(f"  {icon:6s} {item['label']}")
        if item["detail"]:
            print(f"         {item['detail']}")

    print(f"\n  PASS: {PASS_COUNT}  WARNING: {WARN_COUNT}  FAIL: {FAIL_COUNT}")

    if FAIL_COUNT > 0:
        print(f"\n  VERDICT: FAIL — {FAIL_COUNT} blocking issue(s)")
        for b in [i for i in RESULTS if i["status"] == "FAIL"]:
            print(f"    - {b['label']}")
    elif WARN_COUNT > 0:
        print(f"\n  VERDICT: CONDITIONAL PASS — {WARN_COUNT} warning(s)")
    else:
        print(f"\n  VERDICT: PASS — All checks passed")

    print(f"\n  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 1 if FAIL_COUNT > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
