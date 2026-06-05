from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # DAY_FACT May 2026 all slices Lima
    print("=== DAY_FACT: All slices Lima May 2026 ===")
    cur.execute("""
        SELECT business_slice_name, fleet_display_name,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               SUM(revenue_yego_final)::numeric AS rev_final
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
        GROUP BY business_slice_name, fleet_display_name
        ORDER BY trips DESC
    """)
    total_trips = 0
    total_rev = 0
    for r in cur.fetchall():
        t = int(r['trips'] or 0)
        rf = float(r['rev_final'] or 0)
        total_trips += t
        total_rev += rf
        print(f"  {r['business_slice_name']} [{r['fleet_display_name']}]: trips={t:,} drv={r['drivers']} rev_final={rf:,.0f}")
    print(f"  TOTAL: trips={total_trips:,} rev_final={total_rev:,.0f}")

    # MONTH_FACT MoM Auto Regular
    print("\n=== MONTH_FACT: Auto Regular Lima MoM ===")
    cur.execute("""
        SELECT month,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               SUM(revenue_yego_net)::numeric AS rev_net
        FROM ops.real_business_slice_month_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
        GROUP BY month ORDER BY month DESC LIMIT 5
    """)
    prev = None
    for r in cur.fetchall():
        t = int(r['trips'] or 0)
        delta = ""
        if prev:
            dt = t - prev['trips']
            dp = (dt/prev['trips']*100) if prev['trips'] else 0
            delta = f"  MoM: {dt:+d} ({dp:+.1f}%)"
        print(f"  {r['month']}: trips={t:,} drv={r['drivers']} rev={r['rev_net']}{delta}")
        prev = {'trips': t, 'rev': r['rev_net']}

    # ALL WEEKS revenue Auto Regular
    print("\n=== WEEKS: Auto Regular Lima, by revenue ===")
    cur.execute("""
        SELECT week_start,
               SUM(trips_completed)::bigint AS trips,
               AVG(avg_ticket) AS ticket,
               SUM(revenue_yego_final)::numeric AS rev_final
        FROM ops.real_business_slice_week_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
        GROUP BY week_start
        ORDER BY week_start
    """)
    weeks = cur.fetchall()
    if weeks:
        tvals = [int(w['trips'] or 0) for w in weeks]
        rvals = [float(w['rev_final'] or 0) for w in weeks]
        avg_t = sum(tvals)/len(tvals)
        avg_r = sum(rvals)/len(rvals) if sum(rvals) > 0 else 1
        for i, w in enumerate(weeks):
            t = tvals[i]
            rf = rvals[i]
            ratio_t = t/avg_t if avg_t else 1
            ratio_r = rf/avg_r if avg_r else 1
            flag = ""
            if ratio_t > 1.5 or ratio_t < 0.5: flag += " TRIPS_ANOMALO"
            if ratio_r > 1.5 or ratio_r < 0.5: flag += " REV_ANOMALO"
            print(f"  {w['week_start']}: trips={t:,} ticket={w['ticket']:.2f} rev_final={rf:,.0f} t_ratio={ratio_t:.2f} r_ratio={ratio_r:.2f}{flag}")

    # Park/slice mapping
    print("\n=== BUSINESS SLICE MAPPING: Lima ===")
    cur.execute("""
        SELECT DISTINCT business_slice_name, fleet_display_name
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
        ORDER BY business_slice_name
    """)
    for r in cur.fetchall():
        print(f"  {r['business_slice_name']} -> fleet: {r['fleet_display_name']}")

    cur.close()
