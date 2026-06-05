from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # RAW TRIPS May 2026 - Peru/Lima
    print("=== RAW TRIPS: Peru, Lima, May 2026 ===")
    cur.execute("""
        SELECT COUNT(*)::bigint AS total_trips,
               COUNT(DISTINCT park_id) AS parks,
               SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS total_rev
        FROM ops.v_real_trips_enriched_base
        WHERE country = 'peru' AND city = 'lima'
          AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
    """)
    r = cur.fetchone()
    print(f"  trips={r['total_trips']} parks={r['parks']} rev={r['total_rev']}")

    # DAY_FACT May 2026 all slices Lima
    print("\n=== DAY_FACT: All slices Lima May 2026 ===")
    cur.execute("""
        SELECT business_slice_name,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               SUM(revenue_yego_final)::numeric AS rev_final,
               SUM(revenue_yego_net)::numeric AS rev_net
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
        GROUP BY business_slice_name
        ORDER BY trips DESC
    """)
    total_day_trips = 0
    total_day_rev = 0
    total_day_final = 0
    for r in cur.fetchall():
        t = int(r['trips'] or 0)
        total_day_trips += t
        rf = float(r['rev_final'] or 0)
        rn = float(r['rev_net'] or 0)
        total_day_rev += rn
        total_day_final += rf
        print(f"  {r['business_slice_name']}: trips={t} drv={r['drivers']} rev_net={rn} rev_final={rf}")
    print(f"  TOTAL: trips={total_day_trips} rev_net={total_day_rev:,.2f} rev_final={total_day_final:,.2f}")

    # MONTH_FACT comparison MoM
    print("\n=== MONTH_FACT: Auto Regular Lima MoM ===")
    cur.execute("""
        SELECT month,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               SUM(revenue_yego_net)::numeric AS rev_net
        FROM ops.real_business_slice_month_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND month IN ('2026-03-01', '2026-04-01', '2026-05-01', '2025-05-01')
        GROUP BY month ORDER BY month DESC
    """)
    prev = None
    for r in cur.fetchall():
        t = int(r['trips'] or 0)
        delta = ""
        if prev:
            dt = t - prev['trips']
            dp = (dt/prev['trips']*100) if prev['trips'] else 0
            delta = f"  MoM: {dt:+d} ({dp:+.1f}%)"
        print(f"  {r['month']}: trips={t} drv={r['drivers']} rev={r['rev_net']}{delta}")
        prev = {'trips': t, 'rev': r['rev_net']}

    # TOP 5 WEEKS by revenue
    print("\n=== TOP 5 WEEKS: Auto Regular Lima, revenue ===")
    cur.execute("""
        SELECT week_start,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               AVG(avg_ticket) AS ticket,
               SUM(revenue_yego_final)::numeric AS rev_final
        FROM ops.real_business_slice_week_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
        GROUP BY week_start
        ORDER BY SUM(revenue_yego_final) DESC NULLS LAST
        LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"  {r['week_start']}: trips={r['trips']} drv={r['drivers']} ticket={r['ticket']:.2f} rev_final={r['rev_final']}")

    # Revenue by week for ALL weeks to find anomalies
    print("\n=== ALL WEEKS: Auto Regular Lima, by revenue ===")
    cur.execute("""
        SELECT week_start,
               SUM(trips_completed)::bigint AS trips,
               AVG(avg_ticket) AS ticket,
               SUM(revenue_yego_final)::numeric AS rev_final,
               SUM(revenue_yego_net)::numeric AS rev_net
        FROM ops.real_business_slice_week_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
        GROUP BY week_start
        ORDER BY week_start DESC
        LIMIT 12
    """)
    weeks = cur.fetchall()
    weeks.reverse()
    avg_trips = sum(int(w['trips'] or 0) for w in weeks) / len(weeks) if weeks else 1
    for w in weeks:
        t = int(w['trips'] or 0)
        ratio = t/avg_trips if avg_trips else 1
        flag = " <<< ANOMALO" if ratio > 1.5 or ratio < 0.5 else ""
        print(f"  {w['week_start']}: trips={t} ticket={w['ticket']:.2f} rev_final={w['rev_final']} rev_net={w['rev_net']} ratio={ratio:.2f}{flag}")

    cur.close()
