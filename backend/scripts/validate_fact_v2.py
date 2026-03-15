#!/usr/bin/env python3
"""Quick validation of ops.v_real_trip_fact_v2."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from dotenv import load_dotenv
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

from app.db.connection import get_db, init_db_pool
init_db_pool()

with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SET statement_timeout = '180000'")

    cur.execute("""
        SELECT trip_outcome_norm, COUNT(*)
        FROM ops.v_real_trip_fact_v2
        WHERE trip_date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY 1 ORDER BY 2 DESC
    """)
    print("=== Trip outcomes (last 7 days) ===")
    for r in cur.fetchall():
        print("  %s: %s" % (r[0], r[1]))

    cur.execute("""
        SELECT cancel_reason_group, COUNT(*)
        FROM ops.v_real_trip_fact_v2
        WHERE is_cancelled AND trip_date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """)
    print("\n=== Cancel reason groups (last 7 days) ===")
    for r in cur.fetchall():
        print("  %s: %s" % (r[0] or "NULL", r[1]))

    cur.execute("""
        SELECT
            ROUND(AVG(trip_duration_minutes)::numeric, 1) as avg_min,
            ROUND(MIN(trip_duration_minutes)::numeric, 1) as min_min,
            ROUND(MAX(trip_duration_minutes)::numeric, 1) as max_min,
            COUNT(*) FILTER (WHERE trip_duration_minutes IS NOT NULL) as with_duration
        FROM ops.v_real_trip_fact_v2
        WHERE is_completed AND trip_date >= CURRENT_DATE - INTERVAL '7 days'
    """)
    r = cur.fetchone()
    print("\n=== Duration stats (completed, last 7 days) ===")
    print("  avg=%s min, min=%s, max=%s, with_duration=%s" % (r[0], r[1], r[2], r[3]))

    cur.execute("""
        SELECT trip_hour, COUNT(*)
        FROM ops.v_real_trip_fact_v2
        WHERE trip_date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY 1 ORDER BY 1
    """)
    print("\n=== Hourly distribution (last 7 days) ===")
    for r in cur.fetchall():
        bar = "#" * max(1, r[1] // 200)
        print("  %2dh: %5d %s" % (r[0], r[1], bar))

    cur.close()
