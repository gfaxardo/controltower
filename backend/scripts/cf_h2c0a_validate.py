"""CF-H2C.0A: Full validation for Lima park coverage certification."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

LIMA = "08e20910d81d42658d4334d3f6d10ac0"

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("CF-H2C.0A — LIMA COVERAGE CERTIFICATION")
    print("=" * 80)

    # ======================================================================
    # 1. DAILY ORDERS COVERAGE: Yango vs CT
    # ======================================================================
    print("\n--- 1. DAILY ORDERS COVERAGE ---")
    cur.execute("""
        SELECT
            y.order_date,
            y.orders_completed AS yango_orders,
            y.unique_drivers AS yango_drivers,
            COALESCE(ct.ct_completed, 0) AS ct_orders,
            COALESCE(ct.ct_drivers, 0) AS ct_drivers,
            CASE WHEN COALESCE(ct.ct_completed, 0) > 0
                 THEN ROUND(y.orders_completed::numeric / ct.ct_completed * 100, 1)
                 ELSE NULL END AS coverage_pct,
            CASE WHEN COALESCE(ct.ct_completed, 0) > 0 THEN
                CASE
                    WHEN y.orders_completed::numeric / ct.ct_completed >= 0.95 THEN 'PASS'
                    WHEN y.orders_completed::numeric / ct.ct_completed >= 0.70 THEN 'WARN'
                    ELSE 'FAIL'
                END
            ELSE 'NO_CT_DATA' END AS status
        FROM raw_yango.mv_orders_day y
        LEFT JOIN (
            SELECT fecha_finalizacion::date AS d,
                   COUNT(*) FILTER (WHERE condicion = 'Completado') AS ct_completed,
                   COUNT(DISTINCT conductor_id) FILTER (WHERE condicion = 'Completado') AS ct_drivers
            FROM public.trips_2026
            WHERE park_id = %s
            GROUP BY fecha_finalizacion::date
        ) ct ON y.order_date = ct.d
        WHERE y.park_id = %s
        ORDER BY y.order_date
    """, (LIMA, LIMA))

    print(f"{'Date':>12s} {'Yango':>8s} {'CT':>8s} {'Cover%':>8s} {'Status':>8s} {'Y-Drivers':>10s} {'CT-Drivers':>10s}")
    print("-" * 70)
    for r in cur.fetchall():
        print(f"{str(r['order_date']):>12s} {r['yango_orders'] or 0:>8d} {r['ct_orders']:>8d} "
              f"{r['coverage_pct'] or 0:>7.1f}% {r['status']:>8s} "
              f"{r['yango_drivers'] or 0:>10d} {r['ct_drivers']:>10d}")

    # ======================================================================
    # 2. ORDERS RAW COUNT VERIFICATION
    # ======================================================================
    print("\n--- 2. RAW ORDERS BY DATE (direct from orders_raw) ---")
    cur.execute("""
        SELECT order_ended_at::date AS d,
               COUNT(*) AS total,
               COUNT(*) FILTER (WHERE order_status = 'complete') AS completed,
               MIN(order_ended_at) AS min_ts,
               MAX(order_ended_at) AS max_ts
        FROM raw_yango.orders_raw
        WHERE park_id = %s
        GROUP BY order_ended_at::date
        ORDER BY d
    """, (LIMA,))
    print(f"{'Date':>12s} {'Total':>8s} {'Completed':>10s} {'Min':>22s} {'Max':>22s}")
    print("-" * 80)
    for r in cur.fetchall():
        print(f"{str(r['d']):>12s} {r['total']:>8d} {r['completed']:>10d} "
              f"{str(r['min_ts'])[:22]:>22s} {str(r['max_ts'])[:22]:>22s}")

    # ======================================================================
    # 3. REVENUE COVERAGE (transactions)
    # ======================================================================
    print("\n--- 3. TRANSACTIONS / REVENUE BY DATE ---")
    cur.execute("""
        SELECT event_at::date AS d,
               COUNT(*) AS txn,
               COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS pf_count,
               COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS pf_revenue,
               COALESCE(SUM(amount) FILTER (WHERE category_name = 'Cash'), 0) AS gmv_cash,
               COALESCE(SUM(amount) FILTER (WHERE category_name = 'Card payment'), 0) AS gmv_card
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
        GROUP BY event_at::date
        ORDER BY d
    """, (LIMA,))
    print(f"{'Date':>12s} {'Txn':>8s} {'PartnerFee':>11s} {'Revenue':>12s} {'GMV Cash':>10s} {'GMV Card':>10s}")
    print("-" * 70)
    for r in cur.fetchall():
        print(f"{str(r['d']):>12s} {r['txn']:>8d} {r['pf_count']:>11d} "
              f"{r['pf_revenue']:>12.2f} {r['gmv_cash']:>10.2f} {r['gmv_card']:>10.2f}")

    # ======================================================================
    # 4. REVENUE COMPARISON vs CT day_fact
    # ======================================================================
    print("\n--- 4. REVENUE COMPARISON: Yango vs CT day_fact ---")
    cur.execute("""
        SELECT
            y.revenue_date,
            y.revenue_partner_fee_amount AS ya_rev,
            COALESCE(ct.ct_rev, 0) AS ct_rev,
            CASE WHEN COALESCE(ct.ct_rev, 0) > 0
                 THEN ROUND((y.revenue_partner_fee_amount - ct.ct_rev) / ct.ct_rev * 100, 1)
                 ELSE NULL END AS delta_pct,
            CASE WHEN ct.ct_rev > 0 THEN
                CASE
                    WHEN ABS((y.revenue_partner_fee_amount - ct.ct_rev) / ct.ct_rev) <= 0.05 THEN 'PASS'
                    WHEN ABS((y.revenue_partner_fee_amount - ct.ct_rev) / ct.ct_rev) <= 0.20 THEN 'WARN'
                    ELSE 'FAIL'
                END
            ELSE 'NO_CT' END AS status
        FROM raw_yango.mv_revenue_day y
        LEFT JOIN (
            SELECT trip_date, COALESCE(SUM(revenue_yego_final), 0) AS ct_rev
            FROM ops.real_business_slice_day_fact
            WHERE city = 'lima' AND country = 'peru'
            GROUP BY trip_date
        ) ct ON y.revenue_date = ct.trip_date
        WHERE y.park_id = %s
        ORDER BY y.revenue_date
    """, (LIMA,))
    print(f"{'Date':>12s} {'Yango Rev':>12s} {'CT Rev':>12s} {'Delta%':>8s} {'Status':>8s}")
    print("-" * 55)
    for r in cur.fetchall():
        print(f"{str(r['revenue_date']):>12s} {r['ya_rev'] or 0:>12.2f} {r['ct_rev']:>12.2f} "
              f"{r['delta_pct'] or 0:>7.1f}% {r['status']:>8s}")

    # ======================================================================
    # 5. FRESHNESS
    # ======================================================================
    print("\n--- 5. FRESHNESS ---")
    cur.execute("""
        SELECT
            'orders' AS endpoint,
            MAX(order_ended_at) AS last_event,
            MAX(api_fetched_at) AS last_ingested,
            (NOW() - MAX(order_ended_at)) AS data_delay
        FROM raw_yango.orders_raw
        WHERE park_id = %s
        UNION ALL
        SELECT
            'transactions',
            MAX(event_at),
            MAX(api_fetched_at),
            (NOW() - MAX(event_at))
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
    """, (LIMA, LIMA))
    for r in cur.fetchall():
        print(f"  {r['endpoint']:15s}: last_event={str(r['last_event'])[:19]} "
              f"last_ingested={str(r['last_ingested'])[:19]} "
              f"delay={r['data_delay']}")

    # ======================================================================
    # 6. INGESTION RUN HEALTH
    # ======================================================================
    print("\n--- 6. INGESTION RUNS (last 15) ---")
    cur.execute("""
        SELECT run_id, endpoint_group, date_from, status,
               records_fetched, records_inserted, error_count,
               started_at, finished_at
        FROM raw_yango.api_ingestion_run
        ORDER BY started_at DESC
        LIMIT 15
    """)
    for r in cur.fetchall():
        print(f"  [{r['status']:11s}] {r['endpoint_group']:17s} "
              f"date={r['date_from']} "
              f"fetched={r['records_fetched'] or 0:>5d} ins={r['records_inserted'] or 0:>5d} "
              f"err={r['error_count'] or 0:>2d} "
              f"started={str(r['started_at'])[:19]}")

    # ======================================================================
    # 7. DRIVERS
    # ======================================================================
    print("\n--- 7. DRIVERS SUMMARY ---")
    cur.execute("""
        SELECT
            COUNT(DISTINCT driver_profile_id) FILTER (WHERE work_status = 'working') AS working,
            COUNT(DISTINCT driver_profile_id) AS total_yango,
            COUNT(DISTINCT driver_profile_id) FILTER (WHERE has_contract_issue = true) AS contract_issues
        FROM raw_yango.driver_profiles_raw
        WHERE park_id = %s
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  Yango drivers total: {r['total_yango']} (working: {r['working']}, contract_issues: {r['contract_issues']})")

    cur.execute("""
        SELECT COUNT(DISTINCT driver_profile_id) AS active_today
        FROM raw_yango.orders_raw
        WHERE park_id = %s
          AND order_ended_at::date = (SELECT MAX(order_ended_at::date) FROM raw_yango.orders_raw WHERE park_id = %s)
          AND order_status = 'complete'
    """, (LIMA, LIMA))
    r = cur.fetchone()
    print(f"  Yango drivers on latest day: {r['active_today']}")

    # ======================================================================
    # 8. WATERMARKS
    # ======================================================================
    print("\n--- 8. WATERMARKS ---")
    cur.execute("""
        SELECT park_id, endpoint_group, last_source_date, status,
               records_total, consecutive_failures
        FROM raw_yango.ingestion_watermark
        ORDER BY park_id, endpoint_group
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  {r['endpoint_group']:17s}: last={r['last_source_date']} status={r['status']} "
                  f"records={r['records_total']} failures={r['consecutive_failures']}")
    else:
        print("  (no watermarks yet)")

    # ======================================================================
    # 9. ZOMBIE CHECK
    # ======================================================================
    print("\n--- 9. ZOMBIE RUNS (running > 1 hour) ---")
    cur.execute("""
        SELECT COUNT(*) AS zombie_count
        FROM raw_yango.api_ingestion_run
        WHERE status = 'running' AND started_at < NOW() - INTERVAL '1 hour'
    """)
    r = cur.fetchone()
    print(f"  Zombie runs: {r['zombie_count']}")

    # ======================================================================
    # 10. SUMMARY
    # ======================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    cur.execute("""
        WITH ya AS (
            SELECT order_ended_at::date AS d, COUNT(*) AS orders
            FROM raw_yango.orders_raw WHERE park_id = %s
            AND order_status = 'complete'
            GROUP BY order_ended_at::date
        ),
        ct AS (
            SELECT fecha_finalizacion::date AS d,
                   COUNT(*) FILTER (WHERE condicion = 'Completado') AS trips
            FROM public.trips_2026 WHERE park_id = %s
            GROUP BY fecha_finalizacion::date
        )
        SELECT ya.d, ya.orders, COALESCE(ct.trips, 0) AS ct_trips,
               CASE WHEN COALESCE(ct.trips, 0) > 0
                    THEN ROUND(ya.orders::numeric / ct.trips * 100, 1)
                    ELSE NULL END AS coverage
        FROM ya
        LEFT JOIN ct ON ya.d = ct.d
        WHERE ya.d >= '2026-06-01'
        ORDER BY ya.d
    """, (LIMA, LIMA))

    total_ya = 0; total_ct = 0; days = 0; pass_days = 0
    print(f"\n{'Date':>12s} {'Yango':>8s} {'CT':>8s} {'Cover%':>8s} {'Verdict':>10s}")
    print("-" * 55)
    for r in cur.fetchall():
        ya = r['orders'] or 0; ct = r['ct_trips']; cov = r['coverage'] or 0
        verdict = 'PASS' if cov >= 95 else ('WARN' if cov >= 70 else 'FAIL')
        print(f"{str(r['d']):>12s} {ya:>8d} {ct:>8d} {cov:>7.1f}% {verdict:>10s}")
        total_ya += ya; total_ct += ct; days += 1
        if cov >= 95: pass_days += 1

    print(f"\n  Total Yango orders (Jun 1-11): {total_ya}")
    print(f"  Total CT trips (Jun 1-11): {total_ct}")
    print(f"  Aggregate coverage: {total_ya / max(total_ct, 1) * 100:.1f}%")
    print(f"  Days with >=95% coverage: {pass_days}/{days}")

    cur.close()
