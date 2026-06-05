from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. RAW TRIPS May 2026 - Peru/Lima
    print("=== RAW TRIPS: Peru, Lima, May 2026 ===")
    cur.execute("""
        SELECT COUNT(*)::bigint AS total_trips,
               COUNT(DISTINCT park_id) AS parks,
               SUM(comision_empresa_asociada) FILTER (WHERE completed_flag) AS total_rev_raw
        FROM ops.v_real_trips_enriched_base
        WHERE country = 'peru' AND city = 'lima'
          AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
          AND resolution_status = 'resolved'
    """)
    r = cur.fetchone()
    print(f"Raw resolved: trips={r['total_trips']} parks={r['parks']} rev_raw={r['total_rev_raw']}")

    # 2. DAY_FACT May 2026 - Auto Regular Lima
    print("\n=== DAY_FACT: Auto Regular, Lima, May 2026 ===")
    cur.execute("""
        SELECT SUM(trips_completed)::bigint AS trips,
               SUM(trips_cancelled)::bigint AS cancelled,
               SUM(active_drivers)::bigint AS drivers,
               AVG(avg_ticket) AS ticket,
               AVG(trips_per_driver) AS tpd,
               SUM(revenue_yego_net)::numeric AS rev_net,
               SUM(revenue_yego_final)::numeric AS rev_final,
               COUNT(DISTINCT trip_date) AS days
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
    """)
    r = cur.fetchone()
    print(f"Day_fact Auto Regular: trips={r['trips']} cancel={r['cancelled']} drv={r['drivers']} ticket={r['ticket']:.2f} tpd={r['tpd']:.1f} rev_net={r['rev_net']} rev_final={r['rev_final']} days={r['days']}")

    # 3. MONTH_FACT May 2026 - Auto Regular Lima
    print("\n=== MONTH_FACT: Auto Regular, Lima, May 2026 ===")
    cur.execute("""
        SELECT SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               AVG(avg_ticket) AS ticket,
               AVG(trips_per_driver) AS tpd,
               SUM(revenue_yego_net)::numeric AS rev_net
        FROM ops.real_business_slice_month_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND month = '2026-05-01'
    """)
    r = cur.fetchone()
    print(f"Month_fact Auto Regular: trips={r['trips']} drv={r['drivers']} ticket={r['ticket']:.2f} tpd={r['tpd']:.1f} rev_net={r['rev_net']}")

    # 4. ALL SLICES May 2026 Lima
    print("\n=== ALL SLICES: Lima, May 2026 (day_fact) ===")
    cur.execute("""
        SELECT business_slice_name,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               SUM(revenue_yego_net)::numeric AS rev_net,
               SUM(revenue_yego_final)::numeric AS rev_final
        FROM ops.real_business_slice_day_fact
        WHERE country = 'peru' AND city = 'lima'
          AND trip_date >= '2026-05-01' AND trip_date < '2026-06-01'
        GROUP BY business_slice_name
        ORDER BY trips DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['business_slice_name']}: trips={r['trips']} drv={r['drivers']} rev_final={r['rev_final']}")

    # 5. Monthly comparison May vs April (for -30% analysis)
    print("\n=== MONTHLY COMPARISON: Auto Regular Lima ===")
    cur.execute("""
        SELECT month,
               SUM(trips_completed)::bigint AS trips,
               SUM(active_drivers)::bigint AS drivers,
               SUM(revenue_yego_net)::numeric AS rev_net
        FROM ops.real_business_slice_month_fact
        WHERE country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
          AND month IN ('2026-04-01', '2026-05-01', '2025-05-01')
        GROUP BY month
        ORDER BY month DESC
    """)
    for r in cur.fetchall():
        print(f"  {r['month']}: trips={r['trips']} drv={r['drivers']} rev_net={r['rev_net']}")

    cur.close()
