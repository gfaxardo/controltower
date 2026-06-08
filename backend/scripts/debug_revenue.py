import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Check month_fact revenue for Lima directly
        cur.execute("""
            SELECT month, business_slice_name, revenue_yego_final, trips_completed
            FROM ops.real_business_slice_month_fact
            WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(city)) = LOWER(TRIM(%s))
              AND month >= %s
            ORDER BY month, business_slice_name
        """, ("peru", "lima", "2026-01-01"))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            rev = r["revenue_yego_final"]
            trips = r["trips_completed"]
            m = str(r["month"])[:10]
            print(f"{m} | {r['business_slice_name']:15s} | trips={trips:>8d} | rev={rev}")
        print(f"\nTotal: {len(rows)} rows")
        nulls = [r for r in rows if r["revenue_yego_final"] is None]
        has_rev = [r for r in rows if r["revenue_yego_final"] is not None and r["revenue_yego_final"] > 0]
        print(f"NULL revenue: {len(nulls)} rows")
        print(f"Non-zero revenue: {len(has_rev)} rows")
        if nulls:
            print("NULL rows:")
            for r in nulls:
                print(f"  {str(r['month'])[:10]} {r['business_slice_name']} trips={r['trips_completed']}")

        # Check day_fact revenue for same slices/months (revenue_yego_final by month)
        print("\n--- Day fact revenue (rolled up to month) ---")
        cur.execute("""
            SELECT date_trunc('month', trip_date)::date AS mth, business_slice_name,
                   SUM(revenue_yego_final) AS day_rev,
                   SUM(trips_completed) AS trips
            FROM ops.real_business_slice_day_fact
            WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(city)) = LOWER(TRIM(%s))
              AND trip_date >= %s
            GROUP BY 1, 2
            ORDER BY 1, 2
        """, ("peru", "lima", "2026-01-01"))
        day_rows = [dict(r) for r in cur.fetchall()]
        for r in day_rows:
            print(f"{str(r['mth'])[:10]} | {r['business_slice_name']:15s} | trips={r['trips']:>8d} | rev={r['day_rev']}")

        # Compare
        print("\n--- Gap Analysis (day_sum - month) ---")
        day_idx = {(str(r["mth"])[:10] + "|" + r["business_slice_name"]): r["day_rev"] for r in day_rows}
        for r in rows:
            key = str(r["month"])[:7] + "-01" if len(str(r["month"])) > 7 else str(r["month"])
            dk = key + "|" + r["business_slice_name"]
            day_r = day_idx.get(dk, 0)
            month_r = r["revenue_yego_final"] or 0
            gap = (day_r or 0) - (month_r or 0)
            flag = "GAP" if abs(gap) > 1 else "OK"
            print(f"  {key[:10]} {r['business_slice_name']:15s} | day={day_r:>10,.0f} month={month_r:>10,.0f} gap={gap:>10,.0f} [{flag}]")
    finally:
        cur.close()
