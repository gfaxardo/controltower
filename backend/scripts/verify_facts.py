import sys; sys.path.insert(0, '.')
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    facts = [
        'ops.driver_weekly_segment_fact',
        'ops.driver_segment_migration_fact',
        'ops.driver_operational_priority_fact',
        'ops.driver_supply_overview_weekly_fact',
        'ops.driver_serving_freshness_fact',
    ]
    for f in facts:
        cur.execute(f"SELECT COUNT(*) as cnt, MAX(refreshed_at) as ref FROM {f}")
        r = cur.fetchone()
        cnt = r['cnt'] if r else 0
        ref = str(r['ref'])[:19] if r and r['ref'] else 'N/A'
        max_period = 'N/A'
        if 'weekly_segment' in f:
            cur.execute(f"SELECT MAX(week_start) as mp FROM {f}")
            mp = cur.fetchone()
            max_period = str(mp['mp'])[:10] if mp and mp['mp'] else 'N/A'
        elif 'migration' in f or 'priority' in f:
            col = 'current_week_start' if 'migration' in f else 'week_start'
            cur.execute(f"SELECT MAX({col}) as mp FROM {f}")
            mp = cur.fetchone()
            max_period = str(mp['mp'])[:10] if mp and mp['mp'] else 'N/A'
        elif 'supply_overview' in f:
            cur.execute(f"SELECT MAX(week_start) as mp FROM {f}")
            mp = cur.fetchone()
            max_period = str(mp['mp'])[:10] if mp and mp['mp'] else 'N/A'

        print(f"{f:<45} rows={cnt:>8,}  max_period={max_period:<12}  refreshed={ref}")

    # Freshness
    print()
    cur.execute("SELECT fact_name, freshness_status, row_count, freshness_reason FROM ops.driver_serving_freshness_fact ORDER BY fact_name")
    for r in cur.fetchall():
        print(f"  {r['fact_name']:<45} {r['freshness_status']:<10} rows={r['row_count']:>8,}  {r['freshness_reason']}")
