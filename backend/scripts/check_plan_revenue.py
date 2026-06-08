import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

with get_db() as conn:
    cur = conn.cursor()
    try:
        # Lima revenue
        cur.execute(
            "SELECT COUNT(*), SUM(COALESCE(projected_revenue,0)), "
            "COUNT(*) FILTER (WHERE projected_revenue > 0) "
            "FROM ops.plan_trips_monthly WHERE TRIM(country)=%s AND TRIM(city)=%s",
            ("PE", "Lima"))
        r = cur.fetchone()
        print(f"Lima: rows={r[0]} total_rev={r[1]} has_rev>0={r[2]}")

        # Colombia
        cur.execute(
            "SELECT COUNT(*), SUM(COALESCE(projected_revenue,0)), "
            "COUNT(*) FILTER (WHERE projected_revenue > 0) "
            "FROM ops.plan_trips_monthly WHERE TRIM(country)=%s", ("CO",))
        r2 = cur.fetchone()
        print(f"Colombia: rows={r2[0]} total_rev={r2[1]} has_rev>0={r2[2]}")

        # Peru all cities
        cur.execute(
            "SELECT TRIM(city), COUNT(*), SUM(COALESCE(projected_revenue,0)), "
            "COUNT(*) FILTER (WHERE projected_revenue > 0) "
            "FROM ops.plan_trips_monthly WHERE TRIM(country)=%s GROUP BY TRIM(city) ORDER BY TRIM(city)",
            ("PE",))
        print("\nPeru by city:")
        for row in cur.fetchall():
            print(f"  {row[0]:15s} rows={row[1]:5d} total_rev={row[2]:>12,.0f} has_rev>0={row[3]}")

        # Peru projected_trips for context
        cur.execute(
            "SELECT SUM(COALESCE(projected_trips,0)) FROM ops.plan_trips_monthly "
            "WHERE TRIM(country)=%s AND TRIM(city)=%s", ("PE", "Lima"))
        trips = cur.fetchone()[0]
        print(f"\nLima projected_trips total: {trips:,}")

    finally:
        cur.close()
