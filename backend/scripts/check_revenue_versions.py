import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT plan_version, COUNT(*), 
                   COALESCE(SUM(projected_revenue), 0) AS total_rev,
                   COUNT(*) FILTER (WHERE projected_revenue > 0) AS has_rev,
                   MAX(created_at) AS latest_created
            FROM ops.plan_trips_monthly
            WHERE TRIM(country) = %s AND TRIM(city) = %s
            GROUP BY plan_version
            ORDER BY MAX(created_at) DESC NULLS LAST
        """, ("PE", "Lima"))
        for r in cur.fetchall():
            d = dict(r)
            print(f"{d['plan_version']:30s} rows={d['count']:5d} rev={d['total_rev']:>12,.0f} has_rev={d['has_rev']:4d} created={d['latest_created']}")

        # Check which version get_latest_plan_version returns
        cur.execute("SELECT plan_version FROM ops.plan_trips_monthly ORDER BY created_at DESC NULLS LAST LIMIT 1")
        latest = cur.fetchone()
        print(f"\nget_latest_plan_version would return: {latest['plan_version'] if latest else 'NONE'}")
    finally:
        cur.close()
